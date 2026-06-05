# Chapter Draft Finalization Flow Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make chapter generation produce editable drafts first, then synchronously run summary, memory, vector, and foreshadowing finalization only after the user confirms.

**Architecture:** Keep the existing `Chapter` and `ChapterVersion` tables. Reinterpret `waiting_for_confirm` as the draft review state, add `finalizing` for synchronous post-processing, and move finalization side effects behind a new confirm-finalize endpoint. Reuse `ChapterGenerationTraceService` so the existing node inspector can show inputs, actions, outputs, and failures.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Pydantic, Vue 3, TanStack Query, Vitest, Pytest.

---

## File Structure

- Modify `backend/app/schemas/novel.py`: add `FINALIZING`, confirm-finalize request/response schemas, and foreshadowing sync stats schema.
- Modify `backend/app/services/novel_service.py`: make `replace_chapter_versions()` save drafts by default and keep selected-version assignment only for explicit finalization.
- Modify `backend/app/services/pipeline_orchestrator.py`: stop auto-finalizing generation output; rename persist trace semantics to draft saving.
- Modify `backend/app/api/routers/writer.py`: add synchronous confirm-finalize endpoint and helper, remove old background finalization behavior from active user paths, and record post-processing trace nodes.
- Modify `frontend/src/api/novel.ts`: add `finalizing` status, confirm-finalize API types and method.
- Modify `frontend/src/queries/novel.ts`: replace selection mutation with confirm-finalize mutation.
- Modify `frontend/src/views/WritingDesk.vue`: route confirm button to synchronous finalization, set local `finalizing`, wait for response, and refresh current chapter.
- Modify `frontend/src/components/writing-desk/WDWorkspace.vue`: treat `finalizing` as node-console state and keep draft confirmation for `waiting_for_confirm`.
- Modify `frontend/src/components/writing-desk/workspace/VersionSelector.vue`: change copy to draft confirmation and add manual draft edit before confirm.
- Modify `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`: add finalization step labels and trace call-type labels.
- Add or modify backend tests under `backend/tests/`.
- Add or modify frontend tests under `frontend/src/components/__tests__/`.

---

### Task 1: Backend Contract Tests And Schemas

**Files:**
- Modify: `backend/app/schemas/novel.py`
- Add: `backend/tests/test_chapter_draft_finalize_contract_static.py`

- [ ] **Step 1: Write failing schema contract tests**

Create `backend/tests/test_chapter_draft_finalize_contract_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS_SOURCE = ROOT / "app/schemas/novel.py"


def _source() -> str:
    return SCHEMAS_SOURCE.read_text(encoding="utf-8")


def test_chapter_generation_status_includes_finalizing() -> None:
    source = _source()

    assert 'FINALIZING = "finalizing"' in source


def test_confirm_finalize_contracts_exist() -> None:
    source = _source()

    assert "class ConfirmFinalizeChapterRequest(BaseModel):" in source
    assert "selected_version_index: int" in source
    assert "edited_content: Optional[str] = None" in source
    assert "skip_vector_update: bool = False" in source
    assert "class ForeshadowingSyncStats(BaseModel):" in source
    assert "created: int = 0" in source
    assert "developing: int = 0" in source
    assert "revealed: int = 0" in source
    assert "class ConfirmFinalizeChapterResponse(BaseModel):" in source
    assert "chapter: Chapter" in source
    assert "finalize: ConfirmFinalizeStats" in source
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
timeout 60s pytest backend/tests/test_chapter_draft_finalize_contract_static.py -q
```

Expected: fails because `FINALIZING` and confirm-finalize schemas do not exist.

- [ ] **Step 3: Add backend schemas**

In `backend/app/schemas/novel.py`, update the enum and add schemas after `Chapter`:

```python
class ChapterGenerationStatus(str, Enum):
    NOT_GENERATED = "not_generated"
    GENERATING = "generating"
    EVALUATING = "evaluating"
    SELECTING = "selecting"
    FAILED = "failed"
    EVALUATION_FAILED = "evaluation_failed"
    WAITING_FOR_CONFIRM = "waiting_for_confirm"
    FINALIZING = "finalizing"
    SUCCESSFUL = "successful"
```

```python
class ConfirmFinalizeChapterRequest(BaseModel):
    selected_version_index: int = Field(..., ge=0)
    edited_content: Optional[str] = None
    skip_vector_update: bool = False


class ForeshadowingSyncStats(BaseModel):
    created: int = 0
    developing: int = 0
    revealed: int = 0


class ConfirmFinalizeStats(BaseModel):
    summary_generated: bool = False
    memory_updated: bool = False
    vector_ingested: bool = False
    foreshadowing_sync: ForeshadowingSyncStats = Field(default_factory=ForeshadowingSyncStats)


class ConfirmFinalizeChapterResponse(BaseModel):
    chapter: Chapter
    finalize: ConfirmFinalizeStats
```

- [ ] **Step 4: Verify schema tests pass**

Run:

```bash
timeout 60s pytest backend/tests/test_chapter_draft_finalize_contract_static.py -q
```

Expected: pass.

---

### Task 2: Generation Saves Drafts Instead Of Completed Chapters

