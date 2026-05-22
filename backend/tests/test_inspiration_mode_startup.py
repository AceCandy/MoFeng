from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INSPIRATION_MODE = ROOT / "frontend/src/views/InspirationMode.vue"


def _source() -> str:
    return INSPIRATION_MODE.read_text(encoding="utf-8")


def test_inspiration_mode_starts_with_local_opening_message():
    source = _source()

    assert "INSPIRATION_OPENING_MESSAGE" in source
    assert "INSPIRATION_INITIAL_UI_CONTROL" in source


def test_start_conversation_does_not_request_first_ai_turn():
    source = _source()

    start_block = source.split("const startConversation = async () => {", 1)[1].split(
        "\nconst restoreConversation",
        1,
    )[0]

    assert "handleUserInput(null)" not in start_block
    assert "showLocalOpeningMessage()" in start_block


def test_start_conversation_reuses_unfinished_inspiration_project():
    source = _source()

    assert "readUnfinishedInspirationProjectId" in source
    assert "HttpRequestError" in source
    assert "unfinished_inspiration" in source
    assert "router.replace" in source
    assert "restoreConversation(existingProjectId)" in source
