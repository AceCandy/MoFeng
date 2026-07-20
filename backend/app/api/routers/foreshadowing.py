# AIMETA P=伏笔API_伏笔列表查询|R=伏笔列表查询|NR=不含创建回收分析|E=route:GET_/api/novels/*/foreshadowings|X=http|A=伏笔查询|D=fastapi,sqlalchemy|S=db|RD=./README.ai
"""伏笔管理 API 接口"""
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_session
from ...services.foreshadowing_service import ForeshadowingService
from ...services.novel_service import NovelService
from ...core.dependencies import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/novels", tags=["foreshadowing"])


def _handle_foreshadowing_error(action: str) -> HTTPException:
    logger.exception("%s失败", action)
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"{action}失败，请稍后重试",
    )


@router.get("/{project_id}/foreshadowings")
async def list_foreshadowings(
    project_id: str,
    status: Optional[str] = Query(None),
    foreshadowing_type: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
    current_user = Depends(get_current_user),
):
    """获取伏笔列表"""
    # 越权校验置于 try 外：非项目拥有者统一返回 404，与“项目不存在”同码同文案，
    # 避免被下方通用异常处理吞成 500 并泄露项目存在性（审计 #14）
    novel_service = NovelService(session)
    await novel_service.ensure_project_owner(project_id, current_user.id)
    try:
        service = ForeshadowingService(session)
        foreshadowings, total = await service.get_foreshadowings(
            project_id=project_id,
            status=status,
            foreshadowing_type=foreshadowing_type,
            limit=limit,
            offset=offset,
        )

        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "data": [
                {
                    "id": f.id,
                    "chapter_number": f.chapter_number,
                    "content": f.content,
                    "type": f.type,
                    "status": f.status,
                    "resolved_chapter_number": f.resolved_chapter_number,
                    "is_manual": f.is_manual,
                    "ai_confidence": f.ai_confidence,
                    "author_note": f.author_note,
                    "created_at": f.created_at.isoformat(),
                }
                for f in foreshadowings
            ],
        }
    except Exception:
        raise _handle_foreshadowing_error("获取伏笔列表")
