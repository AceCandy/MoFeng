# 技术设计

## 边界

本任务只调整测试。生产行为继续由现有 Vite 配置、Vue Query mutation、SSE 读取器和 HTTP 包装器提供。

## 静态断言到运行时断言的映射

1. `viteConfigStatic.spec.ts`
   - 移除 `readFileSync`、`resolve` 和字符串顺序比较。
   - 重置模块后注入不完整 localStorage，设置开发环境和 DevTools 开关，动态导入并执行 Vite config factory。
   - 以配置成功返回、localStorage shim 可用和 DevTools 插件进入配置作为行为证据。

2. `queries/__tests__/novel.spec.ts`
   - 复用现有 `QueryClient + VueQueryPlugin + createApp` 挂载模式。
   - mock 概念对话 API 成功；让 `invalidateQueries` 返回受控未完成 Promise。
   - 断言 mutation 结果先于刷新 Promise 完成，随后释放 Promise 并清理应用。

3. `api/__tests__/novel.spec.ts`
   - mock `fetch` 返回只发送 `final`、暂不关闭的 `ReadableStream`。
   - 调用公开的 `NovelAPI.converseConceptStream`，断言返回 final payload 且底层 cancel 被调用。

4. 新增 `api/__tests__/http.spec.ts`
   - mock `fetch` 返回 409 JSON Response。
   - 调用 `requestRaw`，直接断言 `HttpRequestError` 的运行时字段。

5. `test_frontend_tanstack_query_static.py`
   - 删除两个已由以上用例覆盖的函数。
   - 不移动、不改写其余架构静态测试。

## 隔离与兼容

- 使用 Vitest 已有的 module/global/env stub 能力，测试后恢复模块、环境变量、global 和 mock。
- 不依赖源码格式、注释文案或语句排列。
- 不新增依赖，不改变应用运行时接口。

## 风险与回滚

- Vite 配置测试会触碰进程环境和全局 localStorage；必须在单测清理阶段恢复，避免污染其他用例。
- 挂起 Promise 和未关闭流必须在用例结束前释放或取消，避免测试进程悬挂。
- 全部改动为测试文件，回滚时可直接恢复本任务 diff，不涉及数据或兼容迁移。

