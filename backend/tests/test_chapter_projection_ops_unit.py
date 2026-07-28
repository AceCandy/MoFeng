from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.api.routers import chapter_projections as projection_router
from app.api.routers import writer as writer_router
from app.schemas.chapter_projection import ChapterProjectionOperationRequest
from app.schemas.job import ChapterProjectionJobPayload
from app.services import chapter_projection_handlers as projection_handlers
from app.services import chapter_projection_service as projection_service_module
from app.services.chapter_ingest_service import PreparedChapterIngestion
from app.services.chapter_projection_handlers import _run_activity
from app.services.chapter_projection_ops import (
    ChapterProjectionConflictError,
    ChapterProjectionNotFoundError,
    ChapterProjectionOpsService,
    ChapterProjectionRateLimitError,
)
from app.services.chapter_projection_rollout import (
    ChapterProjectionRolloutConflictError,
    ChapterProjectionRolloutService,
    evaluate_rollout_gate,
    validate_rollout_owner_state,
    validate_rollout_transition,
)
from app.services.chapter_projection_service import (
    ChapterFinalizeConflictError,
    ChapterProjectionService,
)
from app.services.job_service import AmbiguousActivityError
from app.services.job_worker import PermanentJobError, RetryableJobError
from app.utils.ai_telemetry import AICallResult, TokenUsage, combine_ai_call_results


PROJECT_ID = "11111111-1111-1111-1111-111111111111"
REVISION_ID = "22222222-2222-2222-2222-222222222222"
RUN_ID = "33333333-3333-3333-3333-333333333333"
GENERATION = "44444444-4444-4444-4444-444444444444"
WORKFLOW_ID = "workflow-1"
OUTBOX_ID = "55555555-5555-5555-5555-555555555555"


def _request(projection_name: str = "memory") -> ChapterProjectionOperationRequest:
    return ChapterProjectionOperationRequest(
        project_id=PROJECT_ID,
        chapter_id=7,
        revision=2,
        projection_name=projection_name,
        idempotency_key="operation-1",
        reason="repair failed projection",
        outbox_event_id=OUTBOX_ID,
    )


def _eligibility_objects():
    chapter = SimpleNamespace(
        current_revision=2,
        tombstone_revision=0,
        source_hash="a" * 64,
        projection_generation=GENERATION,
    )
    revision = SimpleNamespace(
        revision=2,
        source_hash="a" * 64,
        source_generation=GENERATION,
        lifecycle="finalizing",
        required_projections=["summary", "memory", "foreshadowing"],
    )
    outbox = SimpleNamespace(revision=2)
    rollout = SimpleNamespace(owner="projection", state="projection")
    dependency = SimpleNamespace(id="summary-run")
    return chapter, revision, outbox, rollout, dependency


def test_projection_eligibility_rejects_stale_tombstone_and_wrong_rollout() -> None:
    chapter, revision, outbox, rollout, dependency = _eligibility_objects()
    kwargs = {
        "request": _request(),
        "chapter": chapter,
        "revision": revision,
        "outbox": outbox,
        "rollout": rollout,
        "previous": None,
        "dependency": dependency,
        "active_projections": ["summary"],
    }

    assert ChapterProjectionOpsService._eligibility_reason(**kwargs) is None

    chapter.current_revision = 3
    assert ChapterProjectionOpsService._eligibility_reason(**kwargs) == "stale_revision"
    chapter.current_revision = 2
    chapter.tombstone_revision = 2
    assert ChapterProjectionOpsService._eligibility_reason(**kwargs) == "tombstoned_revision"
    chapter.tombstone_revision = 0
    rollout.owner = "legacy"
    assert ChapterProjectionOpsService._eligibility_reason(**kwargs) == "rollout_owner_mismatch"


def test_projection_eligibility_enforces_dependency_and_reconcile_gate() -> None:
    chapter, revision, outbox, rollout, _dependency = _eligibility_objects()
    common = {
        "chapter": chapter,
        "revision": revision,
        "outbox": outbox,
        "rollout": rollout,
        "previous": None,
    }

    assert (
        ChapterProjectionOpsService._eligibility_reason(
            request=_request("memory"),
            dependency=None,
            active_projections=["summary"],
            **common,
        )
        == "summary_dependency_missing"
    )
    assert (
        ChapterProjectionOpsService._eligibility_reason(
            request=_request("reconcile"),
            dependency=None,
            active_projections=["summary", "memory"],
            **common,
        )
        == "required_projection_gate_not_satisfied"
    )


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        ("legacy", "shadow"),
        ("shadow", "draining"),
        ("shadow", "legacy"),
        ("draining", "projection"),
        ("draining", "shadow"),
        ("projection", "legacy"),
    ],
)
def test_rollout_state_machine_allows_only_declared_edges(
    from_state: str,
    to_state: str,
) -> None:
    validate_rollout_transition(from_state, to_state)