**Files:**
- Modify: `backend/app/services/pipeline_orchestrator.py`
- Modify: `backend/app/services/novel_service.py`
- Modify: `backend/tests/test_pipeline_langgraph_refactor_static.py`

- [ ] **Step 1: Write failing static tests for draft semantics**

Append to `backend/tests/test_pipeline_langgraph_refactor_static.py`:

```python
def test_pipeline_persists_generated_versions_as_draft_not_successful() -> None:
    source = _source()
    block = source.split("async def _graph_persist_versions", 1)[1].split(
        "async def _graph_build_response",
        1,
    )[0]

    assert 'node_key="save_draft"' in block
    assert 'node_label="保存草稿"' in block
    assert 'finalize_version_index=state["best_version_index"]' not in block
    assert '"将章节状态标记为已完成"' not in block
    assert '"保存草稿节点不调用模型"' in block
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
timeout 60s pytest backend/tests/test_pipeline_langgraph_refactor_static.py::test_pipeline_persists_generated_versions_as_draft_not_successful -q
```

Expected: fails because `_graph_persist_versions()` still records `persist_versions` as final output and passes `finalize_version_index`.

- [ ] **Step 3: Update pipeline draft save**

In `backend/app/services/pipeline_orchestrator.py`, change `_graph_persist_versions()`:

```python
versions_models = await self.novel_service.replace_chapter_versions(
    chapter,
    contents,
    metadata,
    evaluation_feedback=evaluation_feedback,
)
```

Change the trace call:

```python
await self.trace_service.record_success(
    project_id=state["project_id"],
    chapter_number=state["chapter_number"],
    node_key="save_draft",
    node_label="保存草稿",
    stage="save_draft",
    input_payload={
        "version_count": len(contents),
        "content_lengths": [len(content or "") for content in contents],
        "recommended_version_index": state["best_version_index"],
    },
    output_payload={
        "versions": [
            {"index": item["index"], "version_id": item["version_id"]}
            for item in variants
        ],
        "status": ChapterGenerationStatus.WAITING_FOR_CONFIRM.value,
    },
    metadata={
        "trace_kind": "workflow",
        "call_type": "database_write",
        "summary": "将候选草稿写入版本表，等待人工确认定稿。",
        "actions": [
            "更新章节生成状态为保存草稿",
            "替换本轮章节候选版本列表",
            "保留 AI 推荐版本索引供前端默认选中",
            "将章节状态标记为待确认定稿",
        ],
        "data_writes": ["chapters", "chapter_versions"],
        "model_calls": [],
        "skip_reason": "保存草稿节点不调用模型",
        "metrics": {
            "version_count": len(contents),
            "content_lengths": [len(content or "") for content in contents],
            "recommended_version_index": state["best_version_index"],
        },
    },
    started_at=started_at,
    ended_at=datetime.now(CN_TIMEZONE),
)
```

Ensure `ChapterGenerationStatus` is imported in this module if not already available.

- [ ] **Step 4: Keep `replace_chapter_versions()` draft-first**

In `backend/app/services/novel_service.py`, keep the `finalize_version_index` branch only for direct helper use, but generation must no longer pass it. Ensure the `else` branch remains:

```python
chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
chapter.generation_step = f"waiting_for_confirm|v={len(versions)}"
chapter.generation_progress = 100
chapter.generation_step_index = 7
chapter.generation_step_total = 7
```

Do not set `chapter.selected_version_id` in this branch.

- [ ] **Step 5: Verify draft semantics test passes**

Run:

```bash
timeout 60s pytest backend/tests/test_pipeline_langgraph_refactor_static.py::test_pipeline_persists_generated_versions_as_draft_not_successful -q
```

Expected: pass.

---

### Task 3: Synchronous Confirm-Finalize Backend Endpoint

**Files:**
- Modify: `backend/app/api/routers/writer.py`
- Modify: `backend/app/schemas/novel.py`
- Add: `backend/tests/test_confirm_finalize_router_static.py`

- [ ] **Step 1: Write failing router structure tests**

Create `backend/tests/test_confirm_finalize_router_static.py`:

```python
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WRITER_SOURCE = ROOT / "app/api/routers/writer.py"


def _source() -> str:
    return WRITER_SOURCE.read_text(encoding="utf-8")


def test_confirm_finalize_endpoint_runs_synchronous_pipeline() -> None:
    source = _source()

    assert '@router.post("/novels/{project_id}/chapters/{chapter_number}/confirm-finalize"' in source
    assert "response_model=ConfirmFinalizeChapterResponse" in source
    assert "ChapterGenerationStatus.FINALIZING.value" in source
    assert 'node_key="confirm_finalize"' in source
    assert 'node_key="real_summary"' in source
    assert 'node_key="finalize_memory"' in source
    assert 'node_key="chapter_ingest"' in source
    assert 'node_key="foreshadowing_sync"' in source
    assert 'node_key="finalized"' in source
    assert 'node_key="finalization_error"' in source


def test_confirm_finalize_does_not_schedule_background_tasks() -> None:
    block = _source().split("async def confirm_finalize_chapter", 1)[1].split(
        "\n\n@router.",
        1,
    )[0]

    assert "background_tasks.add_task" not in block
    assert "_schedule_finalize_task" not in block
```

