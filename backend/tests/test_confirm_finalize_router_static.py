from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WRITER_SOURCE = ROOT / "app/api/routers/writer.py"


def _source() -> str:
    return WRITER_SOURCE.read_text(encoding="utf-8")


def test_confirm_finalize_endpoint_submits_one_durable_job() -> None:
    source = _source()

    assert '"/novels/{project_id}/chapters/{chapter_number}/confirm-finalize"' in source
    assert "response_model=BackgroundTaskResponse" in source
    assert "status_code=202" in source
    block = source.split("async def confirm_finalize_chapter", 1)[1].split("\n\n@router.", 1)[0]
    assert block.count("await _enqueue_chapter_finalize(") == 1
    assert "selected_version_index=request.selected_version_index" in block
    assert "edited_content=request.edited_content" in block
    assert "skip_vector_update=request.skip_vector_update" in block


def test_confirm_finalize_does_not_execute_long_pipeline_in_web_process() -> None:
    block = (
        _source()
        .split("async def confirm_finalize_chapter", 1)[1]
        .split(
            "\n\n@router.",
            1,
        )[0]
    )

    assert "background_tasks.add_task" not in block
    assert "_schedule_finalize_task" not in block
    assert "FinalizeService(" not in block
    assert "LLMService(" not in block


def test_writer_has_no_synchronous_finalize_pipeline() -> None:
    source = _source()

    assert "_confirm_finalize_chapter_sync" not in source
    assert "_record_finalize_workflow_success" not in source


def test_advanced_generate_submits_durable_generation_job() -> None:
    source = _source()
    block = source.split('@router.post("/advanced/generate"', 1)[1].split(
        '\n\n@router.post("/chapters/{chapter_number}/finalize"',
        1,
    )[0]

    assert "response_model=BackgroundTaskResponse" in block
    assert "status_code=202" in block
    assert "await _enqueue_chapter_generation(" in block
    assert "PipelineOrchestrator(" not in block


def test_select_endpoint_no_longer_background_syncs_foreshadowing() -> None:
    source = _source()
    block = source.split('"/novels/{project_id}/chapters/select"', 1)[1].split(
        "\n\n@router.post",
        1,
    )[0]

    assert "_sync_foreshadowings_after_finalize" not in block
    assert "background_tasks.add_task" not in block
