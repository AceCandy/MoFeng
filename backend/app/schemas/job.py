# AIMETA P=持久任务payload契约_版本化业务参数|R=任务payload校验|NR=不含任务执行逻辑|E=ChapterOutlineJobPayload_ChapterGenerationJobPayload_ChapterFinalizeJobPayload|X=internal|A=pydantic_contract|D=pydantic|S=none|RD=./README.ai
from typing import Optional

from pydantic import BaseModel, Field

from .novel import FlowConfig


class ChapterOutlineJobPayload(BaseModel):
    """章节大纲 durable job v1 的持久参数。"""

    project_id: str = Field(min_length=1, max_length=36)
    start_chapter: int = Field(ge=1)
    num_chapters: int = Field(ge=1, le=20)


class ChapterEditPostprocessJobPayload(BaseModel):
    """章节编辑后处理 durable job v1 的不可变正文引用。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    selected_version_id: int = Field(ge=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    skip_vector_update: bool = False


class ChapterFinalizeJobPayload(ChapterEditPostprocessJobPayload):
    """章节确认定稿 durable job v1 的不可变正文引用。"""


class ChapterGenerationJobPayload(BaseModel):
    """章节 LangGraph 生成 durable job v1 的持久参数。"""

    project_id: str = Field(min_length=1, max_length=36)
    chapter_number: int = Field(ge=1)
    writing_notes: Optional[str] = None
    flow_config: FlowConfig = Field(default_factory=FlowConfig)
    from_node_key: Optional[str] = None