- [ ] **Step 2: Run the failing router tests**

Run:

```bash
timeout 60s pytest backend/tests/test_confirm_finalize_router_static.py -q
```

Expected: fails because the endpoint and trace nodes do not exist.

- [ ] **Step 3: Import schemas and services in `writer.py`**

Update imports in `backend/app/api/routers/writer.py`:

```python
from ...schemas.novel import (
    Chapter as ChapterSchema,
    ChapterGenerationStatus,
    ConfirmFinalizeChapterRequest,
    ConfirmFinalizeChapterResponse,
    ConfirmFinalizeStats,
    ForeshadowingSyncStats,
)
```

If `ChapterSchema` and `ChapterGenerationStatus` are already imported, merge the new schema names into the existing import.

- [ ] **Step 4: Add small trace helpers**

Add near `_build_generation_failure_detail()` or before finalize helpers:

```python
async def _record_finalize_workflow_success(
    trace_service: ChapterGenerationTraceService,
    *,
    project_id: str,
    chapter_number: int,
    node_key: str,
    node_label: str,
    input_payload: dict,
    output_payload: dict,
    actions: list[str],
    data_reads: list[str] | None = None,
    data_writes: list[str] | None = None,
    started_at: Optional[datetime] = None,
) -> None:
    ended_at = datetime.now(CN_TIMEZONE)
    await trace_service.record_success(
        project_id=project_id,
        chapter_number=chapter_number,
        node_key=node_key,
        node_label=node_label,
        stage=node_key,
        input_payload=input_payload,
        output_payload=output_payload,
        metadata={
            "trace_kind": "workflow",
            "call_type": node_key,
            "summary": f"{node_label}执行完成。",
            "actions": actions,
            "data_reads": data_reads or [],
            "data_writes": data_writes or [],
            "model_calls": [],
        },
        uses_llm=False,
        started_at=started_at or ended_at,
        ended_at=ended_at,
    )
```

- [ ] **Step 5: Add confirm-finalize endpoint**

Add in `backend/app/api/routers/writer.py` before the old select route:

```python
@router.post(
    "/novels/{project_id}/chapters/{chapter_number}/confirm-finalize",
    response_model=ConfirmFinalizeChapterResponse,
)
async def confirm_finalize_chapter(
    project_id: str,
    chapter_number: int,
    request: ConfirmFinalizeChapterRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> ConfirmFinalizeChapterResponse:
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    return await _confirm_finalize_chapter_sync(
        session=session,
        novel_service=novel_service,
        project_id=project_id,
        chapter_number=chapter_number,
        request=request,
        user_id=current_user.id,
    )
```

- [ ] **Step 6: Add synchronous finalization helper**

Add `_confirm_finalize_chapter_sync()` in `writer.py`. Use this exact control flow:

