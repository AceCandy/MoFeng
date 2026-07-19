import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.routers.writer import _build_evaluation_failure_detail, _build_generation_failure_detail
from app.models import Chapter, ChapterOutline, ChapterVersion, NovelBlueprint, NovelProject
from app.models.user import User
from app.services.novel_service import NovelService
from app.services.pipeline_orchestrator import PipelineConfig, PipelineOrchestrator


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SOURCE = ROOT / "app/services/pipeline_orchestrator.py"
WRITER_ROUTER_SOURCE = ROOT / "app/api/routers/writer.py"
NOVEL_SERVICE_SOURCE = ROOT / "app/services/novel_service.py"
REQUIREMENTS = ROOT / "requirements.txt"


def _source() -> str:
    return PIPELINE_SOURCE.read_text(encoding="utf-8")


def _writer_generate_block() -> str:
    source = WRITER_ROUTER_SOURCE.read_text(encoding="utf-8")
    return source.split('@router.post("/novels/{project_id}/chapters/generate"', 1)[1].split(
        "\n\n@router.post(\"/novels/{project_id}/chapters/select\"",
        1,
    )[0]


def _writer_evaluate_block() -> str:
    source = WRITER_ROUTER_SOURCE.read_text(encoding="utf-8")
    return source.split('@router.post("/novels/{project_id}/chapters/evaluate"', 1)[1].split(
        "\n\n@router.post(\"/novels/{project_id}/chapters/finalize\"",
        1,
    )[0]


def test_backend_requirements_pins_langgraph_dependency() -> None:
    requirements = REQUIREMENTS.read_text(encoding="utf-8")

    assert "langgraph==" in requirements


def test_pipeline_orchestrator_invokes_compiled_langgraph() -> None:
    source = _source()

    assert "from langgraph.graph import END, START, StateGraph" in source
    assert "StateGraph(PipelineGraphState)" in source
    assert ".ainvoke(initial_state)" in source


def test_pipeline_graph_sequence_covers_every_generation_stage() -> None:
    assert PipelineOrchestrator.GRAPH_SEQUENCE == (
        "initialize_chapter",
        "collect_context",
        "generate_chapter_mission",
        "build_visibility_context",
        "prepare_enhanced_context",
        "prepare_memory_context",
        "prepare_retrieval_context",
        "build_writer_prompt",
        "generate_versions",
        "review_versions",
        "apply_post_generation_reviews",
        "persist_versions",
        "build_response",
    )


def test_pipeline_review_context_uses_visible_blueprint() -> None:
    context = PipelineOrchestrator._build_review_context(
        writer_blueprint={"characters": [{"name": "林墨"}]},
        blueprint_dict={"characters": [{"name": "不应使用"}]},
        chapter_number=3,
        outline_title="入山",
        outline_summary="主角进入旧山道",
        chapter_mission={"pov": "林墨"},
        history_context={
            "previous_summary": "上一章摘要",
            "previous_tail": "上一章结尾",
            "completed_chapters": [{"chapter_number": 1, "summary": "开端"}],
        },
    )

    assert context["novel_blueprint"] == {"characters": [{"name": "林墨"}]}
    assert context["chapter_outline"]["chapter_number"] == 3
    assert context["previous_chapter"]["summary"] == "上一章摘要"
    assert context["completed_chapters"] == [{"chapter_number": 1, "summary": "开端"}]


def test_pipeline_stage_flags_preserve_existing_debug_contract() -> None:
    config = PipelineConfig(
        enable_preview=True,
        enable_optimizer=True,
        enable_consistency=True,
        enable_enrichment=True,
        enable_constitution=True,
        enable_persona=True,
        enable_six_dimension=True,
        enable_reader_sim=True,
        enable_self_critique=True,
        enable_memory=True,
        enable_rag=True,
        rag_mode="two_stage",
    )

    flags = PipelineOrchestrator._build_stage_flags(config)

    assert flags == {
        "preview": True,
        "optimizer": True,
        "consistency": True,
        "enrichment": True,
        "constitution": True,
        "persona": True,
        "six_dimension": True,
        "reader_sim": True,
        "self_critique": True,
        "memory": True,
        "rag": True,
        "rag_mode": True,
    }


