# AIMETA P=数据库引导审计_版本账本和旧库认领|R=数据引导账本_旧库认领审计|NR=不含执行逻辑|E=DatabaseBootstrapVersion_LegacyDatabaseAdoption|X=internal|A=ORM模型|D=sqlalchemy|S=db|RD=./README.ai
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class DatabaseBootstrapVersion(Base):
    """记录不可变数据引导步骤的执行状态和二进制回滚下限。"""

    __tablename__ = "database_bootstrap_versions"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    minimum_binary_version: Mapped[int] = mapped_column(Integer, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))


class LegacyDatabaseAdoption(Base):
    """审计 operator 对已知旧库基线的显式认领。"""

    __tablename__ = "legacy_database_adoptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    schema_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    adopted_revision: Mapped[str] = mapped_column(String(64), nullable=False)
    operator: Mapped[str] = mapped_column(String(128), nullable=False)
    backup_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    result: Mapped[str] = mapped_column(String(32), nullable=False)
    adopted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
