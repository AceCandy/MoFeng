# AIMETA P=Linuxdo_OAuth安全测试|R=state绑定_原子消费_cookie清理|NR=不访问真实Redis或OAuth|E=test_*|X=internal|A=security_test|D=pytest,httpx|S=test|RD=./README.ai
from __future__ import annotations

import asyncio
import hashlib
import threading
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
from fastapi import FastAPI, HTTPException
from redis.exceptions import ResponseError

from app.api.routers import auth as auth_router
from app.core.config import settings
from app.schemas.user import Token
from app.services import auth_service as auth_service_module
from app.services.auth_service import AuthService, LinuxdoOAuthStateError

_LINUXDO_CONFIG = {
    "linuxdo.client_id": "client-id",
    "linuxdo.client_secret": "client-secret",
    "linuxdo.redirect_uri": "https://app.example/api/auth/linuxdo/register",
    "linuxdo.auth_url": "https://provider.example/oauth/authorize",
    "linuxdo.token_url": "https://provider.example/oauth/token",
    "linuxdo.user_info_url": "https://provider.example/api/user",
}


class _FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.calls: list[tuple[object, ...]] = []
        self.thread_ids: list[int] = []
        self._lock = threading.Lock()
        self.getdel_error: Exception | None = None

    def set(self, key: str, value: str, *, ex: int, nx: bool) -> bool:
        self.thread_ids.append(threading.get_ident())
        self.calls.append(("set", key, value, ex, nx))
        with self._lock:
            if nx and key in self.values:
                return False
            self.values[key] = value
        return True

    def getdel(self, key: str) -> str | None:
        self.thread_ids.append(threading.get_ident())
        self.calls.append(("getdel", key))
        if self.getdel_error:
            raise self.getdel_error
        with self._lock:
            return self.values.pop(key, None)


def _service(monkeypatch, redis_client: _FakeRedis | None) -> tuple[AuthService, object]:
    session = SimpleNamespace(add=Mock(), commit=AsyncMock())
    service = AuthService(session)
    service.is_linuxdo_login_enabled = AsyncMock(return_value=True)
    service._get_config_value = AsyncMock(side_effect=_LINUXDO_CONFIG.get)

    def get_redis_client():
        if redis_client is not None:
            redis_client.thread_ids.append(threading.get_ident())
        return redis_client

    monkeypatch.setattr(auth_service_module, "_get_redis_client", get_redis_client)
    return service, session


def _install_provider_transport(
    monkeypatch,
    *,
    user_payload: dict[str, object] | None = None,
) -> list[httpx.Request]:
    real_async_client = httpx.AsyncClient
    requests: list[httpx.Request] = []
    payload = user_payload or {
        "id": 42,
        "username": "linuxdo-user",
        "email": "user@example.com",
    }

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/oauth/token"):
            return httpx.Response(200, json={"access_token": "provider-token"})
        if request.url.path.endswith("/api/user"):
            return httpx.Response(200, json=payload)
        return httpx.Response(404)

    def client_factory(*_args, **_kwargs):
        return real_async_client(transport=httpx.MockTransport(handler))

    monkeypatch.setattr(auth_service_module.httpx, "AsyncClient", client_factory)
    monkeypatch.setattr(
        auth_service_module,
        "assert_safe_base_url",
        lambda *_args, **_kwargs: None,
    )
    return requests


def _reject_provider_client(*_args, **_kwargs):
    raise AssertionError("state 校验失败时不得创建 provider HTTP client")


def _app_with_service(service) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.dependency_overrides[auth_router.get_auth_service] = lambda: service
    return app


