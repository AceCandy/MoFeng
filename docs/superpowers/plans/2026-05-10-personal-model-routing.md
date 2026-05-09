# Personal Model Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build personal multi-provider, multi-model, per-AI-stage model routing for chat and embedding workloads.

**Architecture:** Add user-scoped provider, model, and stage-route records beside the current legacy `llm_configs` table. Keep `LLMService` as the single runtime resolver so feature services only pass a stage key and never inspect provider credentials directly. Update the personal settings page to manage providers, available models, and stage defaults.

**Tech Stack:** FastAPI, SQLAlchemy 2 async ORM, Pydantic v2, pytest, Vue 3 Composition API, TypeScript, Vite.

---

## File Structure

Backend files:

- Create: `backend/app/models/ai_model_config.py`
  - Owns `UserModelProvider`, `UserAIModel`, and `UserAIStageRoute`.
- Modify: `backend/app/models/__init__.py`
  - Exports the new ORM models so `Base.metadata.create_all` loads them.
- Create: `backend/app/repositories/ai_model_config_repository.py`
  - Provides user-scoped provider/model/stage-route lookups.
- Modify: `backend/app/repositories/__init__.py`
  - Exports the repository classes.
- Modify: `backend/app/schemas/llm_config.py`
  - Adds provider, model, stage-route, and compatibility response schemas.
- Modify: `backend/app/services/llm_config_service.py`
  - Adds provider/model/stage CRUD, discovery, testing, and legacy migration helpers.
- Modify: `backend/app/api/routers/llm_config.py`
  - Adds the new `/api/llm-config/*` endpoints.
- Modify: `backend/app/services/llm_service.py`
  - Resolves chat and embedding config by stage and model override.
- Modify: `backend/app/db/init_db.py`
  - Backfills new records from legacy `llm_configs`.
- Modify: selected AI call sites in:
  - `backend/app/api/routers/novels.py`
  - `backend/app/api/routers/writer.py`
  - `backend/app/api/routers/optimizer.py`
  - `backend/app/api/routers/analytics.py`
  - `backend/app/api/routers/review.py`
  - `backend/app/services/ai_review_service.py`
  - `backend/app/services/chapter_context_service.py`
  - `backend/app/services/chapter_ingest_service.py`
  - `backend/app/services/knowledge_retrieval_service.py`
  - `backend/app/services/import_service.py`
  - `backend/app/services/preview_generation_service.py`

Backend tests:

- Modify: `backend/tests/test_llm_service.py`
- Create: `backend/tests/test_llm_config_service.py`
- Create: `backend/tests/test_llm_config_routes_static.py`
- Create: `backend/tests/test_ai_stage_routing_static.py`

Frontend files:

- Modify: `frontend/src/api/llm.ts`
- Create: `frontend/src/components/llm-settings/types.ts`
- Create: `frontend/src/components/llm-settings/ProviderProfiles.vue`
- Create: `frontend/src/components/llm-settings/ModelPool.vue`
- Create: `frontend/src/components/llm-settings/StageRoutes.vue`
- Create: `frontend/src/components/llm-settings/DiagnosticsPanel.vue`
- Modify: `frontend/src/components/LLMSettings.vue`

---

## Stage Keys

Use this shared backend constant in `backend/app/services/llm_service.py` and mirror
the same string union in `frontend/src/components/llm-settings/types.ts`:

```python
CHAT_STAGE_KEYS = {
    "import_analysis",
    "concept_conversation",
    "world_blueprint",
    "chapter_outline",
    "chapter_blueprint",
    "chapter_mission",
    "chapter_preview",
    "chapter_writing",
    "chapter_rewrite",
    "chapter_compression",
    "chapter_enrichment",
    "version_review",
    "chapter_optimization",
    "deep_review",
    "emotion_analysis",
    "consistency_check",
    "summary_memory",
    "rag_query",
    "foreshadowing",
}

EMBEDDING_STAGE_KEYS = {"rag_embedding"}
```

---

## Task 1: Add Backend Data Model and Repository

**Files:**
- Create: `backend/app/models/ai_model_config.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/app/repositories/ai_model_config_repository.py`
- Modify: `backend/app/repositories/__init__.py`
- Create: `backend/tests/test_llm_config_service.py`

- [ ] **Step 1: Write failing model/repository tests**

Add this initial test file:

```python
# backend/tests/test_llm_config_service.py
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.llm_config_service import LLMConfigService


@pytest.mark.asyncio
async def test_mask_api_key_keeps_only_suffix():
    service = LLMConfigService(AsyncMock())

    assert service._mask_api_key("sk-1234567890") == "******7890"
    assert service._mask_api_key("") is None
    assert service._mask_api_key(None) is None


@pytest.mark.asyncio
async def test_pick_default_model_requires_capability():
    service = LLMConfigService(AsyncMock())
    models = [
        SimpleNamespace(id=1, model_name="embed", capabilities_json={"embedding": True}, is_enabled=True),
        SimpleNamespace(id=2, model_name="chat", capabilities_json={"chat": True}, is_enabled=True),
    ]

    selected = service._pick_default_model(models, capability="chat")

    assert selected.id == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py -q
```

Expected: fails because `_mask_api_key` and `_pick_default_model` do not exist.

- [ ] **Step 3: Add ORM models**

Create `backend/app/models/ai_model_config.py`:

```python
# AIMETA P=个人AI模型配置模型_供应商模型和阶段路由|R=模型配置表|NR=不含调用逻辑|E=UserModelProvider_UserAIModel_UserAIStageRoute|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from ..db.base import Base


class UserModelProvider(Base):
    """用户级模型供应商档案，保存 API 地址和密钥。"""

    __tablename__ = "user_model_providers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    provider_type: Mapped[str] = mapped_column(String(32), default="openai_compatible")
    base_url: Mapped[str] = mapped_column(Text)
    api_key_encrypted: Mapped[str | None] = mapped_column(Text)
    api_key_preview: Mapped[str | None] = mapped_column(String(32))
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    models: Mapped[list["UserAIModel"]] = relationship(
        "UserAIModel",
        back_populates="provider",
        cascade="all, delete-orphan",
    )


class UserAIModel(Base):
    """用户登记的可用模型，归属一个供应商档案。"""

    __tablename__ = "user_ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("user_model_providers.id", ondelete="CASCADE"), index=True)
    display_name: Mapped[str] = mapped_column(String(120))
    model_name: Mapped[str] = mapped_column(String(160))
    capabilities_json: Mapped[dict] = mapped_column(JSON, default=dict)
    context_window: Mapped[int | None] = mapped_column(Integer)
    is_default_chat: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default_embedding: Mapped[bool] = mapped_column(Boolean, default=False)
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    provider: Mapped[UserModelProvider] = relationship("UserModelProvider", back_populates="models")


class UserAIStageRoute(Base):
    """用户级 AI 阶段到模型的默认路由。"""

    __tablename__ = "user_ai_stage_routes"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    stage: Mapped[str] = mapped_column(String(64), primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("user_ai_models.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    model: Mapped[UserAIModel] = relationship("UserAIModel")
```

- [ ] **Step 4: Export models**

Modify `backend/app/models/__init__.py`:

```python
from .ai_model_config import UserAIModel, UserAIStageRoute, UserModelProvider
```

Add the names to `__all__`:

```python
    "UserModelProvider",
    "UserAIModel",
    "UserAIStageRoute",
```

- [ ] **Step 5: Add repository**

Create `backend/app/repositories/ai_model_config_repository.py`:

