"""pytest 全局 fixture。"""
import pytest

from app.core.config import settings


@pytest.fixture(autouse=True)
def _bypass_ssrf_in_integration_tests():
    """集成测试旁路 SSRF 校验（矩阵由 tests/test_ssrf.py 专门覆盖）。

    同时规避沙箱 DNS 把外部域名解析到 198.18 私有段导致的误拒。
    """
    previous = settings.allow_private_llm_endpoints
    settings.allow_private_llm_endpoints = True
    yield
    settings.allow_private_llm_endpoints = previous
