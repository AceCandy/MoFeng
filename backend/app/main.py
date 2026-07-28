# AIMETA P=FastAPI应用入口_装配路由依赖和生命周期管理|R=应用启动_路由注册_中间件配置|NR=不含业务逻辑实现|E=uvicorn_app.main:app|X=http|A=FastAPI_app实例|D=fastapi,uvicorn|S=net,db|RD=./README.ai
"""FastAPI 应用入口，负责装配路由、依赖与生命周期管理。"""

import logging
from logging.config import dictConfig
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import assert_production_security, settings
from .db.readiness import check_database_readiness
from .services.prompt_service import PromptService
from .db.session import AsyncSessionLocal
from .api.routers import api_router


dictConfig(
    {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s [%(levelname)s] %(name)s - %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            }
        },
        "loggers": {
            "backend": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.app": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.api": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
            "backend.services": {
                "level": settings.logging_level,
                "handlers": ["console"],
                "propagate": False,
            },
        },
        "root": {
            "level": "WARNING",
            "handlers": ["console"],
        },
    }
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    assert_production_security()
    readiness = await check_database_readiness()
    if readiness.ready:
        async with AsyncSessionLocal() as session:
            prompt_service = PromptService(session)
            await prompt_service.preload()
    else:
        logger.warning(
            "数据库未就绪，跳过 Prompt 预热，codes=%s",
            ",".join(readiness.codes),
        )
    yield


app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 配置：仅允许白名单来源，生产环境通过 CORS_ORIGINS 配置具体域名
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


# Liveness 只确认应用进程可响应，不访问依赖。
@app.get("/health", tags=["Health"])
@app.get("/api/health", tags=["Health"])
async def health_check():
    """健康检查接口，返回应用状态。"""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
    }


@app.get("/ready", tags=["Health"])
@app.get("/api/ready", tags=["Health"])
async def readiness_check():
    """动态检查数据库 schema、bootstrap 与二进制回滚下限。"""

    readiness = await check_database_readiness()
    return JSONResponse(
        status_code=200 if readiness.ready else 503,
        content=readiness.as_dict(),
    )
