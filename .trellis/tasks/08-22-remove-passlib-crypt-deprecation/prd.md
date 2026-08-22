# 消除 passlib crypt 弃用预警

## Goal

消除密码哈希路径对已弃用 Python `crypt` 模块的导入依赖，同时保持现有 bcrypt 密码库、认证行为和安全参数兼容。

## Background

- 当前锁定 `passlib==1.7.4`、`bcrypt==3.2.2`，`backend/app/core/security.py` 使用 `CryptContext(schemes=["bcrypt"])`。
- passlib 导入 `crypt` 会产生弃用预警，Python 3.13 将移除该标准库模块。
- 已存用户密码是 bcrypt hash；替换封装不能导致现有用户无法登录。

## Requirements

- R1. 基于项目锁定版本、官方文档和源码比较最小可维护方案；优先使用维护中的 bcrypt 封装，不自制密码算法。
- R2. 禁止用 warning filter、全局忽略或仅换告警类别伪造解决。
- R3. 保持现有 bcrypt hash 的 verify 兼容、新 hash 安全参数、错误输入行为及认证服务公开契约。
- R4. 不执行批量密码迁移；若新封装支持按登录渐进升级，必须单独说明并取得批准后才能加入。
- R5. 依赖变更只覆盖密码哈希所需包，锁文件通过项目现有依赖生成流程更新。

## Acceptance Criteria

- [ ] 导入安全模块和运行认证测试时不再产生 `crypt`/passlib 相关弃用预警。
- [ ] 既有 bcrypt hash 可验证，错误密码被拒绝，新 hash 可被当前实现和兼容测试验证。
- [ ] 登录、注册、改密、默认管理员密码检查等相关测试通过。
- [ ] 后端 Ruff、快速 profile 与依赖一致性检查通过。
- [ ] 没有明文密码、hash 或测试密钥进入日志、文档和提交材料。

## Out of Scope

- 改变密码策略、登录 UX、token 机制或批量重哈希数据库。
- 升级无关认证/加密依赖或引入自研密码哈希实现。

## Notes

- 具体替代库和兼容策略在该子任务独立规划时确定。
