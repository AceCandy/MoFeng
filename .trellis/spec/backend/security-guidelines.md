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

### Password hashing contract

#### 1. Scope / Trigger

Apply when changing password hashing, verification, authentication dependencies, or
stored bcrypt compatibility.

#### 2. Signatures

- `hash_password(password: str) -> str`
- `verify_password(plain_password: str, hashed_password: str) -> bool`

#### 3. Contracts

- Use `bcrypt>=4.3.0,<5.0.0` directly; do not reintroduce passlib or a wrapper that
  only delegates to bcrypt.
- Encode passwords as UTF-8, reject NUL, and generate `$2b$` hashes with 12 rounds.
- Preserve bcrypt 4.3's 72-byte truncation so existing long-password behavior and
  stored hashes remain compatible. A change to bcrypt 5+ requires a separate migration
  decision because it rejects passwords longer than 72 bytes.
- Verification must accept existing passlib-generated bcrypt hashes. Do not add batch
  migration or login-time rehashing without a separate approved task.

#### 4. Validation & Error Matrix

| Condition | Required behavior |
| --- | --- |
| Correct password and valid existing bcrypt hash | Return `True` |
| Wrong password and valid bcrypt hash | Return `False` |
| Password contains NUL | Raise `ValueError` |
| Hash is malformed or not ASCII bcrypt text | Raise `ValueError` |
| Password differs only after byte 72 | Preserve bcrypt 4.3 truncation behavior |

#### 5. Good / Base / Bad Cases

- Good: a passlib-generated `$2b$12$...` fixture verifies through `bcrypt.checkpw`.
- Base: a Unicode password round-trips after UTF-8 encoding.
- Bad: filtering the `crypt` deprecation warning while passlib remains imported.

#### 6. Tests Required

- Assert new hash prefix, Unicode round-trip, wrong-password rejection, NUL rejection,
  a fixed existing passlib hash, malformed hash handling, and the exact 72/73 UTF-8
  byte boundary.
- Import `app.core.security` with `DeprecationWarning` treated as an error.

#### 7. Wrong vs Correct

```python
# Wrong: imports Python's deprecated crypt path through passlib.
pwd_context = CryptContext(schemes=["bcrypt"])

# Correct: one maintained implementation with explicit compatibility parameters.
bcrypt.hashpw(password_bytes, bcrypt.gensalt(rounds=12, prefix=b"2b"))
```

### SECRET_KEY strength gate

`app/core/config.py::assert_production_security` runs at app startup (`main.py` lifespan) and before explicit data bootstrap. In `production` it refuses to proceed when `SECRET_KEY` is shorter than 32 chars or matches a known weak/default value (`ChangeMe123!`, `"secret"`, etc.).

```python
def assert_production_security(config: Settings = settings) -> None:
    if config.environment != "production":
        return
    key = config.secret_key or ""
    if len(key) < 32 or key.strip() in _WEAK_SECRET_KEYS:
        raise RuntimeError(...)
```

Non-production environments skip the check so local dev keeps working with placeholder keys.

The same gate covers `ADMIN_DEFAULT_PASSWORD` only when `BOOTSTRAP_CREATE_DEFAULT_ADMIN=true`: in production it rejects passwords shorter than 8 chars or matching a known weak/default value (`ChangeMe123!`, `your-admin-password-change-me`, etc.). The deployment script requires a non-empty password under the same condition; disabling default-admin bootstrap permits an empty value. Credentials are consumed only by `db-bootstrap` and never logged.

### Default admin password rotation

`AuthService.requires_password_reset` flags any `is_admin` user whose hash still verifies against `settings.admin_default_password`. The flag flows into the token as `must_change_password`; the frontend forces a change. This covers **all** admins (matched by `is_admin`, not by username). `change_password` additionally rejects setting an admin's password back to the default.

### Verification code comparison

Email codes are compared with `secrets.compare_digest` (`AuthService.verify_code`) — constant-time, no early-exit. Codes are stored in Redis (`vcode:{email}`, TTL 300s) when `REDIS_URL` is set, falling back to an in-process dict so multi-worker deployments stay consistent. Send frequency is rate-limited via `vcode:last:{email}` (60s).

### OAuth registration gate

`handle_linuxdo_callback` checks `is_registration_enabled()` before creating a user from an OAuth callback — OAuth is not a backdoor around the registration switch. Username collisions are disambiguated with `secrets.token_hex(3)`.

### Linux.do OAuth state contract

#### 1. Scope / Trigger

