"""assert_production_security 对默认管理员密码的校验测试（H3）。"""
import pytest

from app.core.config import assert_production_security, settings

_STRONG_SECRET = "a" * 32  # 满足 SECRET_KEY 长度 >=32 且非弱值


def test_assert_production_security_rejects_default_admin_password(monkeypatch) -> None:
    """生产环境使用占位符默认密码必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "your-admin-password-change-me")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_rejects_known_weak_admin_password(monkeypatch) -> None:
    """生产环境使用已知弱口令 ChangeMe123! 必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "ChangeMe123!")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_rejects_short_admin_password(monkeypatch) -> None:
    """生产环境管理员密码长度 <8 必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "short1")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_passes_with_strong_admin_password(monkeypatch) -> None:
    """生产环境强密码 + 强 SECRET_KEY 应通过校验（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "a-very-strong-password-123")
    assert_production_security()  # 不抛即通过


def test_assert_production_security_skips_non_production(monkeypatch) -> None:
    """非生产环境跳过校验，即使使用默认占位符密码（H3）。"""
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "admin_default_password", "your-admin-password-change-me")
    assert_production_security()  # 不抛即通过


def test_production_allows_empty_admin_password_when_admin_bootstrap_is_disabled() -> None:
    config = settings.model_copy(
        update={
            "environment": "production",
            "debug": False,
            "secret_key": _STRONG_SECRET,
            "bootstrap_create_default_admin": False,
            "admin_default_password": "",
        }
    )

    assert_production_security(config)
