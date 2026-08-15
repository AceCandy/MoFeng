from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _block(path: str, start: str, end: str) -> str:
    source = (ROOT / path).read_text(encoding="utf-8")
    return source.split(start, 1)[1].split(end, 1)[0]


def test_enhanced_flow_has_no_noncanonical_context_fallback() -> None:
    block = _block(
        "app/services/enhanced_writing_flow.py",
        "async def prepare_writing_context(",
        "def _build_persona_style_hints(",
    )

    assert "ChapterContext.model_validate(chapter_context)" in block
    assert "get_constitution(" not in block
    assert "ensure_default_persona(" not in block
    assert "get_foreshadowing_reminders(" not in block


def test_review_and_workflow_entrypoints_receive_canonical_context() -> None:
    router = _block(
        "app/api/routers/review.py",
        "async def review_six_dimension(",
        '@router.post("/consistency")',
    )
    workflow_provider = _block(
        "app/services/chapter_workflow_handler.py",
        "class ChapterWorkflowLLMProviders:",
        "class ChapterWorkflowBindingAssembler:",
    )
    review_service = _block(
        "app/services/six_dimension_review_service.py",
        "async def review_chapter(",
        "async def quick_review(",
    )

    assert "ChapterContextResolver(" in router
    assert "ReviewContextAdapter.to_prompt_context(chapter_context)" in router
    assert "ChapterContext.model_validate(request.context_snapshot)" in workflow_provider
    assert "GenerationContextAdapter.to_context(context)" in workflow_provider
    assert "ReviewContextAdapter.to_prompt_context(context)" in workflow_provider
    assert "constitution_context" in review_service
    assert "writer_persona_context" in review_service
    assert "get_constitution(" not in review_service
    assert "get_active_persona(" not in review_service