def test_regular_generate_endpoint_delegates_to_langgraph_pipeline() -> None:
    block = _writer_generate_block()

    assert "orchestrator = PipelineOrchestrator(session)" in block
    assert "await orchestrator.generate_chapter(" in block
    assert '"preset": "basic"' in block
    assert '"enable_rag": True' in block
    assert "return await _load_project_schema(novel_service, project_id, current_user.id)" in block

    legacy_local_orchestration = [
        "prompt_service = PromptService(session)",
        "llm_service = LLMService(session)",
        "context_builder = WriterContextBuilder()",
        "guardrails = ChapterGuardrails()",
        "_generate_chapter_mission(",
        "_get_rag_context(",
        "replace_chapter_versions(chapter",
    ]
    for legacy_marker in legacy_local_orchestration:
        assert legacy_marker not in block


def test_regular_generate_endpoint_exposes_runtime_error_detail() -> None:
    block = _writer_generate_block()

    assert "_build_generation_failure_detail(exc)" in block
    assert 'detail="生成章节失败，请重试。"' not in block


def test_generation_failure_detail_keeps_reason_and_redacts_secrets() -> None:
    detail = _build_generation_failure_detail(
        RuntimeError("阶段 chapter_writing 使用的供应商缺少 API Key")
    )
    secret_detail = _build_generation_failure_detail(RuntimeError("api_key=sk-live-secret 请求失败"))

    assert detail == "生成章节失败：阶段 chapter_writing 使用的供应商缺少 API Key"
    assert "sk-live-secret" not in secret_detail
    assert "api_key=[已隐藏]" in secret_detail


def test_evaluate_endpoint_records_failure_trace_and_detail() -> None:
    block = _writer_evaluate_block()

    assert "_build_evaluation_failure_detail(exc)" in block
    assert 'node_key="quality_review"' in block
    assert "trace_service.record_failure" in block
    assert 'chapter.generation_step = f"evaluation_failed|error={failure_summary}"' in block
    assert 'detail="评审失败，请重试"' not in block


def test_evaluation_failure_detail_keeps_reason_and_redacts_secrets() -> None:
    detail = _build_evaluation_failure_detail(RuntimeError("模型返回空结果"))
    secret_detail = _build_evaluation_failure_detail(RuntimeError("token=sk-live-secret 调用失败"))

    assert detail == "AI评审失败：模型返回空结果"
    assert "sk-live-secret" not in secret_detail
    assert "token=[已隐藏]" in secret_detail


def test_langgraph_pipeline_preserves_stage_routing_keys() -> None:
    source = _source()

    for stage_key in (
        'stage="summary_memory"',
        'stage="chapter_mission"',
        'stage="chapter_writing"',
        'stage="chapter_rewrite"',
        'stage="chapter_compression"',
        'stage="chapter_enrichment"',
        'stage="chapter_optimization"',
    ):
        assert stage_key in source


def test_langgraph_pipeline_preserves_word_count_safeguards() -> None:
    source = _source()

    assert "async def _expand_chapter_to_minimum_word_count(" in source
    assert "minimum_acceptable_word_count = int(minimum_word_count * 0.85)" in source
    assert "模型未返回有效正文" in source
    assert "低于最低要求" in source


def test_langgraph_pipeline_records_generation_trace_nodes() -> None:
    source = _source()

    assert "ChapterGenerationTraceService" in source
    assert "await self.trace_service.clear_for_chapter(" in source
    assert 'node_key="director_mission"' in source
    assert 'node_key="rag_retrieval"' in source
    assert 'node_key="draft_generation"' in source
    assert 'raw_response=response' in source


def test_pipeline_trace_metadata_describes_actions_and_model_calls() -> None:
    source = _source()

    assert '"trace_kind": "workflow"' in source
    assert '"trace_kind": "llm"' in source
    assert '"call_type": "database_context"' in source
    assert '"call_type": "rag_retrieval"' in source
    assert '"call_type": "chat_llm"' in source
    assert '"model_calls"' in source
    assert '"actions"' in source
    assert '"data_reads"' in source
    assert '"metrics"' in source
    assert '"skip_reason"' in source
    assert "是否调用摘要模型由前文章节是否缺少 real_summary 决定" in source


def test_pipeline_marks_director_mission_before_running_director_llm() -> None:
    source = _source()
    block = source.split("async def _graph_generate_chapter_mission", 1)[1].split(
        "async def _graph_build_visibility_context",
        1,
    )[0]

    assert block.index('step="director_mission"') < block.index("chapter_mission = await self._generate_chapter_mission(")