```python
async def _confirm_finalize_chapter_sync(
    *,
    session: AsyncSession,
    novel_service: NovelService,
    project_id: str,
    chapter_number: int,
    request: ConfirmFinalizeChapterRequest,
    user_id: int,
) -> ConfirmFinalizeChapterResponse:
    trace_service = ChapterGenerationTraceService(session)
    stats = ConfirmFinalizeStats()
    stmt = (
        select(Chapter)
        .options(
            selectinload(Chapter.versions),
            selectinload(Chapter.evaluations),
            selectinload(Chapter.selected_version),
        )
        .where(Chapter.project_id == project_id, Chapter.chapter_number == chapter_number)
    )
    result = await session.execute(stmt)
    chapter = result.scalars().first()
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    versions = sorted(chapter.versions or [], key=lambda item: item.created_at)
    if request.selected_version_index < 0 or request.selected_version_index >= len(versions):
        raise HTTPException(status_code=400, detail="候选草稿索引无效")

    selected_version = versions[request.selected_version_index]
    final_content = (
        request.edited_content
        if request.edited_content is not None
        else selected_version.content
    )
    final_content = (final_content or "").strip()
    if not final_content:
        raise HTTPException(status_code=400, detail="最终正文为空，无法定稿")

    chapter.status = ChapterGenerationStatus.FINALIZING.value
    chapter.generation_progress = 90
    chapter.generation_step = "confirm_finalize"
    chapter.generation_step_index = 8
    chapter.generation_step_total = 12
    selected_version.content = final_content
    chapter.selected_version_id = selected_version.id
    chapter.selected_version = selected_version
    chapter.word_count = count_chapter_words(final_content)
    await session.commit()

    try:
        await _record_finalize_workflow_success(
            trace_service,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="confirm_finalize",
            node_label="确认定稿",
            input_payload={
                "selected_version_index": request.selected_version_index,
                "edited": request.edited_content is not None,
            },
            output_payload={
                "selected_version_id": selected_version.id,
                "word_count": chapter.word_count,
            },
            actions=["校验候选草稿", "保存最终正文", "绑定选中版本"],
            data_reads=["chapters", "chapter_versions"],
            data_writes=["chapters", "chapter_versions"],
        )

        llm_service = LLMService(session)
        prompt_service = PromptService(session)
        summary_prompt = await prompt_service.get_prompt("extraction")
        if not summary_prompt:
            raise HTTPException(status_code=500, detail="未配置摘要提示词，请联系管理员配置 'extraction' 提示词")
        summary_raw = await llm_service.get_summary(
            final_content,
            temperature=0.15,
            user_id=user_id,
            timeout=180.0,
            system_prompt=summary_prompt,
            stage="summary_memory",
        )
        summary_text = remove_think_tags(summary_raw).strip()
        if not summary_text:
            raise HTTPException(status_code=500, detail="章节梳理为空，无法定稿")
        chapter.real_summary = summary_text
        await session.commit()
        stats.summary_generated = True
        await trace_service.record_success(
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="real_summary",
            node_label="生成章节梳理",
            stage="summary_memory",
            system_prompt=summary_prompt,
            user_prompt=final_content,
            raw_response=summary_raw,
            cleaned_output=summary_text,
            input_payload={"content_chars": len(final_content)},
            output_payload={"summary_chars": len(summary_text)},
            metadata={
                "trace_kind": "llm",
                "call_type": "chat_llm",
                "summary": "生成最终正文的真实章节梳理并写回 Chapter.real_summary。",
                "actions": ["读取摘要提示词", "调用摘要模型", "清理 think 标签", "写回章节梳理"],
                "data_writes": ["chapters.real_summary"],
            },
        )

        vector_store = None
        if settings.vector_store_enabled and not request.skip_vector_update:
            vector_store = VectorStoreService()
        finalize_service = FinalizeService(getattr(session, "sync_session", session), llm_service, vector_store)
        finalize_result = await finalize_service.finalize_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            chapter_text=final_content,
            user_id=user_id,
            skip_vector_update=request.skip_vector_update,
        )
        stats.memory_updated = True
        await _record_finalize_workflow_success(
            trace_service,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="finalize_memory",
            node_label="更新记忆快照",
            input_payload={"content_chars": len(final_content), "skip_vector_update": request.skip_vector_update},
            output_payload=finalize_result,
            actions=["更新全局摘要", "更新角色状态", "更新剧情线", "创建章节快照"],
            data_reads=["project_memory", "characters"],
            data_writes=["project_memory", "chapter_snapshots", "chapter_blueprints"],
        )

        ingest_service = ChapterIngestionService(llm_service=llm_service)
        outline_result = await session.execute(
            select(ChapterOutline).where(
                ChapterOutline.project_id == project_id,
                ChapterOutline.chapter_number == chapter_number,
            )
        )
        outline = outline_result.scalars().first()
        chapter_title = outline.title if outline and outline.title else f"第{chapter_number}章"
        await ingest_service.ingest_chapter(
            project_id=project_id,
            chapter_number=chapter_number,
            title=chapter_title,
            content=final_content,
            summary=summary_text,
            user_id=user_id,
        )
        stats.vector_ingested = True
        await _record_finalize_workflow_success(
            trace_service,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="chapter_ingest",
            node_label="写入章节索引",
            input_payload={"title": chapter_title, "content_chars": len(final_content), "summary_chars": len(summary_text)},
            output_payload={"ingested": True},
            actions=["切分章节正文", "生成向量", "写入章节检索索引"],
            data_reads=["chapters", "chapter_outlines"],
            data_writes=["vector_store"],
        )

        sync_stats = await _sync_foreshadowings_for_chapter(
            session,
            project_id=project_id,
            chapter=chapter,
            content=final_content,
            user_id=user_id,
        )
        stats.foreshadowing_sync = ForeshadowingSyncStats(**{
            "created": int(sync_stats.get("created", 0)),
            "developing": int(sync_stats.get("developing", 0)),
            "revealed": int(sync_stats.get("revealed", 0)),
        })
        await _record_finalize_workflow_success(
            trace_service,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="foreshadowing_sync",
            node_label="同步伏笔",
            input_payload={"content_chars": len(final_content)},
            output_payload=stats.foreshadowing_sync.model_dump(),
            actions=["抽取本章新伏笔", "判断历史伏笔推进", "写入伏笔状态历史"],
            data_reads=["foreshadowings"],
            data_writes=["foreshadowings", "foreshadowing_status_history"],
        )

        chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
        chapter.generation_progress = 100
        chapter.generation_step = "finalized"
        chapter.generation_step_index = 12
        chapter.generation_step_total = 12
        await session.commit()
        await _record_finalize_workflow_success(
            trace_service,
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="finalized",
            node_label="定稿完成",
            input_payload={"selected_version_id": selected_version.id},
            output_payload={"status": ChapterGenerationStatus.SUCCESSFUL.value, "word_count": chapter.word_count},
            actions=["确认所有后处理节点完成", "标记章节为已完成"],
            data_writes=["chapters"],
        )
    except Exception as exc:
        await session.rollback()
        chapter.status = ChapterGenerationStatus.WAITING_FOR_CONFIRM.value
        chapter.generation_step = "finalization_failed"
        await session.commit()
        await trace_service.record_failure(
            project_id=project_id,
            chapter_number=chapter_number,
            node_key="finalization_error",
            node_label="定稿失败",
            stage="finalization_error",
            error=_build_generation_failure_detail(exc),
            input_payload={"selected_version_index": request.selected_version_index},
            metadata={
                "trace_kind": "workflow",
                "call_type": "finalization_error",
                "summary": "定稿后处理失败，章节保留草稿待确认状态。",
                "actions": ["回滚事务", "恢复草稿待确认状态", "记录失败原因"],
                "data_writes": ["chapters"],
            },
        )
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=_build_generation_failure_detail(exc)) from exc

    refreshed = await novel_service.get_chapter_schema(project_id, user_id, chapter_number)
    return ConfirmFinalizeChapterResponse(chapter=refreshed, finalize=stats)
```

