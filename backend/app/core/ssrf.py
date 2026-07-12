# AIMETA P=SSRF防护_base_url安全校验|R=拒绝私有/元数据/特殊地址|NR=不含业务逻辑|E=assert_safe_base_url|X=internal|A=校验工具|D=stdlib|S=net|RD=./README.ai
"""SSRF 防护：校验用户配置的 LLM/Embedding/TTS base_url 不指向私有、链路本地或云元数据地址。

非法时抛 ``ValueError``，由调用方转成对应的领域异常（HTTP 400 / 配置错误）。
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

# 云厂商元数据服务地址（IMDS），SSRF 高危目标，单独列出以确保拦截
_CLOUD_METADATA_HOSTS = {"169.254.169.254", "fd00:ec2::254"}


def assert_safe_base_url(
    url: str | None,
    *,
    allow_loopback: bool = True,
    allow_private: bool = False,
) -> None:
    """校验 base_url 安全性，非法抛 ValueError。

    - 仅允许 http/https 协议；
    - 解析主机全部 A/AAAA 记录，逐条校验 IP 分类；
    - 默认放行环回（本机 ollama 等合法本地服务），拒绝其他私有/链路本地/元数据/组播/保留地址。
    """
    if not url or not url.strip():
        raise ValueError("API URL 不能为空")
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"不支持的 API URL 协议：{parsed.scheme or '空'}（仅允许 http/https）")
    host = parsed.hostname
    if not host:
        raise ValueError("API URL 缺少主机名")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        # 主机不可解析时上游请求同样会失败，不构成 SSRF 风险，放行
        return
    if not infos:
        return
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if str(ip) in _CLOUD_METADATA_HOSTS:
            raise ValueError(f"不允许访问云元数据地址：{ip}")
        if ip.is_loopback:
            if not allow_loopback:
                raise ValueError(f"不允许访问环回地址：{ip}")
            continue
        if ip.is_link_local:
            raise ValueError(f"不允许访问链路本地地址：{ip}")
        if ip.is_multicast or ip.is_unspecified or ip.is_reserved:
            raise ValueError(f"不允许访问特殊地址：{ip}")
        if ip.is_private and not allow_private:
            raise ValueError(
                f"不允许访问私有内网地址：{ip}（内网部署可在服务端开启 ALLOW_PRIVATE_LLM_ENDPOINTS）"
            )
