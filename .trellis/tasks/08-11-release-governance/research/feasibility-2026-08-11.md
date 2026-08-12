# R1 可行性核验（2026-08-11）

## 结论

R1 可在现有 pip/npm、Docker Buildx、Compose、DB CLI 和 worker CLI 上实施，不需要新的
包管理器或发布框架。设计必须补入 PyJWT 窄迁移，因为实时审计证明
`python-jose`/`ecdsa` 无可升级修复；忽略 advisory 无法满足父任务契约。

## 当前依赖证据

- `backend/requirements.txt` 混有 runtime 与 pytest/pytest-asyncio/testcontainers，无
  hashes；`requirements-dev.txt` 只追加 Black/mypy/Ruff。
- `pipx run pip-audit -r backend/requirements.txt`：8 个包、27 条 advisory。
- `pip-audit --fix --dry-run` 可升级 python-dotenv、python-multipart、
  langchain-text-splitters、langgraph-checkpoint-postgres、Starlette；不能修复
  `python-jose` 与 `ecdsa`。
- JWT 调用仅在 `backend/app/core/security.py`：encode/decode、固定 algorithms allowlist、
  统一 decode 异常。PyJWT 官方接口支持同样的 HS256 调用、datetime claims 和
  `InvalidTokenError` 基类。
- `langchain-text-splitters` 只由 `ChapterIngestionService` 的
  `RecursiveCharacterTextSplitter` 使用，已有章节标点切分测试可覆盖升级兼容性。
- `npm audit --omit=dev --audit-level=high --json`：5 项，4 high、1 moderate。当前
  package-lock 仍锁定 DOMPurify 3.4.5、Lodash/Lodash-ES 4.17.21、nanoid 3.3.11、
  PostCSS 8.5.6；上游已有修复版本。
- pip-tools 7.6.0 可通过 pipx 运行；项目工作树未因审计命令产生依赖文件修改。

## 当前发布证据

- `.github/workflows/docker-publish.yml` 当前顺序是：计算版本 -> 推 Git tag -> 检查
  Docker 凭据 -> 同时 build/push version 和 latest -> inspect -> metadata。
- workflow 顶层 `contents: write`，`cancel-in-progress: true`；无 full gate、audit、Trivy、
  smoke、digest 校验或 promotion。
- `release-metadata/version-info.json` 没有 `image_digest`。
- `docker/build-push-action` 官方 action 定义提供 `digest` output，并支持 platforms、
  labels、provenance；Trivy action 支持 image-ref、severity 与非零 exit-code。
- OCI Distribution Specification 的 manifest tag PUT 没有强制 compare-and-swap 前置条件；
  条件 HTTP push 只对支持 ETag 的 registry 是可选能力，不能默认 Docker Hub promotion
  具备原子 CAS。
- 2026-08-11 只读核验公开状态：远端 `v0.1.34` peeled commit 为
  `61bf906331ef763699854a8deccabbbddc947f40`；`acecandy/mofeng:0.1.34` 与 `:latest`
  均为 `sha256:1c5b270ac955265d35aa97a96608dcca60d879a501e020d4fbd760b07496e66a`，
  provenance revision 同为该 commit；仓库 metadata 仍为 `0.1.33` 且无 `image_digest`。

## 可复用部署能力

- Compose 已有 `migrate -> bootstrap -> app/worker`，app 使用 `/api/ready` healthcheck，
  worker 使用 `python -m app.worker health`。
- DB CLI 已有 `db-migrate`、`db-bootstrap`、`db-check`；worker CLI 已有 `health`、
  `metrics`，无需修改业务 API。
- 本机 Docker 28.5.2、Compose 2.40.3、Buildx 0.29.1 可用于本地 build/smoke。
- 真实 registry promotion、GitHub job permissions、Docker Hub credential 和首个正式发布
  一致性只能在仓库环境验证；本地测试不能替代。

## 风险与验证抓手

- FastAPI/Starlette、langchain-text-splitters 属于跨版本升级，必须依赖全量后端测试和
  对应 focused tests，不以“能安装”作为兼容证据。
- npm lock 更新会带动直接依赖根的传递版本，必须执行 unit/build/Playwright。
- Git/registry 非事务；拆分幂等 job 后，以 source SHA 和 manifest digest 做恢复判断。
- `latest` 安全更新必须依赖仓库内 concurrency 串行、正式 tag 唯一写入方、前一 digest
  快照与 promotion 前后校验；若存在其他 writer，普通 tag promotion 仍有无法由 workflow
  完全消除的竞态，必须暂停自动发布并先收敛凭据权限。
- metadata 可利用 Git ref push 的非快进保护和文件 blob 基线实现乐观锁；无关 main 提交
  可重建 metadata commit，metadata 已被其他发布改变时必须失败关闭。
- 首次 R1 必须兼容当前 legacy metadata 漂移，但只能在最高远端 Git tag、同版本镜像、
  `latest` 和 provenance 四方一致时建立前一 digest；新 metadata schema 生效后禁用推断，
  避免未来发布漂移被兼容逻辑掩盖。
- multi-platform 扫描必须验证每个平台 digest，不能用 manifest 或 amd64 单次扫描代替。
- smoke 必须以 digest 拉取并在 trap 中清理，不能使用真实生产 secret 或数据库。