- [ ] **Step 7: Convert old select endpoint away from legacy behavior**

Replace the body of `/novels/{project_id}/chapters/select` so it no longer performs background vector or foreshadowing work. It should delegate to `_confirm_finalize_chapter_sync()` and return the loaded project:

```python
result = await _confirm_finalize_chapter_sync(
    session=session,
    novel_service=novel_service,
    project_id=project_id,
    chapter_number=request.chapter_number,
    request=ConfirmFinalizeChapterRequest(selected_version_index=request.version_index),
    user_id=current_user.id,
)
return await _load_project_schema(novel_service, project_id, current_user.id)
```

Remove the old `_sync_foreshadowings_after_finalize` background task block from this endpoint.

- [ ] **Step 8: Verify router tests pass**

Run:

```bash
timeout 60s pytest backend/tests/test_confirm_finalize_router_static.py -q
```

Expected: pass.

---

### Task 4: Remove Active Old Background Finalization Paths

**Files:**
- Modify: `backend/app/api/routers/writer.py`
- Modify: `backend/tests/test_confirm_finalize_router_static.py`

- [ ] **Step 1: Write failing tests that active paths do not schedule finalization**

Append:

```python
def test_advanced_generate_no_longer_schedules_async_finalize() -> None:
    source = _source()
    block = source.split('@router.post("/advanced/generate"', 1)[1].split(
        '\n\n@router.post("/chapters/{chapter_number}/finalize"',
        1,
    )[0]

    assert "_schedule_finalize_task" not in block
    assert "flow_config.async_finalize" not in block


def test_select_endpoint_no_longer_background_syncs_foreshadowing() -> None:
    source = _source()
    block = source.split('@router.post("/novels/{project_id}/chapters/select"', 1)[1].split(
        "\n\n@router.post",
        1,
    )[0]

    assert "_sync_foreshadowings_after_finalize" not in block
    assert "background_tasks.add_task" not in block
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
timeout 60s pytest backend/tests/test_confirm_finalize_router_static.py::test_advanced_generate_no_longer_schedules_async_finalize backend/tests/test_confirm_finalize_router_static.py::test_select_endpoint_no_longer_background_syncs_foreshadowing -q
```

Expected: fails because advanced generate still schedules async finalization or select still backgrounds sync.

- [ ] **Step 3: Remove `async_finalize` scheduling**

In `advanced_generate_chapter()`, delete this block:

```python
flow_config = request.flow_config
if flow_config.async_finalize and result.get("variants"):
    best_index = result.get("best_version_index", 0)
    variants = result["variants"]
    if 0 <= best_index < len(variants):
        selected_version_id = variants[best_index]["version_id"]
        background_tasks.add_task(
            _schedule_finalize_task,
            request.project_id,
            request.chapter_number,
            selected_version_id,
            current_user.id,
            False,
        )
```

Keep:

```python
return AdvancedGenerateResponse(**result)
```

- [ ] **Step 4: Keep background helper only if still used by edit paths**

Do not delete `_sync_foreshadowings_after_finalize` if `edit` and `edit-fast` still use it. The goal is to remove old generation/selection finalization behavior, not manual edit sync.

- [ ] **Step 5: Verify tests pass**

Run:

```bash
timeout 60s pytest backend/tests/test_confirm_finalize_router_static.py -q
```

Expected: pass.

---

### Task 5: Frontend API And Mutation Contracts

**Files:**
- Modify: `frontend/src/api/novel.ts`
- Modify: `frontend/src/queries/novel.ts`
- Add: `frontend/src/components/__tests__/chapterDraftFinalizeStatic.spec.ts`

- [ ] **Step 1: Write failing frontend static tests**

Create `frontend/src/components/__tests__/chapterDraftFinalizeStatic.spec.ts`:

```ts
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const readSource = (relativePath: string) =>
  readFileSync(resolve(process.cwd(), relativePath), 'utf8')

describe('chapter draft finalization contracts', () => {
  it('adds finalizing status and confirm finalize API', () => {
    const api = readSource('src/api/novel.ts')

    expect(api).toContain("'finalizing'")
    expect(api).toContain('export interface ConfirmFinalizeChapterRequest')
    expect(api).toContain('selected_version_index: number')
    expect(api).toContain('edited_content?: string | null')
    expect(api).toContain('export interface ConfirmFinalizeChapterResponse')
    expect(api).toContain('static async confirmFinalizeChapter')
    expect(api).toContain('/confirm-finalize')
  })

  it('uses confirm finalize mutation instead of select mutation in writing desk', () => {
    const queries = readSource('src/queries/novel.ts')
    const desk = readSource('src/views/WritingDesk.vue')

    expect(queries).toContain('export function useConfirmFinalizeChapterMutation')
    expect(queries).toContain('NovelAPI.confirmFinalizeChapter')
    expect(desk).toContain('useConfirmFinalizeChapterMutation')
    expect(desk).toContain('confirmFinalizeChapterMutation')
  })
})
```

