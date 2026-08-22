# 技术方案

## Boundaries

最小行为差距是：API/状态/导航当前会把“缺失或临时状态”伪装成真实结果，部分切换会直接销毁未保存表单，移动抽屉仍影响布局和辅助技术树。修复放在这些状态的拥有者，而不是在每个调用点增加临时判断。

预计修改范围：

- 后端：系统配置响应 schema/service/router 测试；不改表结构。
- 前端共享层：详情导航、详情数据 query、弹窗无障碍、路由状态。
- 前端页面/组件：认证、工作台、灵感、写作台、设置、管理与管理详情的局部行为和样式。
- 合同：OpenAPI 与生成 TypeScript 类型随 schema 变更同步。
- 测试：现有 UI audit 回归测试、组件/查询测试及后端安全测试。

明确不做：新会话协议、数据库加密迁移、视觉重设计、无关重构、新依赖。

## Design

### 1. 系统配置安全边界

- `SystemConfigCreate/Update` 继续接收值；`SystemConfigRead` 改为可空 `value` 并增加 `is_sensitive`。
- `ConfigService` 用一个保守的键名分类函数识别明确秘密段；敏感新值复用现有 Fernet `encrypt` 后持久化，内部消费者复用 `decrypt`（旧明文原样兼容），并通过统一 `_to_read` 转换所有 list/get/upsert/patch 响应；敏感项 `value=None`，从源头保证所有路由不回显。
- 前端表格、移动卡片、搜索和编辑弹窗只消费 `is_sensitive`。敏感项显示“已配置”，打开编辑时值为空，PATCH 省略空 `value` 以保留原值。
- 添加 service/router 回归测试，断言秘密原值不出现在序列化响应中；测试只使用虚构固定值。

### 2. 共享详情数据与导航

- `adminQueryKeys` 增加按项目 ID 的详情 key，复用已有 `AdminAPI.getNovelDetails`；`NovelDetailShell` 根据 `isAdmin` 选择普通或管理员 query，统一生成 `novel`。
- `useShellSectionNavigation` 成为分区唯一状态拥有者：补 `chapters`，合法化 query，切换时 `router.push`，监听 route query 支持前进/后退。
- `ShellTopbar` 对普通与管理员都可用，提供移动菜单、唯一 H1；普通用户显示继续写作，管理员保持返回管理列表。

### 3. 章节状态与抽屉

- `WDSidebar` 的完成态优先于选中章的临时 workflow phase，统一由现有状态函数输出，不在模板散加条件。
- 写作台移动端使用单一互斥抽屉状态；关闭侧栏加 `aria-hidden` 与 `inert`，CSS 确保离屏元素不扩展画布。
- 共享 `useDialogA11y` 在打开对话框时对背景兄弟节点施加可恢复的 inert，并保持现有焦点陷阱、滚动锁和焦点恢复。

### 4. 脏状态与危险操作

- 设置页复用 `PersonalModelRouting` 已暴露的 `isDirty/save`，在 tab 切换、路由离开和 beforeunload 三个边界阻止静默丢失。
- `PromptManagement` 以当前服务端 Prompt 快照和编辑表单做直接比较，暴露 `isDirty`；Prompt 切换和 `AdminView` 分区切换前使用现有 `useAlert().showConfirm`。
- 用户启停保留现有 mutation，只在调用前加一次确认并补语义化名称；不引入撤销系统。

### 5. 灵感重开与工作台动作

- 灵感重开复用现有 `deleteNovels` mutation：确认后先删除当前未完成项目，成功后才清前端状态并创建新会话；失败则不清状态并给出错误。
- 工作台从同一个现有项目状态判定同时派生 CTA 文案与目标路由，避免文案和跳转各自维护。

### 6. 视觉与无障碍 polish

- 只调整报告定位的 token/opacity/标题/滚动可达性：移除会把词笺整体压到低对比的 opacity，删除和风险文字改用已存在的高对比语义色。
- 移动阶段路由用原生/现有折叠组件分组，只展开当前组；桌面布局不变。
- 保持 `DESIGN.md` 的微直角、熟宣、界格、朱砂/石青权责和断点契约，不新增视觉体系。

## Data Flow

```text
system_configs row -> ConfigService._to_read -> SystemConfigRead(value=null,is_sensitive=true)
                  -> OpenAPI/generated TS -> SettingsManagement status-only rendering

route.query.section <-> useShellSectionNavigation -> ordinary/admin section query
admin detail route -> AdminAPI.getNovelDetails -> admin project query -> shared overview/chapters

persisted chapter success + transient workflow phase -> WDSidebar status resolver -> trusted label/CTA
```

## Compatibility and Rollback

- `SystemConfigRead.value` 从必填字符串变为可空是有意合同变更，必须同一次更新 OpenAPI 和生成类型；写接口保持兼容。
- 无数据库迁移。回滚可按“安全合同”“共享导航/查询”“页面交互/样式”三批分别撤销。
- 敏感配置一旦曾经暴露，代码修复不能使旧凭证重新安全；部署后仍需运维轮换。

## Risks

- 敏感键误判会影响管理员编辑体验；采用明确段匹配并以测试覆盖正反例。
- 全局 inert 需兼容嵌套弹层；实现需要记录原属性并按引用计数恢复。
- 脏状态确认容易在 query 刷新时误触发；服务端刷新使用强制同步路径，不走用户切换确认。
- 9 页浏览器回归依赖现有本地服务和测试账号；若环境不可用，必须明确未验证项，不能声称通过。