@pytest.mark.asyncio
async def test_create_authorization_hashes_state_and_uses_threaded_redis(monkeypatch) -> None:
    redis_client = _FakeRedis()
    service, _session = _service(monkeypatch, redis_client)
    monkeypatch.setattr(auth_service_module.secrets, "token_urlsafe", lambda _size: "browser-state")
    main_thread = threading.get_ident()

    url, state, secure = await service.create_linuxdo_authorization()

    expected_key = f"oauth:linuxdo:state:{hashlib.sha256(state.encode()).hexdigest()}"
    query = parse_qs(urlsplit(url).query)
    assert state == "browser-state"
    assert secure is True
    assert query == {
        "client_id": ["client-id"],
        "redirect_uri": ["https://app.example/api/auth/linuxdo/register"],
        "response_type": ["code"],
        "scope": ["user"],
        "state": ["browser-state"],
    }
    assert redis_client.calls == [
        (
            "set",
            expected_key,
            "1",
            auth_service_module.LINUXDO_OAUTH_STATE_TTL_SECONDS,
            True,
        )
    ]
    assert "browser-state" not in expected_key
    assert redis_client.thread_ids
    assert all(thread_id != main_thread for thread_id in redis_client.thread_ids)


@pytest.mark.asyncio
async def test_create_authorization_allows_local_http_without_secure_cookie(monkeypatch) -> None:
    redis_client = _FakeRedis()
    service, _session = _service(monkeypatch, redis_client)
    config = {**_LINUXDO_CONFIG, "linuxdo.redirect_uri": "http://localhost:8000/api/auth/linuxdo/register"}
    service._get_config_value = AsyncMock(side_effect=config.get)
    monkeypatch.setattr(settings, "environment", "development")

    _url, _state, secure = await service.create_linuxdo_authorization()

    assert secure is False


@pytest.mark.asyncio
async def test_create_authorization_rejects_production_http_redirect(monkeypatch) -> None:
    redis_client = _FakeRedis()
    service, _session = _service(monkeypatch, redis_client)
    config = {**_LINUXDO_CONFIG, "linuxdo.redirect_uri": "http://app.example/api/auth/linuxdo/register"}
    service._get_config_value = AsyncMock(side_effect=config.get)
    monkeypatch.setattr(settings, "environment", "production")

    with pytest.raises(ValueError, match="HTTPS"):
        await service.create_linuxdo_authorization()

    assert redis_client.calls == []


@pytest.mark.asyncio
async def test_create_authorization_fails_closed_without_redis(monkeypatch) -> None:
    service, _session = _service(monkeypatch, None)

    with pytest.raises(ConnectionError, match="state"):
        await service.create_linuxdo_authorization()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "state", "browser_state"),
    [
        (None, "state", "state"),
        ("code", None, "state"),
        ("code", "state", None),
        ("code", "state", "other-state"),
    ],
)
async def test_callback_rejects_missing_or_mismatched_request_state_before_provider(
    monkeypatch,
    code: str | None,
    state: str | None,
    browser_state: str | None,
) -> None:
    service, _session = _service(monkeypatch, _FakeRedis())
    service._consume_linuxdo_state = AsyncMock()
    monkeypatch.setattr(auth_service_module.httpx, "AsyncClient", _reject_provider_client)

    with pytest.raises(LinuxdoOAuthStateError, match="重新发起"):
        await service.handle_linuxdo_callback(code, state, browser_state)

    service._consume_linuxdo_state.assert_not_awaited()


@pytest.mark.asyncio
async def test_callback_rejects_expired_state_before_provider(monkeypatch) -> None:
    service, _session = _service(monkeypatch, _FakeRedis())
    service._consume_linuxdo_state = AsyncMock(return_value=False)
    monkeypatch.setattr(auth_service_module.httpx, "AsyncClient", _reject_provider_client)

    with pytest.raises(LinuxdoOAuthStateError, match="重新发起"):
        await service.handle_linuxdo_callback("code", "state", "state")


@pytest.mark.asyncio
async def test_getdel_failure_is_unavailable_without_fallback(monkeypatch) -> None:
    redis_client = _FakeRedis()
    redis_client.getdel_error = ResponseError("unknown command 'GETDEL'")
    service, _session = _service(monkeypatch, redis_client)

    with pytest.raises(ConnectionError, match="state"):
        await service._consume_linuxdo_state("state")


