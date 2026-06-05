# Chapter Delete Policy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add guarded chapter deletion for unlocked ungenerated outlines and the latest completed chapter, including explicit confirmations and full artifact cleanup.

**Architecture:** Keep the existing writer delete endpoint and `NovelService.delete_chapters()` boundary. Add backend-side policy enforcement and confirmation tokens so UI checks are advisory only, and extend cleanup to generated artifacts, finalization artifacts, and vector data.

**Tech Stack:** FastAPI, SQLAlchemy async ORM, Vue 3, TanStack Query, Vitest, Pytest.

---

## File Structure

- Modify `backend/app/schemas/novel.py`: add confirmation fields to `DeleteChapterRequest`.
- Modify `backend/app/api/routers/writer.py`: pass confirmation fields through and keep vector cleanup in the delete route.
- Modify `backend/app/services/novel_service.py`: enforce tail-only outline deletion, latest-completed deletion, strong confirmation, and artifact cleanup.
- Modify `backend/app/services/vector_store_service.py`: make vector delete failures visible to callers.
- Modify `frontend/src/composables/useAlert.ts`, `frontend/src/components/CustomAlert.vue`, and `frontend/src/App.vue`: support a confirmation input for destructive second-step confirmation.
- Modify `frontend/src/api/novel.ts`, `frontend/src/queries/novel.ts`, `frontend/src/views/WritingDesk.vue`, and `frontend/src/components/writing-desk/WDSidebar.vue`: send delete confirmation payloads and align UI affordance with backend policy.
- Modify `backend/tests/test_chapter_delete_policy.py` and `frontend/src/components/__tests__/wdSidebarDeleteChapter.spec.ts`: cover policy and confirmation behavior.

## Tasks

### Task 1: Backend Policy Tests

- [x] Extend `backend/tests/test_chapter_delete_policy.py` to prove the current implementation does not yet enforce tail-only outline deletion, strong confirmation for completed chapters, full finalization artifact cleanup, and vector delete failure propagation.
- [x] Run `backend/.venv/bin/python -m pytest backend/tests/test_chapter_delete_policy.py -q` and confirm the new assertions fail for the expected reasons.

### Task 2: Backend Policy Implementation

- [x] Add `delete_artifacts_confirmed` and `confirmation_text` to `DeleteChapterRequest`.
- [x] Update the writer delete route to pass those fields into `NovelService.delete_chapters()`.
- [x] Update `NovelService.delete_chapters()` to:
  - allow `not_generated` and missing `Chapter` outlines only when the requested set is a tail-contiguous range;
  - require `delete_artifacts_confirmed=true` and exact confirmation text `删除第N章及全部产物` for the latest completed chapter;
  - delete versions, evaluations, generation traces, snapshots, character states, auto foreshadowings, and status histories from the deleted completed chapter;
  - restore `ProjectMemory.last_updated_chapter` to the previous completed chapter when deleting the latest completed chapter;
  - call vector cleanup for completed chapters and fail the request if cleanup fails.
- [x] Update `VectorStoreService.delete_by_chapters()` so exceptions are re-raised after logging.
- [x] Re-run the backend policy test until it passes.

### Task 3: Frontend Confirmation Tests

- [x] Extend `frontend/src/components/__tests__/wdSidebarDeleteChapter.spec.ts` to assert the sidebar only offers deletion for the latest completed chapter and tail ungenerated outlines.
- [x] Add static assertions that `WritingDesk.vue` performs two confirmation steps and sends `delete_artifacts_confirmed` plus `confirmation_text` for completed chapter deletion.
- [x] Run `npm run test:unit -- src/components/__tests__/wdSidebarDeleteChapter.spec.ts` from `frontend/` and confirm the new assertions fail before implementation.

### Task 4: Frontend Implementation

- [x] Add optional confirmation-input support to the shared alert dialog.
- [x] Update `NovelAPI.deleteChapter()` and `useDeleteChapterMutation()` to accept payload fields beyond `chapter_numbers`.
- [x] Update `WDSidebar.vue` to show delete affordance only for the latest completed chapter and tail-contiguous ungenerated outlines.
- [x] Update `WritingDesk.vue` delete flow to run two confirmations for every delete; completed chapter deletion must require the exact artifact confirmation phrase.
- [x] Re-run the frontend delete test until it passes.

### Task 5: Final Verification

- [x] Run `backend/.venv/bin/python -m pytest backend/tests/test_chapter_delete_policy.py -q`.
- [x] Run `npm run test:unit -- src/components/__tests__/wdSidebarDeleteChapter.spec.ts` from `frontend/`.
- [x] Review `git diff --check`.