def test_pipeline_does_not_record_user_waiting_time_as_trace_node() -> None:
    source = _source()

    assert 'node_key="waiting_for_confirm"' not in source
    assert 'node_key="selecting_version"' not in source


def test_pipeline_auto_reviews_and_refines_without_manual_choice() -> None:
    source = _source()
    review_block = source.split("async def _run_ai_review", 1)[1].split(
        "async def _run_self_critique",
        1,
    )[0]
    post_review_block = source.split("async def _graph_apply_post_generation_reviews", 1)[1].split(
        "async def _graph_persist_versions",
        1,
    )[0]
    persist_block = source.split("async def _graph_persist_versions", 1)[1].split(
        "async def _graph_build_response",
        1,
    )[0]

    assert "review_single_version(" in review_block
    assert "只有一个版本，跳过对比评审" not in review_block
    assert "_run_review_guided_refinement(" in post_review_block
    assert 'node_key="review_refinement"' in source
    assert '"optimize_recommended_version"' in source
    assert 'node_key="persist_versions"' in persist_block
    assert 'node_label="保存草稿"' in persist_block
    assert 'finalize_version_index=state["best_version_index"]' not in persist_block


def test_pipeline_persists_generated_versions_as_draft_not_successful() -> None:
    source = _source()
    block = source.split("async def _graph_persist_versions", 1)[1].split(
        "async def _graph_build_response",
        1,
    )[0]

    assert 'node_key="persist_versions"' in block
    assert 'node_label="保存草稿"' in block
    assert 'finalize_version_index=state["best_version_index"]' not in block
    assert '"将章节状态标记为已完成"' not in block
    assert '"保存草稿节点不调用模型"' in block


def test_novel_service_no_longer_keeps_finalize_version_index_branch() -> None:
    service_source = NOVEL_SERVICE_SOURCE.read_text(encoding="utf-8")
    block = service_source.split("async def replace_chapter_versions", 1)[1].split(
        "async def select_chapter_version",
        1,
    )[0]

    assert "finalize_version_index" not in block
    assert "ChapterGenerationStatus.SUCCESSFUL.value" not in block
    assert 'generation_step = "completed"' not in block
    assert "chapter.selected_version_id = None" in block
    assert "chapter.real_summary = None" in block


def test_pipeline_review_and_refinement_failures_are_not_silently_ignored() -> None:
    source = _source()

    assert "raise RuntimeError(\"AI评审失败" in source
    assert "raise RuntimeError(\"修复润色失败" in source
    assert "logger.warning(\"AI 评审失败，跳过" not in source
    assert "沿用默认版本选择" not in source


@pytest.mark.asyncio(loop_scope="session")
async def test_pipeline_director_mission_failure_terminates_generation(db_session_factory) -> None:
    class FakePromptService:
        async def get_prompt(self, name: str) -> str:
            assert name == "chapter_plan"
            return "章节规划提示词"

    class FakeLLMService:
        async def get_llm_response(self, **kwargs):
            raise RuntimeError("500: AI 未返回有效内容（结束原因: stop）")

    class FakeTraceService:
        def __init__(self):
            self.failures = []

        async def record_failure(self, **kwargs):
            self.failures.append(kwargs)

    orchestrator = object.__new__(PipelineOrchestrator)
    orchestrator.prompt_service = FakePromptService()
    orchestrator.llm_service = FakeLLMService()
    orchestrator.trace_service = FakeTraceService()

    with pytest.raises(RuntimeError, match="规划剧情失败.*AI 未返回有效内容"):
        await orchestrator._generate_chapter_mission(
            project_id="project-director-failure",
            chapter_number=1,
            blueprint_dict={},
            previous_summary="上一章摘要",
            previous_tail="上一章结尾",
            outline_title="第一章",
            outline_summary="开篇",
            writing_notes="无额外要求",
            introduced_characters=[],
            all_characters=[],
            user_id=1,
        )

    assert orchestrator.trace_service.failures[-1]["node_key"] == "director_mission"
    assert "继续" not in orchestrator.trace_service.failures[-1]["metadata"]["summary"]


