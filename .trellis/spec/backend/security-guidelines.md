# Backend Security Guidelines

> Production security baseline for boundaries controlled by user input: CORS, secret-field encryption, SSRF, and authn/authz hardening. New code that touches any of these boundaries must follow this guide.

---

## CORS

`app/main.py` wires `CORSMiddleware` with origins from `settings.cors_origins_list` (the `cors_origins` setting split on comma). `allow_credentials=True`, so **`cors_origins` must never contain the wildcard `*`** — browsers reject credentialed responses under a wildcard origin.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Rules:
- Add allowed origins via the `CORS_ORIGINS` env var (comma-separated full origins, scheme included), never hardcode.
- `cors_origins_list` is a `@property` on `Settings` (`app/core/config.py`); consume it, do not re-parse the raw string elsewhere.
- `assert_production_security` does not validate CORS — the wildcard-plus-credentials footgun is prevented by convention, not by a startup gate.

---

## Secret-field encryption (Fernet)

User upstream API keys are stored as ciphertext. `app/core/crypto.py` derives a Fernet key from `SECRET_KEY` via PBKDF2-HMAC-SHA256 (480k iterations, fixed salt) and prefixes ciphertext with `v1:`.

```python
from app.core.crypto import encrypt, decrypt, is_encrypted

stored = encrypt(plaintext_api_key)   # persist this
plain  = decrypt(stored)              # read back; None if invalid token
is_encrypted(stored)                  # True iff prefixed
```

Rules:
- Encrypt at the service boundary before persisting; decrypt on read. Layers above the service never see ciphertext.
- `decrypt` returns the value as-is when it has no `v1:` prefix — intentional for migrating legacy plaintext rows. New writes always go through `encrypt`.
- On `InvalidToken` (key rotation / corruption) `decrypt` returns `None` rather than raising — callers must tolerate a missing key.
- Never log decrypted values. Expose only a masked `api_key_preview` to the frontend.
- The Fernet key is derived from `SECRET_KEY`; rotating `SECRET_KEY` invalidates every stored API key. Plan a re-encryption migration before rotating.

---

## SSRF protection for user-supplied base_url

LLM / Embedding / TTS `base_url` values are user-configurable and must pass `app/core/ssrf.py::assert_safe_base_url` before any outbound request.

```python
from app.core.ssrf import assert_safe_base_url

assert_safe_base_url(url, allow_loopback=True, allow_private=False)
```

The check:
- Rejects schemes other than `http`/`https`.
- Resolves the hostname via `socket.getaddrinfo` and inspects **every** A/AAAA record (not just the first) — defeats DNS-rebinding to a private IP.
- Rejects cloud metadata endpoints (`169.254.169.254`, `fd00:ec2::254`), link-local, multicast, unspecified, and reserved addresses.
- Defaults: loopback allowed (local ollama etc.), other private addresses rejected. Callers may pass `allow_private=True` for a trusted intranet deployment.
- An unresolvable hostname is allowed (the upstream request will fail anyway; no SSRF risk).

Rules:
- Call `assert_safe_base_url` where the config is accepted (e.g. `llm_config_service`). It raises `ValueError`; the router translates to HTTP 400.

---

## Auth hardening

### SECRET_KEY strength gate

`app/core/config.py::assert_production_security` runs at app startup (`main.py` lifespan). In `production` it refuses to boot when `SECRET_KEY` is shorter than 32 chars or matches a known weak/default value (`ChangeMe123!`, `"secret"`, etc.).

```python
def assert_production_security() -> None:
    if settings.environment != "production":
        return
    key = settings.secret_key or ""
    if len(key) < 32 or key.strip() in _WEAK_SECRET_KEYS:
        raise RuntimeError(...)
```

Non-production environments skip the check so local dev keeps working with placeholder keys.

### Default admin password rotation

`AuthService.requires_password_reset` flags any `is_admin` user whose hash still verifies against `settings.admin_default_password`. The flag flows into the token as `must_change_password`; the frontend forces a change. This covers **all** admins (matched by `is_admin`, not by username). `change_password` additionally rejects setting an admin's password back to the default.

### Verification code comparison

Email codes are compared with `secrets.compare_digest` (`AuthService.verify_code`) — constant-time, no early-exit. Codes are stored in Redis (`vcode:{email}`, TTL 300s) when `REDIS_URL` is set, falling back to an in-process dict so multi-worker deployments stay consistent. Send frequency is rate-limited via `vcode:last:{email}` (60s).

### OAuth registration gate

`handle_linuxdo_callback` checks `is_registration_enabled()` before creating a user from an OAuth callback — OAuth is not a backdoor around the registration switch. Username collisions are disambiguated with `secrets.token_hex(3)`.

### Resource ownership

`NovelService.ensure_project_owner(project_id, user_id)` is the single ownership gate for project-scoped routes:

```python
project = await self.repo.get_by_id(project_id)
if not project:
    raise HTTPException(404, "项目不存在")
if project.user_id != user_id:
    raise HTTPException(403, "无权访问该项目")
```

> **Known divergence from the audit recommendation**: the audit asked unauthorized access to return 404 (to avoid leaking that a resource exists), but the implementation returns 403 for "exists but not yours" and 404 only for "does not exist". 403 does leak existence. Aligning to 404 is a tracked follow-up; until then, new ownership checks should match the current 403/404 split for consistency.

---

## Review checklist

- [ ] No new `allow_origins=["*"]`; CORS origins come from `settings.cors_origins_list`.
- [ ] User-supplied `base_url` passes `assert_safe_base_url` before outbound use.
- [ ] Secret fields (API keys) written via `crypto.encrypt`; only a masked preview leaves the backend.
- [ ] Verification codes compared with `secrets.compare_digest`; send rate-limited.
- [ ] OAuth / user-creation paths respect `is_registration_enabled()`.
- [ ] Project-scoped routes go through `ensure_project_owner`.
- [ ] No secrets in log lines (see [logging-guidelines](./logging-guidelines.md)).
