# Replayable Chapter Projection Contract

## 1. Scope / Trigger

Apply this contract whenever code creates, dispatches, replays, executes, reconciles,
or tombstones a Chapter projection, records its AI usage, or purges inactive derived
artifacts. It covers the canonical revision, immutable outbox lineage,
projection-domain rows, rollout fencing, telemetry, retention audit, and their
interaction with the durable job runtime.

This contract prevents three failure classes: a projection running from a forged or
drifted outbox identity, a replay deriving a job from rows observed at different
times, and deadlocks caused by aggregate writers acquiring the same rows in
different orders.

## 2. Signatures

```python
validate_finalize_outbox_event(
    event: FinalizeOutboxEvent,
) -> tuple[ChapterFinalizeOutboxPayload | None, FinalizeOutboxValidationError | None]

await load_current_projection(
    session,
    *,
    payload: ChapterProjectionJobPayload,
    user_id: int,
    job_id: str,
    expected_projection: str,
    for_update: bool,
) -> CurrentProjection | None
```

Live aggregate lock order:

```text
operator replay: User(project owner + operator, id ASC) -> Chapter
                 -> ChapterOutboxEvent -> ChapterRevision
                 -> ChapterProjectionRollout -> ChapterProjectionRun(id ASC)
dispatcher/runtime: Chapter -> ChapterOutboxEvent -> ChapterRevision
                    -> ChapterProjectionRollout -> ChapterProjectionRun
rollout transition: Chapter -> ChapterProjectionRollout
retention purge: User -> Chapter -> ChapterRevision
                 -> ChapterProjectionRun(id ASC) -> inactive artifact(id ASC)
```

Deleted aggregate lock order:

```text
ChapterOutboxEvent -> tombstone ChapterRevision -> target ChapterRevision
                   -> ChapterProjectionRun
```

The durable worker outcome path may lock `BackgroundTask -> Chapter`. A transaction
that already owns Chapter must not then lock a legacy BackgroundTask row; rollout
checks read legacy job state at READ COMMITTED without adding the reverse edge.

## 3. Contracts

- `ChapterOutboxEvent` is immutable lineage, not a queue state row. Producers,
  dispatcher, replay operations, and runtime consumers share one event type/version,
  canonical JSON fingerprint, and finalize envelope validator.
- A live projection transaction first locks Chapter. Every live writer then follows
  the aggregate lock order above; skipping a row is allowed, reversing two rows is
  not. A deleted Chapter has no stable Chapter row, so tombstone work uses its
  immutable outbox event as the first lock.
- Replay loads and locks the complete scope once. Eligibility, audit response,
  `ChapterProjectionRun`, and durable job payload are all derived from that snapshot;
  no helper may re-query runs or rollout state after the decision.
- Runtime acceptance validates both sides of the lineage: the stored event must pass
  type/version/fingerprint/envelope validation, and the durable job payload must
  match its project, chapter, revision, source hash/generation, workflow stream,
  rollout owner/generation/fencing token, execution mode, and outbox event id.
- Projection rows contain domain identity and outcomes only. `BackgroundTask` and
  `JobService` remain the sole owners of claim, lease, retry, attempt, executor
  generation, and fencing authority.
- External LLM/vector work runs without an open database transaction. Fenced outcome
  writers reopen a short transaction and re-run the current projection guard before
  activating any artifact.
- A canonical source or rollout fence mismatch returns stale/rejected behavior and
  creates no active artifact. Replays append a new run/attempt and never overwrite
  historical runs or the original outbox fact.
- Every completed projection AI activity persists provider/model/stage identity,
  normalized token usage, usage completeness, and an explicit known/unknown cost
  envelope. Cost is known only when `cost_known`, amount, and currency agree. Metrics
  count only external side-effect classes, bucket unknown status/reason strings, and
  never aggregate different currencies.
- Retention is an explicit admin command, never a background cascade. It accepts only
  `rag` or non-manual `foreshadowing`, resolves one exact project/chapter/revision/
  artifact generation, and requires the revision lifecycle to be `superseded` or
  `tombstoned`. `legacy`, current, active, in-progress, and manual artifacts are
  protected.
- Purge locks inactive candidate ids before the active-state check. DELETE repeats
  project, chapter, revision, generation, inactive, and manual-protection predicates;
  a row-count mismatch rolls back as `artifact_state_changed`. Preview, rejection,
  and completed purge append bounded, idempotent audit records. Canonical revisions,
  outbox, projection runs, and retention audit are never purge targets.
- Alembic head `f2a6c9d4e8b1` is expand-only. Its AI usage and retention audit data have
  no destructive downgrade; binary rollback keeps the schema and must pass
  `db-check` rollback-floor validation.

## 4. Validation & Error Matrix