Apply this contract when changing the Linux.do login route, callback route, Redis state
storage, or OAuth cookie behavior. It prevents login CSRF and replay across workers.

#### 2. Signatures

- `create_linuxdo_authorization() -> tuple[str, str, bool]` returns the provider URL,
  raw browser state, and whether the cookie must be `Secure`.
- `handle_linuxdo_callback(code, state, browser_state) -> Token` validates and consumes
  state before reading provider credentials or making provider HTTP requests.

#### 3. Contracts

- Generate state with `secrets.token_urlsafe(32)` and keep it for exactly 300 seconds.
- Store only `sha256(state)` under `oauth:linuxdo:state:<digest>` with Redis
  `SET ... NX EX 300`; consume it atomically with Redis 6.2+ `GETDEL`.
- Run synchronous Redis initialization, `SET`, and `GETDEL` via `asyncio.to_thread`.
- Bind the query state to a HostOnly, HttpOnly, SameSite=Lax cookie whose path is
  `/api/auth/linuxdo`; derive `Secure` from the configured redirect URI.
- Production redirect URIs require HTTPS. Development HTTP is limited to loopback.
- Redis is mandatory when Linux.do login is enabled; never reuse the verification-code
  in-process fallback for OAuth state.

#### 4. Validation & Error Matrix

| Condition | Public result |
| --- | --- |
| Missing code, query state, or cookie; mismatch; expiry; replay | 400 and delete cookie |
| Redis missing, unavailable, or without `GETDEL` | 503 and delete cookie |
| Linux.do login disabled | 404 and delete callback cookie |
| Production callback URI is not HTTPS | Login request fails before redirect |
| Valid, unconsumed state | Exactly one provider token exchange |

#### 5. Good / Base / Bad Cases

- Good: matching query/cookie values plus one Redis key enter the provider exchange once.
- Base: an existing external user can log in while registration is disabled.
- Bad: a second or concurrent callback cannot enter the provider exchange.

#### 6. Tests Required

- Assert the Redis key contains only the SHA-256 digest and uses `NX`, `EX`, and `GETDEL`.
- Assert missing, mismatched, expired, replayed, and concurrent callbacks do not produce
  more than one provider request sequence.
- Assert login/callback 503 behavior, cookie attributes, cookie cleanup, HTTPS policy,
  the registration gate, and the disabled-provider 404 behavior.

#### 7. Wrong vs Correct

```python
# Wrong: state is not browser-bound or atomically consumed.
if redis_client.get(state):
    await exchange_code(code)

# Correct: compare first, atomically consume the hashed key, then call the provider.
if not secrets.compare_digest(state, browser_state):
    raise LinuxdoOAuthStateError(...)
if not await consume_hashed_state_with_getdel(state):
    raise LinuxdoOAuthStateError(...)
await exchange_code(code)
```

### Resource ownership

`NovelService.ensure_project_owner(project_id, user_id)` is the single ownership gate for project-scoped routes. Unauthorized access returns the **same 404 as a missing project** — same status, same detail — so a caller cannot learn whether a resource exists:

```python
project = await self.repo.get_by_id(project_id)
if not project:
    raise HTTPException(404, "项目不存在")
if project.user_id != user_id:
    # 越权访问统一返回 404，与"项目不存在"同码同文案，避免泄露项目存在性
    raise HTTPException(404, "项目不存在")
```

`_ensure_project_owner_light` (a read-only variant that selects only `user_id`) follows the same rule. Every project-scoped route (`novels`, `projects`, `writer`, `optimizer`, `review`, …) goes through one of these — do not add ad-hoc ownership checks in routers. Covered by `tests/test_project_owner_authorization.py`.

> Do **not** return 403 for ownership failures: 403 ("authenticated but forbidden") leaks that the resource exists. 403 remains correct for unrelated gates — admin-role requirements (`dependencies.py`) and registration/OAuth switches (`auth_service.py`) — which are not resource-existence leaks.

---

## Review checklist

- [ ] No new `allow_origins=["*"]`; CORS origins come from `settings.cors_origins_list`.
- [ ] User-supplied `base_url` passes `assert_safe_base_url` before outbound use.
- [ ] Secret fields (API keys) written via `crypto.encrypt`; only a masked preview leaves the backend.
- [ ] Verification codes compared with `secrets.compare_digest`; send rate-limited.
- [ ] OAuth / user-creation paths respect `is_registration_enabled()`.
- [ ] Project-scoped routes go through `ensure_project_owner`.
- [ ] No secrets in log lines (see [logging-guidelines](./logging-guidelines.md)).
