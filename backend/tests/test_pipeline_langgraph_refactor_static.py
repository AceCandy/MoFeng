from pathlib import Path

from app.services.pipeline_orchestrator import PipelineConfig, PipelineOrchestrator


ROOT = Path(__file__).resolve().parents[1]
PIPELINE_SOURCE = ROOT / "app/services/pipeline_orchestrator.py"
REQUIREMENTS = ROOT / "requirements.txt"


def _source() -> str:
    return PIPELINE_SOURCE.read_text(encoding="utf-8")


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
