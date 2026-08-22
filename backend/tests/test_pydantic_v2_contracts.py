# AIMETA P=Pydantic读取模式契约测试|R=ORM属性读取_序列化_JSON字段|NR=不测试路由或数据库|E=test:pydantic-v2-contracts|X=internal|A=read-schema-contracts|D=pytest,pydantic|S=test|RD=../app/schemas/README.ai
from datetime import datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.schemas.admin import UpdateLogRead
from app.schemas.config import SystemConfigRead
from app.schemas.llm_config import LLMConfigRead
from app.schemas.novel import Blueprint, NovelProject
from app.schemas.prompt import PromptRead
from app.schemas.user import User


@pytest.mark.parametrize(
    ("schema_type", "source", "expected"),
    [
        (
            LLMConfigRead,
            SimpleNamespace(user_id=1),
            {
                "llm_provider_url": None,
                "llm_provider_api_key": None,
                "llm_provider_model": None,
                "embedding_provider_url": None,
                "embedding_provider_api_key": None,
                "embedding_provider_model": None,
                "embedding_provider_format": None,
                "user_id": 1,
            },
        ),
        (
            UpdateLogRead,
            SimpleNamespace(
                id=2,
                content="更新内容",
                created_at=datetime(2026, 8, 22),
                is_pinned=False,
            ),
            {
                "id": 2,
                "content": "更新内容",
                "created_at": datetime(2026, 8, 22),
                "created_by": None,
                "is_pinned": False,
            },
        ),
        (
            SystemConfigRead,
            SimpleNamespace(key="feature", value="on"),
            {
                "key": "feature",
                "value": "on",
                "description": None,
                "is_sensitive": False,
                "is_configured": False,
            },
        ),
        (
            Blueprint,
            SimpleNamespace(title="蓝图"),
            {
                "title": "蓝图",
                "target_audience": "",
                "genre": "",
                "style": "",
                "tone": "",
                "one_sentence_summary": "",
                "full_synopsis": "",
                "world_setting": {},
                "characters": [],
                "relationships": [],
                "chapter_outline": [],
            },
        ),
        (
            NovelProject,
            SimpleNamespace(id="project-1", user_id=3, title="小说", initial_prompt="灵感"),
            {
                "id": "project-1",
                "user_id": 3,
                "title": "小说",
                "initial_prompt": "灵感",
                "conversation_history": [],
                "blueprint": None,
                "chapters": [],
            },
        ),
        (
            PromptRead,
            SimpleNamespace(id=4, name="chapter", title="章节", content="正文", tags="a,b"),
            {
                "name": "chapter",
                "title": "章节",
                "content": "正文",
                "tags": ["a", "b"],
                "id": 4,
            },
        ),
        (
            User,
            SimpleNamespace(id=5, username="reader"),
            {
                "username": "reader",
                "email": None,
                "id": 5,
                "is_admin": False,
                "is_active": True,
                "must_change_password": False,
            },
        ),
    ],
)
def test_read_schemas_preserve_attribute_dump_and_json_schema_contracts(
    schema_type: type[BaseModel],
    source: SimpleNamespace,
    expected: dict[str, object],
) -> None:
    instance = schema_type.model_validate(source)
    dumped = instance.model_dump()

    assert schema_type.model_config.get("from_attributes") is True
    assert dumped == expected
    assert set(schema_type.model_json_schema()["properties"]) == set(expected)
