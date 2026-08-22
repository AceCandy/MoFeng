# AIMETA P=提示词模式_提示模板请求响应|R=提示词结构|NR=不含业务逻辑|E=PromptSchema|X=internal|A=Pydantic模式|D=pydantic|S=none|RD=./README.ai
import re
from typing import Any, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")
MAX_TITLE_LENGTH = 255
MAX_TAG_COUNT = 12
MAX_TAG_LENGTH = 24
MAX_SERIALIZED_TAG_LENGTH = 255


def _normalize_tags(tags: Optional[List[str]]) -> Optional[List[str]]:
    if tags is None:
        return None

    normalized: list[str] = []
    seen: set[str] = set()
    for raw_tag in tags:
        tag = (raw_tag or "").strip()
        if not tag:
            continue
        if "," in tag:
            raise ValueError("标签不能包含英文逗号")
        if len(tag) > MAX_TAG_LENGTH:
            raise ValueError(f"单个标签长度不能超过 {MAX_TAG_LENGTH} 个字符")
        if tag not in seen:
            normalized.append(tag)
            seen.add(tag)

    if len(normalized) > MAX_TAG_COUNT:
        raise ValueError(f"标签数量不能超过 {MAX_TAG_COUNT} 个")

    if len(",".join(normalized)) > MAX_SERIALIZED_TAG_LENGTH:
        raise ValueError("标签总长度过长，请减少标签数量或缩短标签文本")

    return normalized or None


class PromptBase(BaseModel):
    """Prompt 基础模型。"""

    name: str = Field(..., description="唯一标识，用于代码引用", min_length=1, max_length=100)
    title: Optional[str] = Field(default=None, description="可读标题", max_length=MAX_TITLE_LENGTH)
    content: str = Field(..., description="提示词具体内容", min_length=1)
    tags: Optional[List[str]] = Field(default=None, description="标签集合")

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not NAME_PATTERN.fullmatch(normalized):
            raise ValueError("名称仅支持字母、数字、下划线和中划线，且必须以字母或数字开头")
        return normalized

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("提示词内容不能为空")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _normalize_tags(value)


class PromptCreate(PromptBase):
    """创建 Prompt 时使用的模型。"""

    pass


class PromptUpdate(BaseModel):
    """更新 Prompt 时使用的模型。"""

    title: Optional[str] = Field(default=None, max_length=MAX_TITLE_LENGTH)
    content: Optional[str] = Field(default=None)
    tags: Optional[List[str]] = Field(default=None)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        if not value.strip():
            raise ValueError("提示词内容不能为空")
        return value

    @field_validator("tags")
    @classmethod
    def validate_tags(cls, value: Optional[List[str]]) -> Optional[List[str]]:
        return _normalize_tags(value)


class PromptRead(PromptBase):
    """对外暴露的 Prompt 数据结构。"""

    model_config = ConfigDict(from_attributes=True)

    id: int

    @classmethod
    def model_validate(cls, obj: Any, *args: Any, **kwargs: Any) -> "PromptRead":  # type: ignore[override]
        """在转换 ORM 模型时，将字符串标签拆分为列表。"""
        if hasattr(obj, "id") and hasattr(obj, "name"):
            raw_tags = getattr(obj, "tags", None)
            if isinstance(raw_tags, str):
                processed = [tag for tag in raw_tags.split(",") if tag]
            elif isinstance(raw_tags, list):
                processed = raw_tags
            else:
                processed = None
            data = {
                "id": getattr(obj, "id"),
                "name": getattr(obj, "name"),
                "title": getattr(obj, "title", None),
                "content": getattr(obj, "content", None),
                "tags": processed,
            }
            return super().model_validate(data, *args, **kwargs)
        return super().model_validate(obj, *args, **kwargs)
