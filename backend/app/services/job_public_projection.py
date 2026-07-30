# AIMETA P=持久任务公开投影_错误与日志脱敏|R=公开文本脱敏_任务快照白名单|NR=不读取私有payload或提交事务|E=sanitize_public_text|X=internal|A=projection|D=regex|S=none|RD=./README.ai
"""Build the allowlisted public projection of a durable job."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from ..models.background_task import BackgroundTask
from ..schemas.task import BackgroundTaskResponse

_SECRET_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(api[_-]?key|authorization|token|secret|password)\b"
    r"(\s*[=:]\s*)(?:bearer\s+)?([^,\s;]+)"
)
_BEARER_CREDENTIAL_PATTERN = re.compile(r"(?i)\bbearer(\s+)([^,\s;]+)")
_PUBLIC_LOG_LEVELS = {"debug", "info", "warning", "error", "critical"}


def sanitize_public_text(value: str, *, max_length: int = 300) -> str:
    """压平、限长并隐藏公开错误或日志中的常见凭据。"""

    normalized = re.sub(r"\s+", " ", value).strip() or "任务执行失败"
    redacted = _SECRET_ASSIGNMENT_PATTERN.sub(r"\1\2[已隐藏]", normalized)
    redacted = _BEARER_CREDENTIAL_PATTERN.sub(r"Bearer\1[已隐藏]", redacted)
    return redacted if len(redacted) <= max_length else f"{redacted[:max_length].rstrip()}..."


def _isoformat(value: Optional[datetime]) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _public_log_entries(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    projected: list[dict[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict):
            continue
        timestamp = entry.get("timestamp")
        level = entry.get("level")
        message = entry.get("message")
        if (
            not isinstance(timestamp, str)
            or not isinstance(level, str)
            or not isinstance(message, str)
        ):
            continue
        normalized_level = level.lower()
        projected.append(
            {
                "timestamp": timestamp[:64],
                "level": normalized_level if normalized_level in _PUBLIC_LOG_LEVELS else "info",
                "message": sanitize_public_text(message),
            }
        )
    return projected


def public_job_snapshot(job: BackgroundTask) -> dict[str, Any]:
    """构造可进入 task list、snapshot 与 SSE event log 的白名单任务快照。"""

    return {
        "id": job.id,
        "user_id": job.user_id,
        "project_id": job.project_id,
        "stream_type": job.stream_type,
        "stream_id": job.stream_id,
        "task_type": job.task_type,
        "title": job.title,
        "status": BackgroundTaskResponse.public_status(job.status),
        "progress": job.progress,
        "error": sanitize_public_text(job.error) if isinstance(job.error, str) else None,
        "log_entries": _public_log_entries(job.log_entries),
        "created_at": _isoformat(job.created_at),
        "updated_at": _isoformat(job.updated_at),
        "started_at": _isoformat(job.started_at),
        "completed_at": _isoformat(job.completed_at),
    }
