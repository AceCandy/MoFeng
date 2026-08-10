# Durable Job And Event Log Contract

## 1. Scope / Trigger

Apply this contract when changing durable job persistence, worker claiming, handler registration, task list/detail responses, task SSE, Redis wake-up, event retention, or worker deployment. The contract keeps database recovery, user-visible state, and external side effects separate so a process crash cannot silently lose work or create a false exactly-once guarantee.

## 2. Signatures

### Service and worker boundary

```python
await JobService(session).enqueue_job(
    user_id: int,
    job_type: str,
    title: str,
    project_id: str | None = None,
    payload: dict[str, Any] | None = None,
    payload_version: int = 1,
    idempotency_key: str | None = None,
    max_attempts: int = 3,
    stream_type: str | None = None,
    stream_id: str | None = None,
) -> BackgroundTask

await JobService(session).claim_next(
    worker_id: str,
    lease_seconds: int,
    executor_generation: int = 1,
) -> JobLease | None

JobLease(
    job_id: str,
    worker_id: str,
    fencing_token: int,
    attempt: int,
    max_attempts: int,
    job_type: str,
    payload_version: int,
    payload: dict[str, Any],
    user_id: int,
    project_id: str | None,
    executor_generation: int,
    lease_expires_at: datetime,
)
```

Every handler is registered by the exact tuple `(job_type, payload_version)` and declares one `SideEffectClass`: `transactional`, `idempotent_external`, or `ambiguous_external`.

Chapter candidate persistence uses the existing execution context:

```python
await ChapterWorkflowCandidatePersistenceService(execution).execute(
    ChapterWorkflowPersistCandidatesInput(
        candidate_refs: list[ChapterWorkflowActivityRef],
        review_ref: ChapterWorkflowActivityRef | None,
        post_review_refs: dict[int, list[ChapterWorkflowActivityRef]],
    )
) -> ChapterWorkflowPersistCandidatesExecution
```

Its state update contains only `node_key`, `candidate_version_ids`, and the
`persist_candidates` activity/result references.

Model response adapters expose one shared terminal and content boundary:

```python
{"content": str | None, "finish_reason": str | None}
parse_chapter_content_response(raw: str) -> tuple[str, dict[str, Any]]
parse_optimizer_response(raw: str) -> tuple[str, str]
```

### HTTP and SSE boundary

```text
GET /api/tasks?limit=<1..50>
GET /api/tasks/{task_id}
GET /api/tasks/snapshot?limit=<1..50>[&stream_type=<job|workflow>&stream_id=<id>]
GET /api/tasks/events?limit=<1..50>[&cursor=<non-negative>][&stream_type=<job|workflow>&stream_id=<id>]
Last-Event-ID: <same value as cursor when both are present>
```

SSE events are `snapshot`, `task`, `reset`, and a sanitized terminal `error`. A `task`
event uses the durable `JobEvent.cursor` as the SSE `id`. The three state-bearing data
payloads are `BackgroundTaskSnapshotResponse`, `BackgroundTaskEventResponse`, and
`BackgroundTaskCursorResetResponse`; each carries `schema_version: Literal[1]`.

### Persistent boundary

- `background_tasks` is the current row. It stores payload version, attempt policy, lease owner/expiry, heartbeat, fencing token, executor generation, stream identity, and current result.
- `job_events` is append-only history. `cursor` is globally increasing; `(stream_type, stream_id, sequence)` is unique.
- `job_event_streams` owns the stream user/project identity and the locked stream-local sequence watermark.
- `job_activities` stores external activity intent/result under unique `(job_id, activity_key)` and a unique provider request key.
- `job_executor_controls` selects the active worker generation; `job_worker_heartbeats` records process lifecycle but does not grant result-write authority.

## 3. Contracts

### State and transaction contract

- A state, progress, retry, cancel, dead-letter, or completion transition and its `JobEvent` append commit in one service-owned PostgreSQL transaction.
- Repositories may flush but never commit. The transition service is the only transaction owner for the current row plus event append.
- Claim locks an eligible row with `FOR UPDATE SKIP LOCKED`, increments `attempt` and `fencing_token`, assigns the lease, appends `job.started` or `job.reclaimed`, then commits before invoking the handler.
- Heartbeat, progress, activity result, success, failure, and cancel completion require the exact `job_id + worker_id + fencing_token + executor_generation` lease to remain unexpired. `attempt` is carried into activity/retry records and advances with the fencing token; the fencing token is the database write authority. A stale worker may finish local work but cannot commit its outcome.
- An inactive executor generation cannot claim new work. Rollout changes the durable generation before old workers drain or lose their leases.

### Enqueue and retry contract

- `payload_version >= 1`, `max_attempts >= 1`, and a supplied idempotency key is non-blank and at most 255 characters.
- The canonical enqueue key is `(user_id, job_type, idempotency_key)`. A duplicate returns the existing job only when `project_id`, `payload_version`, canonical payload, and stream identity match; otherwise it fails as a conflicting request.
- A successful enqueue inserts the current row and appends `job.queued` in the same transaction.
- Retryable errors move to `retry_wait` with policy backoff. Permanent errors fail immediately. Exhausted retries move to `dead_letter`. Unknown `(job_type, payload_version)` also dead-letters instead of guessing a payload shape.
- Public compatibility maps `retry_wait -> queued` and `dead_letter | needs_attention | cancelled -> failed`; the frontend remains a four-state consumer until that public contract is deliberately versioned.

### Production readiness and payload contract

#### 1. Scope / Trigger

Apply this contract when changing durable-job payload admission, runtime metrics,
retention cleanup, worker alert thresholds, or the deployment environment. These
settings describe the PostgreSQL control-plane gate; they do not claim a provider
throughput benchmark.

#### 2. Signatures

```text
JOB_PEAK_CONCURRENCY=<integer >= 1>                 # default: 20
JOB_LOAD_TEST_CONCURRENCY=<integer >= 2 * peak>     # default: 40
JOB_PAYLOAD_MAX_BYTES=<integer >= 1>                # default: 1048576
JOB_MAX_DURATION_SECONDS=<integer >= 1>             # default: 1800
JOB_EVENT_RETENTION_DAYS=<integer >= 1>              # default: 30
JOB_RETENTION_MAX_BYTES=<integer >= 1>              # default: 107374182400
JOB_RECOVERY_SLO_SECONDS=<integer >= 1>              # default: 300
JOB_QUEUE_AGE_ALERT_SECONDS=<integer >= 1>           # default: 60
JOB_PROJECTION_LAG_ALERT_SECONDS=<integer >= 1>      # default: 300
```

```python
await JobService(session).get_runtime_metrics(
    now: datetime | None = None,
    queue_age_alert_after_seconds: int | None = None,
    retention_max_bytes: int | None = None,
) -> JobRuntimeMetrics
```

The worker `metrics` command emits a `production_readiness` object with the nine
configured values and emits runtime `queue_depth`, `oldest_queued_age_seconds`,
`event_lag`, `oldest_event_lag_seconds`, `retained_event_bytes`, and stable `alerts`.

#### 3. Contracts

- Enqueue accepts a JSON object only. The canonical JSON representation is UTF-8
  encoded and must be no larger than `JOB_PAYLOAD_MAX_BYTES`; the exact boundary is
  accepted and the first byte above it is rejected.
- `JOB_LOAD_TEST_CONCURRENCY` is rejected at settings construction when it is below
  twice `JOB_PEAK_CONCURRENCY`.
- Queue-age, expired-lease, dead-letter, event-lag, and retention-budget conditions
  produce stable alert codes. Chapter projection metrics use the same configured
  lag threshold instead of a hard-coded duration.
- `retained_event_bytes` is the sum of PostgreSQL `pg_column_size(JobEvent.payload)`
  for retained events. It is a payload-storage budget signal, not a full relation
  plus index-size accounting.
- `JOB_MAX_DURATION_SECONDS` and `JOB_RECOVERY_SLO_SECONDS` are declared readiness
  profile/SLO values and are emitted by metrics; they are not an implicit provider
  timeout or automatic retry policy.

#### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Payload is not a JSON object | Reject enqueue with `ValueError` |
| Payload is not JSON serializable | Reject enqueue with `ValueError` |
| Canonical payload exceeds the configured byte limit | Reject enqueue with `ValueError` |
| Load-test concurrency is below `2 * peak` | Reject settings construction |
| Queue age exceeds its threshold | Add `job_queue_age` alert |
| Expired lease or dead-letter exists | Add `job_expired_lease` or `job_dead_letter` |
| Oldest unprojected event exceeds projection lag threshold | Add `job_event_lag` |
| Retained payload bytes exceed budget | Add `job_retention_budget` |

#### 5. Good / Base / Bad Cases

- Good: a payload exactly at 1 MiB is admitted, its duplicate idempotency key returns
  the same job, and metrics report a bounded retention/lag snapshot.
- Base: Redis is disabled; PostgreSQL metrics and worker scanning still expose the
  same alert codes, with no correctness dependency on wake-up notifications.
- Bad: accept a list payload, silently truncate canonical JSON, or infer a production
  SLO from a synthetic job test that called a real LLM provider.

#### 6. Tests Required

- Settings tests assert the nine defaults and reject a load-test value below twice the
  configured peak.
- Enqueue tests assert object-only payloads, JSON serialization failures, exact-limit
  acceptance, and over-limit rejection.
- PostgreSQL metrics tests assert queue age, expired lease, dead-letter, event lag,
  retention bytes, and all stable alert codes.
- Worker CLI tests assert `production_readiness` and runtime metrics are JSON-safe;
  deployment tests run `docker compose -f deploy/docker-compose.yml config --quiet`.
- Readiness evidence records a 2x control-plane rehearsal and recovery P95 separately
  from any future real-provider load test.

#### 7. Wrong vs Correct

```python
# Wrong: a payload limit based on character count can undercount UTF-8 bytes.
if len(json.dumps(payload)) > limit:
    raise ValueError("payload too large")
```

```python
# Correct: canonical JSON and UTF-8 bytes are the admission contract.
payload_size = len(_canonical_json(payload).encode("utf-8"))
if payload_size > settings.job_payload_max_bytes:
    raise ValueError("payload too large")
```

### External side-effect contract

- `transactional`: the outcome writer executes inside the fenced PostgreSQL success transaction.
- `idempotent_external`: persist an activity intent first, pass the stable provider request key to the provider, and upsert the result by activity key.
- `ambiguous_external`: if the call may have happened but no durable result exists, stop automatic replay and move the job to `needs_attention`/`dead_letter`.
- After durable identity and job/run status-pair validation, matching root/run
  `needs_attention + ambiguous_external_result` is a stable reconciliation state.
  Checkpoint missing/drift evidence must not recategorize it or replace its public error;
  only an audited `retry_external` or cancel command may advance it.
- Internal model-activity failure logs contain only the stage, failure phase,
  content-addressed activity/input identifiers, and exception type. They never include
  the exception message or traceback, provider request key, prompt, Chapter content,
  provider response, token values, or secrets.
- Database fencing guarantees one valid database outcome writer. It never proves an external provider call happened exactly once and cannot undo a call made by a stale process.
- Provider transports normalize terminal reasons before service collection; Anthropic
  `max_tokens` is the shared `length` failure and partial content is never a successful
  model activity result.
- Chapter candidate, post-review, and optimizer adapters parse strictly first, then may
  use the shared JSON sanitizer for recoverable string quoting. When the prompt requires
  structured output, an unparseable response or a parsed object without a supported正文
  field fails before activity completion. Candidate prompts that allow plain text preserve
  it unchanged; a leading `[` or `{` alone is not proof of JSON.
- API optimization, review-guided refinement, and Pipeline dimension optimization use
  the same optimizer response parser. Mandatory refinement propagates parse failure;
  optional dimensions retain their prior正文 rather than adopting the raw response.
  Extracting one field fragment does not validate the structured response: the complete
  JSON object must parse before any optimizer field is accepted.

### Public projection and event stream contract

- Task list, snapshot, and SSE task payloads use the same allowlisted public projection. They never populate `payload` or `result` (the serializer may return `null` or omit those optional fields). Writers sanitize public `error` and `log_entries` before persistence; projections forward those stored public fields rather than raw exception objects.
- Task detail uses the same projection and may include the result for the owning user. It still hides the input payload.
- Public error/log text is length-bounded and secret-redacted before it enters the current row or append-only event.
- `stream_type` and `stream_id` are optional as a pair and invalid separately. A scoped snapshot/SSE request authorizes the stream against the current user before streaming headers are returned. Missing and foreign streams both return 404.
- Snapshot tasks and `resume_cursor` come from one database snapshot. A scoped snapshot also binds `snapshot_revision` to the stream sequence and cursor.
- HTTP and SSE snapshots pass through the same frontend runtime decoder before state
  mutation. Snapshot/task/reset payloads validate `schema_version` and the fields used
  by cursor/reducer logic. Snapshot `stream_type`/`stream_id` must match the requested
  scope (or both remain absent/null for an unscoped request). Unknown outer event names
  are ignored; malformed, scope-drifted, or unknown-version payloads never enter task
  state.
- PostgreSQL event rows are the source of truth. Redis only wakes readers; missing, duplicated, disconnected, or restarted Redis cannot change ordering or recovery.
- `cursor` and `Last-Event-ID` must agree. Events with `cursor <= current_cursor` are ignored by the client. When retention emits `reset {schema_version: 1, reason: "cursor_expired", retained_through_cursor}`, the client obtains a new snapshot pair for the same scope, replaces local state/cursor, then reconnects.
- The first malformed or unsupported stream payload triggers one snapshot fetch for the
  same authenticated scope. If that recovery snapshot is also invalid, the client
  aborts SSE, clears its SSE override/cursor, and yields to the existing 15-second
  polling query. Network failures retain the bounded reconnect path.
- A stream callback may mutate state only while its AbortController is the current
  non-aborted connection. Late callbacks from a prior identity/scope are discarded.
- Changing authenticated user or stream scope clears the prior snapshot and cursor before reconnecting.

