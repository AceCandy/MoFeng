import pytest

from app.services.chapter_word_count_settings import (
    build_word_count_requirement_text,
    DEFAULT_CHAPTER_TARGET_WORD_COUNT,
    MIN_CHAPTER_TARGET_WORD_COUNT,
    resolve_word_count_requirements,
    should_compress_chapter,
)


class DummyConfig:
    def __init__(self, value):
        self.value = value


class DummyRepo:
    def __init__(self, values):
        self.values = values

    async def get_by_key(self, key):
        value = self.values.get(key)
        return DummyConfig(value) if value is not None else None


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_word_count_requirements_uses_system_config_value():
    target, minimum = await resolve_word_count_requirements(
        DummyRepo({"writer.chapter_word_limit": "4500"})
    )

    assert target == 4500
    assert minimum == 3600


@pytest.mark.asyncio(loop_scope="session")
async def test_resolve_word_count_requirements_ignores_invalid_low_value():
    target, minimum = await resolve_word_count_requirements(
        DummyRepo({"writer.chapter_word_limit": "1200"})
    )

    assert target == DEFAULT_CHAPTER_TARGET_WORD_COUNT
    assert minimum == MIN_CHAPTER_TARGET_WORD_COUNT


def test_build_word_count_requirement_text_includes_hard_upper_limit():
    text = build_word_count_requirement_text(4000)

    assert "不得超过 4400 字" in text
    assert "超出上限必须压缩" in text


def test_should_compress_chapter_detects_excessive_output():
    assert should_compress_chapter("哈" * 4600, 4000)
    assert not should_compress_chapter("哈" * 4300, 4000)
