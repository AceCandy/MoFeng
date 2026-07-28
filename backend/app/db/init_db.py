# AIMETA P=数据库初始化兼容入口_显式流程组合|R=建库_迁移_版本化引导|NR=不供应用启动调用|E=init_db|X=internal|A=兼容函数|D=sqlalchemy,alembic|S=db|RD=./README.ai
import logging

from .bootstrap import run_bootstrap
from .migration import create_database, run_migrations

logger = logging.getLogger(__name__)


async def init_db() -> None:
    """兼容旧调用方的显式安装入口；应用 runtime 不得调用。"""

    logger.warning("旧数据库初始化入口已弃用，请改用 app.db.cli 的显式命令")
    await create_database()
    await run_migrations()
    await run_bootstrap()
