# Backend Error Handling

> How errors are raised, translated, and returned to clients.

---

## Current state (read this first)

The codebase has **two coexisting error-signaling patterns** and **no custom exception classes** and **no global `@app.exception_handler`**. When writing new code, follow the Recommended pattern below; do not propagate the coupled pattern.

| Pattern | Where used | Verdict for new code |
|---------|------------|----------------------|
| **A. Service raises `ValueError`, router translates to `HTTPException`** | `user_service`, `llm_config_service`, `foreshadowing_service`, `prompt_service` | ✅ Recommended |
| **B. Service raises `HTTPException` directly** | `auth_service`, `novel_service`, `llm_service`, `import_service`, `update_log_service`, `chapter_generation_trace_service` | ⚠️ Legacy — couples service layer to FastAPI, do not extend |
| `RuntimeError` raised and never translated | `ai_review_service` | ⚠️ Becomes an uncontrolled 500 |

---

## Recommended pattern: raise domain errors, translate at the router

Services signal failure with a plain exception (`ValueError` today; a future `DomainError` base class is a candidate). The router catches and converts it to an `HTTPException` with the right status code.

Good example — service side, `app/services/user_service.py`:

```python
try:
    await self.session.commit()
except IntegrityError as exc:
    await self.session.rollback()
    raise ValueError("用户名或邮箱已存在") from exc
```

Good example — router side, `app/api/routers/admin.py`:

```python
try:
    user = await service.create_user_admin(payload)
except ValueError as e:
    raise HTTPException(status_code=400, detail=str(e))
```

Why: the service stays import-safe and testable without FastAPI; HTTP status mapping lives at the edge.

---

## "Not found" via Optional + router 404

For missing records, services return `Optional[...]` (or `bool`) and the router raises 404. `app/api/routers/admin.py`:

```python
user = await service.get_user(user_id)
if not user:
    raise HTTPException(status_code=404, detail="用户不存在")
```

---

## API error response shape

FastAPI's default error envelope is `{"detail": "<message>"}`. Frontend `requestRaw` reads `detail` first, then `message`/`error`/`msg`/`title`/`errors[]` (see `frontend/src/api/http.ts`). Keep error messages user-readable and Chinese, since they surface directly in the UI.

| Status | Use for |
|--------|---------|
| 400 | Validation / business rule violation (e.g. "用户名或邮箱已存在") |
| 401 | Missing or invalid credentials |
| 403 | Authenticated but not allowed (e.g. non-admin hits admin route) |
| 404 | Resource not found |
| 409 | Conflict (rare; integrity violations currently map to 400) |
| 422 | Pydantic validation failure (FastAPI default) |
| 500 | Unexpected server error |

---

## Async/sync boundary

When wrapping a sync library that can throw (e.g. SMTP), use `asyncio.to_thread` and translate the caught exception inside the service. `app/services/auth_service.py`:

```python
try:
    await asyncio.to_thread(_send)
except Exception as exc:
    raise HTTPException(status_code=500, detail="验证码发送失败，请检查邮件配置") from exc
```

(This case legitimately raises `HTTPException` because SMTP failure has no domain meaning beyond "send failed" — acceptable, but for new domain rules prefer `ValueError` + router translation.)

---

## Anti-patterns to avoid

- **Raising `HTTPException` from deep inside a service or repository.** It couples the data/business layer to FastAPI and prevents the service from being reused by Celery tasks or scripts.
- **Swallowing all exceptions and returning an empty result.** Masks failures as "no data". Known occurrence — `app/api/routers/llm_config.py` returns `[]` on any exception with only a log. Prefer letting the exception propagate to the router, or return a typed error.
- **Raising `RuntimeError` that nothing catches.** Becomes an opaque 500. Either translate at the router or add a global handler.
- **`except Exception: pass`** anywhere outside a deliberate, commented fallback.
- **Returning `None` to mean "error" for non-lookup operations** (ambiguous with "not found").
- **Wrapping N independent LLM/external calls in one `try/except` that forces all-or-nothing, or silently swallowing each call's failure.** A single call failing must not discard the others' results nor report `success=True` when nothing was produced. Use a per-call wrapper (e.g. `FinalizeService._safe_llm_call`) that catches, records the failure into a result list, and returns `None`; the orchestrator then sets `success` strictly from how many calls produced a valid value, with `partial_success` when some failed. See `app/services/finalize_service.py`.

---

## Future direction (not yet implemented)

A `DomainError` base class plus a single `@app.exception_handler(DomainError)` in `app/main.py` would unify Patterns A and B, centralize the status-code map, and give Celery/script callers a stable exception type. Treat this as a migration target, not a prerequisite for small changes.
