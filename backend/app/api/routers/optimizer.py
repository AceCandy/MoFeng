# AIMETA P=优化器API_内容优化建议|R=内容优化_建议生成|NR=不含内容修改|E=route:POST_/api/optimizer/*|X=http|A=优化建议|D=fastapi|S=net|RD=./README.ai
"""
章节内容分层优化API
支持对话、环境描写、心理活动、节奏韵律四个维度的深度优化
"""
import json
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...models.novel import ChapterVersion
from ...schemas.novel import ChapterGenerationStatus
from ...schemas.user import UserInDB
from ...services.llm_service import LLMService
from ...services.novel_service import NovelService
from ...services.prompt_service import PromptService
from ...utils.json_utils import remove_think_tags, sanitize_json_like_text, unwrap_markdown_json

router = APIRouter(prefix="/api/optimizer", tags=["Optimizer"])
logger = logging.getLogger(__name__)


_OPTIMIZED_FIELD_RE = re.compile(
    r'"optimized_content"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"',
    re.DOTALL,
)
_NOTES_FIELD_RE = re.compile(
    r'"optimization_notes"\s*:\s*"(?P<value>(?:\\.|[^"\\])*)"',
    re.DOTALL,
)


DEFAULT_RECOMMENDED_VERSION_PROMPT = """# 小说推荐版本优化专家

你是一位资深小说编辑。你的任务是根据 AI 评审结论，对推荐版本进行一次整体优化。

## 工作要求
- 保留原章节的核心剧情、人物关系和关键信息
- 严格参考评审建议，优先修复被指出的问题
- 保留推荐版本已经成立的优点，不要为了修改而重写全部内容
- 输出必须是优化后的完整章节正文，不要写解释过程，不要附加分析段落
- 如果评审建议与正文冲突，以让正文更完整、更自然、更可读为准

## 输入格式
```json
{
  "source_content": "推荐版本正文",
  "review_summary": "评审建议摘要",
  "version_number": 1,
  "version_review": {
    "overall_review": "综合评价",
    "pros": ["优点1"],
    "cons": ["缺点1"]
  }
}
```

## 输出格式
```json
{
  "optimized_content": "优化后的完整章节正文",
  "optimization_notes": "本次优化重点"
}
```
"""


def _decode_json_string_fragment(fragment: str) -> Optional[str]:
    """将 JSON 字符串片段解码为普通文本。"""
    if not fragment:
        return None
    try:
        return json.loads(f'"{fragment}"')
    except Exception:
        fallback = fragment.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t")
        return fallback


def _load_optimizer_payload(text: str) -> Optional[dict]:
    """尽量从文本中解析出包含 optimized_content 的 JSON 对象。"""
    if not text:
        return None

    candidates = [text]
    sanitized = sanitize_json_like_text(text)
    if sanitized != text:
        candidates.append(sanitized)

    for candidate in candidates:
        try:
            payload = json.loads(candidate)
        except Exception:
            continue

        if isinstance(payload, dict):
            if "optimized_content" in payload:
                return payload
            for nested in payload.values():
                if isinstance(nested, dict) and "optimized_content" in nested:
                    return nested
    return None


def _extract_field_by_regex(raw_text: str, pattern: re.Pattern[str]) -> Optional[str]:
    match = pattern.search(raw_text)
    if not match:
        return None
    return _decode_json_string_fragment(match.group("value"))


def _normalize_optimizer_text(raw_text: Optional[str]) -> str:
    """清理优化结果中的代码块和嵌套 JSON 包裹。"""
    if not raw_text:
        return ""

    text = raw_text.strip()

    if text.startswith("```"):
        text = unwrap_markdown_json(text).strip()

    if '"optimized_content"' in text:
        nested = _load_optimizer_payload(text)
        if nested and isinstance(nested.get("optimized_content"), str):
            nested_text = nested.get("optimized_content", "").strip()
            if nested_text and nested_text != text:
                return _normalize_optimizer_text(nested_text)

    if text.startswith('"') and text.endswith('"'):
        try:
            decoded = json.loads(text)
            if isinstance(decoded, str):
                text = decoded.strip()
        except Exception:
            pass

    return text