## 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Empty worker id or invalid lease/heartbeat interval | Reject configuration before claiming |
| Executor control is missing | Fail closed and require the database migration |
| Worker generation is inactive | Stop new claims; do not run a handler |
| Lease owner/token/generation no longer matches, or lease expired | Raise lease-lost behavior; do not append an outcome event |
| Duplicate enqueue has different canonical inputs | Reject the idempotency conflict; do not create a second job |
| Handler tuple is unknown | Append a public dead-letter transition; do not deserialize heuristically |
| Retryable failure below `max_attempts` | Append failure/retry event and schedule `retry_wait` |
| Permanent failure or attempts exhausted | Append terminal failed/dead-letter event |
| Ambiguous external activity is unresolved | Move to `needs_attention`/`dead_letter`; never auto-replay |
| Root/run already agree on `needs_attention + ambiguous_external_result` | Preserve the original category and public error regardless of checkpoint missing/drift evidence |
| Model activity context ref is absent, unfinished, hash-drifted, or its snapshot differs | Reject before creating the model activity intent; do not call the provider |
| Model activity upstream ref set/stage/result/output differs | Reject before creating the next intent; same root job and matching entity identity alone do not authorize the input |
| Model provider returns but typed output validation is uncertain | Mark that activity ambiguous and move the root job/run to `needs_attention`; do not retry the provider automatically |
| Provider terminal reason means output-length exhaustion | Normalize to `length` and reject the partial response before activity completion |
| Candidate response is a damaged structured wrapper or lacks a supported正文 field | Raise; do not persist the wrapper, field names, or partial正文 as a ChapterVersion |
| Structured正文 has an unclosed fence/object or explanatory text outside its JSON/fence | Raise; only a complete JSON value or complete full-response fence may be unwrapped |
| Optimizer text contains a field fragment but no complete JSON object | Raise; field-level regex extraction must not bypass object validation |
| Plain正文 starts with bracketed prose such as `[注]` or `{旁白}` | Preserve it unchanged unless it actually parses as a structured response |
| Optional正文 rewrite/expansion/compression/enrichment cannot pass the response boundary | Preserve the previous validated正文; a required initial candidate fails instead |
| Trace recovery lacks `output_payload.full_content` from the successful finalized node | Do not rebuild from `cleaned_output`; fall back to an earlier validated workflow state |
| Candidate persistence ref is unfinished, hash-drifted, wrong-stage, or not bound to the referenced candidate/review chain | Reject before creating the transactional intent; do not write ChapterVersion rows |
| Root lease/fence, active run identity, or Chapter base revision drifts before the outcome transaction | Roll back the candidate rows, activity result, and event together |
| Current or historical canonical ChapterVersion is present | Preserve every version referenced by Chapter or ChapterRevision; replace only unselected/unreferenced drafts |
| Only one of `stream_type` / `stream_id` is supplied | HTTP 400 |
| Stream is absent or owned by another user | HTTP 404 with the same public message |
| `Last-Event-ID` is negative/non-integer, or differs from `cursor` | HTTP 400 before streaming |
| `cursor` query is negative/non-integer | Reject through FastAPI request validation before streaming |
| Cursor is older than retention watermark | Emit one typed `reset`, then close the stream |
| State-bearing payload is malformed or has unsupported `schema_version` | Do not mutate state; attempt one same-scope snapshot recovery |
| Snapshot response scope differs from the request | Treat it as malformed; do not replace snapshot/cursor |
| Superseded connection delivers a late snapshot/task/reset | Ignore it without changing current state |
| Same-scope recovery snapshot is malformed or unsupported | Abort SSE state and retain the polling fallback |
| Outer SSE event name is unknown | Ignore it without changing task state or cursor |
| Redis is unavailable | Continue PostgreSQL polling and emit keepalives |
| Event lacks an allowlisted public task snapshot | Log internally and emit only a sanitized SSE error |

## 5. Good / Base / Bad Cases

- Good: process A claims attempt 1 and is terminated; after lease expiry process B claims attempt 2 with a higher fencing token, appends `job.reclaimed`, and is the only process allowed to commit the terminal outcome.
- Good: an idempotent provider call times out after reaching the provider; the retry reuses the provider request key and records one canonical activity result.
- Base: Redis is disabled. Worker scans and SSE database polling still deliver ordered transitions, with higher latency but identical state.
- Base: a client reconnects with the last durable cursor and receives only later events in ascending cursor order.
- Bad: treating a Redis notification as the task event, accepting a result without a lease token, or retrying an ambiguous provider call because the database row has no result.
- Good: a model activity becomes ambiguous before its latest checkpoint id is copied to
  the run; reconciliation preserves the original external-result error until an audited
  command resolves it.
- Bad: replace an external-result ambiguity with `checkpoint_drift`, or log a caught
  provider/validation exception whose message may contain prompt content or credentials.
- Bad: returning ORM `payload`/`result` directly from task list/SSE or resuming a reset stream without fetching a new snapshot pair.
- Good: an optimizer response with recoverable unescaped正文 quotes is extracted, while
  an unclosed JSON wrapper fails before candidate persistence.
- Base: ordinary正文 beginning with `[注]` or `{旁白}` remains unchanged.
- Base: an optional正文 transform returns a damaged wrapper and the prior validated正文 remains selected.
- Bad: treat provider `max_tokens` as success, extract JSON from surrounding prose, return raw JSON after extraction fails, or rebuild a version from trace `cleaned_output`.
- Good: candidate persistence rereads model activities, verifies their
  content-addressed provenance, then writes versions and the transactional
  activity result under the root fence.
- Bad: delete every ChapterVersion at candidate time, clear the current selected
  version, or let a recomputed checkpoint/trace payload authorize domain writes.

## 6. Tests Required

- PostgreSQL integration: concurrent workers claim one eligible row once; a stale fencing token cannot heartbeat, write progress, complete, fail, or cancel it.
- Real process recovery: process A claims and is terminated by the OS; process B starts independently, waits for lease expiry, reclaims, and completes. Assert attempt increment, fencing increment, `job.queued -> job.started -> job.reclaimed -> job.succeeded` event order, and final owner cleanup.
- Retry matrix: retry/backoff, permanent failure, max-attempt dead-letter, cancellation, unknown payload version, and inactive generation.
- External activity: crash-after-provider-call-before-result is tested separately for provider dedupe and ambiguous dead-letter. Never use a transactional-only test as evidence of external exactly-once behavior.
- Workflow model activities: real PostgreSQL tests cover stable candidate ordinal/post-review stage keys, replay call counts, private request/result separation, exact upstream-ledger verification, result tamper rejection, ambiguity synchronization, safe internal failure logging, and one AI usage row across replay.
- Workflow reconciliation: real PostgreSQL tests prove that matching root/run
  `ambiguous_external_result` remains unchanged when the run checkpoint id is null and
  the saver already has a later checkpoint; no replacement event is appended.
- Model response boundary tests cover provider stop-reason normalization, recoverable
  unescaped quotes, damaged/missing正文 wrappers, nested JSON, literal backslashes,
  orphan field fragments, mixed explanatory text, unclosed fences, leading bracketed
  prose, leading version-heading removal, optional-transform preservation, and trace
  recovery without `cleaned_output` fallback.
- Workflow candidate persistence: real PostgreSQL tests cover outcome-writer rollback, commit-before-checkpoint replay, concurrent replay producing one candidate set, stale fence/base revision rejection, cross-wired provenance rejection, current canonical preservation, and absence of正文/review reports from activity request/result, JobEvent, and checkpoint updates.
- Enqueue: concurrent identical keys return one canonical row/outcome; mismatched canonical inputs fail without a duplicate.
- Event log: state/event atomicity, global cursor order, stream-local sequence uniqueness, owner filtering, retention cleanup, and reset watermark.
- Snapshot/SSE: snapshot/event race has no gap; reconnect deduplicates; query/header mismatch fails; foreign stream is indistinguishable from missing; Redis-off polling passes.
- Projection: list, snapshot, SSE, and detail assert that private payload is absent; list/snapshot/SSE also assert result is absent and error text is sanitized.
- Frontend: shared HTTP/SSE snapshot decoding covers valid snapshot/task/reset,
  malformed shapes, unsupported versions, response-scope mismatch, and unknown outer
  events; invalid data never invokes handlers. The reducer ignores old cursors, reset
  refetches the same scope before reconnect, identity/scope change clears cursor, late
  callbacks from the old connection are ignored, a failed recovery yields to the
  15-second polling fallback, and network errors retain bounded reconnect.
- Test isolation: PostgreSQL combination suites run in the session's disposable
  `mofeng_pytest_<uuid>` database. Migration or independent-process tests may own a
  separate randomly named disposable database such as `mofeng_workflow_<uuid>` when
  their lifecycle requires it. Child OS workers receive the generated URL. Every form
  follows the same cleanup/resource-audit contract; `TEST_POSTGRES_URL` remains service
  location only, and the configured database or its `public` schema never becomes a
  shared mutation/cleanup target.

## 7. Wrong vs Correct

### Wrong

```python
job = BackgroundTask(..., event_sequence=0)
await repo.add(job)                  # INSERT flush
sequence = await next_sequence(job) # mutates the persistent job and flushes again
event = public_snapshot(job)        # may read an expired onupdate attribute
```

This creates an unnecessary second write to the job row and may trigger implicit async ORM I/O while serializing it.

### Correct

```python
job = BackgroundTask(..., event_sequence=0)  # transient
sequence = await next_sequence(job)          # lock stream and assign sequence first
await repo.add(job)                           # one INSERT flush for the job
await repo.add_event(JobEvent(sequence=sequence, payload={"task": public_snapshot(job)}))
await session.commit()
```

