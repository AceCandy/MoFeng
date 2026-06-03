from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1] / "app"


def test_chapter_word_count_writes_use_non_whitespace_counter():
    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        for line_number, line in enumerate(source.splitlines(), start=1):
            compact = line.replace(" ", "")
            if "word_count=len(" in compact or "chapter.word_count=len(" in compact:
                offenders.append(f"{path.relative_to(BACKEND_ROOT)}:{line_number}:{line.strip()}")

    assert offenders == []
