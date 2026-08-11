import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.api.routers import optimizer


@pytest.mark.parametrize(
    ("raw_response", "expected_content", "expected_notes"),
    [
        (
            '{"optimized_content":"优化正文","optimization_notes":"调整节奏"}',
            "优化正文",
            "调整节奏",
        ),
        (
            '```json\n{"optimized_content":"他按住"左胸"。",'
            '"optimization_notes":"修正动作"}\n```',
            '他按住"左胸"。',
            "修正动作",
        ),
        (
            '{"result":{"optimized_content":"嵌套正文","optimization_notes":"嵌套说明"}}',
            "嵌套正文",
            "嵌套说明",
        ),
        (
            '{"optimized_content":"# 版本一\\n正文","optimization_notes":"去除标题"}',
            "正文",
            "去除标题",
        ),
        (
            '{"optimized_content":"## 版本 2\\n正文","optimization_notes":"去除标题"}',
            "正文",
            "去除标题",
        ),
    ],
)
def test_parse_optimizer_response_extracts_structured_content(
    raw_response: str,
    expected_content: str,
    expected_notes: str,
) -> None:
    assert optimizer._parse_optimizer_response(raw_response) == (
        expected_content,
        expected_notes,
    )


@pytest.mark.parametrize(
    "raw_response",
    [
        "优化后的纯正文",
        '```json\n{"optimized_content":"未闭合正文',
        '```json\n{"optimized_content":"完整正文"}',
        '{"optimized_content":"正文"',
        '"optimized_content":"游离正文"',
        '```json\n{"optimized_content":"正文"\n```',
        '以下是结果：\n{"optimized_content":"完整正文"}',
        '说明\n```json\n{"optimized_content":"完整正文"}\n```\n尾注',
        '{"optimization_notes":"只有说明"}',
        '{"optimized_content":""}',
        '{"optimized_content":"   "}',
        '{"optimized_content":123}',
        '{"optimized_content":"# 版本一"}',
    ],
)
def test_parse_optimizer_response_rejects_unstructured_or_incomplete_content(
    raw_response: str,
) -> None:
    with pytest.raises(RuntimeError, match="优化响应格式无效"):
        optimizer._parse_optimizer_response(raw_response)


@pytest.mark.asyncio(loop_scope="session")
async def test_optimize_chapter_does_not_expose_model_exception(
    monkeypatch,
    caplog,
) -> None:
    session = object()
    sensitive_error = "provider failure: 敏感响应片段"

    class DummyNovelService:
        def __init__(self, db_session):
            assert db_session is session

        async def ensure_project_owner(self, project_id, user_id):
            assert project_id == "project-1"
            assert user_id == 42
            return SimpleNamespace(
                chapters=[
                    SimpleNamespace(
                        chapter_number=3,
                        selected_version=SimpleNamespace(content="原正文"),
                    )
                ],
            )

    class DummyPromptService:
        def __init__(self, db_session):
            assert db_session is session

        async def get_prompt(self, prompt_name):
            assert prompt_name == "optimize_dialogue"
            return "优化提示词"

    class DummyLLMService:
        def __init__(self, db_session):
            assert db_session is session

        async def get_llm_response(self, **kwargs):
            raise RuntimeError(sensitive_error)

    monkeypatch.setattr(optimizer, "NovelService", DummyNovelService)
    monkeypatch.setattr(optimizer, "PromptService", DummyPromptService)
    monkeypatch.setattr(optimizer, "LLMService", DummyLLMService)

    with caplog.at_level(logging.ERROR, logger=optimizer.__name__):
        with pytest.raises(optimizer.HTTPException) as exc_info:
            await optimizer.optimize_chapter(
                request=optimizer.OptimizeRequest(
                    project_id="project-1",
                    chapter_number=3,
                    dimension="dialogue",
                ),
                session=session,
                current_user=SimpleNamespace(id=42),
            )

    assert exc_info.value.detail == "优化过程中发生错误"
    assert "RuntimeError" in caplog.text
    assert sensitive_error not in caplog.text
    assert sensitive_error not in exc_info.value.detail


