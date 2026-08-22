# 前端依赖现代化与安全升级设计

## Boundary

父任务维护共同约束、执行顺序和最终集成复核。依赖清单、锁文件、Node 配置与必要兼容代码只在对应子任务中修改。

## Upgrade Strategy

1. 先用普通 `npm audit fix` 收敛已知漏洞，建立安全基线。
2. 再升级所有不跨主版本的直接依赖，减少后续主版本迁移的变量。
3. 将本地、CI、Docker 与类型定义统一到 Node 24，并迁移构建和测试工具链主版本。
4. 最后迁移影响运行时路由、状态和 Markdown 渲染的框架主版本。

## Compatibility Contracts

- 锁文件必须通过 `npm ci` 复现，生产依赖审计保持为 0。
- Node 运行时最低版本必须同时满足 Vite、Vitest、jsdom 和脚本工具要求；`@types/node` 跟随真实 Node 主版本。
- TypeScript 保持 strict，OpenAPI 生成 artifact 不因升级产生未提交漂移。
- 路由、Pinia 状态、Markdown 消毒、编辑器交互和 bundle 硬预算保持现有对外行为。

## Trade-offs

- 不执行一次性全量 latest 更新：它无法定位具体主版本回归，也不利于独立回滚。
- Node 统一到 24 而非继续兼容 Docker Node 20：jsdom 30 与 npm-run-all2 9 的最低版本已高于现有 Node 20 基线。
- `@types/node` 不升级到 26：类型定义领先于真实运行时会允许代码使用部署环境不存在的 API。
- 若原生 npm 串行脚本可覆盖唯一调用，则删除 `npm-run-all2`，避免继续维护其传递依赖；否则升级并保留。

## Rollout and Rollback

每个子任务形成一个独立产品提交。任一批次失败时仅回滚该批次，已验证的前序批次保留；父任务不直接承载产品改动。