@pytest.mark.parametrize(
    ("from_state", "to_state"),
    [
        ("legacy", "projection"),
        ("shadow", "projection"),
        ("projection", "shadow"),
        ("legacy", "draining"),
    ],
)
def test_rollout_state_machine_rejects_skipped_or_reverse_edges(
    from_state: str,
    to_state: str,
) -> None:
    with pytest.raises(ChapterProjectionRolloutConflictError) as captured:
        validate_rollout_transition(from_state, to_state)
    assert captured.value.code == "illegal_rollout_transition"


@pytest.mark.parametrize(
    ("owner", "state"),
    [
        ("legacy", "legacy"),
        ("legacy", "shadow"),
        ("legacy", "draining"),
        ("projection", "projection"),
    ],
)
def test_rollout_owner_state_accepts_only_single_writer_pairs(
    owner: str,
    state: str,
) -> None:
    validate_rollout_owner_state(owner, state)


@pytest.mark.parametrize(
    ("owner", "state"),
    [
        ("projection", "legacy"),
        ("projection", "shadow"),
        ("projection", "draining"),
        ("legacy", "projection"),
        ("unknown", "projection"),
    ],
)
def test_rollout_owner_state_rejects_split_brain_pairs(
    owner: str,
    state: str,
) -> None:
    with pytest.raises(ChapterProjectionRolloutConflictError) as captured:
        validate_rollout_owner_state(owner, state)
    assert captured.value.code == "rollout_owner_state_invalid"


def test_rollout_manifest_ids_reject_duplicates() -> None:
    with pytest.raises(ChapterProjectionRolloutConflictError) as captured:
        ChapterProjectionRolloutService._manifest_ids(
            {"ids": [1, 1]},
            "ids",
            int,
        )
    assert captured.value.code == "rollback_manifest_invalid"


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_value", [None, "invalid", [], {}])
async def test_rollout_manifest_rejects_invalid_revision_before_database_access(
    invalid_value,
) -> None:
    session = SimpleNamespace(execute=AsyncMock(side_effect=AssertionError("unexpected query")))
    service = ChapterProjectionRolloutService(session)
    chapter = SimpleNamespace(current_revision=1)
    rollout = SimpleNamespace(
        generation=2,
        rollback_manifest={
            "revision": invalid_value,
            "projection_rollout_generation": 2,
        },
    )

    with pytest.raises(ChapterProjectionRolloutConflictError) as captured:
        await service._restore_legacy_artifacts(chapter=chapter, rollout=rollout)

    assert captured.value.code == "rollback_manifest_invalid"
    session.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_finalize_rejects_draining_rollout_with_domain_conflict(monkeypatch) -> None:
    rollout_service = SimpleNamespace(
        ensure_projection_rollout=AsyncMock(
            return_value=SimpleNamespace(owner="legacy", state="draining")
        )
    )
    monkeypatch.setattr(
        projection_service_module,
        "ChapterProjectionRolloutService",
        lambda _session: rollout_service,
    )
    service = ChapterProjectionService(SimpleNamespace())
    service._lock_revision_state = AsyncMock(return_value=(1, None))

    with pytest.raises(ChapterProjectionRolloutConflictError) as captured:
        await service.create_finalize(
            chapter=SimpleNamespace(id=7),
            selected_version=SimpleNamespace(id=8),
            source_content="正文",
            source_hash="a" * 64,
            user_id=1,
            skip_vector_update=True,
            idempotency_key="finalize-1",
        )

    assert captured.value.code == "rollout_finalize_unavailable"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_error", "expected_status", "expected_detail"),
    [
        (
            ChapterFinalizeConflictError(
                "finalize_idempotency_conflict",
                "定稿幂等键冲突",
            ),
            409,
            "定稿幂等键冲突",
        ),
        (
            ChapterProjectionRolloutConflictError("rollout_finalize_unavailable"),
            409,
            "rollout_finalize_unavailable",
        ),
        (ValueError("idempotency_key 不能为空"), 400, "idempotency_key 不能为空"),
    ],
)
async def test_writer_finalize_maps_only_domain_conflicts_to_409(
    monkeypatch,
    service_error,
    expected_status,
    expected_detail,
) -> None:
    submission = SimpleNamespace(submit=AsyncMock(side_effect=service_error))
    monkeypatch.setattr(
        writer_router,
        "ChapterFinalizeSubmissionService",
        lambda _session: submission,
    )

    with pytest.raises(HTTPException) as captured:
        await writer_router._enqueue_chapter_finalize(
            session=SimpleNamespace(),
            project_id=PROJECT_ID,
            chapter_number=1,
            user_id=1,
            selected_version_id=2,
        )

    assert captured.value.status_code == expected_status
    assert captured.value.detail == expected_detail