All derived fields are assigned before the job enters the session, and the current row plus public event commit atomically.

For workflow candidate persistence, do not call the legacy committing service:

```python
# Wrong: commits domain rows independently and makes checkpoint replay replace IDs.
await NovelService(session).replace_chapter_versions(chapter, contents, metadata)

# Correct: result references authorize one fenced PostgreSQL outcome transaction.
execution = await ChapterWorkflowCandidatePersistenceService(context).execute(refs)
checkpoint_update = execution.state_update()
```

```python
# Wrong: provider-specific truncation and invalid wrappers become successful正文.
finish_reason = event["stop_reason"]
return raw_response

# Correct: normalize at transport, then validate before completing the activity.
finish_reason = "length" if event["stop_reason"] == "max_tokens" else event["stop_reason"]
content, report = parse_chapter_content_response(raw_response)
```

## 8. Durable Chapter Workflow Extension

Apply these additional rules when a Chapter generation run uses LangGraph persistence:

- Reuse `BackgroundTask`, `JobActivity`, and the workflow-scoped `JobEvent` stream as the only execution, side-effect, and event control plane. `ChapterWorkflowRun` may own orchestration phase, graph version, frozen context, and the active Chapter slot; it must not duplicate lease, attempt, fencing, retry, or event sequencing.
- One stable identity spans the complete run: `ChapterWorkflowRun.id == LangGraph thread_id == JobEvent stream_id`. Root, finalize dispatcher, and projection jobs retain distinct job ids but reference that workflow stream.
- The root job may enter internal `waiting` only through a fenced service transition. `waiting` releases worker identity, lease, and heartbeat, remains ineligible for ordinary claim, retains the workflow active slot, and maps to public `queued` until the public task contract is versioned.
- A workflow transition locks `BackgroundTask -> ChapterWorkflowRun -> Chapter`, updates the root job and workflow run, and appends its allowlisted workflow event in one service-owned transaction. Projection consumers do not reverse this order; a separate resumer reacquires the root job before waking a projection-pending run.
- A graph checkpoint contains only versioned serializable identifiers, hashes, state markers, and activity/result references. It never contains an ORM object, database session, provider client, service, prompt or Chapter正文. The frozen canonical context remains on the workflow run and follows the Chapter context contract.
- Every side-effecting graph node uses the existing `JobActivity` ledger with a stable logical input hash. A successful activity is reused. A transactional outcome and its activity result commit together under the root job fence.
- Model-backed `plan_and_direct`, each candidate ordinal, `version_review`, and every enabled post-review stage are separate `ambiguous_external` activities. Their canonical request metadata contains only workflow/schema identity, node/stage, and the complete private input hash; prompt, context snapshot, mission, candidate content, and review reports remain in the private activity result.
- Production model adapters pass the activity's stable provider request key unchanged to
  the provider transport. The key supports correlation and provider-side deduplication
  when available; it does not turn an `ambiguous_external` call into an exactly-once
  operation. A missing durable result still enters `needs_attention` unless a future
  provider-specific contract can verify the remote outcome.
- A model activity input carries `context_activity_key`, `context_result_hash`, and the exact `upstream_refs: {ref_name: {activity_key, result_hash}}` required by its stage. Before creating a new intent, the service rereads those activities under the same root job and verifies `succeeded` status, expected stage, content-addressed result, and exact private output equality. Same-project/same-chapter data is not sufficient evidence of frozen identity.
- A model activity result records the non-sensitive `subject_ordinal` and `upstream_result_hashes`. Candidate persistence accepts references only, reconstructs private candidate/review/post-review outputs from the ledger, and rejects a review or post-review result that is not bound to the exact candidate result hashes being persisted.
- `persist_candidates` is a `transactional` activity. Its outcome writer runs after the root JobRun, workflow run, and Chapter locks; it validates the base revision again, locks existing ChapterVersion rows by ascending id, preserves the current selected version and every historical `ChapterRevision.selected_version_id`, writes candidate/evaluation rows, and completes the activity/event in the same transaction. It never reads generation trace or calls `clear_from_node`.
- A provider may return the typed output or `AICallResult[typed output]`. Telemetry is persisted with the private result and the existing `AIUsageRecord` in the activity completion transaction; replay neither calls the provider nor writes a second usage row.
- An unresolved `ambiguous_external` activity is immutable and moves the root job plus workflow run to `needs_attention`; worker reclaim, graph replay, and ordinary retry must not invoke the provider again. Only a persisted `retry_external` command with actor audit and `acknowledge_possible_duplicate=true` may derive one new activity intent from its command id. Replaying that command returns the same intent. Unknown provider results cannot be injected manually.
- Durable commands are `select`, `retry`, `retry_external`, `retry_projection`, and `cancel`. The inbox validates command id, payload version, expected workflow row revision, expected Chapter revision, and expected checkpoint id. A stale command is rejected without graph resume and exposes the current snapshot; a checkpoint-applied command marker is reconciled before any repeated resume.
- Graph V1 uses stable node keys `freeze_context`, `plan_and_direct`, `generate_candidates`, `review_candidates`, `persist_candidates`, `waiting_for_selection`, `finalize_revision`, `projection_pending`, `observe_projection`, and `successful`. Existing trace keys and `from_node_key` remain legacy-drain adapters and are never checkpoint recovery inputs for a new run.
- Finalize and every projection child job inherit the original workflow stream. The workflow may observe projection completion, but only the projection reconciler may move the current Chapter revision to `successful`.

### Ambiguous external activity command recovery

#### 1. Scope / Trigger

Apply when `retry_external` or an activity-bound `cancel` resolves an unresolved
`ambiguous_external` model activity. This path resumes the existing run and reuses its
durable upstream activity results; it does not create a replacement workflow run.

#### 2. Signatures

```python
ChapterWorkflowCommandEnvelope(
    type: Literal["select", "retry", "retry_external", "retry_projection", "cancel"],
    expected_checkpoint_id: str | None,
    payload: dict[str, Any],
)

ActivityExecution(
    activity_key: str,
    provider_request_key: str,
    should_execute: bool,
    result: dict[str, Any] | None = None,
)

await JobRepository.get_latest_manual_retry_for_update(
    *, job_id: str, logical_step_key: str
) -> JobActivity | None
```

The derived activity key is `manual_retry:<command_id>`. Its request records the
`manual_retry_command_id`, original `logical_step_key`, duplicate-call acknowledgement,
the canonical provider request, and the replaced activity identity.

#### 3. Contracts

- `expected_checkpoint_id` is required but nullable. Only `retry_external` and
  `cancel` may carry null; `select`, `retry`, and `retry_projection` require a non-null
  checkpoint. Every command still compares the supplied value with the locked run, so
  null matches only a run whose current checkpoint id is also null.
- Submitting `retry_external`, or `cancel` with an activity key, appends acceptance,
  applies the command, creates or replays its derived intent, transitions the root/run,
  appends application events, and commits once. Leaving such a command pending for a
  separate consumer is forbidden. Standard cancel without an activity key remains a
  terminal command and does not resume the graph.
- Graph node code continues to request the original logical activity key. Before any
  provider call, `begin_activity` may substitute only the latest command-derived manual
  intent whose applied command, run, activity identities, acknowledgement, replaced
  activity, provider request key, and canonical request all match.
- The returned `ActivityExecution.activity_key` is the storage identity for provider
  result validation, checkpoint/result references, completion, ambiguity, and replay.
  The original ambiguous activity remains immutable audit evidence.
- `manual_retry_pending` may transition once to `started` under the current lease.
  A manual activity already in `started` or `ambiguous` is uncertain and must stop in
  `needs_attention` without another provider call. A `succeeded` manual activity replays
  its durable result without another provider call.
- Successful upstream activities retain their original keys and replay normally, so
  graph re-entry invokes only the unresolved logical node's command-derived activity.

#### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Determinate command has null checkpoint | Reject at envelope validation |
| Supplied checkpoint differs from the locked run, including null vs non-null | Reject as `stale_checkpoint` |
| Retry command lacks activity key or duplicate-call acknowledgement | Reject before creating an intent |
| Referenced original activity is absent, non-ambiguous, or has a non-canonical request | Reject and roll back command events/intent |
| Derived intent identity differs from its applied command or original activity | Roll back and fail closed before provider invocation |
| Derived activity is `manual_retry_pending` | Mark `started` under the lease and invoke the provider once |
| Derived activity is `started` or `ambiguous` | Enter/retain `needs_attention`; never invoke the provider automatically |
| Derived activity is `succeeded` | Replay the stored result without provider invocation |

#### 5. Good / Base / Bad Cases

- Good: a run with null checkpoint submits one acknowledged external retry, is requeued,
  reuses every successful upstream result, and stores the new provider result under the
  command-derived activity while preserving the original ambiguous row.
- Base: the client repeats the same command id or the graph revisits a succeeded manual
  activity; both return the same intent/result without another provider call.
- Bad: mark the command accepted but leave it pending, call the provider under the
  original ambiguous key, treat null as a checkpoint wildcard, or replay a manual
  activity whose prior call may already have happened.

#### 6. Tests Required

- PostgreSQL integration starts with a real ambiguous model call and null run checkpoint,
  submits `retry_external`, asserts command application plus requeue in one transaction,
  claims a new lease, and proves only the target provider call count increases once.
- Assert the original activity remains ambiguous, the command-derived activity succeeds,
  and all completion/result/replay identities use the derived key.
- Force the derived activity separately to `started` and `ambiguous`; assert graph re-entry
  raises ambiguous-result handling and the provider call count does not increase.
- Schema/frontend tests accept null checkpoint for external retry and cancel, and reject
  null checkpoint for select, ordinary retry, and projection retry.

#### 7. Wrong vs Correct

```python
# Wrong: the command exists, but no runtime path consumes its derived intent.
command.status = "pending"
return ActivityExecution(activity_key=logical_key, should_execute=True)

# Correct: apply and queue atomically, then persist under the verified derived identity.
await apply_retry_external(command)
execution = await begin_activity(activity_key=logical_key, request_payload=canonical_request)
result = await provider(provider_request_key=execution.provider_request_key)
await complete_activity(activity_key=execution.activity_key, result=result)
```

### Activity progress and live trace contract

#### 1. Scope / Trigger

Apply when a durable Chapter workflow activity must expose its current node, progress,
or node-detail input/action/output before the root job reaches a wait or terminal state.

#### 2. Signatures

```python
ChapterWorkflowTransitionAdapter.apply_activity_event(
    *,
    job: BackgroundTask,
    context: LockedChapterWorkflowTransition,
    source_event_type: str,
    request_payload: dict[str, object],
    now: datetime,
) -> ChapterWorkflowEvent | None
```

The trace identity is `(source_run_id, source_event_cursor)`. The frontend accepts a
snapshot only for the current run/project/chapter and refreshes Chapter data whenever
that run's `row_revision` increases.

#### 3. Contracts

- A recognized activity request carries the canonical workflow `node_key`. Its
  `activity.started|retried|succeeded|retryable_failed|failed` event keeps that exact
  event type and adds only the public `workflow` snapshot.
- The activity transition updates `ChapterWorkflowRun.node_key`, monotonic `progress`,
  and `row_revision` before appending the event. The run update, JobEvent, and
  `ChapterGenerationTrace` commit in the same fenced transaction.
- The activity trace metadata contains the current `run_id`, canonical activity input,
  bounded display action, optional public output, call type, and `uses_llm`. It never
  adds the private activity request/result to the public JobEvent.
- The UI filters traces by `metadata.run_id` and refreshes Chapter/project queries on
  accepted same-run `row_revision` growth. SSE is a wake-up path; it does not invent
  progress or display a timer-based fake node transition.

#### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Activity event type is unsupported | Raise before mutating the run |
| Request has no recognized workflow `node_key` | Preserve the ordinary activity event; do not create a workflow trace |
| Target progress is below current progress | Keep current progress; never move backward |
| Lease/fence is stale, or trace/event flush fails | Roll back run, event, activity result, and trace together |
| Snapshot belongs to an old run or older revision | Ignore it and do not refresh current-run details |

#### 5. Good / Base / Bad Cases

- Good: candidate generation starts, the run moves to `generate_candidates` with an
  increased revision, and the UI can inspect a running trace before provider return.
- Base: a non-workflow or compatibility activity lacks `node_key`; its existing event
  behavior remains unchanged.
- Bad: emit only `activity.started` without a workflow snapshot, defer trace projection
  until the worker's next claim, or animate intermediate nodes without durable facts.

#### 6. Tests Required

- PostgreSQL integration asserts started and succeeded events retain their activity
  types, carry updated workflow snapshots, advance progress monotonically, increment
  row revision, and create current-run traces with input/action/output metadata.
- Frontend tests assert same-run row-revision growth invalidates Chapter/project data,
  current-run traces render details, and old/unattributed traces remain filtered out.
- Failure/retry extensions must assert their activity event type, trace status, and
  rollback behavior before changing those branches.

#### 7. Wrong vs Correct

```python
# Wrong: the provider runs, but current workflow state remains on the first node.
await append_event(job, "activity.started")
```

```python
# Correct: one fenced transaction advances the public snapshot and records details.
await self._append_activity_event(
    job,
    "activity.started",
    activity=activity,
    now=now,
    workflow_context=workflow_context,
)
```

### Cancelled Chapter workflow derived-result cleanup

#### 1. Scope / Trigger

Apply whenever a Chapter workflow root job reaches the durable `job.cancelled`
terminal event. A cancel request alone is not sufficient: cleanup runs only inside the
fenced terminal transition after the root job, workflow run, and Chapter are locked.

#### 2. Signatures

```python
await JobService._cleanup_cancelled_chapter_workflow(
    workflow_context: LockedChapterWorkflowTransition,
) -> None
```

Candidate provenance is
`ChapterVersion.metadata_["_chapter_workflow"]["run_id"]`; compatibility trace
provenance is `ChapterGenerationTrace.source_run_id`. The frontend candidate boundary
uses the same current workflow run id and must not fall back to Chapter cached content
while that run has no candidate.

#### 3. Contracts

- Waiting-command cancel, ambiguous-activity cancel, worker `mark_cancelled`, and
  expired-worker reaping all converge on the same `job.cancelled` event path. That path
  runs cleanup before building the workflow terminal snapshot and event.
- Lock ChapterVersion rows in ascending id order. Delete only versions whose provenance
  matches the cancelled run and which are not referenced by
  `Chapter.selected_version_id` or any `ChapterRevision.selected_version_id`.
- Delete evaluations for the selected disposable version ids before deleting those
  versions. Delete compatibility generation traces for the cancelled run, but preserve
  JobEvent, command/activity audit, workflow identity, checkpoints, revisions, outbox,
  and projection records.
- Reset the Chapter to the existing ungenerated defaults only when it has no selected
  version and `current_revision == 0`. A regeneration cancel must not change canonical
  content, summary, revision, selected version, or projection lineage.
- Cleanup, cancelled job/run state, heartbeat clearing, and the terminal event share the
  service-owned transaction. Repeating the terminal cleanup is an empty operation once
  disposable rows are gone; a stale worker remains unable to write through the lost
  root fence.
- The UI clears local candidate/ink previews when cancel is requested. On a following
  run, live draft content comes only from candidates attributed to that run; until one
  exists, the preview is empty.

#### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Cancel requested but root job is not terminal | Keep derived rows until the fenced terminal transition |
| Candidate provenance does not match the cancelled run | Preserve it |
| Candidate is selected by Chapter or any ChapterRevision | Preserve the version and its evaluation |
| Chapter has a selected version or a positive current revision | Preserve all canonical Chapter fields |
| Same cleanup executes more than once | Succeed without deleting additional facts |
| Root lease/fence is stale before terminal persistence | Roll back and reject the stale outcome |

