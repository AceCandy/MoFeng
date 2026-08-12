# 依赖治理与发布状态机

## Goal

让公开 Docker 发布只能从同一 source commit 的全绿质量门产生，并使运行依赖可复现、
可审计，候选镜像经过逐平台扫描和真实 app/worker smoke 后才进入不可变版本、Git tag、
`latest` 与 metadata。

## Background

- 父任务 R1 要求在 Q1 全绿后实施；Q1 已完成并归档。
- 当前 `docker-publish.yml` 在质量检查、Docker 凭据检查和镜像验证前推送 Git tag，随后
  一次构建同时更新版本 tag 与 `latest`，无法安全恢复中间失败。
- 当前 Python 运行与测试依赖混在 `requirements.txt`，没有 input 文件、传递依赖锁或
  hashes；Docker 和 CI 均未使用 `--require-hashes`。
- 2026-08-11 实时审计结果为：Python 8 个包、27 条 advisory；前端生产依赖 5 项，
  其中 4 high、1 moderate。不得沿用 2026-08-10 的旧数字作为完成证据。
- `python-jose` 及其 `ecdsa` 传递依赖存在无修复版本的 advisory。项目仅在
  `backend/app/core/security.py` 使用 JWT encode/decode，因此可用兼容的 PyJWT 做窄迁移，
  保持现有 HS256 token、claims 和 401 行为。
- OCI Distribution API 不保证 tag 更新支持 compare-and-swap；条件写入只是 registry 可选
  能力。因此 `latest` 的安全前提是本 workflow 为正式镜像 tag 的唯一写入方，并配合仓库内
  串行、前置快照校验和 promotion 后校验；不能把普通 tag push 描述成原子 CAS。
- 当前公开状态已经处于旧流程遗留的可恢复中间态：远端 Git `v0.1.34`、镜像
  `:0.1.34` 和 `latest` 绑定 source `61bf906...` 及同一 manifest digest，但仓库 metadata
  仍为 `0.1.33` 且没有 `image_digest`。R1 首次运行必须先安全识别该基线，不能假定三者
  当前已经一致。

## Requirements

### R1.1 依赖分层与锁定

- 新增 `backend/requirements.in`，只维护运行时直接依赖；新增
  `backend/requirements-dev.in`，引用 runtime input 并声明测试、格式化、类型检查和审计
  工具。
- 由固定版本 `pip-tools` 生成完整的 `requirements.txt` 与
  `requirements-dev.txt`，两者包含传递依赖精确版本和 hashes，且不写入开发机特有的
  index/trusted-host。
- `pytest`、`pytest-asyncio`、`testcontainers` 只进入 dev input/lock；生产 Docker 只安装
  runtime lock，并使用 `--require-hashes`。
- 修复有可用版本的 Python advisory；以 PyJWT 替换无可修复版本的
  `python-jose`/`ecdsa`，不改变认证对外行为。
- 更新前端直接依赖根和 `package-lock.json`，消除当前 DOMPurify、Lodash/Lodash-ES、
  nanoid、PostCSS advisory；不使用永久 audit ignore 或无期限 override。

### R1.2 阻断式质量门

- 发布 gate 对同一 `${{ github.sha }}` 运行后端 pytest、Ruff、Black、限定范围 mypy、
  compileall、runtime `pip-audit`，以及前端 API contract、lint、type-check、unit、build、
  Playwright、生产依赖 `npm audit`。
- 任一步失败都必须在构建候选镜像、推 Git tag、更新 `latest` 前停止；不得使用
  `continue-on-error`、retry 掩盖确定性失败或 skip。
- 所有第三方 GitHub Actions 使用完整 commit SHA，并在注释中记录对应 release tag。

### R1.3 候选镜像验证

- 只从 source SHA 构建一次 `linux/amd64`、`linux/arm64` 候选 manifest，推送到非发布语义
  的 `build-<source-sha>` tag，并写入 OCI source/revision/version labels 与 provenance。
- 解析并验证 manifest digest 和每个平台 digest；Trivy 对每个平台 digest 执行
  HIGH/CRITICAL 阻断扫描。
- smoke 必须拉取候选 digest，通过隔离 PostgreSQL 执行 migrate/bootstrap/check，启动
  app 与 durable worker，验证 `/api/ready`、worker `health` 和 `metrics` 后清理资源。
- smoke 复用现有 Compose、DB CLI 和 worker CLI；不新增应用健康接口或第二套部署框架。

### R1.4 可恢复发布状态机

- workflow 使用 `cancel-in-progress: false`；顶层默认 `contents: read`，只有 Git tag 和
  metadata 写入 job 获得 `contents: write`。
