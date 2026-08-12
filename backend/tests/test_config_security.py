"""assert_production_security 对默认管理员密码的校验测试（H3）。"""

import pytest

from app.core.config import Settings, assert_production_security, settings

_STRONG_SECRET = "a" * 32  # 满足 SECRET_KEY 长度 >=32 且非弱值


@pytest.mark.parametrize(
    "env_name",
    ["ALLOW_USER_REGISTRATION", "ALLOW_REGISTRATION"],
)
def test_registration_setting_accepts_canonical_and_legacy_env_names(
    monkeypatch,
    env_name: str,
) -> None:
    monkeypatch.delenv("ALLOW_USER_REGISTRATION", raising=False)
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)
    monkeypatch.setenv(env_name, "false")

    config = Settings(_env_file=None, secret_key=_STRONG_SECRET)

    assert config.allow_registration is False


def test_registration_setting_prefers_canonical_env_name(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_USER_REGISTRATION", "false")
    monkeypatch.setenv("ALLOW_REGISTRATION", "true")

    config = Settings(_env_file=None, secret_key=_STRONG_SECRET)

    assert config.allow_registration is False


def test_registration_setting_preserves_default_and_direct_construction(monkeypatch) -> None:
    monkeypatch.delenv("ALLOW_USER_REGISTRATION", raising=False)
    monkeypatch.delenv("ALLOW_REGISTRATION", raising=False)

    default_config = Settings(_env_file=None, secret_key=_STRONG_SECRET)
    explicit_config = Settings(
        _env_file=None,
        secret_key=_STRONG_SECRET,
        allow_registration=False,
    )

    assert default_config.allow_registration is True
    assert explicit_config.allow_registration is False


def test_settings_fields_do_not_use_deprecated_env_metadata() -> None:
    deprecated_fields = {
        name
        for name, field in Settings.model_fields.items()
        if field.json_schema_extra and "env" in field.json_schema_extra
    }

    assert deprecated_fields == set()


def test_standard_field_names_still_load_from_uppercase_env(monkeypatch) -> None:
    monkeypatch.setenv("SECRET_KEY", _STRONG_SECRET)
    monkeypatch.setenv("JOB_PEAK_CONCURRENCY", "21")
    monkeypatch.setenv("JOB_LOAD_TEST_CONCURRENCY", "42")

    config = Settings(_env_file=None)

    assert config.secret_key == _STRONG_SECRET
    assert config.job_peak_concurrency == 21
    assert config.job_load_test_concurrency == 42


def test_assert_production_security_rejects_default_admin_password(monkeypatch) -> None:
    """生产环境使用占位符默认密码必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "your-admin-password-change-me")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_rejects_known_weak_admin_password(monkeypatch) -> None:
    """生产环境使用已知弱口令 ChangeMe123! 必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "ChangeMe123!")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_rejects_short_admin_password(monkeypatch) -> None:
    """生产环境管理员密码长度 <8 必须拒绝启动（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
    monkeypatch.setattr(settings, "secret_key", _STRONG_SECRET)
    monkeypatch.setattr(settings, "admin_default_password", "short1")
    with pytest.raises(RuntimeError, match="ADMIN_DEFAULT_PASSWORD"):
        assert_production_security()


def test_assert_production_security_passes_with_strong_admin_password(monkeypatch) -> None:
    """生产环境强密码 + 强 SECRET_KEY 应通过校验（H3）。"""
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "debug", False)
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


def test_durable_runtime_readiness_defaults_and_two_x_guard() -> None:
    config = Settings(_env_file=None, secret_key=_STRONG_SECRET)
    assert config.job_peak_concurrency == 20
    assert config.job_load_test_concurrency == 40
    assert config.job_payload_max_bytes == 1024 * 1024
    assert config.job_max_duration_seconds == 1800
    assert config.job_event_retention_days == 30
    assert config.job_retention_max_bytes == 100 * 1024 * 1024 * 1024
    assert config.job_recovery_slo_seconds == 300
    assert config.job_queue_age_alert_seconds == 60
    assert config.job_projection_lag_alert_seconds == 300

    with pytest.raises(ValueError, match="至少是.*2 倍"):
        Settings(
            _env_file=None,
            secret_key=_STRONG_SECRET,
            job_peak_concurrency=20,
            job_load_test_concurrency=39,
        )