#### 5. Good / Base / Bad Cases

- Good: cancelling a waiting run deletes both unselected candidates, their evaluations,
  and that run's traces, then a new run renders an empty preview until its own candidate
  arrives.
- Base: cancelling regeneration of a finalized Chapter removes only the new run's
  disposable drafts and leaves canonical content plus every revision reference intact.
- Bad: clear every ChapterVersion for the Chapter, hide old content only in Vue while
  retaining cancelled drafts, or clean at `cancel_requested` before worker fencing is
  resolved.

#### 6. Tests Required

- Cover waiting, running-worker, ambiguous-activity, and expired-worker cancellation;
  assert the same candidate/evaluation/trace cleanup and cleared terminal heartbeat.
- Repeat cancellation/cleanup and assert idempotence. Protect both the current selected
  version and a version referenced only by ChapterRevision.
- Assert an ungenerated Chapter returns to empty defaults while a finalized Chapter's
  canonical fields and projection lineage remain unchanged.
- Frontend tests must assert immediate local-preview clearing, no previous-run fallback,
  current-run-only candidate display, and one allowed cancel control in the visible
  progress area.

#### 7. Wrong vs Correct

```python
# Wrong: terminal state changes but cancelled drafts remain canonical read candidates.
job.status = "cancelled"
await append_event(job, "job.cancelled")
```

```python
# Correct: the shared fenced terminal event path cleans the current run atomically.
job.status = "cancelled"
await self._append_event(job, "job.cancelled", now=now)
```

### Interrupt checkpoint and root wait handshake

1. **Scope / Trigger**: apply whenever a graph node reaches `waiting_for_selection` or `projection_pending`, or a reclaimed worker observes one of those persisted interrupt checkpoints.
2. **Signatures**: business nodes are supplied through `ChapterWorkflowGraphBindingsV1`; `ChapterWorkflowRuntime.execute(resume_value=...)` returns `JobWaitOutcome` or `JobOutcome`; `JobWorker` converts `JobWaitOutcome` through `JobService.wait_for_resume(lease, workflow_transition=...)` and must not call `mark_succeeded` afterward.
3. **Contracts**: graph bindings may return only serializable state updates and cannot change workflow/schema/run/context/node identity. The graph owns `node_key` advancement. `interrupt()` runs before a resume binding, so node re-execution has no pre-interrupt side effect. The wait outcome carries only status, node key, checkpoint id, and bounded progress. Command submission validates the pre-resume Chapter revision. After the same-thread saver proves `last_applied_command_id`, its runtime callback is the only production caller allowed to persist the marker: `select` must have advanced exactly to `expected_chapter_revision + 1` and selected the command's version, while `retry_projection` must leave the revision unchanged. Pending-command preparation accepts the pre-resume state or that exact type-specific post-state so a crash between checkpoint commit and inbox apply can finish the marker without issuing a second resume.
4. **Validation & Error Matrix**: no checkpoint on resume -> reject; checkpoint not at a recognized interrupt -> reject; pending graph task and state `node_key` disagree -> fail closed; interrupt lacks checkpoint id -> fail closed; wait fence is stale -> `LeaseLostError` and no run/event update; `select` marker without the exact `revision + 1` and selected version -> reject; `retry_projection` marker after any revision change -> reject; marker callback whose checkpoint state does not contain the same command id -> do not call the inbox apply service.
5. **Good / Base / Bad**: good is a new saver/process reading the same `thread_id`, seeing the existing interrupt, and returning the same wait outcome without executing earlier bindings. Good is also a reclaimed select turn observing its already-committed finalize and only marking the inbox command applied. Base is the first invocation writing the checkpoint and then atomically releasing the root lease. Bad is returning an ordinary `JobOutcome`, holding a heartbeat while waiting for a human, applying a caller-supplied marker outside the verified runtime callback, or comparing every command to the pre-resume Chapter revision after `select` legitimately finalized a new revision.
6. **Tests Required**: assert both interrupts on a real PostgreSQL saver; close/reopen the saver between turns; assert prior binding call counts do not increase; assert checkpoint ids advance after resume; assert worker waiting clears owner/expiry/heartbeat, remains unclaimable, keeps the active run slot, emits `workflow.waiting`, and never emits success. Inject a crash after marker persistence but before inbox apply for both `select` and `retry_projection`; a new preparation/runtime turn must apply the existing marker without a second resume. Drift the selected version or revision and assert both preparation and apply fail closed.
7. **Wrong vs Correct**:

```python
# Wrong: releases the lease inside the handler, then the worker submits success with a stale fence.
await JobService(session).wait_for_resume(context.lease, workflow_transition=transition)
return JobOutcome(result={})

# Correct: the worker owns the one fenced terminal action for this execution turn.
return JobWaitOutcome(workflow_transition=transition)

# Wrong: select changed revision itself, but marker apply still requires the old revision.
assert chapter.current_revision == command.expected_chapter_revision

# Correct: validate the command-specific post-state proved by the resumed graph turn.
assert chapter.current_revision == command.expected_chapter_revision + 1
assert chapter.selected_version_id == command.payload["selected_version_id"]
```

The PostgreSQL checkpoint and SQLAlchemy root-wait transaction are separate commits. If the process stops after the checkpoint commit but before root waiting commits, a reclaimed runtime must detect the already-persisted interrupt and return the same `JobWaitOutcome`; it must not invoke the graph or reconstruct position from trace.

Graph V1 checkpoint state is a versioned object with these keys only: `workflow_version`, `state_schema_version`, `run_id`, `node_key`, `context_hash`, `activity_refs`, `result_refs`, `candidate_version_ids`, `selected_version_id`, `last_applied_command_id`, `target_chapter_revision`, and a bounded public `error_category`. Optional values are explicit `null` or empty collections; adding or changing a required key creates a new state schema and graph definition.

Model activity references use these stable names: `plan`, `candidate:<ordinal>`, `review:version_review`, and `post_review:<stage>`. Their Graph update contains only the matching `activity_refs` and `result_refs` entries. Full typed outputs never enter the checkpoint.

The command envelope is `command_id`, `type`, `payload_version`, `payload`, `expected_run_revision`, `expected_chapter_revision`, and `expected_checkpoint_id`. `retry_external` additionally requires `acknowledge_possible_duplicate=true`; no other command accepts that flag. Persisted actor identity comes from authentication, never from the request payload.

Workflow event types are limited to `workflow.started`, `workflow.phase_changed`, `workflow.waiting`, `workflow.command.accepted`, `workflow.command.rejected`, `workflow.command.applied`, `workflow.needs_attention`, `workflow.reconciled`, and `workflow.completed`. Their payload contains the normal allowlisted `task` snapshot plus an optional `workflow` object containing only `run_id`, `row_revision`, `node_key`, `status`, `checkpoint_id`, `command_id`, `command_type`, `reason_code`, `allowed_commands`, and bounded public error/progress fields. Checkpoint state, command payloads, activity payloads, prompts,正文, tokens, and exception text are never event payload fields.

## 9. Generation Trace Compatibility Projection

### 1. Scope / Trigger

Apply when changing workflow `JobEvent` retention, the generation trace compatibility
view, or worker maintenance callbacks. New workflow recovery never reads trace; trace
is a deletable view derived from retained workflow events.

### 2. Signatures

```python
await project_chapter_generation_traces(
    session: AsyncSession,
    *,
    limit: int = 200,
) -> ChapterGenerationTraceProjectionBatch

await rebuild_chapter_generation_traces(
    session: AsyncSession,
    *,
    run_id: str,
    batch_size: int = 500,
) -> int
```

Persistent identity is `(source_run_id, source_event_cursor)`. The singleton
`chapter_generation_trace_projection_checkpoints` row is named
`chapter_generation_trace_v1` and stores the last globally scanned event cursor.

### 3. Contracts

- Alembic revision `c8e5f2a1d4b6` creates and seeds the checkpoint. Runtime never
  inserts or repairs that row; a missing row fails closed.
