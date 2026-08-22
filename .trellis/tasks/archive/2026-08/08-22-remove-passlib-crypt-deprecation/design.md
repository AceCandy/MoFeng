# 技术设计

## 1. 边界

只替换密码哈希适配层和对应直接依赖。认证服务、用户模型、数据库字段、JWT、密码策略及 API 契约保持不变。

## 2. 密码适配

- `security.py` 直接调用维护中的 `bcrypt`，新 hash 固定使用 `$2b$`、12 rounds。
- 密码统一按 UTF-8 编码，hash 按 ASCII 编解码；既有 `$2b$` bcrypt hash 可直接验证。
- 在调用 bcrypt 前显式拒绝 NUL，保持 passlib 当前错误边界。
- bcrypt 限制为 `>=4.3.0,<5.0.0`：获得明确的 Python 3.13 支持，同时避开 5.0 对超过 72 bytes 密码改为抛错的行为变化。
- 保持当前 72-byte 截断兼容，不在本任务改变密码策略或触发批量/登录时重哈希。

## 3. 依赖与锁

- 从 `requirements.in` 删除 `passlib[bcrypt]`，更新 bcrypt 范围。
- 使用项目固定的 pip 24.3.1 / pip-tools 7.6.0 重新生成 runtime/dev hash lock。
- 预期锁文件只移除 passlib、更新 bcrypt 及其必要传递依赖；出现无关升级时停止并收窄生成结果。

## 4. 兼容与回滚

- 测试覆盖正确/错误密码、Unicode、NUL、72/73-byte 边界及 hash 前缀/cost。
- 导入安全模块时把 DeprecationWarning 视为错误，证明不是过滤 warning。
- 回滚时同时恢复适配层、依赖输入和两个锁文件；不涉及数据回滚。
