from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRITER_SOURCE = ROOT / "app/api/routers/writer.py"


def _source() -> str:
    return WRITER_SOURCE.read_text(encoding="utf-8")


def test_confirm_finalize_endpoint_runs_synchronous_pipeline() -> None:
    source = _source()

    assert '@router.post("/novels/{project_id}/chapters/{chapter_number}/confirm-finalize"' in source
    assert "response_model=ConfirmFinalizeChapterResponse" in source
    assert "ChapterGenerationStatus.FINALIZING.value" in source
    assert 'node_key="confirm_finalize"' in source
    assert 'node_key="real_summary"' in source
    assert 'node_key="finalize_memory"' in source
    assert 'node_key="chapter_ingest"' in source
    assert 'node_key="foreshadowing_sync"' in source
    assert 'node_key="finalized"' in source
    assert 'node_key="finalization_error"' in source


def test_confirm_finalize_does_not_schedule_background_tasks() -> None:
    block = _source().split("async def confirm_finalize_chapter", 1)[1].split(
        "\n\n@router.",
        1,
    )[0]

    assert "background_tasks.add_task" not in block
    assert "_schedule_finalize_task" not in block


def test_confirm_finalize_failure_restores_draft_without_selected_content() -> None:
    block = _source().split("async def _confirm_finalize_chapter_sync", 1)[1].split(
        "\n\n@router.post(\"/chapters/{chapter_number}/finalize\"",
        1,
    )[0]
    failure_block = block.split("except Exception as exc:", 1)[1]

    assert "refreshed.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value" in failure_block
    assert "refreshed.selected_version_id = None" in failure_block
    assert "refreshed.selected_version = None" in failure_block
    assert "refreshed.real_summary = None" in failure_block
    assert "refreshed.word_count = 0" in failure_block


def test_advanced_generate_no_longer_schedules_async_finalize() -> None:
    source = _source()
    block = source.split('@router.post("/advanced/generate"', 1)[1].split(
        '\n\n@router.post("/chapters/{chapter_number}/finalize"',
        1,
    )[0]

    assert "_schedule_finalize_task" not in block
    assert "flow_config.async_finalize" not in block


def test_select_endpoint_no_longer_background_syncs_foreshadowing() -> None:
    source = _source()
    block = source.split('@router.post("/novels/{project_id}/chapters/select"', 1)[1].split(
        "\n\n@router.post",
        1,
    )[0]

    assert "_sync_foreshadowings_after_finalize" not in block
    assert "background_tasks.add_task" not in block
