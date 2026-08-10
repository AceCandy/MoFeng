# AIMETA P=认证API_登录注册和令牌管理|R=用户认证_令牌生成|NR=不含用户管理|E=route:POST_/api/auth/*|X=http|A=登录_注册_令牌|D=fastapi,jose|S=db|RD=./README.ai
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.config import settings
from ...core.dependencies import get_current_user
from ...db.session import get_session
from ...schemas.user import AuthOptions, Token, User, UserInDB, UserRegistration
from ...services.auth_service import (
    LINUXDO_OAUTH_STATE_INVALID_DETAIL,
    LINUXDO_OAUTH_STATE_TTL_SECONDS,
    AuthService,
    LinuxdoOAuthStateError,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])
LINUXDO_OAUTH_STATE_COOKIE = "linuxdo_oauth_state"
LINUXDO_OAUTH_COOKIE_PATH = "/api/auth/linuxdo"


def get_auth_service(session: AsyncSession = Depends(get_session)) -> AuthService:
    return AuthService(session)


def _clear_linuxdo_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=LINUXDO_OAUTH_STATE_COOKIE,
        path=LINUXDO_OAUTH_COOKIE_PATH,
    )


def _linuxdo_callback_error(
    status_code: int,
    detail: object,
    headers: Optional[dict[str, str]] = None,
) -> JSONResponse:
    response = JSONResponse(
        status_code=status_code,
        content={"detail": detail},
        headers=headers,
    )
    _clear_linuxdo_state_cookie(response)
    return response


@router.post("/send-code", status_code=204)
async def send_verification_code(email: str, service: AuthService = Depends(get_auth_service)):
    await service.send_verification_code(email)
    logger.info("向 %s 发送验证码", email)


@router.get("/options", response_model=AuthOptions)
async def read_auth_options(service: AuthService = Depends(get_auth_service)):
    """读取认证功能开关，供前端动态渲染。"""
    options = await service.get_auth_options()
    return options


@router.post("/users", response_model=User, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserRegistration, service: AuthService = Depends(get_auth_service)):
    user = await service.register_user(payload)
    logger.info("注册新用户：%s", user.username)
    return User.model_validate(user)


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), service: AuthService = Depends(get_auth_service)):
    user = await service.authenticate_user(form_data.username, form_data.password)
    must_change_password = service.requires_password_reset(user)
    token = await service.create_access_token(user, must_change_password=must_change_password)
    logger.info("用户 %s 登录成功，需改密=%s", form_data.username, must_change_password)
    return token


@router.get("/users/me", response_model=User)
async def read_current_user(current_user: UserInDB = Depends(get_current_user)):
    logger.debug("读取当前用户：%s", current_user.username)
    return current_user


@router.get("/linuxdo/login")
async def login_with_linuxdo(service: AuthService = Depends(get_auth_service)):
    if not await service.is_linuxdo_login_enabled():
        logger.warning("Linux.do 登录未启用")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="未启用 Linux.do 登录")
    try:
        authorization_url, state_value, secure_cookie = await service.create_linuxdo_authorization()
    except ConnectionError as exc:
        logger.warning("Linux.do OAuth state 存储不可用")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Linux.do 登录服务暂不可用，请稍后重试",
        ) from exc
    except ValueError as exc:
        logger.error("Linux.do OAuth 配置不可用，error_type=%s", type(exc).__name__)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    response = RedirectResponse(url=authorization_url)
    response.set_cookie(
        key=LINUXDO_OAUTH_STATE_COOKIE,
        value=state_value,
        max_age=LINUXDO_OAUTH_STATE_TTL_SECONDS,
        path=LINUXDO_OAUTH_COOKIE_PATH,
        secure=secure_cookie,
        httponly=True,
        samesite="lax",
    )
    logger.info("跳转 Linux.do 授权")
    return response


@router.get("/linuxdo/register", response_class=HTMLResponse)
async def register_with_linuxdo(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    service: AuthService = Depends(get_auth_service),
):
    browser_state = request.cookies.get(LINUXDO_OAUTH_STATE_COOKIE)
    try:
        if not await service.is_linuxdo_login_enabled():
            return _linuxdo_callback_error(
                status.HTTP_404_NOT_FOUND,
                "未启用 Linux.do 登录",
            )
        token = await service.handle_linuxdo_callback(code, state, browser_state)
    except LinuxdoOAuthStateError:
        return _linuxdo_callback_error(
            status.HTTP_400_BAD_REQUEST,
            LINUXDO_OAUTH_STATE_INVALID_DETAIL,
        )
    except ConnectionError:
        logger.warning("Linux.do OAuth state 存储不可用")
        return _linuxdo_callback_error(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "Linux.do 登录服务暂不可用，请稍后重试",
        )
    except HTTPException as exc:
        return _linuxdo_callback_error(
            exc.status_code,
            exc.detail,
            headers=exc.headers,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Linux.do OAuth 回调失败，error_type=%s", type(exc).__name__)
        return _linuxdo_callback_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Linux.do 登录失败，请重新发起",
        )

    logger.info("Linux.do 授权回调成功")
    token_json = token.model_dump_json()
    html_content = f"""<!DOCTYPE html>
<html lang=\"zh-CN\">
<head><meta charset=\"UTF-8\"><title>正在跳转</title></head>
<body>
    <p>正在跳转，请稍候...</p>
    <script>
        (function() {{
            const token = JSON.parse('{token_json}');
            try {{
                window.localStorage.setItem('token', token.access_token);
            }} catch (err) {{
                console.error('无法写入本地存储', err);
            }}
            window.location.replace('/workspace');
        }})();
    </script>
</body>
</html>"""
    response = HTMLResponse(content=html_content)
    _clear_linuxdo_state_cookie(response)
    return response
