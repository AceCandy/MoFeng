<!-- AIMETA P=章节工作流发布与回滚演练证据|R=公开关联标识关系与去重计数|NR=不记录连接串_密钥或私有payload|E=gate_true_rollout,gate_false_rollback|X=internal|A=verification_record|D=pytest,postgresql|S=docs|RD=../design.md -->
# Rollout / Rollback Drill

Recorded: 2026-07-31

## Environment

- Tests used the configured local PostgreSQL service to create isolated temporary databases.
- No connection string, credential, private request payload or provider response is recorded here.
- The compatibility HTTP test module passed all 8 tests.

## Gate Enabled Rollout

Test: `test_rollout_gate_open_shares_one_owner_across_legacy_and_new_http`

Public correlation evidence:

- the legacy generate response `id` equals the new current snapshot `root_job_id`;
- the current connection `events_url` ends with the same snapshot `run_id`;
- fixed command id `77777777-7777-4777-8777-777777777777` is accepted once and belongs to that `run_id`;
- the durable run and command share the same `run_id`, and the run retains the same `root_job_id`;
- finalize replay returns the same canonical target revision.

Persisted counts after finalize replay:

```text
ChapterWorkflowRun       1
ChapterWorkflowCommand   1
ChapterRevision          1
ChapterOutboxEvent       1
chapter_workflow jobs    1
chapter_outbox_dispatch  1
chapter_generation jobs  0
```

The selected chapter version, canonical revision and outbox workflow stream all correlate to the same durable run.

## Gate Disabled Rollback

Test: `test_rollback_gate_closed_drains_active_owner_without_duplicate_outcome`

Public correlation evidence:

- an active durable run is created before the start gate is disabled;
- the previous-frontend generate facade and both replayed select calls return the existing `root_job_id`;
- idempotency key `previous-frontend-select-1` maps both select requests to one command identity;
- the command belongs to the existing `run_id`;
- finalize replay returns the same canonical target revision.

Persisted counts after finalize replay are identical to the rollout case: one run, one command, one canonical revision, one outbox event, one workflow root job, one outbox dispatch job and zero legacy `chapter_generation` jobs.

## Verification

```text
focused rollout/rollback: 2 passed
compatibility HTTP module: 8 passed
ruff focused check:        passed
black focused check:       passed
```