def test_pipeline_builds_frontend_evaluation_payload_from_ai_review() -> None:
    feedback = PipelineOrchestrator._build_chapter_evaluation_feedback(
        {
            "ai_review": {
                "mode": "compare",
                "best_version_index": 1,
                "evaluation": "版本2整体更稳",
                "suggestions": "保留版本2并压缩对白",
                "final_recommendation": "选择版本2",
                "version_reviews": [
                    {
                        "version_number": 1,
                        "pros": ["铺垫清楚"],
                        "cons": ["节奏偏慢"],
                        "overall_review": "版本1较稳",
                        "scores": {"coherence": 78},
                    },
                    {
                        "version_number": 2,
                        "pros": ["冲突更强"],
                        "cons": ["个别句子略满"],
                        "overall_review": "版本2综合最佳",
                        "scores": {"coherence": 88},
                    },
                ],
            }
        }
    )

    payload = json.loads(feedback)

    assert payload["best_choice"] == 2
    assert payload["reason_for_choice"] == "选择版本2"
    assert payload["evaluation"]["version1"]["overall_review"] == "版本1较稳"
    assert payload["evaluation"]["version2"]["pros"] == ["冲突更强"]


def test_review_refinement_summary_ignores_conflicting_global_recommendation() -> None:
    summary = PipelineOrchestrator._build_review_refinement_summary(
        {
            "mode": "compare",
            "best_version_index": 1,
            "evaluation": "版本1更适合作为第一章正式稿。",
            "suggestions": "沿用版本2的冲突强度，压缩铺垫。",
            "final_recommendation": "最终建议采用版本1。",
            "flaws": ["版本2个别句子略显堆叠"],
            "version_reviews": [
                {
                    "version_number": 1,
                    "overall_review": "版本1铺垫完整但冲突不足",
                    "cons": ["节奏偏慢"],
                },
                {
                    "version_number": 2,
                    "overall_review": "版本2综合最佳，适合作为修复润色底稿",
                    "cons": ["个别句子略显堆叠"],
                },
            ],
        },
        1,
    )

    assert "推荐采用第 2 个版本" in summary
    assert "版本2综合最佳" in summary
    assert "沿用版本2的冲突强度" in summary
    assert "版本2个别句子略显堆叠" in summary
    assert "版本1更适合" not in summary
    assert "最终建议采用版本1" not in summary


def test_frontend_evaluation_feedback_uses_structured_best_choice_when_text_conflicts() -> None:
    feedback = PipelineOrchestrator._build_chapter_evaluation_feedback(
        {
            "ai_review": {
                "mode": "compare",
                "best_version_index": 1,
                "evaluation": "版本1更适合作为第一章正式稿。",
                "suggestions": "沿用版本2的冲突强度，压缩铺垫。",
                "final_recommendation": "最终建议采用版本1。",
                "version_reviews": [
                    {
                        "version_number": 1,
                        "overall_review": "版本1铺垫完整但冲突不足",
                    },
                    {
                        "version_number": 2,
                        "overall_review": "版本2综合最佳，适合作为修复润色底稿",
                    },
                ],
            }
        }
    )

    payload = json.loads(feedback)

    assert payload["best_choice"] == 2
    assert payload["reason_for_choice"] == "版本2综合最佳，适合作为修复润色底稿"
    assert "版本1更适合" not in payload["reason_for_choice"]
    assert "最终建议采用版本1" not in payload["reason_for_choice"]


def test_langgraph_pipeline_marks_chapter_failed_on_runtime_error() -> None:
    source = _source()

    assert "await self._mark_generation_failed(" in source
    assert 'chapter.status = "failed"' in source
    assert 'chapter.generation_step = "failed"' in source


def test_pipeline_state_does_not_reuse_orm_entities_across_commits() -> None:
    source = _source()

    assert '"project": project' not in source
    assert '"chapter": chapter' not in source
    assert 'state["project"].chapters' not in source
    assert "_serialize_project(state[\"project\"])" not in source
    assert "chapters: List[Chapter]" not in source
    assert "await self._set_chapter_generation_state(" in source
    assert "await self._load_generation_project_schema(" in source
    assert "selectinload(Chapter.selected_version)" in source