- [ ] **Step 2: Run failing frontend static tests**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: fails because API and mutation do not exist.

- [ ] **Step 3: Add API types and method**

In `frontend/src/api/novel.ts`, update `Chapter.generation_status`:

```ts
generation_status:
  | 'not_generated'
  | 'generating'
  | 'evaluating'
  | 'selecting'
  | 'failed'
  | 'evaluation_failed'
  | 'waiting_for_confirm'
  | 'finalizing'
  | 'successful'
```

Add interfaces near chapter/optimizer response types:

```ts
export interface ConfirmFinalizeChapterRequest {
  selected_version_index: number
  edited_content?: string | null
  skip_vector_update?: boolean
}

export interface ConfirmFinalizeChapterResponse {
  chapter: Chapter
  finalize: {
    summary_generated: boolean
    memory_updated: boolean
    vector_ingested: boolean
    foreshadowing_sync: ForeshadowingSyncStats
  }
}
```

Add method:

```ts
static async confirmFinalizeChapter(
  projectId: string,
  chapterNumber: number,
  payload: ConfirmFinalizeChapterRequest,
): Promise<ConfirmFinalizeChapterResponse> {
  return request(`${WRITER_BASE}/${projectId}/chapters/${chapterNumber}/confirm-finalize`, {
    method: 'POST',
    body: JSON.stringify(payload),
    timeoutMs: CHAPTER_GENERATION_TIMEOUT_MS,
  })
}
```

- [ ] **Step 4: Add mutation**

In `frontend/src/queries/novel.ts`:

```ts
export function useConfirmFinalizeChapterMutation(projectId: ProjectIdSource) {
  const { refreshChapter, refreshProjectQueries, upsertChapterInProjectCache } =
    useNovelMutationRefresh(projectId)

  return useMutation({
    mutationFn: (payload: {
      chapterNumber: number
      selectedVersionIndex: number
      editedContent?: string | null
      skipVectorUpdate?: boolean
    }) =>
      NovelAPI.confirmFinalizeChapter(requireProjectId(projectId), payload.chapterNumber, {
        selected_version_index: payload.selectedVersionIndex,
        edited_content: payload.editedContent ?? null,
        skip_vector_update: payload.skipVectorUpdate ?? false,
      }),
    onSuccess: async (response, payload) => {
      upsertChapterInProjectCache(undefined, response.chapter)
      await refreshChapter(undefined, payload.chapterNumber)
      await refreshProjectQueries(requireProjectId(projectId))
    },
  })
}
```

- [ ] **Step 5: Verify frontend contract tests pass**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: pass.

---

### Task 6: Frontend Draft Confirmation And Finalizing UI

**Files:**
- Modify: `frontend/src/views/WritingDesk.vue`
- Modify: `frontend/src/components/writing-desk/WDWorkspace.vue`
- Modify: `frontend/src/components/writing-desk/workspace/VersionSelector.vue`
- Modify: `frontend/src/components/__tests__/chapterDraftFinalizeStatic.spec.ts`

- [ ] **Step 1: Add failing UI behavior tests**

Append to `chapterDraftFinalizeStatic.spec.ts`:

```ts
  it('shows draft confirmation copy and manual edit support', () => {
    const versionSelector = readSource('src/components/writing-desk/workspace/VersionSelector.vue')

    expect(versionSelector).toContain('草稿确认')
    expect(versionSelector).toContain('确认定稿')
    expect(versionSelector).toContain('编辑草稿')
    expect(versionSelector).toContain('draftEditedContent')
    expect(versionSelector).toContain("emit('confirmVersionSelection'")
  })

  it('renders finalizing status in the node console', () => {
    const workspace = readSource('src/components/writing-desk/WDWorkspace.vue')

    expect(workspace).toContain("case 'finalizing':")
    expect(workspace).toContain("return '定稿中'")
    expect(workspace).toContain("status === 'finalizing'")
    expect(workspace).toContain('ChapterGenerating')
  })
```

- [ ] **Step 2: Run failing UI tests**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: fails because UI still uses selection/final version copy.

- [ ] **Step 3: Update `VersionSelector.vue` copy and edit state**

Add draft editing state:

```ts
const draftEditOpen = ref(false)
const draftEditedContent = ref('')

const selectedDraftContent = computed(() =>
  cleanVersionContent(props.availableVersions?.[props.selectedVersionIndex]?.content || ''),
)

const openDraftEdit = () => {
  draftEditedContent.value = selectedDraftContent.value
  draftEditOpen.value = true
}

const confirmDraft = () => {
  emit('confirmVersionSelection', {
    editedContent: draftEditOpen.value ? draftEditedContent.value : null,
  })
}
```

