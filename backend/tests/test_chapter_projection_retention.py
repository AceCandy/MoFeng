# AIMETA P=章节投影制品留存测试|R=验证预览_精确清理_保护边界_幂等审计|NR=不覆盖JobEvent留存|E=pytest|X=test|A=集成测试|D=pytest,postgresql|S=db|RD=../app/README.ai
from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.models.chapter_projection import (
    ChapterProjectionRetentionAudit,
    ChapterProjectionRun,
    ChapterRevision,
)
from app.models.foreshadowing import Foreshadowing
from app.models.novel import Chapter, NovelProject
from app.models.rag import RagChunk, RagSummary
from app.models.user import User
from app.schemas.chapter_projection import ChapterProjectionRetentionRequest
from app.services.chapter_projection_retention import (
    ChapterProjectionRetentionConflictError,
    ChapterProjectionRetentionNotFoundError,
    ChapterProjectionRetentionService,
)


PROJECT_ID = "11111111-1111-1111-1111-111111111111"
OLD_GENERATION = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
CURRENT_GENERATION = "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"


async def _seed_project(session) -> tuple[Chapter, ChapterRevision]:
    session.add(
        User(
            id=1701,
            username="projection-retention-admin",
            hashed_password="secret",
            is_admin=True,
        )
    )
    session.add(
        NovelProject(
            id=PROJECT_ID,
            user_id=1701,
            title="投影留存测试",
            initial_prompt="测试",
        )
    )
    chapter = Chapter(
        project_id=PROJECT_ID,
        chapter_number=1,
        status="finalizing",
        generation_progress=0,
        generation_step_index=1,
        generation_step_total=4,
        word_count=100,
        current_revision=2,
        source_hash="b" * 64,
        required_projection_snapshot=["rag"],
        projection_generation=CURRENT_GENERATION,
        tombstone_revision=0,
    )
    session.add(chapter)
    await session.flush()
    revision = ChapterRevision(
        id="retention-revision-1",
        chapter_id=chapter.id,
        project_id=PROJECT_ID,
        chapter_number=1,
        revision=1,
        source_hash="a" * 64,
        source_content="旧章节正文",
        projection_context={},
        lifecycle="superseded",
        required_projections=["rag"],
        skipped_projections=[],
        source_generation="retention-source-1",
        superseded_by_revision=2,
    )
    session.add(revision)
    await session.flush()
    return chapter, revision


def _request(
    *,
    artifact_kind: str,
    idempotency_key: str,
    max_rows: int = 500,
) -> ChapterProjectionRetentionRequest:
    return ChapterProjectionRetentionRequest(
        project_id=PROJECT_ID,
        chapter_number=1,
        revision=1,
        artifact_generation=OLD_GENERATION,
        artifact_kind=artifact_kind,
        idempotency_key=idempotency_key,
        reason="清理已被替代的投影制品",
        max_rows=max_rows,
    )