def test_rollout_gate_requires_elapsed_window_current_match_and_zero_failures() -> None:
    now = datetime.now(timezone.utc)
    ready = evaluate_rollout_gate(
        state="shadow",
        now=now,
        observation_deadline_at=now,
        required_observations=2,
        successful_observations=2,
        failed_observations=0,
        latest_outcome="match",
        latest_revision=3,
        current_revision=3,
        shadow_diff={"unexplained_count": 0},
    )
    assert ready.ready
    assert ready.reasons == ()

    blocked = evaluate_rollout_gate(
        state="shadow",
        now=now,
        observation_deadline_at=now + timedelta(seconds=1),
        required_observations=2,
        successful_observations=1,
        failed_observations=1,
        latest_outcome="mismatch",
        latest_revision=2,
        current_revision=3,
        shadow_diff={"unexplained_count": 1},
    )
    assert not blocked.ready
    assert set(blocked.reasons) == {
        "observation_window_not_elapsed",
        "insufficient_shadow_observations",
        "shadow_observation_failed",
        "current_revision_not_observed",
        "shadow_diff_gate_failed",
    }
class _ActivityContext:
    def __init__(self) -> None:
        self.failed: list[dict[str, object]] = []
        self.ambiguous = False
        self.completed: list[dict[str, object]] = []

    async def begin_activity(self, _key, *, request_payload):
        return SimpleNamespace(
            should_execute=True,
            result=None,
            provider_request_key="provider-key",
        )

    async def mark_activity_failed(self, _key, **kwargs) -> None:
        self.failed.append(kwargs)

    async def mark_activity_ambiguous(self, _key, **_kwargs) -> None:
        self.ambiguous = True
        raise AmbiguousActivityError("ambiguous")

    async def complete_activity(self, _key, **kwargs) -> None:
        self.completed.append(kwargs)


class _HandlerContext(_ActivityContext):
    def __init__(self) -> None:
        super().__init__()
        self.lease = SimpleNamespace(
            payload=_job_payload().model_dump(mode="json"),
            project_id=PROJECT_ID,
            user_id=1,
            job_id="projection-job",
            attempt=1,
            fencing_token=1,
            executor_generation=1,
        )
        self.progress_updates: list[tuple[str, int | None]] = []

    def session_factory(self):
        class SessionContext:
            async def __aenter__(self):
                return SimpleNamespace()

            async def __aexit__(self, exc_type, exc, traceback):
                return False

        return SessionContext()

    async def progress(self, message: str, *, progress=None) -> None:
        self.progress_updates.append((message, progress))


def _job_payload() -> ChapterProjectionJobPayload:
    return ChapterProjectionJobPayload(
        project_id=PROJECT_ID,
        chapter_id=7,
        chapter_number=2,
        chapter_revision_id=REVISION_ID,
        revision=2,
        source_hash="a" * 64,
        source_generation=GENERATION,
        projection_run_id=RUN_ID,
        artifact_generation=GENERATION,
        workflow_stream_id=WORKFLOW_ID,
        outbox_event_id=OUTBOX_ID,
    )


@pytest.mark.asyncio
async def test_projection_activity_classifies_retryable_provider_error() -> None:
    context = _ActivityContext()

    class ProviderUnavailable(RuntimeError):
        status_code = 503

    async def call():
        raise ProviderUnavailable("private")

    with pytest.raises(RetryableJobError) as captured:
        await _run_activity(
            context,
            _job_payload(),
            activity_key="summary_generation",
            request_payload={},
            call=call,
        )

    assert captured.value.category == "provider_retryable_error"
    assert context.failed == [
        {
            "provider_request_key": "provider-key",
            "error_category": "provider_retryable_error",
            "retryable": True,
        }
    ]
    assert not context.ambiguous