@pytest.mark.parametrize(
    ("error_type", "expected_status", "expected_detail"),
    [
        (ValueError, 400, "推荐版本优化请求无效"),
        (RuntimeError, 500, "评审优化过程中发生错误"),
    ],
)
@pytest.mark.asyncio(loop_scope="session")
async def test_optimize_recommended_version_does_not_expose_exception(
    monkeypatch,
    caplog,
    error_type,
    expected_status: int,
    expected_detail: str,
) -> None:
    session = object()
    sensitive_error = "prompt=敏感正文 provider_request_key=secret-key"

    class DummyService:
        def __init__(self, db_session):
            assert db_session is session

    class DummyNovelService(DummyService):
        async def ensure_project_owner(self, project_id, user_id):
            assert project_id == "project-1"
            assert user_id == 42
            return SimpleNamespace(chapters=[SimpleNamespace(chapter_number=3)])

    async def fail_optimization(**kwargs):
        raise error_type(sensitive_error)

    monkeypatch.setattr(optimizer, "NovelService", DummyNovelService)
    monkeypatch.setattr(optimizer, "PromptService", DummyService)
    monkeypatch.setattr(optimizer, "LLMService", DummyService)
    monkeypatch.setattr(
        optimizer,
        "do_optimize_recommended_version",
        fail_optimization,
    )

    with caplog.at_level(logging.ERROR, logger=optimizer.__name__):
        with pytest.raises(optimizer.HTTPException) as exc_info:
            await optimizer.optimize_recommended_version(
                request=optimizer.OptimizeRecommendedVersionRequest(
                    project_id="project-1",
                    chapter_number=3,
                    source_content="原正文",
                    review_summary="评审建议",
                ),
                session=session,
                current_user=SimpleNamespace(id=42),
            )

    assert exc_info.value.status_code == expected_status
    assert exc_info.value.detail == expected_detail
    assert error_type.__name__ in caplog.text
    assert sensitive_error not in caplog.text
    assert sensitive_error not in exc_info.value.detail


@pytest.mark.asyncio(loop_scope="session")
async def test_apply_optimization_enqueues_unified_postprocess(monkeypatch):
    session = object()
    current_user = SimpleNamespace(id=42)
    captured = {}

    class DummyChapterEditService:
        def __init__(self, db_session):
            assert db_session is session

        async def apply_content(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(job=SimpleNamespace(id="postprocess-job"))

    monkeypatch.setattr(optimizer, "ChapterEditService", DummyChapterEditService)

    result = await optimizer.apply_optimization(
        request=optimizer.ApplyOptimizationRequest(
            project_id="project-1",
            chapter_number=3,
            optimized_content="新\n 内 容",
        ),
        session=session,
        current_user=current_user,
    )

    assert result == {
        "status": "accepted",
        "message": "优化内容已应用，章节后处理已进入队列",
        "task_id": "postprocess-job",
    }
    assert captured == {
        "project_id": "project-1",
        "chapter_number": 3,
        "content": "新\n 内 容",
        "user_id": current_user.id,
        "version_label": "optimized",
    }


def test_optimizer_does_not_import_writer_private_foreshadowing_logic() -> None:
    source = optimizer.__file__
    assert source is not None
    text = Path(source).read_text(encoding="utf-8")

    assert "from .writer import" not in text
    assert "_sync_foreshadowings_for_chapter" not in text


def test_optimizer_frontend_uses_durable_acceptance_contract() -> None:
    root = Path(__file__).resolve().parents[2]
    api_source = (root / "frontend/src/api/novel.ts").read_text(encoding="utf-8")
    response_block = api_source.split("export interface ApplyOptimizationResponse", 1)[1].split(
        "}", 1
    )[0]
    writing_desk = (root / "frontend/src/composables/useWritingDeskOptimize.ts").read_text(
        encoding="utf-8"
    )
    chapter_content = (
        root / "frontend/src/components/writing-desk/workspace/ChapterContent.vue"
    ).read_text(encoding="utf-8")

    assert "status: 'accepted'" in response_block
    assert "task_id: string" in response_block
    assert "foreshadowing_sync" not in response_block
    assert "applyResult.foreshadowing_sync" not in writing_desk
    assert "applyResult.foreshadowing_sync" not in chapter_content
    assert "globalAlert.showToast(applyResult.message, 'success')" in writing_desk
    assert "globalAlert.showToast(applyResult.message, 'success')" in chapter_content
