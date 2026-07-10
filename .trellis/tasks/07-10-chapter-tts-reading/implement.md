# 章节朗读与 TTS 模型接入实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` or `executing-plans` task-by-task. Each task follows test-first implementation and ends with an independent review gate.

**Goal:** 为已完成章节增加可暂停、继续、停止的完整朗读，并支持 MiMo 与 OpenAI Speech 兼容 TTS 模型，未配置或调用失败时回退浏览器朗读。

**Architecture:** 前端 composable 负责文本分段和播放队列；后端认证端点只合成单段文本，并从当前用户唯一默认 TTS 模型选择两个明确协议分支。模型配置复用现有供应商、模型和 Vue Query 数据链路。

**Tech Stack:** FastAPI, SQLAlchemy async, Pydantic v2, httpx, Vue 3, TypeScript, TanStack Vue Query, Vitest.

## Global Constraints

- 每个后端请求最多 2500 个字符。
- API Key、章节正文和上游原始错误正文不得写入日志或返回客户端。
- 不新增第三方依赖，不实现语音克隆、声音设计、音频持久化或任意请求模板。
- 新增 Python、TypeScript、Vue 文件必须包含准确的 AIMETA 首行。
- 只修改本计划列出的功能相关文件，不重构相邻代码。

---

### Task 1: 扩展 TTS 模型配置契约与数据库兼容

**Files:**
- Modify: `backend/app/models/ai_model_config.py`
- Modify: `backend/app/schemas/llm_config.py`
- Modify: `backend/app/services/llm_config_service.py`
- Modify: `backend/app/db/init_db.py`
- Modify: `backend/db/schema.sql`
- Create: `backend/db/migrations/add_tts_model_configuration.sql`
- Modify: `backend/tests/test_llm_config_service.py`
- Create: `backend/tests/test_tts_model_configuration.py`

**Produces:** `UserAIModel`/`UserAIModelRead` fields `is_default_tts`, `tts_protocol`, `tts_voice`, `tts_speed`; normalized capability `tts`; unique default-TTS behavior.

- [ ] Add failing schema tests proving `tts_speed` rejects values outside `0.5..2.0`, protocol accepts only `mimo_chat_audio | openai_speech`, and a TTS model requires protocol and voice.
- [ ] Add failing service tests proving capability normalization preserves `tts`, selecting a default TTS clears the flag on sibling models, and deleting the current default TTS is rejected.
- [ ] Run `timeout 60s pytest -q backend/tests/test_llm_config_service.py backend/tests/test_tts_model_configuration.py`; expect failures for missing TTS fields/behavior.
- [ ] Add the four ORM/Pydantic fields and minimal cross-field validation. Extend `_model_to_read`, create/update assignment, `_normalize_capabilities`, provider capability aggregation, default normalization, and delete protection.
- [ ] Add dialect-compatible startup `ALTER TABLE` statements, canonical `schema.sql` columns, and the migration note. Existing rows must resolve to `false/null/null/1.0`.
- [ ] Re-run the focused pytest command; expect all selected tests to pass.
- [ ] Review the diff for unrelated model-routing changes before proceeding.

### Task 2: 新增认证 TTS 合成端点与两种协议分支

**Files:**
- Modify: `backend/app/repositories/ai_model_config_repository.py`
- Create: `backend/app/schemas/tts.py`
- Create: `backend/app/services/tts_service.py`
- Create: `backend/app/api/routers/tts.py`
- Modify: `backend/app/api/routers/__init__.py`
- Create: `backend/tests/test_tts_service.py`
- Create: `backend/tests/test_tts_router.py`

**Consumes:** Task 1 TTS model fields.

**Produces:**

```python
class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2500)

@dataclass(frozen=True)
class SpeechAudio:
    content: bytes
    media_type: str

async def TTSService.synthesize(user_id: int, text: str) -> SpeechAudio: ...
```

- [ ] Write failing repository/service tests for user-owned enabled default resolution, disabled provider/model rejection, missing key/voice/protocol, and ensuring no caller-supplied model ID exists.
- [ ] Write failing MiMo tests asserting `/chat/completions`, assistant text, optional speed instruction, WAV voice request, Base64 decode, and rejection of missing audio data.
- [ ] Write failing OpenAI Speech tests asserting `/audio/speech`, `model/input/voice/speed/response_format`, binary MP3 handling, timeout, non-2xx, empty body, and MIME rejection.
- [ ] Write failing router tests for authentication, raw audio response, `409` missing configuration, `422` validation, `502` upstream failure, and `504` timeout.
- [ ] Run `timeout 60s pytest -q backend/tests/test_tts_service.py backend/tests/test_tts_router.py`; expect import/route failures.
- [ ] Implement `get_default_tts()` with eager provider loading, `TTSService` with two private protocol methods using `httpx.AsyncClient`, and the thin authenticated router. Do not add an abstract adapter base class.
- [ ] Register the router and re-run the focused tests; expect all selected tests to pass.
- [ ] Review logs and exception messages to confirm no key, text, or upstream body can escape.

### Task 3: 在乾坤万象中枢增加语音朗读配置 Tab

**Files:**
- Modify: `frontend/src/api/llm.ts`
- Modify: `frontend/src/views/SettingsView.vue`
- Modify: `frontend/src/components/llm-settings/PersonalModelRouting.vue`
- Modify: `backend/tests/test_frontend_tanstack_query_static.py`
- Create: `frontend/src/components/__tests__/ttsSettings.spec.ts`

