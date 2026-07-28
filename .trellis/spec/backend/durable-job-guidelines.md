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

### HTTP and SSE boundary

```text
GET /api/tasks?limit=<1..50>
GET /api/tasks/{task_id}
GET /api/tasks/snapshot?limit=<1..50>[&stream_type=<job|workflow>&stream_id=<id>]
GET /api/tasks/events?limit=<1..50>[&cursor=<non-negative>][&stream_type=<job|workflow>&stream_id=<id>]
Last-Event-ID: <same value as cursor when both are present>
```

SSE events are `snapshot`, `task`, `reset`, and a sanitized terminal `error`. A `task` event uses the durable `JobEvent.cursor` as the SSE `id`.

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

### External side-effect contract

- `transactional`: the outcome writer executes inside the fenced PostgreSQL success transaction.
- `idempotent_external`: persist an activity intent first, pass the stable provider request key to the provider, and upsert the result by activity key.
- `ambiguous_external`: if the call may have happened but no durable result exists, stop automatic replay and move the job to `needs_attention`/`dead_letter`.
- Database fencing guarantees one valid database outcome writer. It never proves an external provider call happened exactly once and cannot undo a call made by a stale process.

### Public projection and event stream contract

- Task list, snapshot, and SSE task payloads use the same allowlisted public projection. They never populate `payload` or `result` (the serializer may return `null` or omit those optional fields). Writers sanitize public `error` and `log_entries` before persistence; projections forward those stored public fields rather than raw exception objects.
- Task detail uses the same projection and may include the result for the owning user. It still hides the input payload.
- Public error/log text is length-bounded and secret-redacted before it enters the current row or append-only event.
- `stream_type` and `stream_id` are optional as a pair and invalid separately. A scoped snapshot/SSE request authorizes the stream against the current user before streaming headers are returned. Missing and foreign streams both return 404.
- Snapshot tasks and `resume_cursor` come from one database snapshot. A scoped snapshot also binds `snapshot_revision` to the stream sequence and cursor.
- PostgreSQL event rows are the source of truth. Redis only wakes readers; missing, duplicated, disconnected, or restarted Redis cannot change ordering or recovery.
- `cursor` and `Last-Event-ID` must agree. Events with `cursor <= current_cursor` are ignored by the client. When retention emits `reset {reason: "cursor_expired", retained_through_cursor}`, the client obtains a new snapshot pair for the same scope, replaces local state/cursor, then reconnects.
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
| Only one of `stream_type` / `stream_id` is supplied | HTTP 400 |
| Stream is absent or owned by another user | HTTP 404 with the same public message |
| `Last-Event-ID` is negative/non-integer, or differs from `cursor` | HTTP 400 before streaming |
| `cursor` query is negative/non-integer | Reject through FastAPI request validation before streaming |
| Cursor is older than retention watermark | Emit one typed `reset`, then close the stream |
| Redis is unavailable | Continue PostgreSQL polling and emit keepalives |
| Event lacks an allowlisted public task snapshot | Log internally and emit only a sanitized SSE error |

## 5. Good / Base / Bad Cases

- Good: process A claims attempt 1 and is terminated; after lease expiry process B claims attempt 2 with a higher fencing token, appends `job.reclaimed`, and is the only process allowed to commit the terminal outcome.
- Good: an idempotent provider call times out after reaching the provider; the retry reuses the provider request key and records one canonical activity result.
- Base: Redis is disabled. Worker scans and SSE database polling still deliver ordered transitions, with higher latency but identical state.
- Base: a client reconnects with the last durable cursor and receives only later events in ascending cursor order.
- Bad: treating a Redis notification as the task event, accepting a result without a lease token, or retrying an ambiguous provider call because the database row has no result.
- Bad: returning ORM `payload`/`result` directly from task list/SSE or resuming a reset stream without fetching a new snapshot pair.

## 6. Tests Required

- PostgreSQL integration: concurrent workers claim one eligible row once; a stale fencing token cannot heartbeat, write progress, complete, fail, or cancel it.
- Real process recovery: process A claims and is terminated by the OS; process B starts independently, waits for lease expiry, reclaims, and completes. Assert attempt increment, fencing increment, `job.queued -> job.started -> job.reclaimed -> job.succeeded` event order, and final owner cleanup.
- Retry matrix: retry/backoff, permanent failure, max-attempt dead-letter, cancellation, unknown payload version, and inactive generation.
- External activity: crash-after-provider-call-before-result is tested separately for provider dedupe and ambiguous dead-letter. Never use a transactional-only test as evidence of external exactly-once behavior.
- Enqueue: concurrent identical keys return one canonical row/outcome; mismatched canonical inputs fail without a duplicate.
- Event log: state/event atomicity, global cursor order, stream-local sequence uniqueness, owner filtering, retention cleanup, and reset watermark.
- Snapshot/SSE: snapshot/event race has no gap; reconnect deduplicates; query/header mismatch fails; foreign stream is indistinguishable from missing; Redis-off polling passes.
- Projection: list, snapshot, SSE, and detail assert that private payload is absent; list/snapshot/SSE also assert result is absent and error text is sanitized.
- Frontend: reducer ignores old cursors, reset refetches the same scope before reconnect, identity/scope change clears cursor, and the 15-second polling fallback remains.

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
