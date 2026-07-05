# Backend Logging Guidelines

> stdlib `logging`, configured once, obtained per module. Lazy formatting everywhere.

---

## Library and setup

Use the standard library `logging` module — **not** loguru or structlog. Configuration lives in `app/main.py` via `dictConfig` and runs once at import time.

```python
from logging.config import dictConfig
dictConfig({
    "version": 1, "disable_existing_loggers": False,
    "formatters": {"default": {"format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
    "loggers": {
        "app": {"level": settings.logging_level, "handlers": ["console"], "propagate": False},
        ...
    },
    "root": {"level": "WARNING", "handlers": ["console"]},
})
```

Format: `%(asctime)s [%(levelname)s] %(name)s - %(message)s`. Level is driven by `settings.logging_level` (env `LOGGING_LEVEL`, validated against the stdlib level names in `app/core/config.py`).

Reference: `app/main.py`.

> Known mismatch: the configured tree also names `backend.*` loggers, but modules emit under `app.*` (because of `getLogger(__name__)` with package path `app.…`). The `app` logger entry is what actually catches real modules. Do not rely on `backend.*` names; keep using `__name__`.

---

## Obtain a logger per module

Top of every module that logs:

```python
import logging
logger = logging.getLogger(__name__)
```

Confirmed across `app/api/routers/auth.py`, `admin.py`, `novels.py`, `app/services/emotion_service.py`, `app/tasks/emotion_tasks.py`, and 30+ other files.

---

## Lazy formatting — always

Pass message arguments as positional `%s` args, never interpolate with f-strings. The logging call can then short-circuit when the level is disabled.

Good example — `app/api/routers/llm_config.py`:

```python
logger.info("用户 %s 获取 LLM 配置包", current_user.id)
```

Bad example — `app/tasks/emotion_tasks.py`:

```python
logger.info(f"任务进度 ... {novel_id}")   # interpolates even if level disabled
```

---

## Log levels

| Level | When (observed convention) | Example |
|-------|----------------------------|---------|
| `debug` | Verbose diagnostic detail; usually gated by `settings.debug`. ~7 uses total — use sparingly. | `logger.debug("读取当前用户：%s", user.id)` |
| `info` | Normal operation: endpoint hit, operation succeeded, scheduled task tick. The default. | `logger.info("管理员 %s 创建用户：%s", admin.username, user.id)` |
| `warning` | Degraded path the request still recovered from: missing optional config, fallback used, retry attempted. | `logger.warning("SMTP 配置缺失，跳过邮件发送")` |
| `error` | Operation failed but the process keeps serving. | `logger.error("LLM 调用失败: %s", exc)` |
| `exception` | Inside an `except` block — logs the traceback. Prefer this over `error(... exc_info=True)`. | `except Exception: logger.exception("生成章节失败")` |

---

## What to log

- Endpoint entry for admin / write operations (with operator id).
- Long-running task start/end with the entity id.
- Branch decisions that affect behavior (e.g. provider fallback, skip path).
- External call outcomes (LLM, SMTP, OAuth).

## What NOT to log

- Passwords, hashed passwords, JWT tokens, refresh tokens, API keys, raw `Authorization` headers.
- Full request bodies that may contain user content secrets (prompt payloads are large — log ids, not content).
- Per-row dumps in hot loops.

---

## Anti-patterns to avoid

- **f-string / `.format` inside the log call.** Use `%s` args. Known in `app/tasks/emotion_tasks.py`.
- **`logger = logging.getLogger(__name__)` declared inside a function or method.** Recreates the logger every call and hides it from configuration. Known in `app/services/auth_service.py` (inside `_send_email`). Declare at module top.
- **`print(...)` for diagnostics.** Goes around the configured handlers and the level system.
- **Logging the same exception twice** (once with `error`, again with `exception`). Pick `exception` inside the handler that owns recovery.
- **Logging secrets** (see above).
