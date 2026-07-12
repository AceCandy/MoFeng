"""SSRF 校验工具的单元测试。

用字面 IP 构造用例，避免依赖外部 DNS（沙箱可能把外部域名解析到 198.18 私有段）。
显式传入 allow_private/allow_loopback，不依赖全局 settings。
"""
import pytest

from app.core.ssrf import assert_safe_base_url


def _ok(url, **kw):
    assert_safe_base_url(url, **kw)  # 不抛即放行


def _bad(url, **kw):
    with pytest.raises(ValueError):
        assert_safe_base_url(url, **kw)


def test_allows_public_and_loopback():
    _ok("https://8.8.8.8/v1")
    _ok("http://127.0.0.1:11434")
    _ok("http://localhost:11434")


def test_rejects_metadata_private_special_nonhttp_empty():
    _bad("http://169.254.169.254")
    _bad("http://10.0.0.1")
    _bad("http://192.168.1.5")
    _bad("http://172.16.0.1")
    _bad("ftp://8.8.8.8")
    _bad("")
    _bad(None)


def test_allow_private_switch():
    _ok("http://10.0.0.1", allow_private=True)


def test_disable_loopback():
    _bad("http://127.0.0.1", allow_loopback=False)