@pytest.mark.asyncio(loop_scope="session")
async def test_preview_then_purge_inactive_rag_generation_is_idempotent(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        chapter, revision = await _seed_project(session)
        run = ChapterProjectionRun(
            id="retention-rag-run",
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=PROJECT_ID,
            revision=1,
            projection_name="rag",
            source_hash="a" * 64,
            artifact_generation=OLD_GENERATION,
            status="succeeded",
            required=True,
            is_active=False,
            checkpoint={},
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                RagChunk(
                    id="retention-rag-chunk",
                    project_id=PROJECT_ID,
                    chapter_number=1,
                    chunk_index=0,
                    content="旧正文片段",
                    embedding=[0.1, 0.2],
                    source_revision=1,
                    artifact_generation=OLD_GENERATION,
                    projection_run_id=run.id,
                    is_active=False,
                ),
                RagSummary(
                    id="retention-rag-summary",
                    project_id=PROJECT_ID,
                    chapter_number=1,
                    title="旧摘要",
                    summary="旧摘要正文",
                    embedding=[0.1, 0.2],
                    source_revision=1,
                    artifact_generation=OLD_GENERATION,
                    projection_run_id=run.id,
                    is_active=False,
                ),
            ]
        )
        await session.commit()

        preview = await ChapterProjectionRetentionService(session).execute(
            request=_request(
                artifact_kind="rag",
                idempotency_key="retention-preview-rag",
            ),
            operator_user_id=1701,
            mode="preview",
        )

        assert preview.status == "eligible"
        assert preview.candidate_rows == {"rag_chunks": 1, "rag_summaries": 1}
        assert await session.scalar(select(func.count(RagChunk.id))) == 1
        assert await session.scalar(select(func.count(RagSummary.id))) == 1

        purge_request = _request(
            artifact_kind="rag",
            idempotency_key="retention-purge-rag",
        )
        purge = await ChapterProjectionRetentionService(session).execute(
            request=purge_request,
            operator_user_id=1701,
            mode="purge",
        )
        repeated = await ChapterProjectionRetentionService(session).execute(
            request=purge_request,
            operator_user_id=1701,
            mode="purge",
        )

        assert purge.status == "completed"
        assert purge.deleted_rows == {"rag_chunks": 1, "rag_summaries": 1}
        assert repeated == purge
        assert await session.scalar(select(func.count(RagChunk.id))) == 0
        assert await session.scalar(select(func.count(RagSummary.id))) == 0
        assert (
            await session.scalar(select(func.count(ChapterProjectionRetentionAudit.id)))
            == 2
        )

        with pytest.raises(
            ChapterProjectionRetentionConflictError,
            match="artifact_generation_already_purged",
        ):
            await ChapterProjectionRetentionService(session).execute(
                request=_request(
                    artifact_kind="rag",
                    idempotency_key="retention-second-purge-rag",
                ),
                operator_user_id=1701,
                mode="purge",
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_purge_preserves_manual_foreshadowing(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        chapter, revision = await _seed_project(session)
        run = ChapterProjectionRun(
            id="retention-foreshadowing-run",
            chapter_revision_id=revision.id,
            chapter_id=chapter.id,
            project_id=PROJECT_ID,
            revision=1,
            projection_name="foreshadowing",
            source_hash="a" * 64,
            artifact_generation=OLD_GENERATION,
            status="stale",
            required=False,
            is_active=False,
            checkpoint={},
        )
        session.add(run)
        await session.flush()
        session.add_all(
            [
                Foreshadowing(
                    project_id=PROJECT_ID,
                    chapter_id=chapter.id,
                    chapter_number=1,
                    chapter_revision=1,
                    artifact_generation=OLD_GENERATION,
                    projection_run_id=run.id,
                    is_active=False,
                    content="AI 伏笔",
                    type="hint",
                    status="planted",
                    is_manual=False,
                ),
                Foreshadowing(
                    project_id=PROJECT_ID,
                    chapter_id=chapter.id,
                    chapter_number=1,
                    chapter_revision=1,
                    artifact_generation=OLD_GENERATION,
                    projection_run_id=run.id,
                    is_active=False,
                    content="作者手工伏笔",
                    type="hint",
                    status="planted",
                    is_manual=True,
                ),
            ]
        )
        await session.commit()

        response = await ChapterProjectionRetentionService(session).execute(
            request=_request(
                artifact_kind="foreshadowing",
                idempotency_key="retention-purge-foreshadowing",
            ),
            operator_user_id=1701,
            mode="purge",
        )
        rows = (
            await session.execute(
                select(Foreshadowing.content, Foreshadowing.is_manual)
                .order_by(Foreshadowing.id)
            )
        ).all()

        assert response.deleted_rows == {"foreshadowings": 1}
        assert rows == [("作者手工伏笔", True)]


@pytest.mark.asyncio(loop_scope="session")
async def test_preview_rejects_active_artifacts_and_batch_overflow(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        await _seed_project(session)
        session.add_all(
            [
                RagChunk(
                    id=f"retention-protected-{index}",
                    project_id=PROJECT_ID,
                    chapter_number=1,
                    chunk_index=index,
                    content="旧正文片段",
                    embedding=[0.1, 0.2],
                    source_revision=1,
                    artifact_generation=OLD_GENERATION,
                    is_active=is_active,
                )
                for index, is_active in ((0, True), (1, False))
            ]
        )
        await session.commit()

        active_response = await ChapterProjectionRetentionService(session).execute(
            request=_request(
                artifact_kind="rag",
                idempotency_key="retention-preview-active",
            ),
            operator_user_id=1701,
            mode="preview",
        )
        assert active_response.status == "rejected"
        assert active_response.reason_code == "active_artifacts"

        await session.execute(
            RagChunk.__table__.update().values(is_active=False)
        )
        await session.commit()
        overflow_response = await ChapterProjectionRetentionService(session).execute(
            request=_request(
                artifact_kind="rag",
                idempotency_key="retention-preview-overflow",
                max_rows=1,
            ),
            operator_user_id=1701,
            mode="preview",
        )
        assert overflow_response.status == "rejected"
        assert overflow_response.reason_code == "retention_batch_too_large"
        assert await session.scalar(select(func.count(RagChunk.id))) == 2


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_rejects_inactive_admin(db_session_factory) -> None:
    async with db_session_factory() as session:
        await _seed_project(session)
        operator = await session.get(User, 1701)
        assert operator is not None
        operator.is_active = False
        await session.commit()

        with pytest.raises(
            ChapterProjectionRetentionNotFoundError,
            match="operator_not_authorized",
        ):
            await ChapterProjectionRetentionService(session).execute(
                request=_request(
                    artifact_kind="rag",
                    idempotency_key="retention-inactive-admin",
                ),
                operator_user_id=1701,
                mode="preview",
            )


@pytest.mark.asyncio(loop_scope="session")
async def test_retention_run_guard_is_scoped_to_exact_chapter_revision(
    db_session_factory,
) -> None:
    async with db_session_factory() as session:
        await _seed_project(session)
        foreign_chapter = Chapter(
            project_id=PROJECT_ID,
            chapter_number=2,
            status="successful",
            generation_progress=100,
            generation_step_index=4,
            generation_step_total=4,
            word_count=100,
            current_revision=1,
            source_hash="c" * 64,
            required_projection_snapshot=["rag"],
            projection_generation=OLD_GENERATION,
            tombstone_revision=0,
        )
        session.add(foreign_chapter)
        await session.flush()
        foreign_revision = ChapterRevision(
            id="retention-foreign-revision",
            chapter_id=foreign_chapter.id,
            project_id=PROJECT_ID,
            chapter_number=2,
            revision=1,
            source_hash="c" * 64,
            source_content="另一章正文",
            projection_context={},
            lifecycle="successful",
            required_projections=["rag"],
            skipped_projections=[],
            source_generation="retention-foreign-source",
        )
        session.add(foreign_revision)
        await session.flush()
        session.add_all(
            [
                ChapterProjectionRun(
                    id="retention-foreign-active-run",
                    chapter_revision_id=foreign_revision.id,
                    chapter_id=foreign_chapter.id,
                    project_id=PROJECT_ID,
                    revision=1,
                    projection_name="rag",
                    source_hash="c" * 64,
                    artifact_generation=OLD_GENERATION,
                    status="succeeded",
                    required=True,
                    is_active=True,
                    checkpoint={},
                ),
                RagChunk(
                    id="retention-exact-revision-chunk",
                    project_id=PROJECT_ID,
                    chapter_number=1,
                    chunk_index=0,
                    content="旧正文片段",
                    embedding=[0.1, 0.2],
                    source_revision=1,
                    artifact_generation=OLD_GENERATION,
                    is_active=False,
                ),
            ]
        )
        await session.commit()

        response = await ChapterProjectionRetentionService(session).execute(
            request=_request(
                artifact_kind="rag",
                idempotency_key="retention-exact-revision-run-guard",
            ),
            operator_user_id=1701,
            mode="purge",
        )

        assert response.status == "completed"
        assert response.deleted_rows == {"rag_chunks": 1, "rag_summaries": 0}


@pytest.mark.asyncio(loop_scope="session")
async def test_purge_rolls_back_when_candidate_becomes_active(
    db_session_factory,
) -> None:
    class StateChangingRetentionService(ChapterProjectionRetentionService):
        async def _delete_artifacts(self, request, candidate_ids):
            await self.session.execute(
                RagChunk.__table__.update()
                .where(RagChunk.id.in_(candidate_ids["rag_chunks"]))
                .values(is_active=True)
            )
            return await super()._delete_artifacts(request, candidate_ids)

    async with db_session_factory() as session:
        await _seed_project(session)
        session.add(
            RagChunk(
                id="retention-state-change-chunk",
                project_id=PROJECT_ID,
                chapter_number=1,
                chunk_index=0,
                content="旧正文片段",
                embedding=[0.1, 0.2],
                source_revision=1,
                artifact_generation=OLD_GENERATION,
                is_active=False,
            )
        )
        await session.commit()

        with pytest.raises(
            ChapterProjectionRetentionConflictError,
            match="artifact_state_changed",
        ):
            await StateChangingRetentionService(session).execute(
                request=_request(
                    artifact_kind="rag",
                    idempotency_key="retention-state-change",
                ),
                operator_user_id=1701,
                mode="purge",
            )

        artifact = await session.get(RagChunk, "retention-state-change-chunk")
        assert artifact is not None
        assert artifact.is_active is False
        assert (
            await session.scalar(select(func.count(ChapterProjectionRetentionAudit.id)))
            == 0
        )