@pytest.mark.asyncio
async def test_concurrent_callback_consumes_state_once_and_replay_fails(monkeypatch) -> None:
    state = "one-time-state"
    redis_client = _FakeRedis()
    state_key = f"oauth:linuxdo:state:{hashlib.sha256(state.encode()).hexdigest()}"
    redis_client.values[state_key] = "1"
    service, _session = _service(monkeypatch, redis_client)
    requests = _install_provider_transport(monkeypatch)
    existing_user = SimpleNamespace(username="existing-user", is_admin=False)
    service.user_repo.get_by_external_id = AsyncMock(return_value=existing_user)
    service.is_registration_enabled = AsyncMock(return_value=False)
    service.create_access_token = AsyncMock(return_value=Token(access_token="app-token"))

    results = await asyncio.gather(
        service.handle_linuxdo_callback("code-a", state, state),
        service.handle_linuxdo_callback("code-b", state, state),
        return_exceptions=True,
    )

    assert sum(isinstance(result, Token) for result in results) == 1
    assert sum(isinstance(result, LinuxdoOAuthStateError) for result in results) == 1
    assert [request.method for request in requests] == ["POST", "GET"]
    service.is_registration_enabled.assert_not_awaited()

    with pytest.raises(LinuxdoOAuthStateError):
        await service.handle_linuxdo_callback("code-c", state, state)
    assert [request.method for request in requests] == ["POST", "GET"]