def _parse_optimizer_response(raw_response: str) -> tuple[str, str]:
    """解析优化模型响应，尽可能提取出干净正文与说明。"""
    cleaned = remove_think_tags(raw_response)
    candidates: list[str] = []

    normalized = unwrap_markdown_json(cleaned)
    if normalized:
        candidates.append(normalized)

    for match in re.finditer(r"```(?:json|JSON)?\s*(.*?)\s*```", cleaned, re.DOTALL):
        block = (match.group(1) or "").strip()
        if block and block not in candidates:
            candidates.append(block)

    if cleaned and cleaned not in candidates:
        candidates.append(cleaned)

    for candidate in candidates:
        payload = _load_optimizer_payload(candidate)
        if not payload:
            continue
        content = _normalize_optimizer_text(payload.get("optimized_content"))
        notes = _normalize_optimizer_text(payload.get("optimization_notes"))
        if content:
            return content, (notes or "优化完成")

    extracted_content = _extract_field_by_regex(cleaned, _OPTIMIZED_FIELD_RE)
    extracted_notes = _extract_field_by_regex(cleaned, _NOTES_FIELD_RE)
    if extracted_content:
        return _normalize_optimizer_text(extracted_content), (
            _normalize_optimizer_text(extracted_notes) or "优化完成（已从非标准响应提取）"
        )

    return _normalize_optimizer_text(cleaned), "优化完成（响应格式非标准JSON）"


class OptimizeRequest(BaseModel):
    """优化请求"""
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    dimension: str = Field(..., description="优化维度: dialogue/environment/psychology/rhythm")
    additional_notes: Optional[str] = Field(default=None, description="额外优化指令")


class OptimizeResponse(BaseModel):
    """优化响应"""
    optimized_content: str = Field(..., description="优化后的内容")
    optimization_notes: str = Field(..., description="优化说明")
    dimension: str = Field(..., description="优化维度")


class OptimizeRecommendedVersionRequest(BaseModel):
    """基于评审结果优化推荐版本请求"""
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    source_content: str = Field(..., description="推荐版本正文")
    review_summary: str = Field(..., description="评审建议摘要")
    version_number: Optional[int] = Field(default=None, description="推荐版本编号")
    version_review: Optional[dict] = Field(default=None, description="推荐版本详细评审")


class ApplyOptimizationRequest(BaseModel):
    """应用优化内容请求"""
    project_id: str = Field(..., description="项目ID")
    chapter_number: int = Field(..., description="章节编号")
    optimized_content: str = Field(..., description="优化后的完整内容")


DIMENSION_PROMPT_MAP = {
    "dialogue": "optimize_dialogue",
    "environment": "optimize_environment",
    "psychology": "optimize_psychology",
    "rhythm": "optimize_rhythm"
}