```python
# AIMETA P=个人AI模型配置仓库_供应商模型阶段路由查询|R=配置CRUD|NR=不含业务逻辑|E=AIModelConfigRepository|X=internal|A=仓库类|D=sqlalchemy|S=db|RD=./README.ai
from typing import Iterable, Optional

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from .base import BaseRepository
from ..models import UserAIModel, UserAIStageRoute, UserModelProvider


class UserModelProviderRepository(BaseRepository[UserModelProvider]):
    model = UserModelProvider

    async def list_by_user(self, user_id: int) -> Iterable[UserModelProvider]:
        result = await self.session.execute(
            select(UserModelProvider)
            .where(UserModelProvider.user_id == user_id)
            .order_by(UserModelProvider.id)
        )
        return result.scalars().all()

    async def get_owned(self, provider_id: int, user_id: int) -> Optional[UserModelProvider]:
        result = await self.session.execute(
            select(UserModelProvider).where(
                UserModelProvider.id == provider_id,
                UserModelProvider.user_id == user_id,
            )
        )
        return result.scalars().first()


class UserAIModelRepository(BaseRepository[UserAIModel]):
    model = UserAIModel

    async def list_by_user(self, user_id: int) -> Iterable[UserAIModel]:
        result = await self.session.execute(
            select(UserAIModel)
            .options(selectinload(UserAIModel.provider))
            .where(UserAIModel.user_id == user_id)
            .order_by(UserAIModel.sort_order, UserAIModel.id)
        )
        return result.scalars().all()

    async def get_owned(self, model_id: int, user_id: int) -> Optional[UserAIModel]:
        result = await self.session.execute(
            select(UserAIModel)
            .options(selectinload(UserAIModel.provider))
            .where(UserAIModel.id == model_id, UserAIModel.user_id == user_id)
        )
        return result.scalars().first()

    async def list_enabled_by_capability(self, user_id: int, capability: str) -> Iterable[UserAIModel]:
        models = await self.list_by_user(user_id)
        return [
            model for model in models
            if model.is_enabled and bool((model.capabilities_json or {}).get(capability))
        ]


class UserAIStageRouteRepository(BaseRepository[UserAIStageRoute]):
    model = UserAIStageRoute

    async def list_by_user(self, user_id: int) -> Iterable[UserAIStageRoute]:
        result = await self.session.execute(
            select(UserAIStageRoute)
            .options(selectinload(UserAIStageRoute.model).selectinload(UserAIModel.provider))
            .where(UserAIStageRoute.user_id == user_id)
            .order_by(UserAIStageRoute.stage)
        )
        return result.scalars().all()

    async def get_by_stage(self, user_id: int, stage: str) -> Optional[UserAIStageRoute]:
        result = await self.session.execute(
            select(UserAIStageRoute)
            .options(selectinload(UserAIStageRoute.model).selectinload(UserAIModel.provider))
            .where(UserAIStageRoute.user_id == user_id, UserAIStageRoute.stage == stage)
        )
        return result.scalars().first()
```

- [ ] **Step 6: Export repositories**

Modify `backend/app/repositories/__init__.py`:

```python
from .ai_model_config_repository import (
    UserAIModelRepository,
    UserAIStageRouteRepository,
    UserModelProviderRepository,
)
```

- [ ] **Step 7: Add minimal helper methods so the tests pass**

In `backend/app/services/llm_config_service.py`, add:

```python
    @staticmethod
    def _mask_api_key(api_key: Optional[str]) -> Optional[str]:
        cleaned = (api_key or "").strip()
        if not cleaned:
            return None
        return f"******{cleaned[-4:]}"

    @staticmethod
    def _pick_default_model(models: list, *, capability: str):
        for model in models:
            capabilities = model.capabilities_json or {}
            if model.is_enabled and capabilities.get(capability):
                return model
        return None
```

- [ ] **Step 8: Run test to verify it passes**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py -q
```

Expected: 2 passed.

- [ ] **Step 9: Commit**

```bash
git add backend/app/models/ai_model_config.py backend/app/models/__init__.py backend/app/repositories/ai_model_config_repository.py backend/app/repositories/__init__.py backend/app/services/llm_config_service.py backend/tests/test_llm_config_service.py
git commit -m "feat: add personal model config storage"
```

---

## Task 2: Add Schemas and LLM Config Service CRUD

**Files:**
- Modify: `backend/app/schemas/llm_config.py`
- Modify: `backend/app/services/llm_config_service.py`
- Modify: `backend/tests/test_llm_config_service.py`

- [ ] **Step 1: Extend service tests**

Append to `backend/tests/test_llm_config_service.py`:

```python
def test_stage_capability_mapping():
    assert LLMConfigService.stage_capability("chapter_writing") == "chat"
    assert LLMConfigService.stage_capability("rag_embedding") == "embedding"


def test_stage_capability_rejects_unknown_stage():
    with pytest.raises(ValueError) as exc_info:
        LLMConfigService.stage_capability("unknown")

    assert "unknown AI stage" in str(exc_info.value)
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py -q
```

Expected: fails because `stage_capability` does not exist.

- [ ] **Step 3: Add schemas**

Append these classes to `backend/app/schemas/llm_config.py`:

```python
from typing import Dict, List


class ProviderBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    provider_type: Literal["openai_compatible", "ollama", "custom"] = "openai_compatible"
    base_url: str = Field(min_length=1)
    api_key: Optional[str] = None
    is_enabled: bool = True


class ProviderCreate(ProviderBase):
    pass


class ProviderUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    provider_type: Optional[Literal["openai_compatible", "ollama", "custom"]] = None
    base_url: Optional[str] = Field(default=None, min_length=1)
    api_key: Optional[str] = None
    is_enabled: Optional[bool] = None


class ProviderRead(BaseModel):
    id: int
    user_id: int
    name: str
    provider_type: str
    base_url: str
    api_key_preview: Optional[str] = None
    is_enabled: bool

    model_config = {"from_attributes": True}


class UserAIModelBase(BaseModel):
    provider_id: int
    display_name: str = Field(min_length=1, max_length=120)
    model_name: str = Field(min_length=1, max_length=160)
    capabilities: Dict[str, bool] = Field(default_factory=lambda: {"chat": True, "embedding": False})
    context_window: Optional[int] = None
    is_default_chat: bool = False
    is_default_embedding: bool = False
    is_enabled: bool = True
    sort_order: int = 0


class UserAIModelCreate(UserAIModelBase):
    pass


class UserAIModelUpdate(BaseModel):
    provider_id: Optional[int] = None
    display_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    model_name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    capabilities: Optional[Dict[str, bool]] = None
    context_window: Optional[int] = None
    is_default_chat: Optional[bool] = None
    is_default_embedding: Optional[bool] = None
    is_enabled: Optional[bool] = None
    sort_order: Optional[int] = None


class UserAIModelRead(BaseModel):
    id: int
    user_id: int
    provider_id: int
    display_name: str
    model_name: str
    capabilities: Dict[str, bool]
    context_window: Optional[int] = None
    is_default_chat: bool
    is_default_embedding: bool
    is_enabled: bool
    sort_order: int

    model_config = {"from_attributes": True}


class StageRouteRead(BaseModel):
    stage: str
    model_id: int


class StageRouteUpsert(BaseModel):
    stage: str
    model_id: int


class StageRoutesPayload(BaseModel):
    routes: List[StageRouteUpsert]


class LLMConfigBundle(BaseModel):
    legacy: Optional[LLMConfigRead] = None
    providers: List[ProviderRead] = Field(default_factory=list)
    models: List[UserAIModelRead] = Field(default_factory=list)
    stage_routes: List[StageRouteRead] = Field(default_factory=list)
```

- [ ] **Step 4: Add stage constants and capability resolver**

In `backend/app/services/llm_config_service.py`, add near module top:

```python
CHAT_STAGE_KEYS = {
    "import_analysis",
    "concept_conversation",
    "world_blueprint",
    "chapter_outline",
    "chapter_blueprint",
    "chapter_mission",
    "chapter_preview",
    "chapter_writing",
    "chapter_rewrite",
    "chapter_compression",
    "chapter_enrichment",
    "version_review",
    "chapter_optimization",
    "deep_review",
    "emotion_analysis",
    "consistency_check",
    "summary_memory",
    "rag_query",
    "foreshadowing",
}
EMBEDDING_STAGE_KEYS = {"rag_embedding"}
ALL_STAGE_KEYS = CHAT_STAGE_KEYS | EMBEDDING_STAGE_KEYS
```

Add to `LLMConfigService`:

```python
    @staticmethod
    def stage_capability(stage: str) -> str:
        if stage in EMBEDDING_STAGE_KEYS:
            return "embedding"
        if stage in CHAT_STAGE_KEYS:
            return "chat"
        raise ValueError(f"unknown AI stage: {stage}")
```

- [ ] **Step 5: Wire repositories into service**

Modify `LLMConfigService.__init__`:

```python
from ..repositories.ai_model_config_repository import (
    UserAIModelRepository,
    UserAIStageRouteRepository,
    UserModelProviderRepository,
)


    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = LLMConfigRepository(session)
        self.system_config_repo = SystemConfigRepository(session)
        self.provider_repo = UserModelProviderRepository(session)
        self.model_repo = UserAIModelRepository(session)
        self.stage_route_repo = UserAIStageRouteRepository(session)
```

- [ ] **Step 6: Add mapper helpers**

Add to `LLMConfigService`:

```python
    @staticmethod
    def _model_to_read(model) -> UserAIModelRead:
        return UserAIModelRead(
            id=model.id,
            user_id=model.user_id,
            provider_id=model.provider_id,
            display_name=model.display_name,
            model_name=model.model_name,
            capabilities=model.capabilities_json or {},
            context_window=model.context_window,
            is_default_chat=model.is_default_chat,
            is_default_embedding=model.is_default_embedding,
            is_enabled=model.is_enabled,
            sort_order=model.sort_order,
        )

    @staticmethod
    def _provider_to_read(provider) -> ProviderRead:
        return ProviderRead.model_validate(provider)

    @staticmethod
    def _route_to_read(route) -> StageRouteRead:
        return StageRouteRead(stage=route.stage, model_id=route.model_id)