@pytest.mark.asyncio(loop_scope="session")
async def test_collect_history_context_loads_selected_version_with_async_session(db_session_factory) -> None:
    async with db_session_factory() as session:
        project_id = "project-history-context"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=1,
                title="测试小说",
                initial_prompt="测试提示",
            )
        )
        session.add(NovelBlueprint(project_id=project_id, title="测试小说"))
        outline = ChapterOutline(
            project_id=project_id,
            chapter_number=1,
            title="旧章",
            summary="旧章概要",
        )
        session.add(outline)
        previous_chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            real_summary="旧章摘要",
            status="successful",
        )
        session.add(previous_chapter)
        await session.flush()
        selected_version = ChapterVersion(
            chapter_id=previous_chapter.id,
            version_label="v1",
            content="前序正文开头。\n前序正文结尾。",
        )
        session.add(selected_version)
        await session.flush()
        previous_chapter.selected_version_id = selected_version.id
        await session.commit()

        orchestrator = PipelineOrchestrator(session)
        history = await orchestrator._collect_history_context(
            project_id=project_id,
            chapter_number=2,
            outlines_map={1: outline},
            user_id=1,
        )

        assert history["completed_chapters"] == [
            {
                "chapter_number": 1,
                "title": "旧章",
                "summary": "旧章摘要",
            }
        ]
        assert history["previous_summary"] == "旧章摘要"
        assert history["previous_tail"] == "前序正文开头。\n前序正文结尾。"


@pytest.mark.asyncio(loop_scope="session")
async def test_mark_generation_failed_records_full_runtime_error_trace(db_session_factory) -> None:
    async with db_session_factory() as session:
        project_id = "project-failed-trace"
        full_error = "修复润色失败：模型返回 JSON 解析错误，真实错误需要完整保留给前端查看"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=1,
                title="测试小说",
                initial_prompt="测试提示",
            )
        )
        session.add(ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇"))
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            status="generating",
            generation_step="review_refinement",
            generation_progress=92,
        )
        session.add(chapter)
        await session.commit()

        orchestrator = PipelineOrchestrator(session)
        await orchestrator._mark_generation_failed(
            project_id=project_id,
            chapter_number=1,
            error=RuntimeError(full_error),
        )

        await session.refresh(chapter)
        traces = await orchestrator.trace_service.list_for_chapter(
            project_id=project_id,
            chapter_number=1,
        )

        assert chapter.status == "failed"
        assert chapter.generation_step.startswith("failed|error=")
        assert traces[-1].node_key == "review_refinement"
        assert traces[-1].status == "failed"
        assert traces[-1].error == full_error


@pytest.mark.asyncio(loop_scope="session")
async def test_replace_chapter_versions_stores_review_feedback_while_waiting_for_confirm(db_session_factory) -> None:
    async with db_session_factory() as session:
        project_id = "project-auto-review-feedback"
        session.add(User(id=1, username="writer", hashed_password="secret"))
        session.add(
            NovelProject(
                id=project_id,
                user_id=1,
                title="测试小说",
                initial_prompt="测试提示",
            )
        )
        session.add(ChapterOutline(project_id=project_id, chapter_number=1, title="第一章", summary="开篇"))
        chapter = Chapter(project_id=project_id, chapter_number=1, status="generating")
        session.add(chapter)
        await session.commit()

        evaluation_feedback = json.dumps(
            {
                "best_choice": 1,
                "reason_for_choice": "单版本评审通过",
                "evaluation": {
                    "version1": {
                        "overall_review": "结构完整",
                        "pros": ["节奏清楚"],
                        "cons": [],
                        "scores": {},
                    }
                },
            },
            ensure_ascii=False,
        )
        await NovelService(session).replace_chapter_versions(
            chapter,
            ["这是自动修复润色后的终稿正文。"],
            evaluation_feedback=evaluation_feedback,
        )

        refreshed = await session.execute(
            select(Chapter)
            .options(
                selectinload(Chapter.evaluations),
                selectinload(Chapter.selected_version),
                selectinload(Chapter.versions),
            )
            .where(Chapter.id == chapter.id)
        )
        saved_chapter = refreshed.scalars().one()

        assert saved_chapter.status == "waiting_for_confirm"
        assert saved_chapter.selected_version_id is None
        assert saved_chapter.real_summary is None
        assert saved_chapter.evaluations[-1].feedback == evaluation_feedback
        assert saved_chapter.evaluations[-1].version_id == saved_chapter.versions[0].id
