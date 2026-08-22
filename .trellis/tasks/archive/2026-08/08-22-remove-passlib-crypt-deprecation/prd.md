# 消除 passlib crypt 弃用预警

## Goal

消除密码哈希路径对已弃用 Python `crypt` 模块的导入依赖，同时保持现有 bcrypt 密码库、认证行为和安全参数兼容。

## Background

- 当前锁定 `passlib==1.7.4`、`bcrypt==3.2.2`，`backend/app/core/security.py` 使用 `CryptContext(schemes=["bcrypt"])`。
- passlib 导入 `crypt` 会产生弃用预警，Python 3.13 将移除该标准库模块。
- 已存用户密码是 bcrypt hash；替换封装不能导致现有用户无法登录。
- 当前 passlib 配置与直接 bcrypt 均使用 `$2b$`、12 rounds；锁定版本的双向 hash 验证已现场确认兼容。
- `bcrypt` 4.3.x 明确支持 Python 3.13，5.0 起会拒绝超过 72 bytes 的密码；若升级应限制 `<5` 并显式保持现有 NUL/72-byte 边界。
- `pwdlib` 的 bcrypt hasher 仍直接委托 `bcrypt`，会增加一层 beta 依赖，当前没有额外兼容收益。
- 已确认移除 passlib 后直接使用 `bcrypt>=4.3.0,<5.0.0`；不引入 pwdlib，不启用渐进重哈希。

## Requirements

- R1. 基于项目锁定版本、官方文档和源码比较最小可维护方案；优先使用维护中的 bcrypt 封装，不自制密码算法。
- R2. 禁止用 warning filter、全局忽略或仅换告警类别伪造解决。
- R3. 保持现有 bcrypt hash 的 verify 兼容、新 hash 安全参数、错误输入行为及认证服务公开契约。
- R4. 不执行批量密码迁移；若新封装支持按登录渐进升级，必须单独说明并取得批准后才能加入。
- R5. 依赖变更只覆盖密码哈希所需包，锁文件通过项目现有依赖生成流程更新。

## Acceptance Criteria

- [x] 导入安全模块和运行认证测试时不再产生 `crypt`/passlib 相关弃用预警。
- [x] 既有 bcrypt hash 可验证，错误密码被拒绝，新 hash 可被当前实现和兼容测试验证。
- [x] 登录、注册、改密、默认管理员密码检查等相关测试通过。
- [x] 后端 Ruff、快速 profile 与依赖一致性检查通过。
- [x] 没有真实明文密码、真实 hash 或真实密钥进入日志、文档和提交材料。

## Out of Scope

- 改变密码策略、登录 UX、token 机制或批量重哈希数据库。
- 升级无关认证/加密依赖或引入自研密码哈希实现。

## Notes

- 依赖锁继续使用项目固定的 pip 24.3.1 / pip-tools 7.6.0 生成流程。
