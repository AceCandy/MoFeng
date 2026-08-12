# 技术设计

## 1. 边界

本任务只改变依赖声明/锁、JWT 库适配、CI/发布 workflow、Docker 安装约束和发布镜像
smoke。应用数据模型、API 契约、业务流程和数据库 schema 不变。

## 2. 依赖模型

```text
requirements.in              runtime direct dependencies
        | pip-compile --generate-hashes
        v
requirements.txt             runtime transitive hash lock

requirements-dev.in          -r requirements.in + test/lint/type/audit tools
        | pip-compile --generate-hashes
        v
requirements-dev.txt         complete development hash lock
```

- input 文件是人工维护源；lock 文件是生成物，评审必须同时检查 input 与 lock diff。
- 生成命令固定 pip-tools 版本并禁用 index/trusted-host 输出，避免开发机镜像源进入仓库。
- Docker runtime builder 只读取 runtime lock。CI 使用 dev lock，并在安装时强制 hashes。
- 前端继续使用 npm 与现有 lockfile v3，不引入新的依赖工具。

### 2.1 Advisory 收敛

- 有固定版本的 Python 包升级到审计给出的最低安全版本或兼容的更新版本，再由完整测试
  证明兼容性。
- `python-jose`/`ecdsa` 无可修复版本，替换为 PyJWT。现有调用只需要
  `jwt.encode`、`jwt.decode` 和统一 decode 异常；PyJWT 接受相同 datetime claims、固定
  algorithms allowlist 和 HS256 key，已有 token 不需要迁移。
- 前端从直接依赖根更新 lock：DOMPurify；Naive UI 对应的 Lodash/Lodash-ES；PostCSS
  对应的 nanoid。只使用上游已发布修复，不写长期 override。

## 3. 发布状态机

```text
check-new-commits / calculate-version
                |
                v
release-gate (same source SHA)
                |
                v
validate-credentials
                |
                v
build-candidate: build-<source-sha> (amd64 + arm64)
                |
                +--> scan-platform[amd64 digest]
                +--> scan-platform[arm64 digest]
                +--> smoke-candidate[manifest digest]
                           |
                           v
                 dry-run stops successfully
                           |
                           v
promote-version -> push-git-tag -> promote-latest -> update-metadata
```

所有 job 显式 checkout `${{ github.sha }}`，并核对 ref 为 `main`、HEAD 等于 source SHA。
版本、image repo、source SHA、manifest digest、platform digest JSON、前一正式 digest 和
metadata blob 通过 job outputs 传递，不从后续可变 tag 反推。

基线解析分两条且不可静默降级：

1. metadata 已含 `image_digest`：以 metadata 的 version/source/digest 为前一正式状态，
   要求 Git tag peeled SHA 与 metadata `commit_sha` 相同、version image digest 与 metadata
   `image_digest` 相同、provenance source/revision 与 repository/commit 相同，并验证正常新
   发布开始时的 `latest`；恢复同一发布时，`latest` 也可已经等于本次目标 digest。
2. pre-R1 metadata 缺少 `image_digest`：只允许以最高远端 SemVer Git tag 建立一次性 legacy
   baseline；其 peeled commit 必须等于同版本镜像 provenance source，且 version image 与
   `latest` manifest digest 相同。任一条件失败即停止；新 schema 写入后不再允许该分支。

### 3.1 候选构建与扫描

- Buildx 只构建一次，候选 tag 不具备公开发布语义。
- `docker/build-push-action` 的 digest output 是 manifest digest；随后用
  `imagetools inspect` 校验 `sha256:<64 hex>` 并提取各平台 digest。
- 对每个平台配置与 BuildKit provenance 做机器校验，确认 OCI source/revision/version 与
  source SHA、版本输出一致；不能只在 workflow 参数中声明后视为已验证。
- 扫描 job 使用 digest matrix，每个平台运行固定版本 Trivy，`exit-code=1`、
  `severity=HIGH,CRITICAL`。manifest 中缺平台、平台重复或 digest 格式错误均失败。
- Actions 与 Trivy CLI 都固定版本；summary 记录 action/Trivy 版本、数据库更新时间、
  source SHA 和 digest，不输出 secret。

### 3.2 候选 smoke

新增 `deploy/scripts/smoke_release_image.sh`，输入只接受完整 image digest reference：