@pytest.mark.asyncio
async def test_projection_activity_classifies_permanent_local_error() -> None:
    context = _ActivityContext()

    async def call():
        raise ValueError("private")

    with pytest.raises(PermanentJobError) as captured:
        await _run_activity(
            context,
            _job_payload(),
            activity_key="memory_parse",
            request_payload={},
            call=call,
        )

    assert captured.value.category == "projection_activity_invalid"
    assert context.failed[0]["retryable"] is False
    assert not context.ambiguous


@pytest.mark.asyncio
async def test_projection_activity_preserves_ambiguous_timeout() -> None:
    context = _ActivityContext()

    async def call():
        raise TimeoutError("private")

    with pytest.raises(AmbiguousActivityError):
        await _run_activity(
            context,
            _job_payload(),
            activity_key="rag_embedding",
            request_payload={},
            call=call,
        )

    assert context.ambiguous
    assert context.failed == []


@pytest.mark.asyncio
async def test_projection_activity_persists_ai_call_with_business_result() -> None:
    context = _ActivityContext()
    ai_call = AICallResult(
        value={"response": "summary"},
        provider_type="openai_compatible",
        model="chat-model",
        model_id=12,
        stage="summary_memory",
        usage=TokenUsage(
            input_tokens=10,
            output_tokens=2,
            total_tokens=12,
            cached_input_tokens=0,
            cache_write_input_tokens=0,
            reasoning_tokens=0,
            is_complete=True,
        ),
        cost_amount="0.000026",
        cost_currency="USD",
        cost_unknown_reason=None,
    )

    async def call():
        return ai_call

    result = await _run_activity(
        context,
        _job_payload(),
        activity_key="summary_generation",
        request_payload={},
        call=call,
    )

    assert result == {"response": "summary"}
    assert context.completed == [
        {
            "provider_request_key": "provider-key",
            "result": {"response": "summary"},
            "ai_call": ai_call,
        }
    ]


def test_ai_call_aggregation_sums_complete_usage_and_cost() -> None:
    first = AICallResult(
        value=[0.1],
        provider_type="openai_compatible",
        model="embedding-model",
        model_id=9,
        stage="rag_embedding",
        usage=TokenUsage(10, 0, 10, 0, 0, 0, True),
        cost_amount="0.000002",
        cost_currency="USD",
        cost_unknown_reason=None,
    )
    second = AICallResult(
        value=[0.2],
        provider_type="openai_compatible",
        model="embedding-model",
        model_id=9,
        stage="rag_embedding",
        usage=TokenUsage(5, 0, 5, 0, 0, 0, True),
        cost_amount="0.000001",
        cost_currency="USD",
        cost_unknown_reason=None,
    )

    combined = combine_ai_call_results({"projection": {}}, [first, second])

    assert combined.value == {"projection": {}}
    assert combined.usage == TokenUsage(15, 0, 15, 0, 0, 0, True)
    assert combined.cost_amount == "0.000003"
    assert combined.cost_currency == "USD"
    assert combined.cost_unknown_reason is None


def test_ai_call_aggregation_propagates_unknown_and_rejects_identity_drift() -> None:
    known = AICallResult(
        value=[0.1],
        provider_type="openai_compatible",
        model="embedding-model",
        model_id=9,
        stage="rag_embedding",
        usage=TokenUsage(10, 0, 10, 0, 0, 0, True),
        cost_amount="0.000002",
        cost_currency="USD",
        cost_unknown_reason=None,
    )
    unknown = AICallResult(
        value=[0.2],
        provider_type="openai_compatible",
        model="embedding-model",
        model_id=9,
        stage="rag_embedding",
        usage=TokenUsage(),
        cost_amount=None,
        cost_currency="USD",
        cost_unknown_reason="usage_unavailable",
    )

    combined = combine_ai_call_results({}, [known, unknown])
    assert not combined.usage.is_complete
    assert combined.usage.input_tokens is None
    assert combined.cost_amount is None
    assert combined.cost_unknown_reason == "usage_unavailable"

    drifted = unknown.with_value([0.3])
    drifted = AICallResult(
        value=drifted.value,
        provider_type=drifted.provider_type,
        model="other-model",
        model_id=drifted.model_id,
        stage=drifted.stage,
        usage=drifted.usage,
        cost_amount=drifted.cost_amount,
        cost_currency=drifted.cost_currency,
        cost_unknown_reason=drifted.cost_unknown_reason,
    )
    with pytest.raises(ValueError, match="provider/model/stage"):
        combine_ai_call_results({}, [known, drifted])