- The projector locks the checkpoint with `FOR UPDATE SKIP LOCKED`. One transaction
  inserts allowlisted trace rows and advances the cursor; callers own commit/rollback.
- A locked checkpoint makes another worker skip the batch without waiting. Unknown or
  non-string node keys degrade to the bounded `workflow` label instead of blocking the
  global cursor.
- Trace metadata is constructed from an explicit public allowlist. Prompt, Chapter
  content, provider response, token values, command payload, checkpoint state, and raw
  exception text never enter the trace.
- JobEvent retention may delete only `cursor <=` the committed projector cursor. If
  the checkpoint is absent or paused behind an event, retention preserves that event.
- Rebuild reads retained events for one run and does not move the global checkpoint.

### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| `limit` or `batch_size` outside `1..500` | Reject before querying |
| Checkpoint row is missing | Raise and preserve every event |
| Checkpoint is locked by another worker | Skip immediately; write nothing |
| Event is not an allowlisted workflow event | Advance the scan cursor without a trace row |
| Workflow payload/run identity is invalid | Advance the scan cursor without a trace row |
| `node_key` is unknown or not a string | Project with the generic `workflow` node |
| Trace insert or cursor flush fails | Roll back both; retry from the prior cursor |
| Retention cutoff is ahead of projector cursor | Delete only through the projector cursor |

### 5. Good / Base / Bad Cases

- Good: a batch writes each `(run_id, event_cursor)` once and commits the cursor in the
  same transaction; replay inserts zero duplicates.
- Base: trace rows are deleted and rebuilt from retained JobEvents without changing
  the workflow snapshot, checkpoint, command state, or Chapter lifecycle.
- Bad: retention deletes an unprojected event, runtime seeds a missing checkpoint, or
  one malformed JSON value permanently blocks all later events.

### 6. Tests Required

- PostgreSQL integration asserts commit/rollback atomicity, duplicate replay, trace
  deletion and rebuild, and no workflow/Chapter state change.
- Assert the metadata key set and absence of prompt, content, token, provider response,
  and raw exception values.
- Use two independent connections to hold the checkpoint lock and prove the contender
  skips without blocking or inserting a duplicate.
- Feed an unhashable JSON `node_key`, assert generic projection, cursor advancement,
  and successful processing of subsequent events.
- Pause the projector behind an old event, run retention, and assert the event remains;
  after projection commits, assert retention can delete it.

### 7. Wrong vs Correct

```python
# Wrong: trace persistence and cursor progress can diverge.
await insert_traces(rows)
await session.commit()
checkpoint.last_event_cursor = events[-1].cursor

# Correct: the caller commits or rolls back both writes together.
await repository.upsert_traces(rows)
checkpoint.last_event_cursor = events[-1].cursor
await session.flush()
```

## 10. Workflow Metrics CLI

### 1. Scope / Trigger

Apply when changing Chapter workflow states, waiting transitions, commands,
checkpoint reconciliation, projection wake-up, or `python -m app.worker metrics`.
The CLI is a bounded operational snapshot, not another workflow control plane.

### 2. Signatures

```text
python -m app.worker metrics
  -> {status_counts, ..., chapter_projections, chapter_workflows}
```

`chapter_workflows` contains `window_seconds`, state and age aggregates, active and
waiting counts, command rejection type/reason counts, needs-attention counts,
`checkpoint_runs_observed`, checkpoint problem counts, projection lag, reconciler
reason counts, and stable `alerts` codes.

### 3. Contracts

- Command rejection and reconciler counts use the inclusive interval
  `created_at >= now - window_seconds`; the default window is 3600 seconds.
- Dynamic workflow status, command type, rejection reason, checkpoint problem, and
  reconciler reason values pass through fixed allowlists. Missing or unknown values
  aggregate into `unknown`; no dynamic value becomes an output key unchanged.
- Waiting count and duration include only roots currently in `BackgroundTask.waiting`
  with run status `waiting_for_selection` or `projection_pending`. Duration uses the
  latest `workflow.waiting` event whose payload status matches the run's current
  status, falling back to the run `updated_at` only when that event is absent.
- Projection lag uses the same current waiting population as waiting duration. A run
  row whose status says `projection_pending` while its root is not waiting is a
  reconciliation inconsistency, not projection lag.
- Checkpoint comparison reads only active `waiting_for_selection`,
  `projection_pending`, and `needs_attention` runs. The output reports the exact
  candidate count as `checkpoint_runs_observed`; queued/running runs are not read.
- Alert codes are stable strings. Metrics never emit run, project, chapter, job, or
  user identifiers, nor command/activity payloads, prompt/Chapter content, provider
  results, tokens, secrets, or raw exception text.

### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| `window_seconds` or an alert threshold is below 1 | Reject before querying |
| Event payload field is missing or not allowlisted | Count it in `unknown` |
| Event timestamp equals the window start | Include it |
| Historical waiting event status differs from current run status | Ignore it for current waiting age |
| Current projection run root is not `waiting` | Exclude it from projection lag |
| Resting-state checkpoint is missing, drifted, invalid, or unreadable | Count the bounded problem code and emit the matching stable alert |
| Checkpoint reader returns no evidence for a candidate | Count `checkpoint_read_unavailable` |

### 5. Good / Base / Bad Cases

- Good: a run moves from selection wait to projection wait; metrics use the latest
  projection-status waiting event and do not reuse the older selection timestamp.
- Base: a legacy/malformed retained event lacks command or reason fields; the CLI
  succeeds and adds one `unknown` count without exposing its payload.
- Bad: use `ChapterWorkflowRun.updated_at` as projection-entered time, query every
  active checkpoint, or expose arbitrary payload strings as metric labels.

### 6. Tests Required

- PostgreSQL integration covers state ages, two waiting phases on one stream,
  root/run status mismatch, needs-attention, checkpoint drift/unavailability,
  projection lag, reconciler reasons, the inclusive window boundary, and malformed
  payloads.
- Assert queued/running runs are absent from checkpoint reader candidates and
  `checkpoint_runs_observed` equals the reader input size.
- Assert unknown values remain in the `unknown` bucket and private identifiers,
  payloads, content, tokens, prompts, and error text are absent from the metrics repr.
- Worker CLI tests assert `chapter_workflows` is emitted as JSON with tuple alerts
  serialized as an array.

### 7. Wrong vs Correct

```python
# Wrong: unrelated updates reset lag and every active run triggers checkpoint I/O.
projection_age = age(run.updated_at)
checkpoint_runs = await repo.list_active_runs()

# Correct: use the matching wait transition and observe only resting states.
projection_age = waiting_state_age_seconds.get("projection_pending")
checkpoint_runs = await repo.list_checkpoint_runs_for_observability()
```

## 11. Terminal Chapter Workflow Private-State Retention

### 1. Scope / Trigger

Apply when changing terminal Chapter workflow checkpoint deletion, command/activity
private-payload scrubbing, the worker maintenance loop, or
`python -m app.worker cleanup-workflows`. This cleanup removes reproducible private
execution state after its retention window. It does not own `JobEvent`/trace
retention or Chapter projection artifact retention, and it never deletes durable
identity or audit facts.

### 2. Signatures

```python
await ChapterWorkflowCheckpointCleaner.delete_threads(
    run_ids: Sequence[str],
) -> None

PostgresChapterWorkflowCheckpointCleaner(database_url: str | URL)

ChapterWorkflowRetentionService(
    session: AsyncSession,
    *,
    checkpoint_reader: ChapterWorkflowCheckpointReader,
    checkpoint_cleaner: ChapterWorkflowCheckpointCleaner,
)

await ChapterWorkflowRetentionService.cleanup(
    *,
    before: datetime,
    limit: int = 100,
) -> ChapterWorkflowRetentionResult

await ChapterWorkflowRepository.list_retention_candidates(
    *,
    before: datetime,
    after_run_id: str | None,
    limit: int,
) -> list[ChapterWorkflowRun]

await ChapterWorkflowRepository.list_revision_workflow_stream_ids(
    *,
    chapter_id: int,
    revision: int,
) -> set[str]
```