1. 拉取 `repo@sha256:...`，在本机赋予仅供 Compose 使用的临时 tag。
2. 用隔离、非生产凭据启动现有 Compose 的 PostgreSQL、migrate、bootstrap、app、worker。
3. 执行 `python -m app.db.cli db-check`，轮询 `/api/ready`，再执行 worker `health` 与
   `metrics` 并校验退出码/JSON。
4. trap 无条件关闭 Compose 并清理临时容器、volume、network 和本地 tag。

脚本不复制迁移或健康逻辑，也不访问真实生产数据、OAuth/LLM secret。Redis 在该 smoke
中关闭，因为发布准入验证的是核心 app/worker/数据库发布单元；Linux.do Redis 前置已由
A2 focused tests 和部署契约覆盖。

## 4. 正式状态与恢复

Git 和 registry 不能形成事务，因此把每个外部状态拆成独立 job，并让 job 幂等：

| 阶段 | 前置条件与首次执行 | 幂等重跑 | 冲突 |
| --- | --- | --- | --- |
| version image | 目标不存在，从候选 digest promotion | 已指向同 digest则成功 | 不同 digest失败，不删除或复用 |
| Git tag | 目标不存在，指向 source SHA | 已指向同 SHA则成功 | 不同 SHA失败，不删除或移动 |
| `latest` | 当前仍等于记录的前一 digest（首次为不存在），promotion 到目标 digest并验证 | 已指向目标 digest则成功 | 其他 digest失败，不覆盖 |
| metadata | 远端文件 blob 仍等于基线，在最新 `origin/main` 上提交 source/digest | 目标身份相同则成功 | metadata blob 已被其他发布改变则失败 |

Git tag 推送后只允许向前恢复，不删除或移动 tag。孤立 version image 保留，只能重跑原
source/digest 继续；候选或 version promotion 不重新 build。metadata 普通 push 因无关 main
提交非快进时，可重新 fetch，并在 metadata blob 仍等于基线后有界重建提交；若 metadata
本身改变则停止，禁止 rebase 后盲写或 force push。

OCI Distribution API 不要求 tag push 支持原子条件更新，不能宣称 `latest` promotion 是
CAS。本设计依赖 `docker-publish-main` concurrency 串行仓库内发布、正式 tag 写凭据只供该
workflow 使用，并在 promotion 紧邻前后校验 digest。无法保证唯一写入方时，自动发布保持
暂停；registry 外部写入仍是必须通过权限治理消除的平台风险。

## 5. 权限与供应链

- workflow 顶层 `contents: read`；只有 Git tag 与 metadata job 使用 `contents: write`。
- Docker 凭据只注入需要 login/inspect/promotion 的 job，不写文件、不输出值。
- 正式镜像 tag 的写凭据只授予该 workflow；人工或其他自动化不得并发写 version/`latest`。
- 第三方 Actions 固定完整 SHA并注释 release tag；不使用浮动 major tag。
- runtime lock 的 hash 校验、npm lock integrity、pip/npm audit、Trivy 和 provenance 分别
  覆盖包下载、依赖 advisory、镜像文件系统和构建来源，不互相替代。

## 6. 兼容与回滚

- PyJWT 保持 token 算法、secret、claims 和异常映射，既有 HS256 token 在有效期内继续
  可用；focused tests 固化该兼容性。
- requirements/lock、Dockerfile、workflow 和 smoke script 分批提交，任一批可在正式
  promotion 前独立回滚。
- runtime/dev lock 都在干净 Python 3.11 环境真实安装；Docker build 再证明 runtime lock
  在目标 Linux 基础镜像可安装，解析 dry-run 不作为安装通过证据。
- 已推 Git tag/不可变版本不回写，只发布修复版本；`latest` 可向前 promotion 到修复版。
- 本地只能验证 locks、测试、workflow 语法、镜像构建和本地 smoke。Docker Hub digest
  promotion、GitHub job 权限及正式 tag/metadata 一致性必须通过仓库环境 dry-run 和首个
  正式发布验证，不能用本地模拟冒充。

## 7. 取舍

- 不抽取单次使用的通用发布框架；直接把状态机写在现有 workflow 中。
- 不新建健康 API；复用现有 DB、HTTP 与 worker CLI。
- 不加入镜像签名或 environment approval；它们有独立的密钥和平台治理边界。
- 不允许永久 advisory ignore；无修复上游依赖用窄替换解决。
- 候选 `build-<source-sha>` 保留用于审计和原发布恢复；自动删除与 registry retention
  不属于本任务，接受按 source commit 累积候选 tag 的存储成本。