**Consumes:** Task 1 model contract and existing `useLLMConfigBundleQuery`/model mutations.

**Produces:** fourth section `tts`, capability-aware model CRUD, and typed fields:

```ts
export type TTSProtocol = 'mimo_chat_audio' | 'openai_speech'

interface TTSModelFields {
  is_default_tts: boolean
  tts_protocol: TTSProtocol | null
  tts_voice: string | null
  tts_speed: number
}
```

- [ ] Add failing component/static tests for the fourth ARIA tab, keyboard navigation, `tts` capability persistence, unique default selection, protocol selector, voice control, and speed bounds.
- [ ] Run `npm --prefix frontend run test:unit -- src/components/__tests__/ttsSettings.spec.ts`; expect missing-tab failures.
- [ ] Extend API interfaces and the existing section/capability mapping. Reuse provider cards, batch model save, model mutations, query invalidation, and manual validation.
- [ ] For MiMo show preset voices `冰糖/茉莉/苏打/白桦/Mia/Chloe/Milo/Dean` plus custom entry; for OpenAI show custom voice ID. Keep audio format fixed and do not add extra settings.
- [ ] Re-run the component test and `timeout 60s pytest -q backend/tests/test_frontend_tanstack_query_static.py`; expect pass.
- [ ] Run `npm --prefix frontend run type-check`; expect exit code 0.

### Task 4: 实现章节文本分段和统一播放队列

**Files:**
- Create: `frontend/src/api/tts.ts`
- Create: `frontend/src/composables/useChapterReader.ts`
- Create: `frontend/src/composables/__tests__/useChapterReader.spec.ts`

**Consumes:** `requestRaw`, auth store, `useLLMConfigBundleQuery`, and `POST /api/tts/speech`.

**Produces:**

```ts
export type ReaderStatus = 'idle' | 'generating' | 'playing' | 'paused'
export const splitSpeechText: (title: string, content: string, limit?: number) => string[]
export const useChapterReader: () => {
  status: Readonly<Ref<ReaderStatus>>
  isBrowserFallback: Readonly<Ref<boolean>>
  start: (title: string, content: string) => Promise<void>
  pause: () => void
  resume: () => void
  stop: () => void
}
```

- [ ] Write failing pure tests for title-first ordering, paragraph/sentence boundaries, hard splitting, empty input, and no segment over 2500 characters.
- [ ] Write failing playback tests with fake `Audio`, object URLs, `speechSynthesis`, and mocked TTS API for start/pause/resume/stop, one-ahead prefetch, no new request while paused, and duplicate-start cancellation.
- [ ] Add failing fallback tests proving no configured TTS uses browser immediately, a failed model segment continues from that segment without replay, and unsupported browser speech surfaces an actionable error.
- [ ] Run `npm --prefix frontend run test:unit -- src/composables/__tests__/useChapterReader.spec.ts`; expect missing-module failures.
- [ ] Implement typed `synthesizeSpeech(text, signal): Promise<Blob>` through `requestRaw`, then implement the smallest queue/state machine satisfying the tests. Revoke every object URL and cancel every active request/utterance on `stop()`.
- [ ] Re-run the focused Vitest file; expect pass, then run `npm --prefix frontend run type-check`; expect exit code 0.

### Task 5: 集成已完成章节工具栏并执行全量复核

**Files:**
- Modify: `frontend/src/components/writing-desk/WDWorkspace.vue`
- Modify: `frontend/src/components/__tests__/wdWorkspaceLockedChapter.spec.ts`
- Modify: `frontend/src/components/__tests__/uiAuditRegression.spec.ts`

**Consumes:** Task 4 `useChapterReader` and existing `selectedChapterResolvedContent`/chapter title.

- [ ] Add failing component tests: finalized content shows one initial reading button; draft/empty/locked chapters do not; active state exposes pause/continue and stop; selecting another chapter and unmounting stop playback.
- [ ] Run `npm --prefix frontend run test:unit -- src/components/__tests__/wdWorkspaceLockedChapter.spec.ts src/components/__tests__/uiAuditRegression.spec.ts`; expect missing-control failures.
- [ ] Integrate the composable into the existing chapter toolbar. Use icon buttons with accessible labels/tooltips, preserve the current utility-group dimensions, and avoid changing unrelated chapter rendering.
- [ ] Re-run the focused component tests; expect pass.
- [ ] Run backend focused suite: `timeout 60s pytest -q backend/tests/test_llm_config_service.py backend/tests/test_tts_model_configuration.py backend/tests/test_tts_service.py backend/tests/test_tts_router.py`.
- [ ] Run frontend suite: `npm --prefix frontend run test:unit`.
- [ ] Run static/type/build gates: `npm --prefix frontend run type-check` and `npm --prefix frontend run build`.
- [ ] Run backend full suite with guard: `timeout 60s pytest -q backend/tests`; if the timeout is reached, report it separately and retain focused-suite evidence.
- [ ] Perform an independent diff review against every PRD acceptance criterion, then record verified and unverified items before commit.

## Rollback Points

1. Task 1 is additive schema work; rollback code can leave the new columns unused.
2. Task 2 can be disabled by removing router registration without affecting model configuration CRUD.
3. Tasks 3-5 are frontend-only and can be reverted independently if browser or audio behavior regresses.

## Final Review Gate

- No unresolved placeholders in planning or implementation.
- Every PRD acceptance criterion maps to at least one test or explicit manual check above.
- No dependency, global configuration, unrelated refactor, or sensitive artifact is introduced.
