# CSS 级联与清理边界研究

## 结论

当前用户可见视觉由两层最终覆盖控制：`main.css` 最后加载全站 `world-class.css`，认证布局再加载 `world-class-auth.css`。组件 scoped CSS 中仍存在旧暖纸、宋楷、印章和纸影声明，但不能按关键词批量删除；只有被最终层逐属性完整接管的声明才可清理。

## 已确认的安全候选

- `AuthIntro.vue`：最终层直接隐藏的 `::before` / `::after`、spine、seal、stamp 装饰规则。
- `Login.vue` / `Register.vue`：最终层完整接管的页面暖纸背景。
- `Login.vue` / `Register.vue`：panel 中已被最终层逐属性覆盖的 border、radius、background、background-image、box-shadow、color；布局、定位、padding 和交互状态保留。
- `AuthIntro.vue`：最终层完整接管的品牌标题、kind/slogan、footmark 字体与排版属性；删除前以 computed style 对照确认未依赖遗漏的 z-index/position。
- `Register.vue`：最终层明确隐藏的标题印章规则。

## 不可批量删除

- 登录/注册输入、按钮、错误反馈、divider 的尺寸、校验布局和交互状态。
- `login-scroll` / `register-scroll` 的 position、z-index、overflow 等未被最终层逐项接管的行为属性。
- 写作正文宋体、描红楷体、AI provenance、落墨动画和稿纸行线；它们是 DESIGN.md 允许的长文/业务状态例外。
- 详情章节阅读、编辑器、设置弹窗和 Naive UI 内部规则中没有完整 computed-style 等价证据的声明。
- `main.css` 的 import 顺序、`world-class.css`、`world-class-auth.css` 文件或导入本身。

## 验证资产

- Playwright 已有 `desktop-chromium` 1440×900 与 `mobile-chromium` Pixel 7 两项目。
- `e2e-fixture-server.mjs` 支持用户/管理员认证、项目详情、写作台、灵感、设置和管理接口，不需要创建真实账号。
- `global-modal-accessibility.spec.ts` 已提供 axe、44px 触控和横向溢出辅助断言。
- `creation-continuity.spec.ts` 已覆盖灵感和写作台的跨设备状态，不应因 UI 清理回归。
- 前置任务的最终截图可作为方向参考，但本任务必须重新生成当前运行时证据，不能把历史截图当作当前通过证明。

## 风险控制

- 先建立当前 computed-style / 路由 E2E 基线，再删除规则。
- 按页面批次删除，每批只触碰被最终层完整覆盖的视觉属性。
- 浏览器输出不等价时立即回滚该批属性，不用新增覆盖修补删除造成的回归。
- 临时截图保留在 Playwright 输出目录或临时目录，不进入仓库。
