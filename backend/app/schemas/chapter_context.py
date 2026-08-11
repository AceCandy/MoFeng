# AIMETA P=章节上下文契约_可冻结事实快照|R=版本化section_稳定序列化_内容寻址|NR=不含数据读取|E=ChapterContext|X=internal|A=schema|D=pydantic|S=memory|RD=./README.ai
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, Generic, List, Optional, TypeVar

from pydantic import BaseModel, ConfigDict, Field, model_validator

CHAPTER_CONTEXT_SCHEMA_VERSION = "chapter-context.v1"
SOURCE_REVISION_SCHEMA_VERSION = "chapter-source-revision.v1"
MISSING_REVISION = "missing"
UNKNOWN_REVISION = "unknown"


def stable_json_dumps(value: Any) -> str:
    """生成跨进程稳定的 JSON，用于持久化快照和内容寻址。"""
    return json.dumps(
        _canonical_json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def _canonical_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, bool, float)):
        return value
    if isinstance(value, Enum):
        return _canonical_json_value(value.value)
    if isinstance(value, datetime):
        if value.tzinfo is not None and value.utcoffset() is not None:
            value = value.astimezone(timezone.utc)
            return value.isoformat().replace("+00:00", "Z")
        return value.isoformat()
    if isinstance(value, dict):
        return {
            str(key): _canonical_json_value(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_canonical_json_value(item) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized = [_canonical_json_value(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(
                item,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ),
        )
    return value


def stable_digest(value: Any) -> str:
    return hashlib.sha256(stable_json_dumps(value).encode("utf-8")).hexdigest()


class ContextSource(str, Enum):
    NOVEL_BLUEPRINT = "novel_blueprint"
    CHAPTER_OUTLINE = "chapter_outline"
    CHAPTER_BLUEPRINT = "chapter_blueprint"
    RUNTIME_INPUT = "runtime_input"
    CHAPTER_HISTORY = "chapter_history"
    PROJECT_MEMORY = "project_memory"
    NOVEL_CONSTITUTION = "novel_constitution"
    WRITER_PERSONA = "writer_persona"
    FORESHADOWING = "foreshadowing"
    CHARACTER_STATE = "character_state"
    VECTOR_RETRIEVAL = "vector_retrieval"
    VISIBILITY_POLICY = "visibility_policy"


class ContextFallback(str, Enum):
    SOURCE_MISSING = "source_missing"
    FIRST_CHAPTER = "first_chapter"
    SUMMARY_MISSING = "summary_missing"
    NOT_PROVIDED = "not_provided"
    DISABLED = "disabled"
    UNAVAILABLE = "unavailable"
    QUERY_EMPTY = "query_empty"
    EMBEDDING_FAILED = "embedding_failed"
    RETRIEVAL_EMPTY = "retrieval_empty"
    RETRIEVAL_FAILED = "retrieval_failed"
    BUDGET_TRUNCATED = "budget_truncated"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


T = TypeVar("T")


class ContextSection(ContractModel, Generic[T]):
    """携带来源、修订和降级信息的 canonical context section。"""

    value: T
    source: ContextSource
    source_revision: str
    truncated: bool = False
    fallback: Optional[ContextFallback] = None


class PreviousChapterContext(ContractModel):
    chapter_number: Optional[int] = None
    summary: str = ""
    tail_excerpt: str = ""


class CompletedChapterContext(ContractModel):
    chapter_number: int
    title: str
    summary: str


class ChapterHistory(ContractModel):
    previous_chapter: PreviousChapterContext = Field(default_factory=PreviousChapterContext)
    completed_chapters: List[CompletedChapterContext] = Field(default_factory=list)


class RAGChunkContext(ContractModel):
    chapter_number: int
    title: str
    content: str
    score: float
    rank: int
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RAGSummaryContext(ContractModel):
    chapter_number: int
    title: str
    summary: str
    score: float
    rank: int


class RelatedChapterContext(ContractModel):
    chapter_number: int
    title: str
    summary: str = ""
    relevance_score: float
    matched_content: str = ""


class ChapterRAGContext(ContractModel):
    mode: str = "none"
    query: str = ""
    chunks: List[RAGChunkContext] = Field(default_factory=list)
    summaries: List[RAGSummaryContext] = Field(default_factory=list)
    related_chapters: List[RelatedChapterContext] = Field(default_factory=list)
    knowledge_context: str = ""
    stats: Dict[str, Any] = Field(default_factory=dict)
    retrieval_snapshot_id: str = MISSING_REVISION


class WriterVisibilityContext(ContractModel):
    writer_blueprint: Dict[str, Any] = Field(default_factory=dict)
    introduced_characters: List[str] = Field(default_factory=list)
    planned_characters: List[str] = Field(default_factory=list)
    allowed_characters: List[str] = Field(default_factory=list)
    forbidden_characters: List[str] = Field(default_factory=list)


class WriterPersonaContext(ContractModel):
    prompt_context: str = ""
    name: str = ""
    catchphrases: List[str] = Field(default_factory=list)
    imperfection_patterns: List[str] = Field(default_factory=list)
    avoid_patterns: List[str] = Field(default_factory=list)


class ChapterContext(ContractModel):
    """章节生成、评审和一致性检查共享的可冻结事实快照。"""

    schema_version: str = CHAPTER_CONTEXT_SCHEMA_VERSION
    source_revision_schema_version: str = SOURCE_REVISION_SCHEMA_VERSION
    policy_version: str
    project_id: str
    chapter_number: int
    source_revision: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    input_hash: str = ""

    blueprint: ContextSection[Dict[str, Any]]
    outline: ContextSection[Dict[str, Any]]
    chapter_blueprint: ContextSection[Dict[str, Any]]
    chapter_mission: ContextSection[Dict[str, Any]]
    writing_notes: ContextSection[str]
    history: ContextSection[ChapterHistory]
    project_memory: ContextSection[Dict[str, Any]]
    constitution: ContextSection[str]
    writer_persona: ContextSection[WriterPersonaContext]
    foreshadows: ContextSection[List[Dict[str, Any]]]
    plot_threads: ContextSection[List[Dict[str, Any]]]
    character_states: ContextSection[List[Dict[str, Any]]]
    rag: ContextSection[ChapterRAGContext]
    writer_visibility: ContextSection[WriterVisibilityContext]

    @model_validator(mode="after")
    def _populate_input_hash(self) -> "ChapterContext":
        expected = stable_digest(self.hash_payload())
        if self.input_hash and self.input_hash != expected:
            raise ValueError("chapter context input_hash 与快照内容不一致")
        if not self.input_hash:
            object.__setattr__(self, "input_hash", expected)
        return self

    def hash_payload(self) -> Dict[str, Any]:
        """返回参与 input_hash 的稳定内容；观测时间不属于业务输入。"""
        payload = self.model_dump(mode="python", exclude={"created_at", "input_hash"})
        return _canonical_json_value(payload)

    def snapshot_payload(self) -> Dict[str, Any]:
        """返回 durable run 可直接保存的稳定快照。"""
        payload = self.model_dump(mode="python", exclude={"created_at"})
        return _canonical_json_value(payload)

    def snapshot_json(self) -> str:
        return stable_json_dumps(self.snapshot_payload())

    def with_updates(self, **updates: Any) -> "ChapterContext":
        payload = self.model_dump(mode="python")
        payload.update(updates)
        payload["input_hash"] = ""
        return ChapterContext.model_validate(payload)


__all__ = [
    "CHAPTER_CONTEXT_SCHEMA_VERSION",
    "MISSING_REVISION",
    "SOURCE_REVISION_SCHEMA_VERSION",
    "UNKNOWN_REVISION",
    "ChapterContext",
    "ChapterHistory",
    "ChapterRAGContext",
    "CompletedChapterContext",
    "ContextFallback",
    "ContextSection",
    "ContextSource",
    "PreviousChapterContext",
    "RAGChunkContext",
    "RAGSummaryContext",
    "RelatedChapterContext",
    "WriterVisibilityContext",
    "WriterPersonaContext",
    "stable_digest",
    "stable_json_dumps",
]