- 正式发布开始时记录当前 metadata blob 和 registry `latest` digest。正常路径从包含
  `image_digest` 的 metadata 解析前一正式状态；仅在升级前 metadata 缺少该字段时，允许
  一次性以最高远端 SemVer Git tag 为入口，并要求其 peeled source SHA、同版本镜像、
  `latest` 和 provenance 完全一致后建立 legacy baseline。任一不一致都在产生正式状态前
  失败；R1 schema 生效后禁止再回退到 legacy 推断。
- 发布凭据必须只供该 workflow 写入 version/`latest`，不能满足唯一写入方约束时不得恢复
  自动发布。
- 正式状态顺序固定为：promote immutable version digest -> verify -> push Git tag ->
  promote `latest` -> verify -> update metadata。
- version image 和 Git tag 拆成独立、可重跑的 job：目标已存在且与预期 source/digest
  相同则视为幂等成功，不同则失败关闭；二者一旦产生不得删除、改写或复用。
- `latest` 已指向目标 digest 时幂等成功；否则只有它仍指向本次发布记录的前一正式 digest
  （首次发布为不存在）时才允许 promotion，其他状态失败关闭。promotion 后必须再次核对
  目标 digest。
- metadata 以发布开始时记录的远端文件 blob 为乐观锁：目标身份
  `version/source SHA/image digest` 相同则幂等成功；远端 metadata 已变为其他发布则失败。
  仅由无关 main 提交造成非快进时，允许重新 fetch、复核 blob 未变后有界重试普通 push，
  禁止 force push。
- metadata 增加 `image_digest`，`commit_sha` 始终指向构建 source commit，而不是后续
  metadata commit。
- `workflow_dispatch` 提供默认安全的 dry-run 路径，只执行至候选扫描和 smoke，不创建
  正式版本 tag、Git tag、`latest` 或 metadata。
- `build-<source-sha>` 候选 tag 保留为审计和原发布恢复入口，不在 workflow 内自动删除；
  registry 生命周期治理继续作为独立平台事项。

## Out Of Scope

- 不处理父任务 U1、D1、T1，也不顺带重构应用业务层。
- 不迁移到 Poetry、uv 等新包管理器，不新增自制发布框架。
- 不引入镜像签名、GitHub environment approval、branch protection 或 registry 保留策略；
  这些需要独立的平台治理决策。
- 不删除或重写历史 Git tag、镜像 tag、release metadata。

## Acceptance Criteria

- [ ] 两个 input 和两个 hash lock 可由固定版本 pip-tools 重现；runtime lock 不含测试工具；
  runtime/dev 均在干净 Python 3.11 环境完成真实 `pip install --require-hashes` 和关键入口
  import，Docker runtime build 也使用 runtime hash lock 完成安装。
- [ ] `pip-audit -r requirements.txt` 返回 0，`npm audit --omit=dev --audit-level=high`
  返回 0，且仓库无永久 ignore、通配 exception 或 `continue-on-error`。
- [ ] PyJWT 迁移后，既有 HS256 token 可解码，过期、篡改、缺失 `sub` 均保持 401；登录、
  OAuth 和认证 focused tests 通过。
- [ ] 后端与前端全量质量命令全部通过，发布 gate 的 job 依赖图保证 gate 失败时没有候选
  build 或正式发布状态。
- [ ] 候选 manifest 包含 amd64/arm64，每个平台 digest 通过 Trivy；逐平台 OCI labels 和
  provenance 的 source/revision 与构建 source SHA 一致；候选 digest 在隔离 PostgreSQL 上
  通过 migrate/bootstrap/check、HTTP readiness、worker health/metrics。
- [ ] dry-run 不创建正式状态；正式运行中 version image、Git tag、`latest`、metadata
  依次产生且都绑定同一 source SHA 和 manifest digest。
- [ ] 仓库管理员确认正式 version/`latest` 的写凭据只供该 workflow 使用；未确认时正式
  promotion 硬失败，不能以 dry-run 通过代替该前置条件。
- [ ] version/Git tag 重跑不会改写目标且冲突失败；孤立 version 只能由原 source/digest
  继续，不删除或复用；`latest` 前一 digest 不符时失败，符合时只前进到已验证 digest。
- [ ] pre-R1 metadata 缺少 digest 时，只有 Git tag、同版本镜像、`latest` 和 provenance
  四方一致才能建立 legacy baseline；任一漂移失败，R1 metadata 生效后该分支不可达。
- [ ] metadata 的相同目标重跑幂等成功；远端 metadata 被其他发布修改时失败；只有
  metadata blob 未变的无关 main 提交允许有界重试，且全程不 force push。
- [ ] 工作树不遗留凭据、临时 env、容器、volume、截图、trace 或 audit 报告。

## Blocking Questions

无。父任务已确定安全失败关闭、无永久审计忽略、Q1 先于 R1 和 digest 驱动发布顺序。
