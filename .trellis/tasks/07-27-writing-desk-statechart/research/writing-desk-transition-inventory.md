# WritingDesk Transition Inventory

Research date: 2026-07-30

## Current Lifecycle Owners

### Page-local mirrors

- `WritingDesk.vue:193-219` creates project/chapter queries alongside `chapterGenerationResult` and `generatingChapter`.
- `WritingDesk.vue:285-360` threads `evaluatingChapter` and lifecycle operations through child components/composables.
- `selectedChapterNumber` and `selectedVersionIndex` are interaction/presentation state and may remain; the result/generating/evaluating fields mirror server work and must not remain lifecycle facts.

### Generation and retry

- `useWritingDeskChapterGeneration.ts:84-148` writes project cache status `generating`, calls the old generation mutation, refetches, then writes `failed` locally on error.
- `useWritingDeskChapterGeneration.ts:151-200` repeats the same ownership for node retry.
- `queries/novel.ts:452-472` waits for background task completion and refreshes project queries inside the mutation, after which the composable refetches again.

Target: durable start/retry commands, one pending command id, server snapshot reconciliation, revision-aware invalidation.

### Standalone evaluation

- `useWritingDeskChapterOps.ts:32-85` owns `evaluatingChapter`, mutates Chapter status to `evaluating`, invokes the old evaluate endpoint and restores the previous local status on error.
- `queries/novel.ts:475-485` refreshes again after evaluation.
- `ChapterEvaluationPanel.vue`, `ChapterGenerating.vue`, `ChapterFailedVersions.vue` and `VersionSelector.vue` expose a standalone evaluate action.

Target: remove the independent evaluate command. Workflow generation already runs review; review failure exposes server `retry` or `retry_external` through `allowed_commands`. Evaluation display remains Chapter/query data.

### Version selection and finalization

- `useWritingDeskConfirm.ts:59-89` writes `finalizing`, calls the old finalize mutation, refetches and restores `waiting_for_confirm` on failure.
- `queries/novel.ts:535-564` waits for completion and refreshes Chapter/Project inside the mutation.

Target: UI selection sends durable workflow `select`; the workflow snapshot owns finalizing/projection/success. There is no separate client `FINALIZE` phase guess.

### Chapter SSE and reconnect

- `useWritingDeskProject.ts:44-48` owns fetch state, AbortController, stream key and reconnect timer.
- `useWritingDeskProject.ts:97-147` subscribes to legacy Chapter SSE, directly upserts Chapter cache, refetches on error and retries after three seconds.
- `WDWorkspace.vue:347-377` watches chapter number, status, versions and content, then infers whether lifecycle polling/SSE is needed.

Target: one workflow-scoped invoked stream actor using durable cursor semantics. Task events only wake a current workflow refetch. Transport health is a parallel region, not inferred from Chapter status/content.

### Derived lifecycle state

- `useWritingDeskChapterState.ts:27-82` combines chapter query, project cache, mutation pending and local refs to derive selecting/evaluating/version visibility.
- `useWritingDeskVersionDetail.ts:264-274` watches Chapter/version data to maintain recommendation/detail presentation.

Target: lifecycle selectors use machine snapshot + server `allowed_commands`; Chapter/version presentation can continue from Vue Query. Recommendation/detail watchers may remain if they do not start work or write lifecycle status.

## Cutover Matrix

| Current behavior | Target owner | Cutover action |
| --- | --- | --- |
| generate/retry local status write | workflow start/command snapshot | replace and delete local write/rollback |
| independent evaluate task | workflow review node + retry commands | remove command and CTA ownership; keep result display |
| finalize mutation and guessed status | durable `select` command | replace and delete guessed transition |
| Chapter SSE status/content inference | workflow event wake-up actor | remove watcher, timer and cache upsert |
| mutation wait + repeated refetch | workflow current query | remove duplicate wait/refresh chain from WritingDesk path |
| `generatingChapter` / `evaluatingChapter` | machine phase/pending command | delete refs and props |
| full Project/Chapter data | Vue Query | retain as sole server cache |
| drawer/modal/focus/version detail | local Vue state | retain |
| AppShell task reminder | existing task query/stream | retain and regression test |

## Server Status Mapping

| Server status | Workflow region state | Notes |
| --- | --- | --- |
| no connection | `idle` | start is the only local eligibility rule |
| `queued`, `running` | `running` | progress comes from snapshot |
| `retry_wait` | `running` | automatic durable retry remains active |
| `waiting_for_selection` | `waitingForSelection` | `select` only when allowed |
| `finalizing` | `finalizing` | no client completion guess |
| `projection_pending` | `projectionPending` | projection retry is distinct |
| `needs_attention` | `failed` | allowed command may require duplicate acknowledgement |
| `failed` | `failed` | public error/category shown |
| `successful` | `succeeded` | refresh Chapter/Project on revision boundary |
| `cancelled` | `cancelled` | terminal display |
| `superseded` | `superseded` | refetch/follow current lineage; no commands |

## Events And Guards

UI intent events:

```text
START
SELECT_VERSION
RETRY
RETRY_EXTERNAL
RETRY_PROJECTION
CANCEL
SCOPE_CHANGED
```

`START` is a separate endpoint intent: it is permitted for no-run idle and for a cancelled terminal run. All run-level commands are permitted only when their exact type appears in server `allowed_commands`.

Transport/reconciliation events:

```text
LOOKUP_RESOLVED
LOOKUP_FAILED
SNAPSHOT_RECONCILED
COMMAND_ACCEPTED
COMMAND_CONFLICT
COMMAND_FAILED
STREAM_CONNECTED
STREAM_WAKE
STREAM_DISCONNECTED
CURSOR_RESET
POLL_TICK
```

Every server-derived event carries scope epoch and, when available, run id/row revision. Guards reject an event when:

- its scope epoch is not current;
- its run id does not match the current run and it is not a new current lookup result;
- its `row_revision` is lower than the applied revision;
- a cursor is duplicate/older;
- its command id is not the pending command;
- a run-level command is absent from `allowed_commands`.

The authoritative workflow/root-job/node value sets are the V1 Pydantic Literals emitted through OpenAPI. Runtime decoder arrays must be type-equal to the generated unions, and transition tests iterate those arrays; this prevents a newly added backend status from silently falling through a frontend default branch.

## Presentation Kept Outside The Machine

- selected chapter and selected version index;
- drawer, modal, assistant visibility and focus management;
- version/evaluation detail parsing and display;
- chapter editor/delete/optimization presentation that does not submit workflow lifecycle commands;
- sidebar mapping, scrolling, labels and locked-prerequisite display;
- reader, clipboard and responsive behavior.

These values may react to current Chapter/query data but must not write workflow status, decide connection ownership or submit generation/finalization side effects.