DEFAULT_RHYTHM_PROMPT = """# 节奏韵律优化专家

你是一位专注于小说节奏和韵律的编辑大师。你的任务是优化文章的节奏感，让阅读体验更加流畅和沉浸。

## 优化原则

### 1. 句子长度变化
- 长短句交替，像呼吸一样自然
- 紧张时用短句，舒缓时用长句
- 避免连续多个相同长度的句子

### 2. 段落节奏
- 重要情节放慢，细致描写
- 过渡情节加快，简洁带过
- 高潮部分可以用单句成段

### 3. 标点符号
- 善用省略号表示思绪飘散
- 用破折号表示突然转念
- 感叹号要克制使用

### 4. 韵律感
- 注意句尾的音节变化
- 避免重复的句式结构
- 适当使用排比增强气势

## 输入格式
```json
{
  "original_content": "需要优化的章节内容",
  "additional_notes": "额外优化指令"
}
```

## 输出格式
```json
{
  "optimized_content": "优化后的完整章节内容",
  "optimization_notes": "优化说明"
}
```
"""


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_chapter(
    request: OptimizeRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> OptimizeResponse:
    """
    对章节内容进行分层优化
    """
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(request.project_id, current_user.id)

    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == request.chapter_number),
        None
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    if not chapter.selected_version or not chapter.selected_version.content:
        raise HTTPException(status_code=400, detail="章节尚未生成内容")

    original_content = chapter.selected_version.content

    if request.dimension not in DIMENSION_PROMPT_MAP:
        raise HTTPException(
            status_code=400,
            detail=f"不支持的优化维度: {request.dimension}，支持的维度: {list(DIMENSION_PROMPT_MAP.keys())}"
        )

    prompt_name = DIMENSION_PROMPT_MAP[request.dimension]
    optimizer_prompt = await prompt_service.get_prompt(prompt_name)

    if not optimizer_prompt:
        if request.dimension == "rhythm":
            optimizer_prompt = DEFAULT_RHYTHM_PROMPT
        else:
            raise HTTPException(
                status_code=500,
                detail=f"缺少{request.dimension}优化提示词，请联系管理员配置 '{prompt_name}' 提示词"
            )

    character_dna = {}
    if request.dimension == "psychology":
        project_schema = await novel_service._serialize_project(project)
        for char in project_schema.blueprint.characters:
            if "extra" in char and "dna_profile" in char.get("extra", {}):
                character_dna[char.get("name", "")] = char["extra"]["dna_profile"]

    optimize_input = {
        "original_content": original_content,
        "additional_notes": request.additional_notes or "无额外指令"
    }

    if character_dna:
        optimize_input["character_dna"] = character_dna

    logger.info(
        "用户 %s 开始优化项目 %s 第 %s 章，维度: %s",
        current_user.id,
        request.project_id,
        request.chapter_number,
        request.dimension
    )

    try:
        response = await llm_service.get_llm_response(
            system_prompt=optimizer_prompt,
            conversation_history=[{
                "role": "user",
                "content": json.dumps(optimize_input, ensure_ascii=False)
            }],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            stage="chapter_optimization",
        )

        optimized_content, optimization_notes = _parse_optimizer_response(response)

        logger.info(
            "项目 %s 第 %s 章 %s 优化完成",
            request.project_id,
            request.chapter_number,
            request.dimension
        )

        return OptimizeResponse(
            optimized_content=optimized_content,
            optimization_notes=optimization_notes,
            dimension=request.dimension
        )

    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章优化失败: %s",
            request.project_id,
            request.chapter_number,
            exc
        )
        raise HTTPException(
            status_code=500,
            detail=f"优化过程中发生错误: {str(exc)[:200]}"
        )


