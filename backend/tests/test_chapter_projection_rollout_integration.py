from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.config import settings
from app.models.background_task import BackgroundTask
from app.models.chapter_projection import (
    ChapterOutboxEvent,
    ChapterProjectionRollout,
    ChapterProjectionRolloutTransition,
    ChapterProjectionRun,
    ChapterProjectionShadowObservation,
    ChapterRevision,
)
from app.models.foreshadowing import Foreshadowing
from app.models.job import AIUsageRecord, JobActivity, JobEvent
from app.models.novel import Chapter, NovelProject
from app.models.project_memory import ChapterSnapshot, ProjectMemory
from app.models.user import User
from app.services.chapter_projection_rollout import (
    ChapterProjectionRolloutConflictError,
    ChapterProjectionRolloutService,
)
from app.services.chapter_projection_service import ChapterProjectionService


async def _add_project(
    session,
    *,
    user_id: int,
    project_id: str,
    username: str,
) -> None:
    session.add(User(id=user_id, username=username, hashed_password="secret"))
    session.add(
        NovelProject(
            id=project_id,
            user_id=user_id,
            title="章节投影集成测试",
            initial_prompt="测试",
        )
    )
    await session.flush()


def _revision(
    *,
    revision_id: str,
    chapter: Chapter,
    revision: int,
    source_hash: str,
    source_generation: str,
    lifecycle: str,
    required: list[str],
) -> ChapterRevision:
    return ChapterRevision(
        id=revision_id,
        chapter_id=chapter.id,
        project_id=chapter.project_id,
        chapter_number=chapter.chapter_number,
        revision=revision,
        source_hash=source_hash,
        source_content=f"第 {chapter.chapter_number} 章正文",
        projection_context={},
        lifecycle=lifecycle,
        required_projections=required,
        skipped_projections=[],
        source_generation=source_generation,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_complete_cutover_then_rollback_restores_exact_legacy_state(
    db_session_factory,
) -> None:
    project_id = "projection-rollout-integration"
    source_hash = "a" * 64
    source_generation = "source-generation-1"
    memory_generation = "memory-generation-1"
    foreshadowing_generation = "foreshadow-generation-1"

    async with db_session_factory() as session:
        await _add_project(
            session,
            user_id=1601,
            project_id=project_id,
            username="projection-rollout-user",
        )
        chapter = Chapter(
            project_id=project_id,
            chapter_number=1,
            real_summary="legacy summary",
            status="finalizing",
            generation_progress=25,
            generation_step="projecting",
            generation_step_index=2,
            generation_step_total=4,
            word_count=100,
            current_revision=1,
            source_hash=source_hash,
            required_projection_snapshot=["summary", "memory", "foreshadowing"],
            projection_generation=source_generation,
            tombstone_revision=0,
        )
        session.add(chapter)
        await session.flush()
        foreign_chapter = Chapter(
            project_id=project_id,
            chapter_number=2,
            status="successful",
            generation_progress=100,
            generation_step="finalized",
            generation_step_index=4,
            generation_step_total=4,
            word_count=80,
        )
        session.add(foreign_chapter)
        await session.flush()
        foreign_foreshadowing = Foreshadowing(
            project_id=project_id,
            chapter_id=foreign_chapter.id,
            chapter_number=2,
            content="其他章节伏笔",
            type="hint",
            status="planted",
            is_manual=False,
        )

        revision = _revision(
            revision_id="rollout-revision-1",
            chapter=chapter,
            revision=1,
            source_hash=source_hash,
            source_generation=source_generation,
            lifecycle="shadow_ready",
            required=["summary", "memory", "foreshadowing"],
        )
        summary_run = ChapterProjectionRun(
            id="rollout-summary-run",
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=project_id,
            revision=1,
            projection_name="summary",
            source_hash=source_hash,
            artifact_generation="summary-generation-1",
            status="succeeded",
            required=True,
            is_active=False,
            checkpoint={},
            result={"summary": "projection summary"},
        )
        memory_run = ChapterProjectionRun(
            id="rollout-memory-run",
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=project_id,
            revision=1,
            projection_name="memory",
            source_hash=source_hash,
            dependency_run_id=summary_run.id,
            artifact_generation=memory_generation,
            status="succeeded",
            required=True,
            is_active=False,
            checkpoint={},
            result={},
        )
        foreshadowing_run = ChapterProjectionRun(
            id="rollout-foreshadow-run",
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=project_id,
            revision=1,
            projection_name="foreshadowing",
            source_hash=source_hash,
            dependency_run_id=summary_run.id,
            artifact_generation=foreshadowing_generation,
            status="succeeded",
            required=True,
            is_active=False,
            checkpoint={},
            result={
                "plan": {
                    "candidates": [],
                    "active": [],
                    "status_decisions": {},
                }
            },
        )
        rollout = ChapterProjectionRollout(
            id="rollout-state-1",
            chapter_id=chapter.id,
            project_id=project_id,
            owner="legacy",
            state="draining",
            generation=2,
            fencing_token=2,
            transition_sequence=0,
            shadow_diff={"unexplained_count": 0},
            observation_started_at=datetime.now(timezone.utc) - timedelta(minutes=5),
            observation_deadline_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            required_observations=1,
            successful_observations=1,
            failed_observations=0,
        )
        observation = ChapterProjectionShadowObservation(
            id="rollout-observation-1",
            rollout_id=rollout.id,
            aggregate_id=str(chapter.id),
            project_id=project_id,
            chapter_id=chapter.id,
            revision=1,
            rollout_generation=2,
            sample_key="revision-1",
            outcome="match",
            digest="b" * 64,
            diff={"unexplained_count": 0},
        )
        memory = ProjectMemory(
            project_id=project_id,
            global_summary="legacy global summary",
            plot_arcs={"legacy": True},
            last_updated_chapter=0,
            version=1,
            projection_revision=0,
            projection_generation=None,
        )
        legacy_snapshot = ChapterSnapshot(
            project_id=project_id,
            chapter_number=1,
            global_summary_snapshot="legacy global summary",
            character_states_snapshot={},
            plot_arcs_snapshot={"legacy": True},
            chapter_summary="legacy summary",
            word_count=100,
            chapter_revision=0,
            artifact_generation="legacy",
            projection_run_id=None,
            is_active=True,
        )
        staged_snapshot = ChapterSnapshot(
            project_id=project_id,
            chapter_number=1,
            global_summary_snapshot="projection global summary",
            character_states_snapshot={},
            plot_arcs_snapshot={"projection": True},
            chapter_summary="projection summary",
            word_count=100,
            chapter_revision=1,
            artifact_generation=memory_generation,
            projection_run_id=memory_run.id,
            is_active=False,
        )
        session.add_all(
            [revision, rollout, memory, legacy_snapshot, foreign_foreshadowing]
        )
        await session.flush()
        session.add_all([summary_run, observation])
        await session.flush()
        session.add_all([memory_run, foreshadowing_run])
        await session.flush()
        session.add(staged_snapshot)
        await session.commit()

        service = ChapterProjectionRolloutService(session)
        cutover = await service.complete_cutover(
            project_id=project_id,
            chapter_id=chapter.id,
            expected_generation=2,
            expected_fencing_token=2,
            operator_user_id=1601,
            reason="integration cutover",
        )
        await session.commit()

        assert cutover["owner"] == "projection"
        assert cutover["state"] == "projection"
        assert cutover["generation"] == 3
        assert chapter.real_summary == "projection summary"
        assert chapter.status == "successful"
        assert revision.lifecycle == "successful"
        assert memory.global_summary == "projection global summary"
        assert memory.projection_revision == 1
        assert legacy_snapshot.is_active is False
        assert staged_snapshot.is_active is True
        assert summary_run.is_active is True
        assert memory_run.is_active is True
        assert foreshadowing_run.is_active is True

        valid_manifest = rollout.rollback_manifest
        assert isinstance(valid_manifest, dict)
        promoted_run_ids = valid_manifest["promoted_projection_run_ids"]
        assert promoted_run_ids
        overlap_manifest = {
            **valid_manifest,
            "previous_active_projection_run_ids": [promoted_run_ids[0]],
        }
        with pytest.raises(ChapterProjectionRolloutConflictError) as overlap_error:
            async with session.begin_nested():
                rollout.rollback_manifest = overlap_manifest
                await service.rollback(
                    project_id=project_id,
                    chapter_id=chapter.id,
                    expected_generation=3,
                    expected_fencing_token=3,
                    operator_user_id=1601,
                    reason="reject overlapping runs",
                )
        assert overlap_error.value.code == "rollback_manifest_invalid"
        await session.refresh(rollout)

        foreign_manifest = {
            **valid_manifest,
            "foreshadowing_states": [
                {
                    "id": foreign_foreshadowing.id,
                    "project_id": project_id,
                    "chapter_id": foreign_chapter.id,
                    "chapter_number": 2,
                    "chapter_revision": 0,
                    "artifact_generation": "legacy",
                    "projection_run_id": None,
                    "is_manual": False,
                    "status": "abandoned",
                    "resolved_chapter_id": None,
                    "resolved_chapter_number": None,
                    "expected_status": "planted",
                    "expected_resolved_chapter_id": None,
                    "expected_resolved_chapter_number": None,
                }
            ],
        }
        with pytest.raises(ChapterProjectionRolloutConflictError) as foreign_state_error:
            async with session.begin_nested():
                rollout.rollback_manifest = foreign_manifest
                await service.rollback(
                    project_id=project_id,
                    chapter_id=chapter.id,
                    expected_generation=3,
                    expected_fencing_token=3,
                    operator_user_id=1601,
                    reason="reject foreign foreshadowing",
                )
        assert foreign_state_error.value.code == "rollback_manifest_invalid"
        await session.refresh(rollout)
        await session.refresh(foreign_foreshadowing)
        assert foreign_foreshadowing.status == "planted"

        restored = await service.rollback(
            project_id=project_id,
            chapter_id=chapter.id,
            expected_generation=3,
            expected_fencing_token=3,
            operator_user_id=1601,
            reason="integration rollback",
        )
        await session.commit()

        assert restored["owner"] == "legacy"
        assert restored["state"] == "legacy"
        assert restored["generation"] == 4
        assert chapter.real_summary == "legacy summary"
        assert chapter.status == "finalizing"
        assert chapter.generation_progress == 25
        assert chapter.generation_step == "projecting"
        assert chapter.generation_step_index == 2
        assert chapter.generation_step_total == 4
        assert revision.lifecycle == "shadow_ready"
        assert memory.global_summary == "legacy global summary"
        assert memory.plot_arcs == {"legacy": True}
        assert memory.last_updated_chapter == 0
        assert memory.projection_revision == 0
        assert memory.projection_generation is None
        assert legacy_snapshot.is_active is True
        assert staged_snapshot.is_active is False
        assert summary_run.is_active is False
        assert memory_run.is_active is False
        assert foreshadowing_run.is_active is False
        assert foreign_foreshadowing.status == "planted"


@pytest.mark.asyncio(loop_scope="session")
async def test_runtime_metrics_separate_current_history_legacy_and_shadow(
    db_session_factory,
    monkeypatch,
) -> None:
    checked_at = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
    project_id = "projection-metrics-integration"

    async with db_session_factory() as session:
        await _add_project(
            session,
            user_id=1602,
            project_id=project_id,
            username="projection-metrics-user",
        )
        chapters = [
            Chapter(
                project_id=project_id,
                chapter_number=number,
                status="finalizing",
                generation_progress=0,
                generation_step_index=1,
                generation_step_total=4,
                word_count=100,
                current_revision=2 if number == 3 else 1,
                source_hash=chr(96 + number) * 64,
                required_projection_snapshot=["summary"],
                projection_generation=f"metrics-source-{number}",
                tombstone_revision=0,
            )
            for number in (1, 2, 3)
        ]
        session.add_all(chapters)
        await session.flush()

        revisions = [
            _revision(
                revision_id="metrics-revision-1",
                chapter=chapters[0],
                revision=1,
                source_hash="a" * 64,
                source_generation="metrics-source-1",
                lifecycle="finalizing",
                required=["summary"],
            ),
            _revision(
                revision_id="metrics-revision-2",
                chapter=chapters[1],
                revision=1,
                source_hash="b" * 64,
                source_generation="metrics-source-2",
                lifecycle="finalizing",
                required=["summary"],
            ),
            _revision(
                revision_id="metrics-revision-3-old",
                chapter=chapters[2],
                revision=1,
                source_hash="x" * 64,
                source_generation="metrics-source-old",
                lifecycle="superseded",
                required=["summary"],
            ),
            _revision(
                revision_id="metrics-revision-3-current",
                chapter=chapters[2],
                revision=2,
                source_hash="c" * 64,
                source_generation="metrics-source-3",
                lifecycle="finalizing",
                required=["summary"],
            ),
        ]
        current_summary = ChapterProjectionRun(
            id="metrics-summary-current",
            chapter_revision_id=revisions[3].id,
            chapter_id=chapters[2].id,
            project_id=project_id,
            revision=2,
            projection_name="summary",
            source_hash="c" * 64,
            artifact_generation="metrics-summary-generation",
            status="queued",
            required=True,
            is_active=False,
            checkpoint={},
        )
        current_memory = ChapterProjectionRun(
            id="metrics-memory-current",
            chapter_revision_id=revisions[3].id,
            chapter_id=chapters[2].id,
            project_id=project_id,
            revision=2,
            projection_name="memory",
            source_hash="c" * 64,
            dependency_run_id=current_summary.id,
            artifact_generation="metrics-memory-generation",
            status="succeeded",
            required=False,
            is_active=True,
            checkpoint={},
        )
        historical_run = ChapterProjectionRun(
            id="metrics-summary-history",
            chapter_revision_id=revisions[2].id,
            chapter_id=chapters[2].id,
            project_id=project_id,
            revision=1,
            projection_name="summary",
            source_hash="x" * 64,
            artifact_generation="metrics-history-generation",
            status="dead_letter",
            required=True,
            is_active=False,
            checkpoint={},
        )
        outboxes = [
            ChapterOutboxEvent(
                id=f"metrics-outbox-{number}",
                aggregate_type="chapter",
                aggregate_id=str(chapter.id),
                chapter_id=chapter.id,
                project_id=project_id,
                revision=chapter.current_revision,
                event_type="ChapterFinalizationRequested",
                event_version=1,
                payload={"execution_mode": mode},
                payload_fingerprint=str(number) * 64,
                idempotency_key=f"metrics-outbox-key-{number}",
                created_at=checked_at - timedelta(seconds=600 if number == 2 else 30),
            )
            for number, chapter, mode in (
                (1, chapters[0], "legacy"),
                (2, chapters[1], "active"),
                (3, chapters[2], "active"),
            )
        ]
        jobs = [
            BackgroundTask(
                id="metrics-job-legacy",
                user_id=1602,
                project_id=project_id,
                task_type="chapter_finalize",
                title="legacy",
                status="dead_letter",
                progress=0,
                payload={"execution_mode": "legacy"},
                payload_version=2,
                available_at=checked_at - timedelta(seconds=500),
                attempt=3,
                max_attempts=3,
                fencing_token=1,
                executor_generation=1,
                stream_type="workflow",
                stream_id="metrics-legacy-stream",
                event_sequence=0,
                dead_lettered_at=checked_at - timedelta(seconds=400),
                created_at=checked_at - timedelta(seconds=500),
                updated_at=checked_at - timedelta(seconds=400),
            ),
            BackgroundTask(
                id="metrics-job-retry",
                user_id=1602,
                project_id=project_id,
                task_type="chapter_finalize",
                title="retry",
                status="retry_wait",
                progress=0,
                payload={"execution_mode": "active"},
                payload_version=2,
                available_at=checked_at + timedelta(seconds=30),
                attempt=1,
                max_attempts=3,
                fencing_token=1,
                executor_generation=1,
                stream_type="workflow",
                stream_id="metrics-retry-stream",
                event_sequence=0,
                created_at=checked_at - timedelta(seconds=450),
                updated_at=checked_at - timedelta(seconds=400),
            ),
            BackgroundTask(
                id="metrics-job-expired",
                user_id=1602,
                project_id=project_id,
                task_type="chapter_projection_memory",
                title="expired",
                status="running",
                progress=10,
                payload={},
                payload_version=1,
                available_at=checked_at - timedelta(seconds=120),
                attempt=2,
                max_attempts=3,
                lease_owner="lost-worker",
                lease_expires_at=checked_at - timedelta(seconds=10),
                fencing_token=2,
                executor_generation=1,
                stream_type="workflow",
                stream_id="metrics-expired-stream",
                event_sequence=1,
                created_at=checked_at - timedelta(seconds=120),
                updated_at=checked_at - timedelta(seconds=20),
                started_at=checked_at - timedelta(seconds=100),
            ),
            BackgroundTask(
                id="metrics-job-dead",
                user_id=1602,
                project_id=project_id,
                task_type="chapter_projection_rag",
                title="dead",
                status="dead_letter",
                progress=0,
                payload={},
                payload_version=1,
                available_at=checked_at - timedelta(seconds=100),
                attempt=3,
                max_attempts=3,
                fencing_token=3,
                executor_generation=1,
                stream_type="workflow",
                stream_id="metrics-dead-stream",
                event_sequence=0,
                dead_lettered_at=checked_at - timedelta(seconds=60),
                created_at=checked_at - timedelta(seconds=100),
                updated_at=checked_at - timedelta(seconds=60),
            ),
        ]
        rollout = ChapterProjectionRollout(
            id="metrics-shadow-rollout",
            chapter_id=chapters[1].id,
            project_id=project_id,
            owner="legacy",
            state="shadow",
            generation=2,
            fencing_token=1,
            transition_sequence=1,
            shadow_diff={"unexplained_count": 1},
            observation_started_at=checked_at - timedelta(seconds=600),
            observation_deadline_at=checked_at - timedelta(seconds=60),
            required_observations=2,
            successful_observations=1,
            failed_observations=1,
            last_observed_at=checked_at - timedelta(seconds=30),
        )
        observation = ChapterProjectionShadowObservation(
            id="metrics-shadow-observation",
            rollout_id=rollout.id,
            aggregate_id=str(chapters[1].id),
            project_id=project_id,
            chapter_id=chapters[1].id,
            revision=1,
            rollout_generation=2,
            sample_key="metrics-sample",
            outcome="match",
            digest="d" * 64,
            diff={"unexplained_count": 0},
            created_at=checked_at - timedelta(seconds=30),
        )
        reclaim_event = JobEvent(
            job_id="metrics-job-expired",
            user_id=1602,
            project_id=project_id,
            stream_type="workflow",
            stream_id="metrics-expired-stream",
            sequence=1,
            event_type="job.reclaimed",
            payload={},
            created_at=checked_at - timedelta(seconds=100),
        )
        activity = JobActivity(
            id="metrics-activity-success",
            job_id="metrics-job-expired",
            activity_key="embedding",
            side_effect_class="idempotent_external",
            status="succeeded",
            provider_request_key="metrics-provider-key",
            attempt=2,
            fencing_token=2,
            request_payload={},
            result_payload={},
            started_at=checked_at - timedelta(seconds=5),
            completed_at=checked_at,
        )
        unknown_activity = JobActivity(
            id="metrics-activity-unknown-cost",
            job_id="metrics-job-expired",
            activity_key="embedding-fallback",
            side_effect_class="idempotent_external",
            status="succeeded",
            provider_request_key="metrics-provider-key-unknown",
            attempt=2,
            fencing_token=2,
            request_payload={},
            result_payload={},
            started_at=checked_at - timedelta(seconds=3),
            completed_at=checked_at,
        )
        transactional_activity = JobActivity(
            id="metrics-activity-transactional",
            job_id="metrics-job-expired",
            activity_key="transactional-write",
            side_effect_class="transactional",
            status="succeeded",
            provider_request_key="metrics-transactional-key",
            attempt=2,
            fencing_token=2,
            request_payload={},
            result_payload={},
            started_at=checked_at - timedelta(seconds=4),
            completed_at=checked_at,
        )
        malformed_cost_activity = JobActivity(
            id="metrics-activity-malformed-cost",
            job_id="metrics-job-expired",
            activity_key="malformed-cost",
            side_effect_class="idempotent_external",
            status="succeeded",
            provider_request_key="metrics-malformed-cost-key",
            attempt=2,
            fencing_token=2,
            request_payload={},
            result_payload={},
            started_at=checked_at - timedelta(seconds=2),
            completed_at=checked_at,
        )
        unknown_status_activity = JobActivity(
            id="metrics-activity-unknown-status",
            job_id="metrics-job-expired",
            activity_key="unknown-status",
            side_effect_class="idempotent_external",
            status="tenant-secret-status",
            provider_request_key="metrics-unknown-status-key",
            attempt=2,
            fencing_token=2,
            request_payload={},
            result_payload={},
            started_at=checked_at - timedelta(seconds=1),
            completed_at=checked_at,
        )
        known_usage = AIUsageRecord(
            job_activity_id=activity.id,
            job_id="metrics-job-expired",
            user_id=1602,
            project_id=project_id,
            provider_type="openai_compatible",
            model_name="metrics-model",
            stage="embedding",
            input_tokens=100,
            output_tokens=20,
            total_tokens=120,
            cached_input_tokens=10,
            cache_write_input_tokens=5,
            reasoning_tokens=2,
            usage_complete=True,
            cost_amount=Decimal("0.125"),
            cost_currency="CNY",
            cost_known=True,
            created_at=checked_at,
        )
        unknown_usage = AIUsageRecord(
            job_activity_id=unknown_activity.id,
            job_id="metrics-job-expired",
            user_id=1602,
            project_id=project_id,
            provider_type="openai_compatible",
            model_name="metrics-model",
            stage="embedding",
            usage_complete=False,
            cost_known=False,
            cost_unknown_reason="pricing_unconfigured",
            created_at=checked_at,
        )
        malformed_cost_usage = AIUsageRecord(
            job_activity_id=malformed_cost_activity.id,
            job_id="metrics-job-expired",
            user_id=1602,
            project_id=project_id,
            provider_type="openai_compatible",
            model_name="metrics-model",
            stage="embedding",
            usage_complete=False,
            cost_known=True,
            created_at=checked_at,
        )
        redacted_unknown_usage = AIUsageRecord(
            job_activity_id=unknown_status_activity.id,
            job_id="metrics-job-expired",
            user_id=1602,
            project_id=project_id,
            provider_type="openai_compatible",
            model_name="metrics-model",
            stage="embedding",
            usage_complete=True,
            cost_known=False,
            cost_unknown_reason="tenant-secret-reason",
            created_at=checked_at,
        )
        rollout_transition = ChapterProjectionRolloutTransition(
            id="metrics-rollout-transition",
            rollout_id=rollout.id,
            aggregate_id=str(chapters[1].id),
            project_id=project_id,
            chapter_id=chapters[1].id,
            sequence=1,
            from_owner="legacy",
            to_owner="legacy",
            from_state="legacy",
            to_state="shadow",
            generation=2,
            fencing_token=1,
            reason="begin metrics shadow",
            details={},
            created_at=checked_at - timedelta(seconds=600),
        )
        session.add_all([*revisions, *outboxes, *jobs, rollout])
        await session.flush()
        session.add_all(
            [
                current_summary,
                historical_run,
                observation,
                reclaim_event,
                activity,
                unknown_activity,
                transactional_activity,
                malformed_cost_activity,
                unknown_status_activity,
                rollout_transition,
            ]
        )
        await session.flush()
        session.add_all(
            [
                current_memory,
                known_usage,
                unknown_usage,
                malformed_cost_usage,
                redacted_unknown_usage,
            ]
        )
        await session.commit()

        metrics = await ChapterProjectionService(session).get_runtime_metrics(
            now=checked_at
        )

        assert metrics["status_counts"] == {"queued": 1, "succeeded": 1}
        assert metrics["history_status_counts"] == {
            "dead_letter": 1,
            "queued": 1,
            "succeeded": 1,
        }
        assert metrics["outbox_total"] == 3
        assert metrics["projection_outbox_total"] == 2
        assert metrics["legacy_outbox_total"] == 1
        assert metrics["outbox_backlog"] == 1
        assert metrics["outbox_oldest_age_seconds"] == 600
        assert metrics["projection_job_status_counts"] == {
            "dead_letter": 1,
            "retry_wait": 1,
            "running": 1,
        }
        assert metrics["projection_job_oldest_age_seconds"]["retry_wait"] == 400
        assert metrics["projection_expired_lease_count"] == 1
        assert metrics["projection_oldest_expired_lease_age_seconds"] == 10
        assert metrics["projection_reclaim_event_count"] == 1
        assert metrics["external_success_count"] == 3
        assert metrics["external_status_counts"] == {"succeeded": 3, "unknown": 1}
        assert metrics["ai_usage_record_count"] == 4
        assert metrics["ai_usage_incomplete_count"] == 2
        assert metrics["ai_usage_token_totals"] == {
            "input": 100,
            "output": 20,
            "total": 120,
            "cached_input": 10,
            "cache_write_input": 5,
            "reasoning": 2,
        }
        assert metrics["ai_cost_known_count"] == 1
        assert metrics["ai_cost_unknown_count"] == 3
        assert metrics["ai_cost_totals"] == {"CNY": "0.125000000000"}
        assert metrics["ai_cost_unknown_counts"] == {
            "cost_envelope_invalid": 1,
            "other": 1,
            "pricing_unconfigured": 1,
        }
        assert metrics["rollout_transition_counts"] == {
            "legacy.legacy->legacy.shadow": 1
        }
        assert metrics["shadow_rollout_count"] == 1
        assert metrics["shadow_observation_outcome_counts"] == {"match": 1}
        assert metrics["shadow_oldest_window_age_seconds"] == 600
        assert metrics["shadow_last_observed_age_seconds"] == 30
        assert metrics["shadow_window_expired_count"] == 1
        assert metrics["shadow_failed_rollout_count"] == 1
        assert set(metrics["alerts"]) >= {
            "chapter_outbox_backlog",
            "chapter_outbox_stuck",
            "chapter_projection_dead_letter",
            "chapter_projection_expired_lease",
            "chapter_projection_retry_stuck",
            "chapter_projection_shadow_failed",
            "chapter_projection_cost_unknown",
            "chapter_projection_usage_incomplete",
        }

        monkeypatch.setattr(settings, "job_projection_lag_alert_seconds", 700)
        relaxed_metrics = await ChapterProjectionService(session).get_runtime_metrics(
            now=checked_at
        )
        assert "chapter_outbox_stuck" not in relaxed_metrics["alerts"]
        assert "chapter_projection_retry_stuck" not in relaxed_metrics["alerts"]
