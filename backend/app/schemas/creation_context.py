# AIMETA P=创作上下文Schema_跨设备恢复合同|R=字段级PATCH_读取响应|NR=不含持久化逻辑|E=CreationContextPatch|X=http|A=request_response|D=pydantic|S=none|RD=./README.ai
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

CreationSurface = Literal["inspiration", "archive", "writing"]
WritingDeskSection = Literal["content", "versions", "evaluation"]


class CreationContextPatch(BaseModel):
    """只更新显式出现的语义位置字段。"""

    model_config = ConfigDict(extra="forbid")

    surface: Optional[CreationSurface] = None
    chapter_number: Optional[int] = Field(default=None, ge=1)
    desk_section: Optional[WritingDeskSection] = None
    inspiration_draft: Optional[str] = Field(default=None, max_length=100_000)
    inspiration_turn: Optional[int] = Field(default=None, ge=0)

    @model_validator(mode="after")
    def validate_patch_fields(self) -> "CreationContextPatch":
        supplied = self.model_fields_set
        if not supplied:
            raise ValueError("至少需要更新一个创作上下文字段")
        draft_fields = {"inspiration_draft", "inspiration_turn"}
        if supplied.intersection(draft_fields) and not draft_fields.issubset(supplied):
            raise ValueError("灵感草稿与轮次必须同时提交")
        if "inspiration_turn" in supplied and self.inspiration_turn is None:
            raise ValueError("灵感轮次不能为空")
        return self


class CreationContextRead(BaseModel):
    """当前用户单个项目的跨设备创作上下文。"""

    model_config = ConfigDict(from_attributes=True)

    user_id: int
    project_id: str
    surface: Optional[CreationSurface] = None
    chapter_number: Optional[int] = None
    desk_section: Optional[WritingDeskSection] = None
    inspiration_draft: Optional[str] = None
    inspiration_turn: Optional[int] = None
    updated_at: datetime