@pytest.mark.asyncio
async def test_callback_keeps_registration_gate_for_new_user(monkeypatch) -> None:
    state = "registration-state"
    redis_client = _FakeRedis()
    state_key = f"oauth:linuxdo:state:{hashlib.sha256(state.encode()).hexdigest()}"
    redis_client.values[state_key] = "1"
    service, session = _service(monkeypatch, redis_client)
    _install_provider_transport(monkeypatch)
    service.user_repo.get_by_external_id = AsyncMock(return_value=None)
    service.is_registration_enabled = AsyncMock(return_value=False)

    with pytest.raises(HTTPException) as exc_info:
        await service.handle_linuxdo_callback("code", state, state)

    assert exc_info.value.status_code == 403
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_login_route_sets_bound_host_only_cookie(monkeypatch) -> None:
    service = SimpleNamespace(
        is_linuxdo_login_enabled=AsyncMock(return_value=True),
        create_linuxdo_authorization=AsyncMock(
            return_value=(
                "https://provider.example/oauth/authorize?state=browser-state",
                "browser-state",
                True,
            )
        ),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/auth/linuxdo/login", follow_redirects=False)

    cookie = response.headers["set-cookie"]
    assert response.status_code == 307
    assert response.headers["location"].endswith("state=browser-state")
    assert f"{auth_router.LINUXDO_OAUTH_STATE_COOKIE}=browser-state" in cookie
    assert f"Path={auth_router.LINUXDO_OAUTH_COOKIE_PATH}" in cookie
    assert f"Max-Age={auth_service_module.LINUXDO_OAUTH_STATE_TTL_SECONDS}" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=lax" in cookie
    assert "Secure" in cookie
    assert "Domain=" not in cookie


@pytest.mark.asyncio
async def test_login_route_keeps_disabled_provider_as_404() -> None:
    service = SimpleNamespace(is_linuxdo_login_enabled=AsyncMock(return_value=False))
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/auth/linuxdo/login", follow_redirects=False)

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_login_route_maps_state_store_failure_to_503() -> None:
    service = SimpleNamespace(
        is_linuxdo_login_enabled=AsyncMock(return_value=True),
        create_linuxdo_authorization=AsyncMock(side_effect=ConnectionError("unavailable")),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        response = await client.get("/api/auth/linuxdo/login", follow_redirects=False)

    assert response.status_code == 503


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("params", "browser_state", "expected_call"),
    [
        ({"code": "code"}, "browser-state", ("code", None, "browser-state")),
        (
            {"code": "code", "state": "browser-state"},
            None,
            ("code", "browser-state", None),
        ),
        (
            {"state": "browser-state"},
            "browser-state",
            (None, "browser-state", "browser-state"),
        ),
    ],
)
async def test_callback_route_maps_missing_state_cookie_or_code_to_400(
    params: dict[str, str],
    browser_state: str | None,
    expected_call: tuple[str | None, str | None, str | None],
) -> None:
    service = SimpleNamespace(
        is_linuxdo_login_enabled=AsyncMock(return_value=True),
        handle_linuxdo_callback=AsyncMock(
            side_effect=LinuxdoOAuthStateError("登录请求已失效，请重新发起")
        ),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        if browser_state is not None:
            client.cookies.set(
                auth_router.LINUXDO_OAUTH_STATE_COOKIE,
                browser_state,
                path=auth_router.LINUXDO_OAUTH_COOKIE_PATH,
            )
        response = await client.get("/api/auth/linuxdo/register", params=params)

    assert response.status_code == 400
    assert response.json() == {"detail": "登录请求已失效，请重新发起"}
    assert "Max-Age=0" in response.headers["set-cookie"]
    service.handle_linuxdo_callback.assert_awaited_once_with(*expected_call)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("enabled_result", "expected_status"),
    [(False, 404), (RuntimeError("config unavailable"), 500)],
)
async def test_callback_route_clears_cookie_when_provider_switch_is_unavailable(
    enabled_result: bool | Exception,
    expected_status: int,
) -> None:
    enabled = (
        AsyncMock(side_effect=enabled_result)
        if isinstance(enabled_result, Exception)
        else AsyncMock(return_value=enabled_result)
    )
    service = SimpleNamespace(
        is_linuxdo_login_enabled=enabled,
        handle_linuxdo_callback=AsyncMock(),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        client.cookies.set(
            auth_router.LINUXDO_OAUTH_STATE_COOKIE,
            "browser-state",
            path=auth_router.LINUXDO_OAUTH_COOKIE_PATH,
        )
        response = await client.get(
            "/api/auth/linuxdo/register",
            params={"code": "code", "state": "browser-state"},
        )

    assert response.status_code == expected_status
    assert "Max-Age=0" in response.headers["set-cookie"]
    service.handle_linuxdo_callback.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (LinuxdoOAuthStateError("登录请求已失效，请重新发起"), 400),
        (ConnectionError("unavailable"), 503),
        (HTTPException(status_code=403, detail="当前暂未开放注册"), 403),
        (RuntimeError("provider failed"), 500),
    ],
)
async def test_callback_route_clears_cookie_on_every_failure(
    error: Exception,
    expected_status: int,
) -> None:
    service = SimpleNamespace(
        is_linuxdo_login_enabled=AsyncMock(return_value=True),
        handle_linuxdo_callback=AsyncMock(side_effect=error),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        client.cookies.set(
            auth_router.LINUXDO_OAUTH_STATE_COOKIE,
            "browser-state",
            path=auth_router.LINUXDO_OAUTH_COOKIE_PATH,
        )
        response = await client.get(
            "/api/auth/linuxdo/register",
            params={"code": "code", "state": "browser-state"},
        )

    cookie = response.headers["set-cookie"]
    assert response.status_code == expected_status
    assert f"{auth_router.LINUXDO_OAUTH_STATE_COOKIE}=" in cookie
    assert "Max-Age=0" in cookie
    assert f"Path={auth_router.LINUXDO_OAUTH_COOKIE_PATH}" in cookie


@pytest.mark.asyncio
async def test_callback_route_clears_cookie_after_success() -> None:
    service = SimpleNamespace(
        is_linuxdo_login_enabled=AsyncMock(return_value=True),
        handle_linuxdo_callback=AsyncMock(return_value=Token(access_token="app-token")),
    )
    app = _app_with_service(service)

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="https://testserver",
    ) as client:
        client.cookies.set(
            auth_router.LINUXDO_OAUTH_STATE_COOKIE,
            "browser-state",
            path=auth_router.LINUXDO_OAUTH_COOKIE_PATH,
        )
        response = await client.get(
            "/api/auth/linuxdo/register",
            params={"code": "code", "state": "browser-state"},
        )

    assert response.status_code == 200
    assert "window.location.replace('/workspace')" in response.text
    assert "Max-Age=0" in response.headers["set-cookie"]
    service.handle_linuxdo_callback.assert_awaited_once_with(
        "code",
        "browser-state",
        "browser-state",
    )