`ChapterWorkflowRetentionResult` contains `scanned`, `cleaned_runs`,
`deleted_threads`, `scrubbed_commands`, `scrubbed_activities`,
`protected_current_revision`, and `checkpoint_unavailable`.

```text
python -m app.worker cleanup-workflows

CHAPTER_WORKFLOW_RETENTION_DAYS=<integer >= 1>             # default: 30
CHAPTER_WORKFLOW_RETENTION_BATCH_SIZE=<integer 1..500>     # default: 100
JOB_EVENT_CLEANUP_INTERVAL_SECONDS=<integer >= 60>         # default: 3600
```

The command has no cutoff or limit arguments. It requires database readiness, derives
the UTC cutoff from `CHAPTER_WORKFLOW_RETENTION_DAYS`, and uses the configured batch
size. The background workflow cleanup currently shares the JobEvent cleanup interval;
there is no separate workflow interval setting.

### 3. Contracts

- A SQL candidate is an inactive `successful|failed|cancelled|superseded` run whose
  root job is `succeeded|failed|dead_letter|cancelled`. Both completion timestamps are
  non-null and strictly older than `before`; the run has no successor and no pending
  command, and it still has a checkpoint id or private command/activity payload.
- Candidate pages use `run.id > after_run_id ORDER BY run.id LIMIT limit`. `limit` is
  the maximum number of runs actually cleaned, not the maximum number inspected.
  `scanned` includes protected or stale candidates and may therefore exceed `limit`.
  A protected prefix must not starve later eligible runs.
- The service locks root `BackgroundTask -> ChapterWorkflowRun -> Chapter ->
  commands/activities`, then revalidates identity, checkpoint id, statuses, completion
  times, successor, and pending-command state. A missing Chapter or a Chapter resolved
  by project/number whose `id` differs from `run.chapter_id` is skipped.
- If `chapter.current_revision == run.base_revision + 1`, canonical outbox lineage is
  authoritative. Missing lineage or lineage containing this run fails closed and
  increments `protected_current_revision`; lineage belonging only to another workflow
  permits the remaining checks. Independently, readable checkpoint state whose
  `target_chapter_revision` equals the current Chapter revision is protected.
- A non-marker checkpoint must be readable with the same checkpoint id and a valid
  state. Missing, unreadable, drifted, or malformed evidence increments
  `checkpoint_unavailable`. The sole recovery exception is `checkpoint_missing` after
  every private payload has already been scrubbed. A run without a checkpoint may be
  cleaned only through its remaining private payload after current-revision checks.
- Cleanup is a recoverable two-phase protocol, not a distributed transaction. Phase 1
  changes command/activity payloads to `{}` and results to `None`, writes
  `checkpoint_id="__retention_pending__"`, and commits. The cleaner then calls the
  pinned saver's real `adelete_thread` for each run. Phase 2 reacquires the rows and
  clears the marker only if it is unchanged. A failure or partial delete leaves the
  marker for an idempotent retry.
- The retention marker is terminal cleanup state. It does not reacquire the active
  slot or prevent a legitimate new run; stale commands against the old run remain
  fenced by expected checkpoint identity.
- JSON storage states are not interchangeable. Non-null request payloads use `{}` as
  the canonical scrubbed value; JSON `null` differs from `{}` and remains selectable.
  Nullable result payloads treat SQL `NULL` and JSON `null` as already empty, while an
  empty object `{}` differs from JSON `null` and remains selectable for normalization.
  SQL `NULL != value` evaluates to unknown, so predicates must use explicit JSONB
  constants rather than Python truthiness.
- Cleanup preserves the workflow run/root job, frozen context, command/activity
  identity, type, status and actor, AI usage/cost, canonical revisions and outbox,
  `JobEvent`, compatibility trace, and projection retention audit. Those records keep
  their independent retention contracts.
- The one-shot CLI emits `command`, every result counter, and `retention_days`. A
  failure emits only the bounded `worker_operation_failed` code and exits non-zero.
  In the background loop, JobEvent and workflow cleanup failures are isolated so one
  cleanup still runs when the other fails.

### 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| `before` is naive | Raise `ValueError`; query nothing |
| `limit` is outside `1..500` | Raise `ValueError`; query nothing |
| Run/job is active, non-terminal, not completed, or not older than cutoff | Exclude it |
| Run has a successor or a pending command | Exclude it |
| Locked identity, status, time, successor, command, or checkpoint differs from candidate | Skip the stale candidate |
| Chapter is missing or `chapter_id` no longer matches | Skip without deleting state |
| Canonical lineage is absent or contains this current-revision run | Protect and increment `protected_current_revision` |
| Checkpoint targets the current Chapter revision | Protect and increment `protected_current_revision` |
| Checkpoint is unreadable, missing unexpectedly, drifted, or malformed | Protect and increment `checkpoint_unavailable` |
| Marker exists but any private payload is not scrubbed | Protect and increment `checkpoint_unavailable` |
| Evidence reports `checkpoint_missing` and all payloads are scrubbed | Continue the recovery protocol |
| Thread deletion fails or only a prefix was deleted | Propagate the error; retain markers for retry |
| No candidates remain | Return all-zero counters without saver deletion |

### 5. Good / Base / Bad Cases

- Good: an old terminal run that does not own the current revision has its private
  payloads scrubbed and checkpoint thread deleted while every durable audit row stays.
- Base: protected runs occupy the first keyset page; scanning advances past them,
  `scanned > limit`, and a later eligible run is still cleaned.
- Base: a process stops after phase 1 or after deleting only some threads. The next
  cleanup observes the marker, repeats idempotent thread deletion, and clears markers
  only after the delete call succeeds.
- Bad: delete an active/needs-attention/current-revision run, treat trace as recovery
  evidence, delete outbox/usage/audit rows, or claim saver and SQL writes are atomic.

### 6. Tests Required

- PostgreSQL integration covers private-payload scrubbing plus preservation of frozen
  context, root payload, identity/status/actor, AI usage/cost, outbox, `JobEvent`, and
  projection audit; rerunning cleanup must inspect no already-cleaned candidate.
- Cover active, needs-attention, recent, pending-command, successor, checkpoint
  unavailable, checkpoint-target-current, and canonical-lineage current-revision
  protection, including current revision after its checkpoint has disappeared.
- Put protected run ids before an eligible id, set `limit=1`, and assert
  `scanned == 2`, one cleaned run, and no starvation.
- Inject delete failure and partial multi-thread deletion; assert phase-1 markers and
  scrubbed payloads persist, then assert retry clears every marker without duplicating
  durable audit facts.
- Persist SQL `NULL`, JSON `null`, and `{}` result payloads in PostgreSQL. Assert their
  storage predicates differ and only `{}` keeps an otherwise payload-only run in the
  candidate query.
- Use the Alembic-installed real `AsyncPostgresSaver`, write a target and sentinel
  thread, call real `adelete_thread`, and assert all target checkpoint tables are empty
  while the sentinel tuple and row counts remain.
- Worker tests assert UTC cutoff and batch configuration injection, bounded CLI JSON,
  database readiness, and independent JobEvent/workflow cleanup failure handling.

### 7. Wrong vs Correct

```python
# Wrong: an external delete cannot share the SQLAlchemy transaction. If the later
# commit fails, the checkpoint is gone while private SQL payloads remain unmarked.
await checkpoint_cleaner.delete_threads([run.id])
scrub_private_payloads(run)
await session.commit()

# Correct: commit recoverable intent first, then finish an idempotent external delete.
scrub_private_payloads(run)
run.checkpoint_id = "__retention_pending__"
await session.commit()

await checkpoint_cleaner.delete_threads([run.id])
locked_run = await lock_run_again(run.id)
if locked_run.checkpoint_id == "__retention_pending__":
    locked_run.checkpoint_id = None
await session.commit()
```