| Condition | Required result |
|-----------|-----------------|
| Event type/version differs from the shared contract | Reject as event contract mismatch |
| Stored payload is not an object or fails Pydantic validation | Reject as invalid finalize outbox |
| Canonical JSON differs from `payload_fingerprint` | Reject as payload mismatch |
| Envelope id/project/aggregate/chapter/revision/stream differs from payload | Reject as identity mismatch |
| Job outbox id or workflow stream differs from the validated event | Runtime returns stale; no outcome commit |
| Chapter revision/hash/generation or tombstone watermark differs | Runtime returns stale; no active artifact |
| Rollout owner/generation/fencing token differs | Replay rejects or runtime returns stale |
| Existing projection is queued/running/retry_wait | Replay rejects with `projection_in_progress` |
| Summary dependency is absent, cross-revision, inactive, or not succeeded | Downstream projection cannot run |
| Two lock waiters serialize in either order | Both finish without deadlock; final state matches the winning order |
| Retention operator is missing, inactive, or not admin | Reject as `operator_not_found` / `operator_not_authorized` |
| Retention revision is current, legacy, active, in progress, or not retirable | Reject with the corresponding stable protection code; delete nothing |
| Retention target exceeds `max_rows` or has no inactive artifacts | Reject as `retention_batch_too_large` / `no_inactive_artifacts` |
| A candidate becomes active or otherwise changes before DELETE | Roll back all deletes as `artifact_state_changed` |
| AI usage is incomplete or cost lacks amount/currency | Preserve as unknown/incomplete, alert, and exclude it from known cost totals |
| F2 downgrade is requested | Refuse; retain usage/retention audit and use the binary rollback floor |
| Isolated PostgreSQL setup fails after schema creation | Dispose any created engine, drop the random schema, and leave no `test_*` namespace |
| Fresh test schema resolves existing tables through `public` | Create all metadata with `checkfirst=False` and fail unless the qualified schema table count matches metadata |

## 5. Good / Base / Bad Cases

- Good: two administrators replay the same Chapter from independent PostgreSQL
  connections. Both wait on the Chapter lock; one creates a queued run/job and the
  other observes it after lock acquisition and returns `projection_in_progress`.
- Good: replay queues a job with rollout fence N, then rollout advances to N+1. The
  queued job remains audit history but runtime rejects it before any projection write.
- Base: a duplicate dispatcher invocation validates the same immutable event and
  returns the existing deterministic job/run.
- Base: a late tombstone uses the outbox event as its stable entry and can only remove
  the exact target revision/generation named by the event.
- Good: retention preview identifies one inactive RAG generation; purge revalidates
  the same revision/generation and atomically removes only those inactive rows while
  retaining the audit.
- Base: pricing or provider usage is unavailable. The activity still completes, but
  usage/cost remains explicitly unknown and blocks a cost-gated cutover delta.
- Bad: validating only revision/run identity while ignoring `outbox_event_id` and
  payload fingerprint.
- Bad: loading a replay scope, releasing the aggregate lock, and re-querying rollout
  or dependency state while building the job payload.
- Bad: a rollout transaction locks Chapter and then a legacy BackgroundTask row,
  creating the reverse of the worker outcome order.
- Bad: a test fixture creates its random PostgreSQL schema before entering the
  cleanup scope, so a table-creation or seed failure leaks the schema.
- Bad: `create_all(checkfirst=True)` runs with `search_path=<random>,public`;
  SQLAlchemy sees public tables, skips DDL, and the test silently writes public.
- Bad: deleting all artifacts by chapter number, purging a manual foreshadowing, or
  treating missing amount/currency as zero cost.

## 6. Tests Required

- Unit tests cover all finalize validator classifications and replay reason-code
  mappings without database mocks hiding payload drift.
- PostgreSQL integration tests use independent `AsyncSession` connections for lock,
  fencing, and race claims. The shared savepoint-backed `db_session_factory` is not
  concurrency evidence.
- A deterministic race test holds the Chapter row in a third transaction, starts all
  competitors, and uses `pg_blocking_pids` to prove every competitor is in the same
  known wait queue before releasing the lock. `asyncio.gather` alone is insufficient.
- Concurrent replay asserts one queued response, one `projection_in_progress`, one
  new durable job, and one queued replay run.
- Replay versus rollout asserts no deadlock and either: rollout wins and replay
  creates no job, or replay wins and the queued old-fence job fails the runtime guard.
- Runtime tests start from a valid event/job lineage, then independently drift the
  outbox id, workflow stream, stored payload, revision, and rollout fence.
- Retention integration tests cover active/inactive admin, exact
  `chapter_revision_id` scoping, legacy/current/manual/active/in-progress protection,
  batch bounds, idempotency, and transaction rollback when candidate state changes.
- Metrics tests prove transactional activities do not enter external counts, unknown
  status/reason values use bounded buckets, malformed cost envelopes are unknown,
  incomplete usage alerts, and per-currency totals remain separate.
- Migration tests cover empty and current databases, ORM/schema convergence for F2
  columns/constraints/indexes, preserved audit rows after refused downgrade, one
  Alembic head, and `db-check` rollback-floor behavior.
- Tests that commit through independent connections run in a randomly named isolated
  PostgreSQL database or schema. Cleanup ownership begins before schema/database
  creation, covers table-creation and seed failures, and disposes/terminates all test
  connections before `DROP DATABASE` or `DROP SCHEMA ... CASCADE`. A fault-injection
  test or equivalent verification asserts no random namespace remains. A fresh
  schema uses `create_all(checkfirst=False)` and asserts its qualified table count
  equals `Base.metadata.tables`; public-table fallback or shared-library DELETE
  cleanup is not the isolation boundary.

## 7. Wrong vs Correct

Wrong:

```python
revision = await lock_revision()
outbox = await lock_outbox()
runs = await query_runs()       # another live path locks outbox before revision
payload = build_job(await query_rollout())
```

Correct:

```python
chapter = await lock_chapter()
outbox = await lock_and_validate_outbox()
revision = await lock_revision()
rollout = await lock_rollout()
runs = await lock_runs_ordered_by_id()

decision = describe_from_locked_scope(chapter, outbox, revision, rollout, runs)
job_payload = build_job_from_locked_scope(decision)
```
