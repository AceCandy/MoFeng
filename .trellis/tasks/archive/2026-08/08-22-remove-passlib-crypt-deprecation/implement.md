# 实施计划

## 1. 回归测试

- 在现有安全模块测试中加入 bcrypt 行为契约：`$2b$`、12 rounds、正确/错误验证、Unicode、NUL 与 72/73-byte 边界。
- 先确认测试可识别 passlib 与直接 bcrypt 的边界差异，再修改实现。

## 2. 最小实现与依赖锁

- 将 `CryptContext` 两个调用替换为直接 bcrypt 适配，更新相关 AIMETA 依赖声明。
- 修改 `requirements.in`，移除 passlib 并约束 `bcrypt>=4.3.0,<5.0.0`。
- 在临时虚拟环境中用固定 pip/pip-tools 重新生成 `requirements.txt` 与 `requirements-dev.txt`；检查无关依赖没有漂移。

## 3. 验证

```bash
cd backend
.venv/bin/python -m pytest -q tests/test_security.py tests/test_database_bootstrap.py tests/test_config_security.py tests/test_auth_linuxdo_oauth.py
.venv/bin/python -W error::DeprecationWarning -c "import app.core.security"
.venv/bin/ruff check app/core/security.py app/services/auth_service.py tests/test_security.py
.venv/bin/python -m pytest -m "not postgres" --strict-markers
```

- 在干净临时环境使用 `pip install --require-hashes -r requirements.txt` 验证 runtime lock，并运行 `pip_audit -r requirements.txt`。
- 独立复核现有 hash 兼容、密码边界、锁文件来源、无 warning filter 和无无关依赖升级。
- 检查 `git diff --check`，确认没有日志、文档或提交材料包含真实密码、真实 hash 或真实密钥。