```

- [ ] **Step 7: Add provider/model CRUD methods**

Add imports:

```python
from ..models import UserAIModel, UserAIStageRoute, UserModelProvider
from ..schemas.llm_config import (
    LLMConfigBundle,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    StageRouteRead,
    StageRoutesPayload,
    UserAIModelCreate,
    UserAIModelRead,
    UserAIModelUpdate,
)
```

Add service methods:

```python
    async def list_bundle(self, user_id: int) -> LLMConfigBundle:
        legacy = await self.get_config(user_id)
        providers = [self._provider_to_read(item) for item in await self.provider_repo.list_by_user(user_id)]
        models = [self._model_to_read(item) for item in await self.model_repo.list_by_user(user_id)]
        routes = [self._route_to_read(item) for item in await self.stage_route_repo.list_by_user(user_id)]
        return LLMConfigBundle(legacy=legacy, providers=providers, models=models, stage_routes=routes)

    async def create_provider(self, user_id: int, payload: ProviderCreate) -> ProviderRead:
        provider = UserModelProvider(
            user_id=user_id,
            name=payload.name.strip(),
            provider_type=payload.provider_type,
            base_url=payload.base_url.strip().rstrip("/"),
            api_key_encrypted=(payload.api_key or "").strip() or None,
            api_key_preview=self._mask_api_key(payload.api_key),
            is_enabled=payload.is_enabled,
        )
        await self.provider_repo.add(provider)
        await self.session.commit()
        return self._provider_to_read(provider)

    async def list_providers(self, user_id: int) -> list[ProviderRead]:
        return [self._provider_to_read(item) for item in await self.provider_repo.list_by_user(user_id)]

    async def update_provider(self, user_id: int, provider_id: int, payload: ProviderUpdate) -> ProviderRead:
        provider = await self.provider_repo.get_owned(provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")
        data = payload.model_dump(exclude_unset=True)
        if "name" in data and data["name"] is not None:
            provider.name = data["name"].strip()
        if "provider_type" in data and data["provider_type"] is not None:
            provider.provider_type = data["provider_type"]
        if "base_url" in data and data["base_url"] is not None:
            provider.base_url = data["base_url"].strip().rstrip("/")
        if "api_key" in data:
            provider.api_key_encrypted = (data["api_key"] or "").strip() or None
            provider.api_key_preview = self._mask_api_key(data["api_key"])
        if "is_enabled" in data and data["is_enabled"] is not None:
            provider.is_enabled = data["is_enabled"]
        await self.session.commit()
        return self._provider_to_read(provider)

    async def create_model(self, user_id: int, payload: UserAIModelCreate) -> UserAIModelRead:
        provider = await self.provider_repo.get_owned(payload.provider_id, user_id)
        if not provider:
            raise ValueError("provider not found")
        model = UserAIModel(
            user_id=user_id,
            provider_id=payload.provider_id,
            display_name=payload.display_name.strip(),
            model_name=payload.model_name.strip(),
            capabilities_json=payload.capabilities,
            context_window=payload.context_window,
            is_default_chat=payload.is_default_chat,
            is_default_embedding=payload.is_default_embedding,
            is_enabled=payload.is_enabled,
            sort_order=payload.sort_order,
        )
        await self.model_repo.add(model)
        await self._normalize_default_flags(user_id, model)
        await self.session.commit()
        return self._model_to_read(model)

    async def list_models(self, user_id: int) -> list[UserAIModelRead]:
        return [self._model_to_read(item) for item in await self.model_repo.list_by_user(user_id)]
```

- [ ] **Step 8: Add default flag normalization**

Add to `LLMConfigService`:

```python
    async def _normalize_default_flags(self, user_id: int, changed_model) -> None:
        models = list(await self.model_repo.list_by_user(user_id))
        if changed_model.is_default_chat:
            for model in models:
                if model.id != changed_model.id:
                    model.is_default_chat = False
        if changed_model.is_default_embedding:
            for model in models:
                if model.id != changed_model.id:
                    model.is_default_embedding = False
```

- [ ] **Step 9: Add stage route upsert**

Add to `LLMConfigService`:

```python
    async def upsert_stage_routes(self, user_id: int, payload: StageRoutesPayload) -> list[StageRouteRead]:
        for item in payload.routes:
            capability = self.stage_capability(item.stage)
            model = await self.model_repo.get_owned(item.model_id, user_id)
            if not model:
                raise ValueError(f"model not found for stage {item.stage}")
            if not (model.capabilities_json or {}).get(capability):
                raise ValueError(f"model {model.model_name} does not support {capability}")
            route = await self.stage_route_repo.get_by_stage(user_id, item.stage)
            if route:
                route.model_id = item.model_id
            else:
                await self.stage_route_repo.add(
                    UserAIStageRoute(user_id=user_id, stage=item.stage, model_id=item.model_id)
                )
        await self.session.commit()
        return [self._route_to_read(item) for item in await self.stage_route_repo.list_by_user(user_id)]
```

- [ ] **Step 10: Run service tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py -q
```

Expected: all tests pass.

- [ ] **Step 11: Commit**

```bash
git add backend/app/schemas/llm_config.py backend/app/services/llm_config_service.py backend/tests/test_llm_config_service.py
git commit -m "feat: add personal model config service"
```

---

## Task 3: Add API Endpoints

**Files:**
- Modify: `backend/app/api/routers/llm_config.py`
- Create: `backend/tests/test_llm_config_routes_static.py`

- [ ] **Step 1: Write static route tests**

Create `backend/tests/test_llm_config_routes_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "app/api/routers/llm_config.py"


def _source() -> str:
    return ROUTER.read_text(encoding="utf-8")


def test_provider_model_and_stage_route_endpoints_exist():
    source = _source()

    assert '@router.get("/providers"' in source
    assert '@router.post("/providers"' in source
    assert '@router.patch("/providers/{provider_id}"' in source
    assert '@router.get("/user-models"' in source
    assert '@router.post("/user-models"' in source
    assert '@router.get("/stage-routes"' in source
    assert '@router.put("/stage-routes"' in source


def test_new_endpoints_require_current_user():
    source = _source()

    for name in [
        "list_providers",
        "create_provider",
        "patch_provider",
        "list_user_models",
        "create_user_model",
        "list_stage_routes",
        "put_stage_routes",
    ]:
        block = source.split(f"async def {name}", 1)[1].split(") ->", 1)[0]
        assert "current_user: UserInDB = Depends(get_current_user)" in block
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_routes_static.py -q
```

Expected: fails because the endpoints do not exist.

- [ ] **Step 3: Add imports**

Modify `backend/app/api/routers/llm_config.py` imports:

```python
from ...schemas.llm_config import (
    LLMConfigBundle,
    LLMConfigCreate,
    LLMConfigRead,
    ModelListRequest,
    ProviderCreate,
    ProviderRead,
    ProviderUpdate,
    StageRouteRead,
    StageRoutesPayload,
    UserAIModelCreate,
    UserAIModelRead,
)
```

- [ ] **Step 4: Change GET bundle response without breaking legacy callers**

Replace the existing `read_llm_config` implementation with:

```python
@router.get("", response_model=LLMConfigBundle)
async def read_llm_config(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> LLMConfigBundle:
    return await service.list_bundle(current_user.id)
```

Keep `PUT ""` and `DELETE ""` in place for legacy save/delete behavior.

- [ ] **Step 5: Add provider endpoints**

Append to `backend/app/api/routers/llm_config.py`:

```python
@router.get("/providers", response_model=List[ProviderRead])
async def list_providers(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[ProviderRead]:
    return await service.list_providers(current_user.id)


@router.post("/providers", response_model=ProviderRead, status_code=status.HTTP_201_CREATED)
async def create_provider(
    payload: ProviderCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    return await service.create_provider(current_user.id, payload)


@router.patch("/providers/{provider_id}", response_model=ProviderRead)
async def patch_provider(
    provider_id: int,
    payload: ProviderUpdate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> ProviderRead:
    try:
        return await service.update_provider(current_user.id, provider_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
```

- [ ] **Step 6: Add model endpoints**

Append:

```python
@router.get("/user-models", response_model=List[UserAIModelRead])
async def list_user_models(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[UserAIModelRead]:
    return await service.list_models(current_user.id)


@router.post("/user-models", response_model=UserAIModelRead, status_code=status.HTTP_201_CREATED)
async def create_user_model(
    payload: UserAIModelCreate,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> UserAIModelRead:
    try:
        return await service.create_model(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 7: Add stage-route endpoints**

Append:

```python
@router.get("/stage-routes", response_model=List[StageRouteRead])
async def list_stage_routes(
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[StageRouteRead]:
    bundle = await service.list_bundle(current_user.id)
    return bundle.stage_routes


@router.put("/stage-routes", response_model=List[StageRouteRead])
async def put_stage_routes(
    payload: StageRoutesPayload,
    service: LLMConfigService = Depends(get_llm_config_service),
    current_user: UserInDB = Depends(get_current_user),
) -> List[StageRouteRead]:
    try:
        return await service.upsert_stage_routes(current_user.id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
```

- [ ] **Step 8: Run route tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_routes_static.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/routers/llm_config.py backend/tests/test_llm_config_routes_static.py
git commit -m "feat: expose personal model config api"
```

---

## Task 4: Add Stage-Aware Runtime Resolver

**Files:**
- Modify: `backend/app/services/llm_service.py`
- Modify: `backend/tests/test_llm_service.py`

- [ ] **Step 1: Add failing resolver tests**

Append to `backend/tests/test_llm_service.py`:

```python
@pytest.mark.asyncio
async def test_resolve_llm_config_uses_stage_route_model():
    service = LLMService(AsyncMock())
    provider = SimpleNamespace(
        base_url="https://api.stage.test/v1",
        api_key_encrypted="stage-key",
        is_enabled=True,
    )
    model = SimpleNamespace(
        id=42,
        model_name="stage-chat",
        capabilities_json={"chat": True},
        is_enabled=True,
        provider=provider,
    )
    service.stage_route_repo = SimpleNamespace(
        get_by_stage=AsyncMock(return_value=SimpleNamespace(model=model))
    )
    service.ai_model_repo = SimpleNamespace(get_owned=AsyncMock(return_value=None))
    service.llm_repo = SimpleNamespace(get_by_user=AsyncMock(return_value=None))

    config = await service._resolve_llm_config_with_policy(
        7,
        require_api_key=True,
        stage="chapter_writing",
    )

    assert config["model"] == "stage-chat"
    assert config["api_key"] == "stage-key"
    assert config["base_url"] == "https://api.stage.test/v1"
    assert config["stage"] == "chapter_writing"


@pytest.mark.asyncio
async def test_resolve_embedding_config_rejects_chat_only_route():
    service = LLMService(AsyncMock())
    provider = SimpleNamespace(
        base_url="https://api.stage.test/v1",
        api_key_encrypted="stage-key",
        is_enabled=True,
    )
    model = SimpleNamespace(
        id=42,
        model_name="chat-only",
        capabilities_json={"chat": True, "embedding": False},
        is_enabled=True,
        provider=provider,
    )
    service.stage_route_repo = SimpleNamespace(
        get_by_stage=AsyncMock(return_value=SimpleNamespace(model=model))
    )
    service.ai_model_repo = SimpleNamespace(get_owned=AsyncMock(return_value=None))

    with pytest.raises(HTTPException) as exc_info:
        await service._resolve_model_route(7, stage="rag_embedding", capability="embedding")

    assert exc_info.value.status_code == 400
    assert "embedding" in exc_info.value.detail
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_service.py -q
```

Expected: fails because `stage` and `_resolve_model_route` are not implemented.

- [ ] **Step 3: Add repository imports and init fields**

Modify `backend/app/services/llm_service.py` imports:

```python
from ..repositories.ai_model_config_repository import (
    UserAIModelRepository,
    UserAIStageRouteRepository,
)
from ..services.llm_config_service import CHAT_STAGE_KEYS, EMBEDDING_STAGE_KEYS
```

Modify `LLMService.__init__`:

```python
        self.ai_model_repo = UserAIModelRepository(session)
        self.stage_route_repo = UserAIStageRouteRepository(session)
```

- [ ] **Step 4: Add stage and override parameters to public methods**

Update method signatures:

```python
    async def get_llm_response(..., stage: str = "chapter_writing", model_id: Optional[int] = None) -> str:
```

```python
    async def stream_llm_response(..., stage: str = "concept_conversation", model_id: Optional[int] = None) -> AsyncGenerator[str, None]:
```

```python
    async def generate(..., stage: str = "chapter_writing", model_id: Optional[int] = None) -> str:
```

```python
    async def get_summary(..., stage: str = "summary_memory", model_id: Optional[int] = None) -> str:
```

```python
    async def get_embedding(..., stage: str = "rag_embedding", model_id: Optional[int] = None) -> List[float]:
```

Pass `stage` and `model_id` into `_stream_and_collect` and resolver calls.

- [ ] **Step 5: Add route resolver**

Add to `LLMService`:

```python
    async def _resolve_model_route(
        self,
        user_id: int,
        *,
        stage: str,
        capability: str,
        model_id: Optional[int] = None,
    ):
        model = None
        if model_id is not None:
            model = await self.ai_model_repo.get_owned(model_id, user_id)
            if not model:
                raise HTTPException(status_code=400, detail="选择的模型不存在或不属于当前用户")
        else:
            route = await self.stage_route_repo.get_by_stage(user_id, stage)
            model = route.model if route else None

        if not model:
            return None
        if not model.is_enabled:
            raise HTTPException(status_code=400, detail=f"模型 {model.model_name} 已禁用")
        if not (model.capabilities_json or {}).get(capability):
            raise HTTPException(status_code=400, detail=f"模型 {model.model_name} 不支持 {capability}")
        provider = model.provider
        if not provider or not provider.is_enabled:
            raise HTTPException(status_code=400, detail=f"模型 {model.model_name} 的供应商不可用")
        base_url = (provider.base_url or "").strip() or None
        api_key = (provider.api_key_encrypted or "").strip() or None
        if not base_url:
            raise HTTPException(status_code=400, detail=f"供应商 {provider.name} 缺少 API URL")
        return {
            "api_key": api_key,
            "base_url": base_url,
            "model": model.model_name,
            "model_id": model.id,
            "stage": stage,
            "provider_type": provider.provider_type,
        }
```

- [ ] **Step 6: Update chat resolver with fallback**

Replace `_resolve_llm_config_with_policy` body with this structure:

```python
    async def _resolve_llm_config_with_policy(
        self,
        user_id: Optional[int],
        *,
        require_api_key: bool,
        stage: str = "chapter_writing",
        model_id: Optional[int] = None,
    ) -> Dict[str, Optional[str]]:
        if not user_id:
            logger.warning("缺少 user_id，拒绝回退到默认 LLM 配置")
            raise HTTPException(
                status_code=400,
                detail="缺少用户上下文，无法读取用户级 LLM 配置。系统默认 LLM 配置已禁用，请重新登录后在模型设置中保存用户级配置。",
            )

        routed = await self._resolve_model_route(
            user_id,
            stage=stage,
            capability="chat",
            model_id=model_id,
        )
        if routed:
            if require_api_key and not routed.get("api_key"):
                raise HTTPException(status_code=400, detail=f"阶段 {stage} 使用的供应商缺少 API Key")
            return routed

        config = await self._get_user_llm_config_record(user_id)
        api_key = (config.llm_provider_api_key or "").strip() or None
        base_url = (config.llm_provider_url or "").strip() or None
        model = (config.llm_provider_model or "").strip() or None

        missing_fields: List[str] = []
        if not base_url:
            missing_fields.append("API URL")
        if require_api_key and not api_key:
            missing_fields.append("API Key")
        if not model:
            missing_fields.append("Model")
        if missing_fields:
            logger.warning("用户 %s 的用户级 LLM 配置不完整: missing=%s", user_id, ",".join(missing_fields))
            raise HTTPException(
                status_code=400,
                detail=f"请先在模型设置中补全用户级 LLM 配置：{'、'.join(missing_fields)}。系统默认 LLM 配置已禁用。",
            )

        return {"api_key": api_key, "base_url": base_url, "model": model, "stage": stage, "model_id": None}
```

- [ ] **Step 7: Update embedding resolver path**

At the start of `get_embedding`, after user context validation, try:

```python
        routed = await self._resolve_model_route(
            user_id,
            stage=stage,
            capability="embedding",
            model_id=model_id,
        )
        if routed:
            target_model = routed["model"]
            provider = "ollama" if routed.get("provider_type") == "ollama" else "openai"
            user_embedding_base_url = routed.get("base_url")
            user_embedding_api_key = routed.get("api_key")
            user_llm_base_url = user_embedding_base_url
            user_llm_api_key = user_embedding_api_key
            user_embedding_provider_format = provider
        else:
            user_llm_config = await self._get_user_llm_config_record(user_id)
```

Keep the existing OpenAI/Ollama embedding request branches after these variables are assigned.

- [ ] **Step 8: Run resolver tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_service.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/services/llm_service.py backend/tests/test_llm_service.py
git commit -m "feat: resolve ai models by stage"
```

---

## Task 5: Add Stage Keys to High-Impact AI Calls

**Files:**
- Modify: `backend/app/api/routers/novels.py`
- Modify: `backend/app/api/routers/writer.py`
- Modify: `backend/app/api/routers/optimizer.py`
- Modify: `backend/app/services/ai_review_service.py`
- Modify: `backend/app/services/import_service.py`
- Modify: `backend/app/services/preview_generation_service.py`
- Modify: `backend/app/services/chapter_ingest_service.py`
- Modify: `backend/app/services/chapter_context_service.py`
- Modify: `backend/app/services/knowledge_retrieval_service.py`
- Create: `backend/tests/test_ai_stage_routing_static.py`

- [ ] **Step 1: Write static routing test**

Create `backend/tests/test_ai_stage_routing_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _source(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_core_user_facing_ai_calls_pass_stage_keys():
    checks = {
        "app/api/routers/novels.py": [
            'stage="concept_conversation"',
            'stage="world_blueprint"',
        ],
        "app/api/routers/writer.py": [
            'stage="chapter_outline"',
            'stage="chapter_mission"',
            'stage="chapter_writing"',
            'stage="chapter_rewrite"',
            'stage="chapter_compression"',
        ],
        "app/api/routers/optimizer.py": [
            'stage="chapter_optimization"',
        ],
        "app/services/ai_review_service.py": [
            'stage="version_review"',
        ],
        "app/services/import_service.py": [
            'stage="import_analysis"',
        ],
        "app/services/preview_generation_service.py": [
            'stage="chapter_preview"',
        ],
    }

    for path, needles in checks.items():
        source = _source(path)
        for needle in needles:
            assert needle in source, f"{needle} missing from {path}"


def test_embedding_calls_pass_rag_embedding_stage():
    checks = [
        "app/services/chapter_ingest_service.py",
        "app/services/chapter_context_service.py",
        "app/services/knowledge_retrieval_service.py",
    ]

    for path in checks:
        source = _source(path)
        assert 'stage="rag_embedding"' in source
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_ai_stage_routing_static.py -q
```

Expected: fails because stage keys are not passed.

- [ ] **Step 3: Add stages in concept and blueprint calls**

Modify `backend/app/api/routers/novels.py`:

```python
    llm_response = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=conversation_history,
        temperature=0.8,
        user_id=current_user.id,
        timeout=240.0,
        stage="concept_conversation",
    )
```

```python
            async for chunk in llm_service.stream_llm_response(
                system_prompt=system_prompt,
                conversation_history=conversation_history,
                temperature=0.8,
                user_id=current_user.id,
                timeout=240.0,
                stage="concept_conversation",
            ):
```

```python
    blueprint_raw = await llm_service.get_llm_response(
        system_prompt=system_prompt,
        conversation_history=formatted_history,
        temperature=0.3,
        user_id=current_user.id,
        timeout=480.0,
        stage="world_blueprint",
    )
```

- [ ] **Step 4: Add stages in writer router**

Modify `backend/app/api/routers/writer.py`:

```python
        response = await llm_service.get_llm_response(
            system_prompt=plan_prompt,
            conversation_history=[{"role": "user", "content": plan_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=120.0,
            stage="chapter_mission",
        )
```

```python
        response = await llm_service.get_llm_response(
            system_prompt=rewrite_prompt,
            conversation_history=[{"role": "user", "content": rewrite_input}],
            temperature=0.3,
            user_id=user_id,
            timeout=300.0,
            response_format=None,
            max_tokens=WRITER_GENERATION_MAX_TOKENS,
            stage="chapter_rewrite",
        )
```

```python
            response = await llm_service.get_llm_response(
                system_prompt=writer_prompt,
                conversation_history=[{"role": "user", "content": final_prompt_input}],
                temperature=0.9,
                user_id=current_user.id,
                timeout=600.0,
                response_format=None,
                max_tokens=WRITER_GENERATION_MAX_TOKENS,
                stage="chapter_writing",
            )
```

```python
    response = await llm_service.get_llm_response(
        system_prompt=outline_prompt,
        conversation_history=[{"role": "user", "content": prompt_input}],
        temperature=0.7,
        user_id=current_user.id,
        stage="chapter_outline",
    )
```

For compression helpers, add `stage="chapter_compression"` to the compression call.

- [ ] **Step 5: Add stages in optimizer and review**

Modify `backend/app/api/routers/optimizer.py`:

```python
        response = await llm_service.get_llm_response(
            system_prompt=optimizer_prompt,
            conversation_history=[{
                "role": "user",
                "content": json.dumps(optimize_input, ensure_ascii=False)
            }],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            stage="chapter_optimization",
        )
```

Modify both review calls in `backend/app/services/ai_review_service.py`:

```python
            response = await self.llm_service.get_llm_response(
                system_prompt=review_prompt,
                conversation_history=[{"role": "user", "content": review_input}],
                temperature=0.3,
                user_id=user_id,
                timeout=180.0,
                stage="version_review",
            )
```

- [ ] **Step 6: Add stages in import and preview services**

Modify import analysis calls:

```python
            response = await self.llm_service.get_llm_response(
                system_prompt=system_prompt,
                conversation_history=messages,
                temperature=0.1,
                user_id=user_id,
                timeout=60.0,
                response_format="json_object",
                stage="import_analysis",
            )
```

Modify preview calls in `preview_generation_service.py` with:

```python
                stage="chapter_preview",
```

- [ ] **Step 7: Add embedding stages**

Modify embedding calls:

```python
            embedding = await self._llm_service.get_embedding(
                chunk_text,
                user_id=user_id,
                stage="rag_embedding",
            )
```

```python
        embedding = await self._llm_service.get_embedding(
            query,
            user_id=user_id,
            stage="rag_embedding",
        )
```

```python
                    embedding = await self.llm_service.get_embedding(
                        query,
                        user_id=user_id,
                        stage="rag_embedding",
                    )
```

- [ ] **Step 8: Run static routing tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_ai_stage_routing_static.py -q
```

Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add backend/app/api/routers/novels.py backend/app/api/routers/writer.py backend/app/api/routers/optimizer.py backend/app/services/ai_review_service.py backend/app/services/import_service.py backend/app/services/preview_generation_service.py backend/app/services/chapter_ingest_service.py backend/app/services/chapter_context_service.py backend/app/services/knowledge_retrieval_service.py backend/tests/test_ai_stage_routing_static.py
git commit -m "feat: route core ai calls by stage"
```

---

## Task 6: Backfill Legacy Config on Startup

**Files:**
- Modify: `backend/app/db/init_db.py`
- Modify: `backend/tests/test_llm_config_service.py`

- [ ] **Step 1: Add migration helper unit test**

Append to `backend/tests/test_llm_config_service.py`:

```python
def test_legacy_provider_name_is_stable():
    assert LLMConfigService.legacy_provider_name("chat") == "Legacy Chat Provider"
    assert LLMConfigService.legacy_provider_name("embedding") == "Legacy Embedding Provider"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py -q
```

Expected: fails because `legacy_provider_name` does not exist.

- [ ] **Step 3: Add helper**

Add to `LLMConfigService`:

```python
    @staticmethod
    def legacy_provider_name(kind: str) -> str:
        return "Legacy Embedding Provider" if kind == "embedding" else "Legacy Chat Provider"
```

- [ ] **Step 4: Add startup backfill function**

Modify `backend/app/db/init_db.py` imports:

```python
from ..models import LLMConfig, Prompt, SystemConfig, User, UserAIModel, UserAIStageRoute, UserModelProvider
```

Add helper after `_ensure_schema_updates`:

```python
async def _ensure_legacy_llm_model_routes(session: AsyncSession) -> None:
    result = await session.execute(select(LLMConfig))
    configs = result.scalars().all()
    for config in configs:
        existing_provider = await session.execute(
            select(UserModelProvider).where(UserModelProvider.user_id == config.user_id)
        )
        if existing_provider.scalars().first():
            continue

        chat_url = (config.llm_provider_url or "").strip().rstrip("/")
        chat_model = (config.llm_provider_model or "").strip()
        chat_key = (config.llm_provider_api_key or "").strip() or None
        if chat_url and chat_model:
            provider = UserModelProvider(
                user_id=config.user_id,
                name="Legacy Chat Provider",
                provider_type="openai_compatible",
                base_url=chat_url,
                api_key_encrypted=chat_key,
                api_key_preview=f"******{chat_key[-4:]}" if chat_key else None,
                is_enabled=True,
            )
            session.add(provider)
            await session.flush()
            model = UserAIModel(
                user_id=config.user_id,
                provider_id=provider.id,
                display_name=chat_model,
                model_name=chat_model,
                capabilities_json={"chat": True, "embedding": False},
                is_default_chat=True,
                is_enabled=True,
            )
            session.add(model)
            await session.flush()
            for stage in (
                "import_analysis",
                "concept_conversation",
                "world_blueprint",
                "chapter_outline",
                "chapter_blueprint",
                "chapter_mission",
                "chapter_preview",
                "chapter_writing",
                "chapter_rewrite",
                "chapter_compression",
                "chapter_enrichment",
                "version_review",
                "chapter_optimization",
                "deep_review",
                "emotion_analysis",
                "consistency_check",
                "summary_memory",
                "rag_query",
                "foreshadowing",
            ):
                session.add(UserAIStageRoute(user_id=config.user_id, stage=stage, model_id=model.id))

        embedding_model = (config.embedding_provider_model or "").strip()
        embedding_url = (config.embedding_provider_url or config.llm_provider_url or "").strip().rstrip("/")
        embedding_key = (config.embedding_provider_api_key or config.llm_provider_api_key or "").strip() or None
        if embedding_url and embedding_model:
            provider_type = "ollama" if (config.embedding_provider_format or "").strip().lower() == "ollama" else "openai_compatible"
            provider = UserModelProvider(
                user_id=config.user_id,
                name="Legacy Embedding Provider",
                provider_type=provider_type,
                base_url=embedding_url,
                api_key_encrypted=embedding_key,
                api_key_preview=f"******{embedding_key[-4:]}" if embedding_key else None,
                is_enabled=True,
            )
            session.add(provider)
            await session.flush()
            model = UserAIModel(
                user_id=config.user_id,
                provider_id=provider.id,
                display_name=embedding_model,
                model_name=embedding_model,
                capabilities_json={"chat": False, "embedding": True},
                is_default_embedding=True,
                is_enabled=True,
            )
            session.add(model)
            await session.flush()
            session.add(UserAIStageRoute(user_id=config.user_id, stage="rag_embedding", model_id=model.id))
```

- [ ] **Step 5: Call backfill during init**

In `init_db`, before `await _ensure_default_prompts(session)`, add:

```python
        await _ensure_legacy_llm_model_routes(session)
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_config_service.py tests/test_llm_service.py -q
```

Expected: all tests pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/db/init_db.py backend/app/services/llm_config_service.py backend/tests/test_llm_config_service.py
git commit -m "feat: backfill legacy llm config routes"
```

---

## Task 7: Add Frontend API Types and Client Methods

**Files:**
- Modify: `frontend/src/api/llm.ts`
- Create: `frontend/src/components/llm-settings/types.ts`

- [ ] **Step 1: Add TypeScript types**

Create `frontend/src/components/llm-settings/types.ts`:

```ts
export type ProviderType = 'openai_compatible' | 'ollama' | 'custom'
export type ModelCapability = 'chat' | 'embedding'

export type AIStageKey =
  | 'import_analysis'
  | 'concept_conversation'
  | 'world_blueprint'
  | 'chapter_outline'
  | 'chapter_blueprint'
  | 'chapter_mission'
  | 'chapter_preview'
  | 'chapter_writing'
  | 'chapter_rewrite'
  | 'chapter_compression'
  | 'chapter_enrichment'
  | 'version_review'
  | 'chapter_optimization'
  | 'deep_review'
  | 'emotion_analysis'
  | 'consistency_check'
  | 'summary_memory'
  | 'rag_query'
  | 'rag_embedding'
  | 'foreshadowing'

export interface ProviderProfile {
  id: number
  user_id: number
  name: string
  provider_type: ProviderType
  base_url: string
  api_key_preview: string | null
  is_enabled: boolean
}

export interface ProviderPayload {
  name: string
  provider_type: ProviderType
  base_url: string
  api_key?: string | null
  is_enabled: boolean
}

export interface UserAIModel {
  id: number
  user_id: number
  provider_id: number
  display_name: string
  model_name: string
  capabilities: Record<ModelCapability, boolean>
  context_window: number | null
  is_default_chat: boolean
  is_default_embedding: boolean
  is_enabled: boolean
  sort_order: number
}

export interface UserAIModelPayload {
  provider_id: number
  display_name: string
  model_name: string
  capabilities: Record<ModelCapability, boolean>
  context_window?: number | null
  is_default_chat: boolean
  is_default_embedding: boolean
  is_enabled: boolean
  sort_order: number
}

export interface StageRoute {
  stage: AIStageKey
  model_id: number
}

export interface LLMConfigBundle {
  legacy: unknown | null
  providers: ProviderProfile[]
  models: UserAIModel[]
  stage_routes: StageRoute[]
}

export const STAGE_GROUPS: Array<{ title: string; stages: Array<{ key: AIStageKey; label: string; capability: ModelCapability }> }> = [
  {
    title: '导入与构思',
    stages: [
      { key: 'import_analysis', label: '导入小说分析', capability: 'chat' },
      { key: 'concept_conversation', label: '概念对话', capability: 'chat' },
      { key: 'world_blueprint', label: '世界蓝图生成', capability: 'chat' },
    ],
  },
  {
    title: '规划',
    stages: [
      { key: 'chapter_outline', label: '章节大纲生成', capability: 'chat' },
      { key: 'chapter_blueprint', label: '章节蓝图', capability: 'chat' },
      { key: 'chapter_mission', label: '章节导演脚本', capability: 'chat' },
    ],
  },
  {
    title: '写作',
    stages: [
      { key: 'chapter_preview', label: '章节预览', capability: 'chat' },
      { key: 'chapter_writing', label: '章节正文生成', capability: 'chat' },
      { key: 'chapter_rewrite', label: '护栏修复', capability: 'chat' },
      { key: 'chapter_compression', label: '字数压缩', capability: 'chat' },
      { key: 'chapter_enrichment', label: '扩写润色', capability: 'chat' },
    ],
  },
  {
    title: '评审与优化',
    stages: [
      { key: 'version_review', label: '版本评审', capability: 'chat' },
      { key: 'chapter_optimization', label: '章节优化', capability: 'chat' },
      { key: 'deep_review', label: '深度审查', capability: 'chat' },
      { key: 'emotion_analysis', label: '情感分析', capability: 'chat' },
      { key: 'consistency_check', label: '一致性检查', capability: 'chat' },
    ],
  },
  {
    title: '记忆与 RAG',
    stages: [
      { key: 'summary_memory', label: '摘要与记忆更新', capability: 'chat' },
      { key: 'rag_query', label: 'RAG 检索规划', capability: 'chat' },
      { key: 'rag_embedding', label: 'RAG 向量模型', capability: 'embedding' },
      { key: 'foreshadowing', label: '伏笔辅助', capability: 'chat' },
    ],
  },
]
```

- [ ] **Step 2: Extend API client**

Modify `frontend/src/api/llm.ts` imports:

```ts
import type {
  LLMConfigBundle,
  ProviderPayload,
  ProviderProfile,
  StageRoute,
  UserAIModel,
  UserAIModelPayload,
} from '@/components/llm-settings/types'
```

Add helpers:

```ts
const parseError = async (response: Response, fallback: string): Promise<never> => {
  try {
    const payload = await response.json()
    throw new Error(payload.detail || fallback)
  } catch (error) {
    if (error instanceof Error && error.message !== fallback) {
      throw error
    }
    throw new Error(fallback)
  }
}

export const getLLMConfigBundle = async (): Promise<LLMConfigBundle> => {
  const response = await fetch(LLM_BASE, { method: 'GET', headers: getHeaders() })
  if (!response.ok) {
    await parseError(response, 'Failed to fetch LLM config bundle')
  }
  return response.json()
}

export const listProviders = async (): Promise<ProviderProfile[]> => {
  const response = await fetch(`${LLM_BASE}/providers`, { method: 'GET', headers: getHeaders() })
  if (!response.ok) {
    await parseError(response, 'Failed to fetch providers')
  }
  return response.json()
}

export const createProvider = async (payload: ProviderPayload): Promise<ProviderProfile> => {
  const response = await fetch(`${LLM_BASE}/providers`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    await parseError(response, 'Failed to create provider')
  }
  return response.json()
}

export const listUserModels = async (): Promise<UserAIModel[]> => {
  const response = await fetch(`${LLM_BASE}/user-models`, { method: 'GET', headers: getHeaders() })
  if (!response.ok) {
    await parseError(response, 'Failed to fetch user models')
  }
  return response.json()
}

export const createUserModel = async (payload: UserAIModelPayload): Promise<UserAIModel> => {
  const response = await fetch(`${LLM_BASE}/user-models`, {
    method: 'POST',
    headers: getHeaders(),
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    await parseError(response, 'Failed to create user model')
  }
  return response.json()
}

export const updateStageRoutes = async (routes: StageRoute[]): Promise<StageRoute[]> => {
  const response = await fetch(`${LLM_BASE}/stage-routes`, {
    method: 'PUT',
    headers: getHeaders(),
    body: JSON.stringify({ routes }),
  })
  if (!response.ok) {
    await parseError(response, 'Failed to save stage routes')
  }
  return response.json()
}
```

- [ ] **Step 3: Run type check**

Run:

```bash
cd frontend
npm run type-check
```

Expected: type check passes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/llm.ts frontend/src/components/llm-settings/types.ts
git commit -m "feat: add model config frontend api"
```

---

## Task 8: Build the New LLM Settings UI

**Files:**
- Create: `frontend/src/components/llm-settings/ProviderProfiles.vue`
- Create: `frontend/src/components/llm-settings/ModelPool.vue`
- Create: `frontend/src/components/llm-settings/StageRoutes.vue`
- Create: `frontend/src/components/llm-settings/DiagnosticsPanel.vue`
- Modify: `frontend/src/components/LLMSettings.vue`

- [ ] **Step 1: Create provider panel**

Create `frontend/src/components/llm-settings/ProviderProfiles.vue`:

```vue
<template>
  <section class="llm-settings__section md-card md-card-outlined">
    <h3 class="md-title-medium llm-settings__section-title">供应商档案</h3>
    <form class="llm-settings__grid" @submit.prevent="submit">
      <label class="md-text-field">
        <span class="md-text-field-label">名称</span>
        <input v-model="form.name" class="md-text-field-input" placeholder="DeepSeek / OpenAI / Ollama">
      </label>
      <label class="md-text-field">
        <span class="md-text-field-label">类型</span>
        <select v-model="form.provider_type" class="md-text-field-input">
          <option value="openai_compatible">OpenAI 兼容</option>
          <option value="ollama">Ollama</option>
          <option value="custom">自定义</option>
        </select>
      </label>
      <label class="md-text-field">
        <span class="md-text-field-label">API URL</span>
        <input v-model="form.base_url" class="md-text-field-input" placeholder="https://api.example.com/v1">
      </label>
      <label class="md-text-field">
        <span class="md-text-field-label">API Key</span>
        <input v-model="form.api_key" class="md-text-field-input" type="password" placeholder="保存后只显示尾号">
      </label>
      <button class="md-btn md-btn-tonal md-ripple" type="submit">新增供应商</button>
    </form>

    <div class="llm-list">
      <div v-for="provider in providers" :key="provider.id" class="llm-list-item">
        <strong>{{ provider.name }}</strong>
        <span>{{ provider.provider_type }}</span>
        <code>{{ provider.base_url }}</code>
        <span>{{ provider.api_key_preview || '无 Key' }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { ProviderPayload, ProviderProfile, ProviderType } from './types'

defineProps<{ providers: ProviderProfile[] }>()
const emit = defineEmits<{ (e: 'create', payload: ProviderPayload): void }>()

const form = reactive<ProviderPayload>({
  name: '',
  provider_type: 'openai_compatible' as ProviderType,
  base_url: '',
  api_key: '',
  is_enabled: true,
})

const submit = () => {
  if (!form.name.trim() || !form.base_url.trim()) {
    return
  }
  emit('create', { ...form, name: form.name.trim(), base_url: form.base_url.trim() })
  form.name = ''
  form.base_url = ''
  form.api_key = ''
}
</script>
```

- [ ] **Step 2: Create model pool panel**

Create `frontend/src/components/llm-settings/ModelPool.vue`:

```vue
<template>
  <section class="llm-settings__section md-card md-card-outlined">
    <h3 class="md-title-medium llm-settings__section-title">可用模型池</h3>
    <form class="llm-settings__grid" @submit.prevent="submit">
      <label class="md-text-field">
        <span class="md-text-field-label">供应商</span>
        <select v-model.number="form.provider_id" class="md-text-field-input">
          <option :value="0">请选择供应商</option>
          <option v-for="provider in providers" :key="provider.id" :value="provider.id">
            {{ provider.name }}
          </option>
        </select>
      </label>
      <label class="md-text-field">
        <span class="md-text-field-label">显示名称</span>
        <input v-model="form.display_name" class="md-text-field-input" placeholder="写作主模型">
      </label>
      <label class="md-text-field">
        <span class="md-text-field-label">模型名</span>
        <input v-model="form.model_name" class="md-text-field-input" placeholder="gpt-4o / deepseek-chat">
      </label>
      <div class="llm-checkbox-row">
        <label><input v-model="form.capabilities.chat" type="checkbox"> 文本</label>
        <label><input v-model="form.capabilities.embedding" type="checkbox"> 向量</label>
        <label><input v-model="form.is_default_chat" type="checkbox"> 默认文本</label>
        <label><input v-model="form.is_default_embedding" type="checkbox"> 默认向量</label>
      </div>
      <button class="md-btn md-btn-tonal md-ripple" type="submit">新增模型</button>
    </form>

    <div class="llm-list">
      <div v-for="model in models" :key="model.id" class="llm-list-item">
        <strong>{{ model.display_name }}</strong>
        <code>{{ model.model_name }}</code>
        <span>{{ providerName(model.provider_id) }}</span>
        <span>{{ capabilityText(model) }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { reactive } from 'vue'
import type { ProviderProfile, UserAIModel, UserAIModelPayload } from './types'

const props = defineProps<{ providers: ProviderProfile[]; models: UserAIModel[] }>()
const emit = defineEmits<{ (e: 'create', payload: UserAIModelPayload): void }>()

const form = reactive<UserAIModelPayload>({
  provider_id: 0,
  display_name: '',
  model_name: '',
  capabilities: { chat: true, embedding: false },
  context_window: null,
  is_default_chat: false,
  is_default_embedding: false,
  is_enabled: true,
  sort_order: 0,
})

const providerName = (providerId: number) =>
  props.providers.find((provider) => provider.id === providerId)?.name || '未知供应商'

const capabilityText = (model: UserAIModel) =>
  [
    model.capabilities.chat ? '文本' : '',
    model.capabilities.embedding ? '向量' : '',
    model.is_default_chat ? '默认文本' : '',
    model.is_default_embedding ? '默认向量' : '',
  ].filter(Boolean).join(' / ')

const submit = () => {
  if (!form.provider_id || !form.display_name.trim() || !form.model_name.trim()) {
    return
  }
  emit('create', {
    ...form,
    display_name: form.display_name.trim(),
    model_name: form.model_name.trim(),
  })
  form.display_name = ''
  form.model_name = ''
}
</script>
```

- [ ] **Step 3: Create stage route panel**

Create `frontend/src/components/llm-settings/StageRoutes.vue`:

```vue
<template>
  <section class="llm-settings__section md-card md-card-outlined">
    <h3 class="md-title-medium llm-settings__section-title">阶段默认模型</h3>
    <div v-for="group in STAGE_GROUPS" :key="group.title" class="llm-stage-group">
      <h4 class="md-title-small">{{ group.title }}</h4>
      <label v-for="stage in group.stages" :key="stage.key" class="md-text-field">
        <span class="md-text-field-label">{{ stage.label }}</span>
        <select
          class="md-text-field-input"
          :value="routeValue(stage.key)"
          @change="update(stage.key, Number(($event.target as HTMLSelectElement).value))"
        >
          <option :value="0">使用默认{{ stage.capability === 'embedding' ? '向量' : '文本' }}模型</option>
          <option v-for="model in modelsByCapability(stage.capability)" :key="model.id" :value="model.id">
            {{ model.display_name }} · {{ model.model_name }}
          </option>
        </select>
      </label>
    </div>
    <button class="md-btn md-btn-filled md-ripple" type="button" @click="save">保存阶段路由</button>
  </section>
</template>

<script setup lang="ts">
import { reactive, watch } from 'vue'
import type { AIStageKey, ModelCapability, StageRoute, UserAIModel } from './types'
import { STAGE_GROUPS } from './types'

const props = defineProps<{ models: UserAIModel[]; routes: StageRoute[] }>()
const emit = defineEmits<{ (e: 'save', routes: StageRoute[]): void }>()

const localRoutes = reactive<Record<string, number>>({})

watch(
  () => props.routes,
  (routes) => {
    Object.keys(localRoutes).forEach((key) => delete localRoutes[key])
    routes.forEach((route) => {
      localRoutes[route.stage] = route.model_id
    })
  },
  { immediate: true },
)

const modelsByCapability = (capability: ModelCapability) =>
  props.models.filter((model) => model.is_enabled && model.capabilities[capability])

const routeValue = (stage: AIStageKey) => localRoutes[stage] || 0

const update = (stage: AIStageKey, modelId: number) => {
  if (modelId > 0) {
    localRoutes[stage] = modelId
  } else {
    delete localRoutes[stage]
  }
}

const save = () => {
  emit('save', Object.entries(localRoutes).map(([stage, model_id]) => ({ stage: stage as AIStageKey, model_id })))
}
</script>
```

- [ ] **Step 4: Create diagnostics panel**

Create `frontend/src/components/llm-settings/DiagnosticsPanel.vue`:

```vue
<template>
  <section class="llm-settings__section md-card md-card-outlined">
    <h3 class="md-title-medium llm-settings__section-title">配置检查</h3>
    <div class="llm-list">
      <div class="llm-list-item">
        <strong>文本默认模型</strong>
        <span>{{ defaultChat ? defaultChat.display_name : '未设置' }}</span>
      </div>
      <div class="llm-list-item">
        <strong>向量默认模型</strong>
        <span>{{ defaultEmbedding ? defaultEmbedding.display_name : '未设置' }}</span>
      </div>
      <div class="llm-list-item">
        <strong>供应商数量</strong>
        <span>{{ providers.length }}</span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ProviderProfile, UserAIModel } from './types'

const props = defineProps<{ providers: ProviderProfile[]; models: UserAIModel[] }>()

const defaultChat = computed(() => props.models.find((model) => model.is_default_chat))
const defaultEmbedding = computed(() => props.models.find((model) => model.is_default_embedding))
</script>
```

- [ ] **Step 5: Replace `LLMSettings.vue` orchestration**

Keep existing CSS classes and replace the script/template core with:

```vue
<template>
  <section class="md-card md-card-elevated llm-settings">
    <header class="llm-settings__header">
      <h2 class="md-headline-small llm-settings__title">模型配置</h2>
      <p class="md-body-medium llm-settings__subtitle">
        配置个人供应商、可用模型，并为不同 AI 阶段选择默认模型。
      </p>
    </header>

    <div v-if="feedback.message" :class="['llm-feedback', `is-${feedback.type}`]">
      {{ feedback.message }}
    </div>

    <ProviderProfiles :providers="providers" @create="handleCreateProvider" />
    <ModelPool :providers="providers" :models="models" @create="handleCreateModel" />
    <StageRoutes :models="models" :routes="stageRoutes" @save="handleSaveRoutes" />
    <DiagnosticsPanel :providers="providers" :models="models" />
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  createProvider,
  createUserModel,
  getLLMConfigBundle,
  updateStageRoutes,
} from '@/api/llm'
import DiagnosticsPanel from './llm-settings/DiagnosticsPanel.vue'
import ModelPool from './llm-settings/ModelPool.vue'
import ProviderProfiles from './llm-settings/ProviderProfiles.vue'
import StageRoutes from './llm-settings/StageRoutes.vue'
import type { ProviderPayload, ProviderProfile, StageRoute, UserAIModel, UserAIModelPayload } from './llm-settings/types'

const emit = defineEmits<{ (e: 'saved'): void }>()

const providers = ref<ProviderProfile[]>([])
const models = ref<UserAIModel[]>([])
const stageRoutes = ref<StageRoute[]>([])
const feedback = ref<{ type: 'success' | 'error'; message: string }>({ type: 'success', message: '' })

const showFeedback = (message: string, type: 'success' | 'error' = 'success') => {
  feedback.value = { message, type }
}

const load = async () => {
  const bundle = await getLLMConfigBundle()
  providers.value = bundle.providers
  models.value = bundle.models
  stageRoutes.value = bundle.stage_routes
}

const handleCreateProvider = async (payload: ProviderPayload) => {
  try {
    providers.value.push(await createProvider(payload))
    showFeedback('供应商已保存')
  } catch (error) {
    showFeedback(error instanceof Error ? error.message : '供应商保存失败', 'error')
  }
}

const handleCreateModel = async (payload: UserAIModelPayload) => {
  try {
    const model = await createUserModel(payload)
    models.value.push(model)
    showFeedback('模型已保存')
  } catch (error) {
    showFeedback(error instanceof Error ? error.message : '模型保存失败', 'error')
  }
}

const handleSaveRoutes = async (routes: StageRoute[]) => {
  try {
    stageRoutes.value = await updateStageRoutes(routes)
    showFeedback('阶段路由已保存')
    emit('saved')
  } catch (error) {
    showFeedback(error instanceof Error ? error.message : '阶段路由保存失败', 'error')
  }
}

onMounted(() => {
  void load()
})
</script>
```

- [ ] **Step 6: Add compact list CSS**

In `LLMSettings.vue` style block, add:

```css
.llm-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 16px;
}

.llm-list-item {
  display: grid;
  grid-template-columns: minmax(140px, 1.2fr) minmax(120px, 1fr) minmax(180px, 2fr) minmax(80px, auto);
  gap: 12px;
  align-items: center;
  padding: 12px;
  border: 1px solid var(--md-outline-variant);
  border-radius: var(--md-radius-md);
  background: var(--md-surface);
}

.llm-stage-group {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}

@media (max-width: 760px) {
  .llm-list-item {
    grid-template-columns: 1fr;
  }
}
```

- [ ] **Step 7: Run frontend checks**

Run:

```bash
cd frontend
npm run type-check
npm run build
```

Expected: type check and production build pass.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/LLMSettings.vue frontend/src/components/llm-settings
git commit -m "feat: redesign personal model settings"
```

---

## Task 9: Full Verification

**Files:**
- No source changes expected.

- [ ] **Step 1: Run backend focused tests**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_llm_service.py tests/test_llm_config_service.py tests/test_llm_config_routes_static.py tests/test_ai_stage_routing_static.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run existing backend tests most likely to catch regressions**

Run:

```bash
cd backend
PYTHONPATH=. pytest tests/test_inspiration_mode_startup.py tests/test_concept_streaming.py tests/test_chapter_word_count_settings.py tests/test_review_context_builder.py -q
```

Expected: all selected tests pass. If `test_concept_streaming.py` is still untracked in the current workspace, keep it uncommitted unless it belongs to this feature branch.

- [ ] **Step 3: Run frontend checks**

Run:

```bash
cd frontend
npm run type-check
npm run build
```

Expected: both commands pass.

- [ ] **Step 4: Manual smoke test**

Start dev services with the project helper:

```bash
python3 dev_servers.py
```

Expected: backend and frontend ports are printed by the helper.

In browser:

1. Open the frontend URL.
2. Log in.
3. Open `设置`.
4. Add a provider with an OpenAI-compatible URL.
5. Add one chat model and mark it default chat.
6. Add one embedding model and mark it default embedding.
7. Route `章节正文生成` to the chat model.
8. Route `RAG 向量模型` to the embedding model.
9. Save stage routes.

Expected:

- API key is shown only as masked preview after save.
- Stage route save shows `阶段路由已保存`.
- No console error appears on the settings page.

- [ ] **Step 5: Stop dev services**

Stop the running dev process with Ctrl-C in its terminal. If a spawned command
session is still open in the agent environment, close it before final handoff.

- [ ] **Step 6: Commit verification-only fixes if any**

If verification required source fixes, commit only those fixed files:

```bash
git status --short
git add <fixed-files>
git commit -m "fix: stabilize personal model routing"
```

If verification required no fixes, do not create an empty commit.

---

## Self-Review Checklist

- Spec coverage:
  - Multiple provider profiles: Task 1, Task 2, Task 3, Task 8.
  - Multiple API keys: Task 1, Task 2, Task 8.
  - Available model pool: Task 1, Task 2, Task 3, Task 8.
  - Stage defaults: Task 2, Task 3, Task 4, Task 5, Task 8.
  - Embedding route: Task 4, Task 5, Task 8.
  - Legacy migration: Task 6.
  - High-frequency override is not included in this implementation slice; the spec marked it as a follow-on capability after stage routing works.

- Placeholder scan:
  - No unfinished markers or unnamed file paths are present.

- Type consistency:
  - Backend uses `UserModelProvider`, `UserAIModel`, `UserAIStageRoute`.
  - Frontend uses `ProviderProfile`, `UserAIModel`, `StageRoute`.
  - Stage strings match between backend constants and frontend `AIStageKey`.