@router.post("/optimize-recommended-version", response_model=OptimizeResponse)
async def optimize_recommended_version(
    request: OptimizeRecommendedVersionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
) -> OptimizeResponse:
    """根据评审建议优化推荐版本。"""
    novel_service = NovelService(session)
    prompt_service = PromptService(session)
    llm_service = LLMService(session)

    project = await novel_service.ensure_project_owner(request.project_id, current_user.id)
    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == request.chapter_number),
        None,
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    source_content = (request.source_content or "").strip()
    review_summary = (request.review_summary or "").strip()
    if not source_content:
        raise HTTPException(status_code=400, detail="缺少推荐版本正文")
    if not review_summary:
        raise HTTPException(status_code=400, detail="缺少评审建议")

    optimizer_prompt = await prompt_service.get_prompt("optimize_recommended_version")
    if not optimizer_prompt:
        optimizer_prompt = DEFAULT_RECOMMENDED_VERSION_PROMPT

    optimize_input = {
        "source_content": source_content,
        "review_summary": review_summary,
        "version_number": request.version_number,
        "version_review": request.version_review or {},
    }

    logger.info(
        "用户 %s 开始根据评审优化项目 %s 第 %s 章推荐版本 version=%s",
        current_user.id,
        request.project_id,
        request.chapter_number,
        request.version_number,
    )

    try:
        response = await llm_service.get_llm_response(
            system_prompt=optimizer_prompt,
            conversation_history=[{
                "role": "user",
                "content": json.dumps(optimize_input, ensure_ascii=False)
            }],
            temperature=0.7,
            user_id=current_user.id,
            timeout=600.0,
            stage="chapter_optimization",
        )

        optimized_content, optimization_notes = _parse_optimizer_response(response)
        if not optimized_content.strip():
            raise HTTPException(status_code=500, detail="优化结果为空，请重试")

        return OptimizeResponse(
            optimized_content=optimized_content,
            optimization_notes=optimization_notes,
            dimension="recommended_version_review",
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception(
            "项目 %s 第 %s 章推荐版本优化失败: %s",
            request.project_id,
            request.chapter_number,
            exc,
        )
        raise HTTPException(
            status_code=500,
            detail=f"评审优化过程中发生错误: {str(exc)[:200]}"
        )


@router.post("/apply-optimization")
async def apply_optimization(
    request: Optional[ApplyOptimizationRequest] = None,
    project_id: Optional[str] = None,
    chapter_number: Optional[int] = None,
    optimized_content: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
    current_user: UserInDB = Depends(get_current_user),
):
    """
    应用优化后的内容到章节，并立即同步伏笔（覆盖本章旧的自动伏笔）。
    """
    novel_service = NovelService(session)

    resolved_project_id = request.project_id if request else project_id
    resolved_chapter_number = request.chapter_number if request else chapter_number
    resolved_optimized_content = request.optimized_content if request else optimized_content

    if not resolved_project_id or resolved_chapter_number is None or resolved_optimized_content is None:
        raise HTTPException(status_code=422, detail="缺少必填参数: project_id/chapter_number/optimized_content")

    project = await novel_service.ensure_project_owner(resolved_project_id, current_user.id)

    chapter = next(
        (ch for ch in project.chapters if ch.chapter_number == resolved_chapter_number),
        None
    )
    if not chapter:
        raise HTTPException(status_code=404, detail="章节不存在")

    target_version = chapter.selected_version
    if not target_version and chapter.versions:
        target_version = sorted(chapter.versions, key=lambda item: item.created_at)[-1]

    if target_version:
        target_version.content = resolved_optimized_content
        if not chapter.selected_version_id:
            chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version
    else:
        target_version = ChapterVersion(
            chapter_id=chapter.id,
            content=resolved_optimized_content,
            version_label="optimized",
        )
        session.add(target_version)
        await session.flush()
        chapter.selected_version_id = target_version.id
        chapter.selected_version = target_version

    chapter.status = ChapterGenerationStatus.SUCCESSFUL.value
    chapter.generation_progress = 100
    chapter.generation_step = "completed"
    chapter.generation_step_index = 7
    chapter.generation_step_total = 7
    chapter.word_count = len(resolved_optimized_content or "")

    try:
        from .writer import _sync_foreshadowings_for_chapter

        sync_stats = await _sync_foreshadowings_for_chapter(
            session,
            project_id=resolved_project_id,
            chapter=chapter,
            content=resolved_optimized_content,
            user_id=current_user.id,
        )
    except Exception as exc:
        await session.rollback()
        logger.exception(
            "应用优化后伏笔同步失败 project=%s chapter=%s err=%s",
            resolved_project_id,
            resolved_chapter_number,
            exc,
        )
        raise HTTPException(status_code=500, detail="优化内容保存失败：伏笔同步异常，请重试")

    logger.info(
        "用户 %s 应用了项目 %s 第 %s 章的优化内容并同步伏笔 created=%s revealed=%s developing=%s",
        current_user.id,
        resolved_project_id,
        resolved_chapter_number,
        sync_stats.get("created", 0),
        sync_stats.get("revealed", 0),
        sync_stats.get("developing", 0),
    )

    return {
        "status": "success",
        "message": "优化内容已应用，伏笔已同步",
        "foreshadowing_sync": sync_stats,
    }
