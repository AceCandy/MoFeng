# AIMETA P=应用配置_环境变量加载和设置类|R=配置加载_环境变量|NR=不含业务逻辑|E=settings|X=internal|A=Settings类|D=pydantic|S=fs|RD=./README.ai
from functools import lru_cache
from typing import Optional

from pydantic import AliasChoices, AnyUrl, Field, HttpUrl, validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    """应用全局配置，所有可调参数集中于此，统一加载自环境变量。"""

    # -------------------- 基础应用配置 --------------------
    app_name: str = Field(default="AI Novel Generator API", description="FastAPI 文档标题")
    environment: str = Field(default="development", description="当前环境标识")
    debug: bool = Field(default=True, description="是否开启调试模式")
    allow_registration: bool = Field(
        default=True,
        validation_alias=AliasChoices(
            "ALLOW_USER_REGISTRATION",
            "ALLOW_REGISTRATION",
        ),
        description="是否允许用户自助注册",
    )
    logging_level: str = Field(
        default="INFO",
        description="应用日志级别",
    )
    cors_origins: str = Field(
        default="http://localhost:6100,http://127.0.0.1:6100",
        description="允许的跨域来源，逗号分隔；生产环境必须配置为具体域名，禁止使用通配符 *",
    )
    allow_private_llm_endpoints: bool = Field(
        default=False,
        description="是否允许 LLM/Embedding/TTS 指向私有/内网地址；仅内网部署时开启",
    )
    version_info_url: Optional[AnyUrl] = Field(
        default="https://raw.githubusercontent.com/2754026865/mofeng/refs/heads/main/release-metadata/version-info.json",
        description="GitHub 版本信息 JSON 地址",
    )
    enable_linuxdo_login: bool = Field(
        default=False,
        description="是否启用 Linux.do OAuth 登录",
    )

    # -------------------- 安全相关配置 --------------------
    secret_key: str = Field(..., description="JWT 加密密钥")
    jwt_algorithm: str = Field(default="HS256", description="JWT 加密算法")
    access_token_expire_minutes: int = Field(
        default=60 * 24 * 7, description="访问令牌过期时间，单位分钟"
    )

    # -------------------- 数据库配置 --------------------
    database_url: Optional[str] = Field(
        default=None, description="完整的数据库连接串，填入后覆盖下方数据库配置"
    )
    postgres_host: str = Field(default="localhost", description="PostgreSQL 主机名")
    postgres_port: int = Field(default=5432, description="PostgreSQL 端口")
    postgres_user: str = Field(default="postgres", description="PostgreSQL 用户名")
    postgres_password: str = Field(default="", description="PostgreSQL 密码")
    postgres_database: str = Field(default="mofeng", description="PostgreSQL 数据库名称")

    # -------------------- 管理员初始化配置 --------------------
    bootstrap_create_default_admin: bool = Field(
        default=True,
        description="显式数据库引导时是否在无管理员的情况下创建默认管理员",
    )
    admin_default_username: str = Field(default="admin", description="默认管理员用户名")
    admin_default_password: str = Field(
        default="your-admin-password-change-me",
        description="默认管理员密码；生产环境必须改为强密码",
    )
    admin_default_email: Optional[str] = Field(default=None, description="默认管理员邮箱")

    # -------------------- LLM 相关配置 --------------------
    openai_api_key: Optional[str] = Field(default=None, description="默认的 LLM API Key")
    openai_base_url: Optional[HttpUrl] = Field(
        default=None,
        validation_alias=AliasChoices("OPENAI_API_BASE_URL", "OPENAI_BASE_URL"),
        description="LLM API Base URL",
    )
    openai_model_name: str = Field(default="gpt-4o-mini", description="默认 LLM 模型名称")
    writer_chapter_versions: int = Field(
        default=1,
        ge=1,
        validation_alias=AliasChoices("WRITER_CHAPTER_VERSION_COUNT", "WRITER_CHAPTER_VERSIONS"),
        description="每次生成章节的候选版本数量（支持 1~2）",
    )
    writer_chapter_word_limit: int = Field(
        default=3000,
        ge=2200,
        description="章节正文生成目标字数下限配置，低于 2200 会回退默认值",
    )
    vector_top_k_chunks: int = Field(
        default=5,
        ge=0,
        description="剧情 chunk 检索条数",
    )
    vector_top_k_summaries: int = Field(
        default=3,
        ge=0,
        description="章节摘要检索条数",
    )
    vector_chunk_size: int = Field(
        default=480,
        ge=128,
        description="章节分块的目标字数",
    )
    vector_chunk_overlap: int = Field(
        default=120,
        ge=0,
        description="章节分块重叠字数",
    )
    vector_store_enabled: bool = Field(
        default=True,
        description="是否启用向量检索（pgvector），关闭后 RAG 检索将跳过",
    )
    chapter_context_shadow_compare: bool = Field(
        default=False,
        description="是否记录 canonical Chapter context 与旧 prompt contract 的脱敏结构差异",
    )
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis 连接串（如 redis://localhost:6379/0），留空则禁用缓存与分布式会话",
    )
    job_worker_name: Optional[str] = Field(
        default=None,
        description="durable worker 服务名；进程实例 ID 会附加 pid 与随机 incarnation",
    )
    job_worker_generation: int = Field(
        default=1,
        ge=1,
        description="durable worker 当前 executor generation",
    )
    job_lease_seconds: int = Field(
        default=120,
        ge=2,
        description="单次 job lease 时长",
    )
    job_heartbeat_interval_seconds: float = Field(
        default=30.0,
        gt=0,
        description="执行中 job lease 续租间隔，必须小于 lease",
    )
    job_worker_heartbeat_interval_seconds: float = Field(
        default=10.0,
        gt=0,
        description="worker 进程生命周期心跳间隔",
    )
    job_worker_poll_interval_seconds: float = Field(
        default=1.0,
        gt=0,
        description="无任务时 PostgreSQL 扫描间隔",
    )
    job_worker_health_stale_seconds: int = Field(
        default=45,
        ge=2,
        description="worker heartbeat 超过该秒数即不健康",
    )
    job_peak_concurrency: int = Field(
        default=20,
        ge=1,
        description="production readiness 预期 durable job 峰值并发",
    )
    job_load_test_concurrency: int = Field(
        default=40,
        ge=1,
        description="production readiness 至少双倍目标并发演练值",
    )
    job_payload_max_bytes: int = Field(
        default=1024 * 1024,
        ge=1,
        description="durable job canonical JSON payload 最大 UTF-8 字节数",
    )
    job_max_duration_seconds: int = Field(
        default=30 * 60,
        ge=1,
        description="durable job 单次执行最大时长",
    )
    job_recovery_slo_seconds: int = Field(
        default=5 * 60,
        ge=1,
        description="worker crash recovery P95 目标上限",
    )
    job_queue_age_alert_seconds: int = Field(
        default=60,
        ge=1,
        description="最老 queued/retry job 超过该秒数触发告警",
    )
    job_projection_lag_alert_seconds: int = Field(
        default=5 * 60,
        ge=1,
        description="projection backlog 超过该秒数触发告警",
    )
    job_event_retention_days: int = Field(
        default=30,
        ge=1,
        description="JobEvent 保留天数",
    )
    job_retention_max_bytes: int = Field(
        default=100 * 1024 * 1024 * 1024,
        ge=1,
        description="JobEvent retention 最大预算字节数",
    )
    job_event_cleanup_interval_seconds: int = Field(
        default=3600,
        ge=60,
        description="worker 执行 JobEvent retention cleanup 的间隔",
    )
    chapter_workflow_retention_days: int = Field(
        default=30,
        ge=1,
        description="terminal Chapter workflow 私有状态保留天数",
    )
    chapter_workflow_retention_batch_size: int = Field(
        default=100,
        ge=1,
        le=500,
        description="单次 Chapter workflow retention 最大 run 数",
    )

    # -------------------- Linux.do OAuth 配置 --------------------
    linuxdo_client_id: Optional[str] = Field(default=None, description="Linux.do OAuth Client ID")
    linuxdo_client_secret: Optional[str] = Field(
        default=None, description="Linux.do OAuth Client Secret"
    )
    linuxdo_redirect_uri: Optional[HttpUrl] = Field(
        default=None, description="Linux.do OAuth 回调地址"
    )
    linuxdo_auth_url: Optional[HttpUrl] = Field(default=None, description="Linux.do OAuth 授权地址")
    linuxdo_token_url: Optional[HttpUrl] = Field(
        default=None, description="Linux.do OAuth Token 获取地址"
    )
    linuxdo_user_info_url: Optional[HttpUrl] = Field(
        default=None, description="Linux.do 用户信息接口地址"
    )

    # -------------------- 邮件配置 --------------------
    smtp_server: Optional[str] = Field(default=None, description="SMTP 服务地址")
    smtp_port: int = Field(default=587, description="SMTP 服务端口")
    smtp_username: Optional[str] = Field(default=None, description="SMTP 登录用户名")
    smtp_password: Optional[str] = Field(default=None, description="SMTP 登录密码")
    email_from: Optional[str] = Field(default=None, description="邮件发送方显示名或邮箱")

    model_config = SettingsConfigDict(
        env_file=("new-backend/.env", ".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @validator("database_url", pre=True, always=True)
    def _normalize_database_url(cls, value: Optional[str]) -> Optional[str]:
        """当环境变量中提供 DATABASE_URL 时，原样返回，便于自定义。"""
        return value.strip() if isinstance(value, str) and value.strip() else value

    @validator("logging_level", pre=True)
    def _normalize_logging_level(cls, value: Optional[str]) -> str:
        """规范日志级别配置。"""
        candidate = (value or "INFO").strip().upper()
        valid_levels = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG", "NOTSET"}
        if candidate not in valid_levels:
            raise ValueError("LOGGING_LEVEL 仅支持 CRITICAL/ERROR/WARNING/INFO/DEBUG/NOTSET")
        return candidate

    @validator("job_load_test_concurrency")
    def _validate_load_test_concurrency(cls, value: int, values: dict[str, object]) -> int:
        """确保 readiness 演练至少覆盖目标峰值的两倍。"""
        peak = values.get("job_peak_concurrency", 20)
        if isinstance(peak, int) and value < peak * 2:
            raise ValueError("JOB_LOAD_TEST_CONCURRENCY 必须至少是 JOB_PEAK_CONCURRENCY 的 2 倍")
        return value

    @property
    def sqlalchemy_database_uri(self) -> str:
        """生成 SQLAlchemy 兼容的异步连接串（PostgreSQL）。"""
        if self.database_url:
            url = make_url(self.database_url)
            database = (url.database or "").strip("/")
            normalized = URL.create(
                drivername=url.drivername,
                username=url.username,
                password=url.password,
                host=url.host,
                port=url.port,
                database=database or None,
                query=url.query,
            )
            return normalized.render_as_string(hide_password=False)

        # PostgreSQL：统一对密码进行 URL 编码，避免特殊字符破坏连接串
        from urllib.parse import quote_plus

        encoded_password = quote_plus(self.postgres_password)
        database = (self.postgres_database or "").strip("/")
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{encoded_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{database}"
        )

    @property
    def cors_origins_list(self) -> list[str]:
        """解析 CORS_ORIGINS 为来源白名单，过滤空白与重复项。"""
        seen: dict[str, None] = {}
        for origin in self.cors_origins.split(","):
            normalized = origin.strip()
            if normalized and normalized not in seen:
                seen[normalized] = None
        return list(seen.keys())


@lru_cache
def get_settings() -> Settings:
    """使用 LRU 缓存确保配置只初始化一次，减少 IO 与解析开销。"""
    return Settings()


settings = get_settings()


# 已知不安全的 SECRET_KEY 默认/弱值，生产环境不得使用
_WEAK_SECRET_KEYS = {
    "",
    "请替换为随机且复杂的字符串",
    "your-secret-key-change-me-to-random-string",
    "your-admin-password-change-me",
    "ChangeMe123!",
    "Admin123456!",
    "secret",
    "change-me",
    "changeme",
}


def assert_production_security(config: Settings = settings) -> None:
    """生产环境启动前校验关键安全配置，弱配置直接拒绝启动。"""
    if config.environment != "production":
        return
    if config.debug:
        raise RuntimeError("生产环境不得开启 debug（debug 模式暴露错误栈与 SQL 参数）")
    key = config.secret_key or ""
    if len(key) < 32 or key.strip() in _WEAK_SECRET_KEYS:
        raise RuntimeError(
            "生产环境 SECRET_KEY 不安全：长度需 >=32 且不得使用默认/弱值；"
            "请用 `openssl rand -hex 32` 生成后写入 SECRET_KEY。"
        )
    admin_pwd = config.admin_default_password or ""
    if config.bootstrap_create_default_admin and (
        len(admin_pwd) < 8 or admin_pwd.strip() in _WEAK_SECRET_KEYS
    ):
        raise RuntimeError(
            "生产环境 ADMIN_DEFAULT_PASSWORD 不安全：长度需 >=8 且不得使用默认/弱值"
            "（如 ChangeMe123!、your-admin-password-change-me）；请设置强密码后写入 ADMIN_DEFAULT_PASSWORD。"
        )