@pytest.mark.asyncio
async def test_summary_handler_uses_result_api_and_persists_telemetry(monkeypatch) -> None:
    context = _HandlerContext()
    current = SimpleNamespace(
        revision=SimpleNamespace(
            projection_context={"summary_prompt": "summarize"},
            source_content="chapter content",
        )
    )
    ai_call = AICallResult(
        value="chapter summary",
        provider_type="openai_compatible",
        model="chat-model",
        model_id=12,
        stage="summary_memory",
        usage=TokenUsage(10, 2, 12, 0, 0, 0, True),
        cost_amount="0.000026",
        cost_currency="USD",
        cost_unknown_reason=None,
    )
    monkeypatch.setattr(
        projection_handlers,
        "_start_projection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        projection_handlers,
        "load_current_projection",
        AsyncMock(return_value=current),
    )
    result_call = AsyncMock(return_value=ai_call)
    monkeypatch.setattr(
        projection_handlers.LLMService,
        "get_summary_result_detached",
        result_call,
    )

    outcome = await projection_handlers.handle_chapter_summary_projection(context)

    result_call.assert_awaited_once()
    assert outcome.result["projection"] == "summary"
    assert context.completed[0]["result"] == {"response": "chapter summary"}
    recorded = context.completed[0]["ai_call"]
    assert isinstance(recorded, AICallResult)
    assert recorded.telemetry_dict() == ai_call.telemetry_dict()


@pytest.mark.asyncio
async def test_rag_handler_aggregates_all_embedding_telemetry(monkeypatch) -> None:
    context = _HandlerContext()
    current = SimpleNamespace(
        revision=SimpleNamespace(
            projection_context={"rag_title": "Chapter"},
            source_content="chapter content",
        ),
        dependency=SimpleNamespace(result={"summary": "chapter summary"}),
    )
    first = AICallResult(
        value=[0.1],
        provider_type="openai_compatible",
        model="embedding-model",
        model_id=9,
        stage="rag_embedding",
        usage=TokenUsage(10, 0, 10, 0, 0, 0, True),
        cost_amount="0.000002",
        cost_currency="USD",
        cost_unknown_reason=None,
    )
    second = first.with_value([0.2])

    class FakeIngestionService:
        async def prepare_chapter(self, *, embedding_provider, **_kwargs):
            chunk_embedding = await embedding_provider("chunk")
            summary_embedding = await embedding_provider("summary")
            return PreparedChapterIngestion(
                enabled=True,
                complete=True,
                chunk_records=[{"embedding": chunk_embedding}],
                summary_records=[{"embedding": summary_embedding}],
            )

    monkeypatch.setattr(
        projection_handlers,
        "_start_projection",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        projection_handlers,
        "load_current_projection",
        AsyncMock(return_value=current),
    )
    monkeypatch.setattr(
        projection_handlers,
        "ChapterIngestionService",
        FakeIngestionService,
    )
    embedding_call = AsyncMock(side_effect=[first, second])
    monkeypatch.setattr(
        projection_handlers.LLMService,
        "get_embedding_result_detached",
        embedding_call,
    )

    outcome = await projection_handlers.handle_chapter_rag_projection(context)

    assert embedding_call.await_count == 2
    assert outcome.result["chunk_count"] == 1
    assert outcome.result["summary_count"] == 1
    recorded = context.completed[0]["ai_call"]
    assert isinstance(recorded, AICallResult)
    assert recorded.usage == TokenUsage(20, 0, 20, 0, 0, 0, True)
    assert recorded.cost_amount == "0.000004"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("service_error", "expected_status"),
    [
        (ChapterProjectionNotFoundError("not_found"), 404),
        (ChapterProjectionConflictError("conflict"), 409),
        (ChapterProjectionRateLimitError("limited"), 429),
    ],
)
async def test_admin_projection_router_maps_operational_errors(
    monkeypatch,
    service_error,
    expected_status,
) -> None:
    service = SimpleNamespace(execute=AsyncMock(side_effect=service_error))
    monkeypatch.setattr(
        projection_router,
        "ChapterProjectionOpsService",
        lambda _session: service,
    )
    session = SimpleNamespace(rollback=AsyncMock())

    with pytest.raises(HTTPException) as captured:
        await projection_router._execute(
            payload=_request(),
            mode="replay",
            session=session,
            admin=SimpleNamespace(id=1),
        )

    assert captured.value.status_code == expected_status
    assert captured.value.detail == str(service_error)
