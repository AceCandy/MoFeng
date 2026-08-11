import os
import re
from typing import Protocol, Tuple

from ..core.config import settings

DEFAULT_CHAPTER_TARGET_WORD_COUNT = 3000
MIN_CHAPTER_TARGET_WORD_COUNT = 2200
MIN_CONFIGURABLE_CHAPTER_WORD_COUNT = 2200
MAX_CHAPTER_WORD_COUNT_RATIO = 1.1
CHAPTER_WORD_LIMIT_CONFIG_KEY = "writer.chapter_word_limit"


class SystemConfigReader(Protocol):
    async def get_by_key(self, key: str): ...


def normalize_chapter_target_word_count(value: object) -> int:
    """归一化章节目标字数，低于生成质量下限时回退默认值。"""
    try:
        parsed = int(str(value or "").strip())
    except (TypeError, ValueError):
        return DEFAULT_CHAPTER_TARGET_WORD_COUNT
    if parsed < MIN_CONFIGURABLE_CHAPTER_WORD_COUNT:
        return DEFAULT_CHAPTER_TARGET_WORD_COUNT
    return parsed


def build_word_count_requirement_text(target_word_count: int) -> str:
    minimum_word_count = resolve_minimum_word_count(target_word_count)
    maximum_word_count = resolve_maximum_word_count(target_word_count)
    return (
        f"目标字数：约 {target_word_count} 字，不得少于 {minimum_word_count} 字，"
        f"不得超过 {maximum_word_count} 字。超出上限必须压缩，禁止继续扩写。"
    )


def resolve_minimum_word_count(target_word_count: int) -> int:
    if target_word_count == DEFAULT_CHAPTER_TARGET_WORD_COUNT:
        return MIN_CHAPTER_TARGET_WORD_COUNT
    return max(MIN_CHAPTER_TARGET_WORD_COUNT, int(target_word_count * 0.8))


def resolve_maximum_word_count(target_word_count: int) -> int:
    return int(target_word_count * MAX_CHAPTER_WORD_COUNT_RATIO)


def count_chapter_words(text: str) -> int:
    """计算章节正文长度，和现有 word_count 口径保持一致：去掉空白后按字符计数。"""
    return len(re.sub(r"\s+", "", text or ""))


def should_compress_chapter(text: str, target_word_count: int) -> bool:
    return count_chapter_words(text) > resolve_maximum_word_count(target_word_count)


async def resolve_word_count_requirements(repo: SystemConfigReader) -> Tuple[int, int]:
    record = await repo.get_by_key(CHAPTER_WORD_LIMIT_CONFIG_KEY)
    if record and getattr(record, "value", None):
        target_word_count = normalize_chapter_target_word_count(record.value)
    else:
        target_word_count = normalize_chapter_target_word_count(
            os.getenv("WRITER_CHAPTER_WORD_LIMIT") or settings.writer_chapter_word_limit
        )
    minimum_word_count = resolve_minimum_word_count(target_word_count)
    return target_word_count, minimum_word_count
