# 实施计划

1. 将 Vite 配置静态 spec 改为真实配置加载测试。
   - 验证：单独运行该 spec。
2. 扩展 novel query spec，覆盖概念对话 mutation 不等待后台刷新。
   - 验证：单独运行 novel query spec。
3. 扩展 Novel API spec，覆盖 SSE final 提前返回和 reader cancel。
   - 验证：单独运行 Novel API spec。
4. 新增最小 HTTP spec，覆盖 409 JSON payload 的错误上下文。
   - 验证：单独运行 HTTP spec。
5. 仅删除两个被替代的 Python 静态测试函数。
   - 验证：运行 `backend/tests/test_frontend_tanstack_query_static.py`。
6. 运行受影响范围和前端全量质量门禁。
   - `npm run test:unit -- src/components/__tests__/viteConfigStatic.spec.ts src/queries/__tests__/novel.spec.ts src/api/__tests__/novel.spec.ts src/api/__tests__/http.spec.ts`
   - `npm run lint`
   - `npm run type-check`
   - `npm run test:unit`
7. 使用 Trellis 独立检查流程复核范围、规范、测试隔离和全量结果；发现问题后修复并重跑对应门禁。

## 回滚点

- 任一运行时测试暴露生产缺陷时停止扩大 diff，回到规划阶段决定是否纳入生产修复。
- 若 Vite 配置无法在当前 Vitest 进程中可靠隔离，保留原测试并重新评估独立 Node 配置加载测试，不以弱化断言换取通过。

