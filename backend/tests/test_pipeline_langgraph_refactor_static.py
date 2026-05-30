from pathlib import Path

from app.services.pipeline_orchestrator import PipelineConfig, PipelineOrchestrator


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SOURCE = ROOT / "app/services/pipeline_orchestrator.py"
WRITER_ROUTER_SOURCE = ROOT / "app/api/routers/writer.py"
REQUIREMENTS = ROOT / "requirements.txt"


def _source() -> str:
    return PIPELINE_SOURCE.read_text(encoding="utf-8")


def _writer_generate_block() -> str:
    source = WRITER_ROUTER_SOURCE.read_text(encoding="utf-8")
    return source.split('@router.post("/novels/{project_id}/chapters/generate"', 1)[1].split(
        "\n\n@router.post(\"/novels/{project_id}/chapters/select\"",
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


def test_langgraph_pipeline_marks_chapter_failed_on_runtime_error() -> None:
    source = _source()

    assert "await self._mark_generation_failed(" in source
    assert 'chapter.status = "failed"' in source
    assert 'chapter.generation_step = "failed"' in source
