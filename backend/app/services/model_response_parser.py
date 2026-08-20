# AIMETA P=模型响应解析_章节正文与优化结果提取|R=完整包装校验_JSON修复_正文验证|NR=不含模型调用|E=parse_chapter_content_response,parse_optimizer_response|X=internal|A=解析器|D=json|S=none|RD=./README.ai
from __future__ import annotations

import json
import re
from typing import Any

from ..utils.json_utils import remove_think_tags, sanitize_json_like_text

_FENCED_RESPONSE_RE = re.compile(
    r"\A```(?:json|JSON)?\s*(?P<body>.*?)\s*```\Z",
    re.DOTALL,
)
_STRUCTURED_RESPONSE_PREFIX_RE = re.compile(
    r'\{[ \t\r\n]*"?(?:content|optimized_content|revised_content|chapter_content|'
    r'chapter_text|text|body|story|optimization_notes|report)"?[ \t\r\n]*:'
)
_LEADING_HEADING_RE = re.compile(r"\A#{1,6}[ \t]+[^\r\n]+(?:\r?\n+|$)")
_LEADING_SEPARATOR_RE = re.compile(r"\A[ \t]*(?:-{3,}|_{3,}|\*{3,})[ \t]*(?:\r?\n+|$)")
_CHAPTER_CONTENT_KEYS = (
    "content",
    "optimized_content",
    "revised_content",
    "chapter_content",
    "chapter_text",
    "text",
    "body",
    "story",
)


def _unwrap_complete_fence(text: str) -> str | None:
    match = _FENCED_RESPONSE_RE.fullmatch(text)
    if not match:
        return None
    body = (match.group("body") or "").strip()
    return (
        body.removeprefix(r"\r\n")
        .removeprefix(r"\n")
        .removesuffix(r"\r\n")
        .removesuffix(r"\n")
        .strip()
    )


def _load_complete_json(text: str) -> object | None:
    candidates = [text]
    fenced = _unwrap_complete_fence(text)
    if fenced is not None:
        candidates.append(fenced)

    for candidate in candidates:
        unescaped = (
            candidate.replace(r"\"", '"')
            .replace(r"\\r", r"\r")
            .replace(r"\\n", r"\n")
            .replace(r"\\t", r"\t")
        )
        for normalized in (candidate, unescaped):
            for parse_candidate in (normalized, sanitize_json_like_text(normalized)):
                try:
                    value: object = json.loads(parse_candidate)
                except json.JSONDecodeError:
                    continue
                return value
    return None


def _chapter_text_from_payload(payload: object) -> str | None:
    if isinstance(payload, str):
        return payload.strip() or None
    if isinstance(payload, dict):
        for key in _CHAPTER_CONTENT_KEYS:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None
    if isinstance(payload, list):
        parts = [_chapter_text_from_payload(item) for item in payload]
        content = "\n\n".join(part for part in parts if part)
        return content or None
    return None


def _strip_leading_heading(content: str) -> str:
    content = _LEADING_HEADING_RE.sub("", content, count=1)
    return _LEADING_SEPARATOR_RE.sub("", content, count=1)


def parse_chapter_content_response(raw_response: str) -> tuple[str, dict[str, Any]]:
    """提取章节正文；结构化包装不完整或缺少正文字段时失败关闭。"""
    content = remove_think_tags(raw_response).strip()
    report: dict[str, Any] = {}

    seen: set[str] = set()
    while content not in seen:
        seen.add(content)
        payload = _load_complete_json(content)
        if payload is None:
            stripped = content.lstrip()
            if stripped.startswith("```") or _STRUCTURED_RESPONSE_PREFIX_RE.search(stripped):
                raise ValueError("模型返回的结构化正文无法解析")
            break

        if isinstance(payload, dict) and not report and isinstance(payload.get("report"), dict):
            report = payload["report"]

        extracted = _chapter_text_from_payload(payload)
        if not extracted:
            raise ValueError("模型返回的结构化正文缺少有效正文")
        if extracted == content:
            break
        content = extracted
    else:
        raise ValueError("模型返回的结构化正文存在循环包装")

    content = _strip_leading_heading(content)
    if content:
        return content, report
    raise ValueError("模型未返回有效正文")


def _load_optimizer_payload(text: str) -> dict[str, Any] | None:
    payload = _load_complete_json(text)
    for _ in range(4):
        if isinstance(payload, str) and payload.strip() != text:
            text = payload.strip()
            payload = _load_complete_json(text)
            continue
        if isinstance(payload, dict):
            if "optimized_content" in payload:
                return payload
            for nested in payload.values():
                if isinstance(nested, dict) and "optimized_content" in nested:
                    return nested
        break
    return None


def _normalize_optimizer_notes(raw_notes: object) -> str:
    if not isinstance(raw_notes, str) or not raw_notes:
        return ""
    notes = raw_notes.strip()
    decoded = _load_complete_json(notes)
    return decoded.strip() if isinstance(decoded, str) else notes


def parse_optimizer_response(raw_response: str) -> tuple[str, str]:
    """提取完整结构化优化响应；无法可靠提取时失败关闭。"""
    cleaned = remove_think_tags(raw_response).strip()
    payload = _load_optimizer_payload(cleaned)
    if payload:
        raw_content = payload.get("optimized_content")
        if isinstance(raw_content, str):
            try:
                content, _report = parse_chapter_content_response(raw_content)
            except ValueError:
                pass
            else:
                notes = _normalize_optimizer_notes(payload.get("optimization_notes"))
                return content, (notes or "优化完成")

    raise RuntimeError("优化响应格式无效：缺少 optimized_content")