Update emits type:

```ts
const emit = defineEmits([
  'hideVersionSelector',
  'update:selectedVersionIndex',
  'showVersionDetail',
  'confirmVersionSelection',
  'evaluateChapter',
  'showEvaluationDetail',
  'regenerateChapter',
])
```

Change button copy:

```vue
<h4 class="md-title-medium font-semibold">
  {{ availableVersions.length > 1 ? '草稿确认' : '生成草稿' }}
</h4>
```

```vue
<button type="button" class="md-btn md-btn-outlined md-ripple" @click="openDraftEdit">
  编辑草稿
</button>
<button
  type="button"
  class="md-btn md-btn-filled md-ripple"
  :disabled="!availableVersions?.[selectedVersionIndex]?.content || isSelectingVersion"
  @click="confirmDraft"
>
  {{ isSelectingVersion ? '定稿中...' : '确认定稿' }}
</button>
```

Add a simple textarea below the selected version cards:

```vue
<div v-if="draftEditOpen" class="version-draft-editor">
  <label class="md-label-large" for="draft-edited-content">编辑草稿正文</label>
  <textarea
    id="draft-edited-content"
    v-model="draftEditedContent"
    class="version-draft-editor__textarea"
    rows="14"
  ></textarea>
  <p class="md-body-small md-on-surface-variant">
    当前编辑稿 {{ getVersionWordCount(draftEditedContent) }} 字
  </p>
</div>
```

- [ ] **Step 4: Update `WDWorkspace.vue` finalizing state**

Update labels:

```ts
case 'finalizing':
  return '定稿中'
```

Update tone:

```ts
if (status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing') return 'progress'
```

Update in-progress helper:

```ts
const isInProgressStatus = (status: Chapter['generation_status'] | null | undefined) => {
  return status === 'generating' || status === 'evaluating' || status === 'selecting' || status === 'finalizing'
}
```

Ensure `currentComponent` sends `finalizing` to `ChapterGenerating`.

- [ ] **Step 5: Update `WritingDesk.vue` confirm handler**

Replace `selectChapterVersionMutation` setup with:

```ts
const confirmFinalizeChapterMutation = useConfirmFinalizeChapterMutation(() => props.id)
```

Update `confirmVersionSelection`:

```ts
const confirmVersionSelection = async (payload?: { editedContent?: string | null }) => {
  const targetChapterNumber = selectedChapterNumber.value
  if (targetChapterNumber === null) return
  if (!availableVersions.value?.[selectedVersionIndex.value]?.content) return

  try {
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'finalizing'
        chapter.generation_step = 'confirm_finalize'
      }
    }

    await confirmFinalizeChapterMutation.mutateAsync({
      chapterNumber: targetChapterNumber,
      selectedVersionIndex: selectedVersionIndex.value,
      editedContent: payload?.editedContent ?? null,
    })
    await refetchChapterIntoProject(targetChapterNumber)
    chapterGenerationResult.value = null
    globalAlert.showSuccess('章节已定稿，后处理已完成', '定稿完成')
  } catch (error) {
    console.error('确认定稿失败:', error)
    if (project.value?.chapters) {
      const chapter = project.value.chapters.find((ch) => ch.chapter_number === targetChapterNumber)
      if (chapter) {
        chapter.generation_status = 'waiting_for_confirm'
      }
    }
    globalAlert.showError(
      `确认定稿失败: ${error instanceof Error ? error.message : '未知错误'}`,
      '定稿失败',
    )
  }
}
```

Leave `selectVersionFromDetail()` as choosing the candidate index only:

```ts
const selectVersionFromDetail = async () => {
  selectedVersionIndex.value = detailVersionIndex.value
  closeVersionDetail()
}
```

- [ ] **Step 6: Verify UI tests pass**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: pass.

---

### Task 7: Finalization Trace Labels In Node Console

**Files:**
- Modify: `frontend/src/components/writing-desk/workspace/ChapterGenerating.vue`
- Modify: `frontend/src/components/__tests__/chapterDraftFinalizeStatic.spec.ts`

- [ ] **Step 1: Add failing trace label tests**

Append:

```ts
  it('labels finalization trace nodes in the console', () => {
    const generating = readSource('src/components/writing-desk/workspace/ChapterGenerating.vue')

    for (const key of [
      'confirm_finalize',
      'real_summary',
      'finalize_memory',
      'chapter_ingest',
      'foreshadowing_sync',
      'finalized',
      'finalization_error',
    ]) {
      expect(generating).toContain(key)
    }

    expect(generating).toContain('确认定稿')
    expect(generating).toContain('生成章节梳理')
    expect(generating).toContain('同步伏笔')
  })
```

- [ ] **Step 2: Run failing trace label test**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: fails until finalization labels are added.

- [ ] **Step 3: Add labels and details**

In `ChapterGenerating.vue`, add these entries to `PIPELINE_LABELS`:

```ts
save_draft: '保存草稿',
confirm_finalize: '确认定稿',
real_summary: '生成章节梳理',
finalize_memory: '更新记忆快照',
chapter_ingest: '写入章节索引',
foreshadowing_sync: '同步伏笔',
finalized: '定稿完成',
finalization_error: '定稿失败',
```

Extend `TRACE_CALL_TYPE_LABELS`:

```ts
confirm_finalize: '确认定稿',
real_summary: '章节梳理',
finalize_memory: '记忆快照',
chapter_ingest: '章节索引',
foreshadowing_sync: '伏笔同步',
finalized: '定稿完成',
finalization_error: '定稿失败',
```

Extend `STEP_DETAILS`:

```ts
confirm_finalize: {
  summary: '确认最终草稿并锁定本次定稿正文。',
  inputs: '候选版本 + 手动修改正文',
  outputs: '最终正文与选中版本',
  next: '生成章节梳理',
},
real_summary: {
  summary: '基于最终正文生成真实章节梳理。',
  inputs: '最终正文',
  outputs: 'Chapter.real_summary',
  next: '更新记忆',
},
finalize_memory: {
  summary: '更新全局摘要、角色状态、剧情线和章节快照。',
  inputs: '最终正文 + 当前项目记忆',
  outputs: '项目记忆与章节快照',
  next: '写入索引',
},
chapter_ingest: {
  summary: '写入章节向量索引，供后续检索使用。',
  inputs: '最终正文 + 章节梳理',
  outputs: '章节检索索引',
  next: '同步伏笔',
},
foreshadowing_sync: {
  summary: '抽取新伏笔并判断历史伏笔推进或回收。',
  inputs: '最终正文 + 历史活跃伏笔',
  outputs: '伏笔表与状态历史',
  next: '定稿完成',
},
finalized: {
  summary: '所有后处理完成，章节进入已完成状态。',
  inputs: '后处理统计',
  outputs: 'successful',
  next: '进入正文查看',
},
finalization_error: {
  summary: '定稿后处理失败，章节保留草稿待确认。',
  inputs: '失败节点上下文',
  outputs: '错误详情',
  next: '修改后重试',
},
```

- [ ] **Step 4: Verify trace label tests pass**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
```

Expected: pass.

---

### Task 8: End-To-End Verification And Cleanup

**Files:**
- Modify only files already touched by Tasks 1-7.
- Test: backend and frontend targeted suites.

- [ ] **Step 1: Run backend targeted tests**

Run:

```bash
timeout 60s pytest \
  backend/tests/test_chapter_draft_finalize_contract_static.py \
  backend/tests/test_confirm_finalize_router_static.py \
  backend/tests/test_pipeline_langgraph_refactor_static.py \
  backend/tests/test_optimizer_router.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run frontend targeted tests**

Run from `frontend/`:

```bash
timeout 60s npm run test:unit -- \
  src/components/__tests__/chapterDraftFinalizeStatic.spec.ts \
  src/components/__tests__/wdWorkspaceLockedChapter.spec.ts
```

Expected: pass.

- [ ] **Step 3: Run type checks**

Run from `frontend/`:

```bash
timeout 60s npm run type-check
```

Expected: pass.

- [ ] **Step 4: Run backend syntax/import sanity**

Run:

```bash
timeout 60s python -m compileall backend/app
```

Expected: pass.

- [ ] **Step 5: Inspect diff for old logic**

Run:

```bash
git diff -- backend/app/api/routers/writer.py backend/app/services/pipeline_orchestrator.py frontend/src/views/WritingDesk.vue
```

Expected:
- generation no longer passes `finalize_version_index=state["best_version_index"]`;
- active user confirmation uses `confirm-finalize`;
- no active path shows generated chapters as `successful` before confirm;
- finalization trace nodes are visible.

- [ ] **Step 6: Commit implementation**

Run:

```bash
git add \
  backend/app/schemas/novel.py \
  backend/app/services/novel_service.py \
  backend/app/services/pipeline_orchestrator.py \
  backend/app/api/routers/writer.py \
  backend/tests/test_chapter_draft_finalize_contract_static.py \
  backend/tests/test_confirm_finalize_router_static.py \
  backend/tests/test_pipeline_langgraph_refactor_static.py \
  frontend/src/api/novel.ts \
  frontend/src/queries/novel.ts \
  frontend/src/views/WritingDesk.vue \
  frontend/src/components/writing-desk/WDWorkspace.vue \
  frontend/src/components/writing-desk/workspace/VersionSelector.vue \
  frontend/src/components/writing-desk/workspace/ChapterGenerating.vue \
  frontend/src/components/__tests__/chapterDraftFinalizeStatic.spec.ts
git commit -m "feat: require manual chapter finalization"
```

Expected: commit succeeds.

---

## Self-Review

- Spec coverage: plan covers draft generation, manual edit, synchronous confirm, `real_summary`, memory, vector ingest, foreshadowing sync, trace visibility, failure behavior, and no old active generation-completion logic.
- Placeholder scan: no `TBD`, `TODO`, or unspecified implementation slots.
- Type consistency: backend uses `finalizing` in schemas and frontend API; frontend mutation maps camelCase payload to backend snake_case; trace node keys match backend and frontend label plan.
