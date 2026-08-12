# MoFeng 增量审计整改设计

> 日期：2026-08-10
> 状态：待拆分实施
> 基线：2026-08-09 全项目审查及 2026-08-10 独立复核
> 性质：在 `docs/audit-governance-2026-07-19.md` 已完成治理之上的增量整改

## 1. 背景

2026-07-19 的治理已经完成 CORS、默认管理员安全、SSRF、CSP、数据库迁移与
bootstrap、资源归属、连接释放等基线。本设计不重新实现这些能力，只处理本轮确认的
新增问题和回归缺口：

1. `ALLOW_USER_REGISTRATION` 在 Pydantic Settings v2 下没有绑定到
   `Settings.allow_registration`，首次 bootstrap 可能写入错误的注册默认值。
2. Linux.do OAuth 缺少与发起浏览器绑定、一次性消费的 `state`。
3. Docker 发布在质量验证和凭据检查之前推送 Git tag，发布没有完整测试、依赖审计和
   镜像扫描门禁。
4. Python 生产依赖混入测试工具，前后端当前依赖快照存在已知漏洞，Python 依赖没有
   完整的传递依赖锁和哈希。
5. `GlobalModalContainer` 没有可访问名称和焦点管理，并自行维护一套不支持多实例的
   body 滚动锁。
6. Playwright、后端 pytest、ruff 和 Black 当前基线未全绿，无法直接作为发布门禁。
7. 写作台仍有键盘操作、对比度、滚动区焦点和移动端触控目标问题。
8. README 没有完整描述 durable worker；task SSE 的 scoped `task` 事件缺少客户端
   scope 复核。

审查时的可复现基线如下。数字用于验收整改是否收敛，不作为永久阈值：

| 检查 | 当前结果 |
| --- | --- |
| 前端 lint / type-check / unit / API contract / build | 通过，31 个测试文件、287 个单测 |
| 前端 Playwright | 2/20 通过 |
| 后端 pytest | 615/620 通过 |
| 后端 ruff | 179 项 |
| 后端 Black | 132 个文件需格式化 |
| 后端 mypy | 配置限定的 durable workflow 文件通过，不代表全后端 |
| `npm audit --omit=dev` | 5 个生产依赖问题，4 high、1 moderate |
| `pip-audit -r backend/requirements.txt` | 8 个包、27 条 advisory |

## 2. 目标与非目标

### 2.1 目标

- 显式配置 `ALLOW_USER_REGISTRATION=false` 时，首次 bootstrap 必须写入关闭注册，且
  后续 bootstrap 不覆盖管理员在数据库中的设置。
- Linux.do OAuth 回调必须同时验证查询参数、发起浏览器和一次性服务端状态；缺失、
  过期、错误或重放均不得兑换 provider token。
- 发布只允许从同一 commit 的全绿质量门产生；不可在镜像验证前创建 Git tag 或更新
  `latest`。
- 生产镜像只安装运行依赖；依赖可复现、可审计，高危和严重漏洞阻断发布。
- 所有 `GlobalModalContainer` 消费方获得一致的 dialog name、初始焦点、焦点陷阱、
  焦点恢复和引用计数滚动锁。
- 恢复全量测试基线后再启用阻断式 CI，避免把“永久红灯”包装成门禁。
- README、SSE decoder 和前端交互语义与项目现行架构契约一致。

### 2.2 非目标

- 不重做 7 月已完成的 CORS、SSRF、CSP、项目归属和 PostgreSQL 迁移设计。
- 不改变 `allow_registration` 当前默认值；本轮修复的是显式环境配置失效，而不是产品
  默认策略。默认值调整需要单独的产品兼容决策。
- 不用数据库表保存 OAuth state，不引入新的会话框架，也不把邮箱验证码的进程内降级
  逻辑复制给 OAuth。
- 不新建全局 modal manager，不重写 AppShell，也不进行视觉风格重做。
- 不在同一批次把 mypy 扩到整个后端；先如实保留当前类型检查范围。
- 不改变服务端 task stream 的用户和 scope 查询条件；SSE 项只是客户端纵深防御。

## 3. 总体原则

1. **安全失败关闭**：OAuth state 无法生成或验证时返回失败，不能降级为无 state 或
   单进程内存状态。
2. **单一配置链路**：环境变量只进入 `Settings`，bootstrap 只补缺失系统配置，运行时
   仍由 `SystemConfig` 优先。
3. **复用现有基础设施**：OAuth 使用已有 Redis 客户端，modal 使用
   `useDialogA11y`，SSE 延伸现有 decoder。
4. **发布按不可逆程度排序**：先验证，再推不可变版本镜像，再推 Git tag，最后更新
   `latest` 和版本元数据。
5. **机械改动与行为改动分离**：依赖锁、全仓格式化和测试行为修复分别提交，便于审查
   和回滚。
6. **门禁必须真绿**：任何新增阻断式检查都要先在主分支达到零失败，禁止长期
   `continue-on-error`。

## 4. 实施批次

整改拆为七个可独立验收的工作包：

| 工作包 | 优先级 | 内容 | 前置条件 |
| --- | --- | --- | --- |
| A1 | P1 | 注册环境变量与 bootstrap 契约 | 无 |
| A2 | P1 | Linux.do OAuth state | 可与 A1 并行 |
| Q1 | P1 | 恢复测试、lint、格式化基线 | 无 |
| R1 | P1 | 依赖治理与发布状态机 | Q1 全绿 |
| U1 | P2 | modal 与写作台可访问性 | 可与 A1/A2 并行 |
| D1 | P2 | worker 部署文档补全 | 无 |
| T1 | P3 | scoped task SSE 客户端复核 | 无 |

A1、A2 应先于下一次公开发布。R1 进入主分支前，自动版本发布应暂停，避免在门禁尚未
恢复时继续产生版本。

## 5. A1：注册配置与 bootstrap 契约

### 5.1 当前问题

`backend/app/core/config.py` 使用：

```python
allow_registration: bool = Field(
    default=True,
    env="ALLOW_USER_REGISTRATION",
)
```

在当前 `pydantic-settings==2.11.0` 下，`Field(env=...)` 只是已废弃的额外元数据，不能
建立 validation alias。实测结果为：

```text
ALLOW_USER_REGISTRATION=false -> settings.allow_registration == True
ALLOW_REGISTRATION=false      -> settings.allow_registration == False
```

错误值随后经 `backend/app/db/system_config_defaults.py` 写入
`auth.allow_registration`。运行时 `AuthService` 优先读取数据库配置，因此错误会在首次
bootstrap 后持续存在；这不是所有运行态注册检查被绕过。

### 5.2 设计决策

公开、文档化的 canonical 名称保持为 `ALLOW_USER_REGISTRATION`。兼容 Pydantic 按字段名
推导出的 `ALLOW_REGISTRATION`，但 canonical 名称优先：

```python
allow_registration: bool = Field(
    default=True,
    validation_alias=AliasChoices(
        "ALLOW_USER_REGISTRATION",
        "ALLOW_REGISTRATION",
    ),
    description="是否允许用户自助注册",
)
```

配置链保持不变：

```text
ALLOW_USER_REGISTRATION / ALLOW_REGISTRATION
                    |
                    v
       Settings.allow_registration
                    |
                    v 仅在 key 缺失时 seed
       auth.allow_registration (SystemConfig)
                    |
                    v 数据库优先，Settings 兜底
       AuthService.is_registration_enabled()
```

同一批次清理 `config.py` 中其余无效的 `env=` 元数据：

- 环境变量名等于字段名大写形式时，删除 `env=`，依赖 BaseSettings 的标准解析。
- 名称不同或需要兼容旧名时，使用 `validation_alias=AliasChoices(...)`。
- 不修改默认值、字段类型、数据库 system config key 或 bootstrap 版本。
- 更新 `.trellis/spec/backend/quality-guidelines.md`，不再把 `env=` 作为 Pydantic v2
  推荐写法。

### 5.3 改动范围

- `backend/app/core/config.py`
- `backend/tests/test_config_security.py`
- `backend/tests/test_database_bootstrap.py`
- `.trellis/spec/backend/quality-guidelines.md`

`backend/env.example`、`deploy/.env.example`、`deploy/docker-compose.yml` 已使用 canonical
名称，仅需静态契约测试，不改名。

### 5.4 验收

- 仅设置 `ALLOW_USER_REGISTRATION=false`，解析结果为 `False`。
- 仅设置兼容名 `ALLOW_REGISTRATION=false`，解析结果为 `False`。
- 两者同时存在且冲突时，`ALLOW_USER_REGISTRATION` 胜出。
- 未设置时仍保持当前默认值 `True`。
- bootstrap 在 key 缺失时写入解析值；key 已存在时不覆盖。
- 普通注册和 OAuth 新用户路径继续只调用 `is_registration_enabled()`。
- Settings 初始化不再产生 `env` 额外关键字的 Pydantic 弃用警告。

## 6. A2：Linux.do OAuth state

### 6.1 安全边界

只把 state 存到 Redis 仍然不够。state 必须同时绑定发起 OAuth 的浏览器，否则攻击者可
自己取得一个合法 state，再把自己的 callback URL 发给受害者。目标链路为：

```text
浏览器 GET /api/auth/linuxdo/login
  -> 校验 Linux.do 开关和 provider 配置
  -> 要求 Redis 可用
  -> state = secrets.token_urlsafe(32)
  -> Redis SET oauth:linuxdo:state:<sha256(state)> 1 NX EX 300
  -> RedirectResponse 设置 HostOnly + HttpOnly + SameSite=Lax state cookie
  -> 使用 urllib.parse.urlencode 生成 provider URL

provider GET /api/auth/linuxdo/register?code=...&state=...
  -> 查询参数 state 与 cookie 使用 secrets.compare_digest 比较
  -> Redis 原子 GETDEL 消费 state
  -> 删除 state cookie
  -> 只有以上全部成功，才兑换 code 和读取用户信息
```

### 6.2 具体约束

- TTL 固定 300 秒，state 至少 256 bit 随机性。
- Redis key 只保存 state 的 SHA-256，不在 key、value、日志或异常中暴露原始 state。
- 写入使用 `NX + EX`；消费使用 Redis 6.2+ `GETDEL`，保证并发回调只成功一次。
- Cookie 不设置 `Domain`，`Path=/api/auth/linuxdo`，`HttpOnly=true`，
  `SameSite=Lax`。`Secure` 由 redirect URI 的 scheme 决定；production 必须拒绝非 HTTPS
  redirect URI，production 判定沿用 `settings.environment == "production"`；非 production
  仅为本地 HTTP 调试允许 `Secure=false`。
- 回调无论成功或失败都用可设置响应头的错误响应清理 cookie。缺失、错误、过期和重放
  统一返回 400
  `登录请求已失效，请重新发起`，不泄露具体失败位置。
- Redis 未配置或不可用时，启用 Linux.do 的 login/callback 返回 503；不得复用邮箱验证码
  的进程内字典降级，因为多 worker 下无法可靠校验。
- 当前 Redis 客户端是同步客户端。state 的 client 初始化、`SET` 和 `GETDEL` 必须通过
  `asyncio.to_thread` 执行，不能阻塞 FastAPI event loop；连接、超时、命令不支持等异常
  统一安全失败为 503。部署前置条件明确为 Redis server 6.2+，不能只校验 Python 包版本。
- `handle_linuxdo_callback(code, state, browser_state)` 必须先验证和消费 state，再进行任何
  provider HTTP 请求。
- 不记录 code、state、access token 或完整 provider 响应。

### 6.3 服务与路由职责

`AuthService` 增加最小的两个私有 state 操作，并让授权 URL 构造进入 service，避免路由
重复掌握 provider 配置和安全顺序：

- `create_linuxdo_authorization() -> tuple[url, state]`
- `_consume_linuxdo_state(state) -> bool`
- `handle_linuxdo_callback(code, state, browser_state)`

路由只负责设置/删除 cookie、把 service 的 `ValueError` 映射为 400、Redis 不可用映射为
503，并返回现有 Redirect/HTML 响应。OAuth 用户绑定、注册开关和唯一约束保持原实现。

### 6.4 改动范围

- `backend/app/api/routers/auth.py`
- `backend/app/services/auth_service.py`
- `backend/tests/test_auth_linuxdo_oauth.py`（新增）
- `backend/env.example`
- `deploy/.env.example`
- `docs/DEPLOYMENT.md`

不新增 ORM model、repository 或 Alembic revision。

### 6.5 验收矩阵

| 场景 | 结果 |
| --- | --- |
| 正常 state + cookie + 未消费 Redis key | 兑换 code，state 被删除 |
| 缺 query state 或缺 cookie | 400，不调用 provider |
| query state 与 cookie 不同 | 400，不调用 provider |
| state 过期 | 400，不调用 provider |
| 同一 callback 重放 | 首次成功，后续 400 |
| 两个并发 callback | 最多一个进入 provider token exchange |
| Redis 未配置/连接失败 | 503，不生成不可验证的授权请求 |
| Redis server 不支持 GETDEL | 503，不降级为非原子 get/delete |
| production redirect URI 为 HTTP | 拒绝生成授权请求 |
| 同一浏览器连续发起两次登录 | 后一次 cookie 胜出，前一次 callback 明确 400 |
| OAuth 已关闭 | 保持现有 404 |
| 注册关闭且 external user 不存在 | 保持现有 403，不创建用户 |
| external user 已存在 | 正常登录，不受注册开关误伤 |

## 7. Q1：先恢复可执行质量基线

发布门禁不能建立在当前失败基线上。Q1 只恢复事实基线，不与安全或功能改动混合。

### 7.1 后端

1. 逐一归因当前 5 个 pytest 失败：生产行为错误则修实现；静态字符串断言漂移则改成
   行为断言；依赖本机版本数的断言改用隔离 fixture。不得简单 skip。
2. ruff 语义问题与 import 排序单独提交。
3. Black 对 `app/` 与 `tests/` 作为纯机械提交执行，禁止夹带业务改动；Alembic 历史
   revision 不纳入批量格式化。
4. mypy 保持 `backend/pyproject.toml` 当前限定范围，并在 CI 名称中明确为
   `durable workflow mypy`，不宣称全后端已类型检查。

### 7.2 前端

1. 将 `writing-desk-workflow.spec.ts` 的旧 `.chapter-workflow` 定位更新为当前页面的
   role/name 契约；只有当前 DOM 缺少稳定语义锚点时才补 `aria-label`。
2. fixture 只模拟当前 API/SSE 契约，不让生产组件迁就旧 fixture。
3. 保留 desktop Chromium 与 mobile Chromium 两个 viewport。
4. Playwright 达到 20/20 后，再加入 U1 新增的 modal/axe 场景。

### 7.3 完成标准

```text
backend: pytest 全绿、ruff 0、Black --check 0、限定范围 mypy 0
frontend: lint/type-check/unit/api:check/build 全绿、Playwright 全绿
```

任何由于外部服务或时间导致的不稳定测试必须先改为 hermetic fixture；不得用 retry 掩盖
确定性失败。

## 8. R1：依赖治理与发布状态机

### 8.1 Python 依赖分层与锁定

沿用 pip 工具链，不引入新的包管理器：

```text
backend/requirements.in       仅人工维护的运行时直接依赖
backend/requirements.txt      pip-compile 生成的运行时全量锁，包含 hashes
backend/requirements-dev.in   -r requirements.in + pytest/ruff/black/mypy/pip-audit
backend/requirements-dev.txt  pip-compile 生成的开发全量锁，包含 hashes
```

- `pytest`、`pytest-asyncio`、`testcontainers` 从运行时依赖移到 dev input。
- 生产 Docker 只安装 `requirements.txt`，并使用 `--require-hashes`。
- `deploy/Dockerfile` 明确执行
  `pip install --no-cache-dir --no-compile --require-hashes -r requirements.txt`。
- backend CI 明确执行 `pip install --require-hashes -r requirements-dev.txt`；不得继续把
  未锁定的 runtime input 作为 dev 安装入口。
- 所有直接依赖先升级到 advisory 给出的最低修复版本；升级失败时单独评估替代库，不使用
  无期限的 audit ignore。
- 生成文件由 `pip-tools` 维护，评审同时检查 input 和 lock diff。
- 前端继续使用现有 `package-lock.json` 与 `npm ci`；`npm ci --no-audit` 可留在镜像构建，
  因为审计在构建前的独立门禁执行。

### 8.2 发布门禁

`docker-publish.yml` 的 `publish` 拆为按依赖排序的 jobs。所有 job 检出同一
`${{ github.sha }}`：

```text
check-new-commits
       |
       v
release-gate
  - backend full pytest / ruff / Black / scoped mypy / compileall
  - frontend api:check / lint / type-check / unit / build / Playwright
  - pip-audit runtime lock
  - npm audit --omit=dev --audit-level=high
       |
       v
validate-credentials
       |
       v
build and push multi-arch :build-<source-sha>
       |
       v
capture manifest digest + every platform digest
       |
       v
Trivy scan every platform digest + smoke the candidate digest
       |
       v
promote the scanned manifest digest to immutable :<version>
       |
       v
push Git tag v<version>
       |
       v
promote :latest to the verified digest
       |
       v
update release-metadata/version-info.json
```

具体规则：

- `concurrency.cancel-in-progress=false`，发布过程不能被下一次定时任务中途取消。
- workflow 顶层权限降为 `contents: read`；只有推 Git tag/metadata 的 job 使用
  `contents: write`。
- Docker 凭据在任何 Git tag 创建前校验。
- 发布 job 开始和推 tag 前分别断言 `git rev-parse HEAD == github.sha`、当前 ref 为 main，
  并重新 fetch remote tags；目标 Git tag 或 registry 版本 tag 已存在且指向相同 source/digest
  时幂等成功，指向不同时失败关闭。
- 只构建一次正式多架构内容，先推到非发布语义的 `build-<source-sha>` tag，并把 OCI
  revision/source/version labels 和 BuildKit provenance 绑定到 source SHA。
- `docker buildx imagetools inspect` 必须解析并校验 `sha256:<64 hex>` manifest digest 及
  每个平台 digest。Trivy 对最终 manifest 的每个平台 digest 扫描，high/critical 为阻断
  项；不得用一个平台的扫描结果代表整个 manifest。
- 扫描后直接把同一个 manifest digest promotion 为不可变版本 tag，不重新 build。版本
  tag inspect 得到的 digest 必须与已扫描 digest 完全一致。
- 候选 digest 使用隔离 PostgreSQL 执行 migrate/bootstrap/check，并启动 app 与 worker；
  验证 HTTP health、worker health/metrics 后销毁测试网络、数据库和容器。smoke 不使用
  真实生产凭据或数据。
- 正式 promotion 先只创建不可变版本 tag，不同时更新 `latest`。
- 版本 digest 验证完成后才允许推 Git tag。
- `latest` 通过 digest promotion 指向已经验证的版本，不重新构建。
- promotion 后再次 inspect `latest`，必须与版本 digest 一致。版本 metadata 新增
  `image_digest`；现有 `commit_sha` 始终指向构建 commit，而不是后续 metadata commit。
- 正式发布开始时记录 metadata blob 和 `latest` digest。metadata 已含 `image_digest` 时以其
  version/source/digest 为前一正式状态；仅在 pre-R1 metadata 缺少该字段时，允许以最高远端
  SemVer Git tag、同版本镜像、`latest` 和 provenance 四方一致的结果建立一次性 legacy
  baseline。任一不一致即停止，新 schema 生效后禁止回退推断。`latest` 已是本次目标 digest
  时幂等成功，否则只有仍等于前一 digest（首次发布为不存在）时才能 promotion。
- metadata 以记录的远端文件 blob 为乐观锁，在最新 `origin/main` 上普通 push；相同发布
  身份幂等成功，metadata 被其他发布改变时停止。无关 main 提交导致非快进时可重新 fetch、
  复核 blob 后有界重试，禁止 force push。
- release workflow 使用的第三方 Actions 和扫描器固定到完整 commit SHA；扫描器版本和
  数据库更新时间写入 job summary。
- 不设置 `continue-on-error`。advisory 临时例外必须有编号、负责人、原因和到期日，且
  不能以通配方式忽略整个包。

### 8.3 非原子发布的失败处理

Git 和 Docker registry 不能形成真正事务，因此按可验证、只向前恢复的状态排序：

| 失败点 | 外部状态 | 处理 |
| --- | --- | --- |
| gate / credential / candidate build | 无发布状态 | 修复后重跑 |
| 已推 SHA candidate、扫描未通过 | 只有非发布 candidate，`latest` 未变 | 保留用于诊断；修复后新 run，不自动删除 |
| 已推版本镜像、未推 Git tag | 只有不可变版本镜像，`latest` 未变 | 只允许原 source/digest 重跑并继续，不删除或复用 |
| 已推 Git tag、未更新 `latest` | 版本已正式存在 | 不移动/删除 tag；前一 digest 仍匹配时恢复 promotion，否则停止 |
| 已更新 `latest`、metadata 失败 | 用户已可拉取版本 | 以 metadata blob 乐观锁重试；并发发布已改变 metadata 时停止 |

Git tag 和 version image 一旦推送即视为不可变。之后只允许原 source/digest 修复前进，不
自动删除、重写或复用。候选 tag 按 source SHA 保留；registry retention 属于独立平台治理。
OCI Distribution API 不保证 tag promotion 具备原子 CAS，因此正式镜像 tag 的写凭据必须
只授予该 workflow，并由 concurrency 串行；否则自动发布不得恢复。

### 8.4 改动范围

- `backend/requirements.in`（新增）
- `backend/requirements.txt`
- `backend/requirements-dev.in`（新增）
- `backend/requirements-dev.txt`
- `deploy/Dockerfile`
- `deploy/scripts/smoke_release_image.sh`（新增）
- `.github/workflows/docker-publish.yml`
- `.github/workflows/frontend-ci.yml`
- `.github/workflows/transport-contract-ci.yml`
- `frontend/package.json`、`frontend/package-lock.json`

## 9. U1：通用弹窗与写作台可访问性

### 9.1 GlobalModalContainer

现有容器已经有 `role=dialog`，但 role 放在遮罩层，未关联标题；组件还重复实现了 ESC 和
body overflow，缺少焦点陷阱、初始焦点和焦点恢复。

最小修复为直接复用现有 `useDialogA11y`：

- 遮罩层只负责布局和 `click.self`，dialog role 移到 `.m3-ink-modal-box`。
- 使用 Vue 3.5 已提供的 `useId()` 生成稳定 title id；`h2` 设置 id，box 设置
  `aria-labelledby`、`aria-modal=true` 和 `tabindex=-1`。
- 组件在挂载期间使用 `active=ref(true)` 调用 `useDialogA11y`，传入 box ref 和
  `handleClose`。
- 删除本组件的 document keydown 和 `document.body.style.overflow` 代码。
- `hideCloseButton` 默认值由 `true` 改为 `false`。只有具备等价、可见关闭命令的调用方
  才可显式隐藏；这是本批次唯一有意的通用组件视觉变化。
- 关闭按钮增加与标题关联的 `aria-label`，现有 `close` emit、遮罩点击和 slot API 不变。
- 不新增 modal manager。多个 modal 的滚动锁依赖 composable 现有引用计数；产品层仍应
  避免同时打开两个全局 modal。

受影响消费者包括 AppShell 的任务日志、个人设置、系统管理、提示词用量、修改密码，
以及 `WDGenerateOutlineModal`、`WDEditChapterModal`、`UserManagement`。全部做一次键盘回归，
不逐个复制焦点逻辑。

### 9.2 写作台交互

- `ChapterPipeline` 保留 `ol > li` 列表结构，在每个非 waiting 节点内使用真实
  `button type=button`；waiting 节点 disabled，Enter/Space 由原生 button 处理，选中节点
  使用 `aria-current=step`。
- 按钮样式在组件 scoped CSS 中 reset，保持 Tooltip、现有布局和 `select` emit 参数不变。
- `.chapter-console__pipeline-title` 改用现有高对比 token，不硬编码颜色；浅色和深色主题
  普通文本均达到至少 4.5:1。
- `WDAssistantPanel` 的独立滚动 aside 增加 `tabindex=0`，保留现有 aria-label；
  `marked -> DOMPurify.sanitize -> v-html` 安全链不得改变。
- 将本轮浏览器实测小于 44x44 的任务日志、AI 助手和口令显示按钮补到至少 44x44 CSS
  px；只扩大 hit area，不放大图标或改变布局轨道。

### 9.3 自动化验收

不增加自制无障碍规则，使用 `@axe-core/playwright`：

- 新增 `useDialogA11y` 单测：初始焦点、正反向 Tab 环、ESC、关闭后恢复焦点、多实例
  body lock。
- 新增 `GlobalModalContainer` 组件测试：role/name、title id、可见关闭按钮和 close emit。
- 新增任务日志 E2E：触发按钮打开后焦点进入 dialog，背景不可 Tab 到达，ESC 关闭后
  焦点回触发按钮。
- 新增 `ChapterPipeline` 单测：非 waiting 节点键盘选择，waiting 节点不可选择。
- desktop/mobile 对登录页、写作台和任务日志 dialog 执行 axe；对三个目标按钮断言
  bounding box 不小于 44x44。
- 浏览器检查两个主题无横向溢出，pipeline 文本对比度不低于 4.5:1。

主要改动文件：

- `frontend/src/components/shared/GlobalModalContainer.vue`
- `frontend/src/composables/useDialogA11y.ts`（原则上只补测试；发现契约缺口才改实现）
- `frontend/src/components/shared/AppShell.vue`
- `frontend/src/components/writing-desk/workspace/ChapterPipeline.vue`
- `frontend/src/components/writing-desk/WDAssistantPanel.vue`
- `frontend/src/views/Login.vue`
- `frontend/e2e/global-modal-accessibility.spec.ts`（新增）
- 对应的 Vitest 测试文件

## 10. D1：部署文档运行拓扑

README 的 Compose 描述从：

```text
migrate -> bootstrap -> app
```

改为：

```text
migrate -> bootstrap -> app + worker
```

并明确：

- `CHAPTER_WORKFLOW_START_ENABLED=true` 时，app 与独立 durable worker 是同一发布单元。
- app HTTP 健康不代表 worker 健康；发布后同时检查 `python -m app.worker health` 和
  `python -m app.worker metrics`。
- migrate/bootstrap 是 one-shot；任一失败时 app 和 worker 均不得启动。
- README 只保留摘要并链接 `docs/DEPLOYMENT.md`，不复制完整迁移和回滚手册。

只修改 `README.md`；`docs/DEPLOYMENT.md` 现有数据库和 worker 发布顺序继续作为权威
运维文档，A2 仅在其中补 Redis/OAuth 前置条件。

## 11. T1：scoped task SSE 纵深校验

服务端已经按 `user_id + stream_type + stream_id` 查询，这一项不是现有跨流泄漏。客户端
仍应执行 transport contract 已要求的 scope 防御，避免未来服务端、代理或 fixture 回归
时把错误事件写入当前流。

当前 snapshot 调用 `matchesStreamScope`，task event 只验证 task 结构。改为：

```text
decodeBackgroundTaskEvent(payload, expectedScope)
  -> 先验证 schema_version/cursor/task shape
  -> expectedScope 存在时，要求 task.stream_type/task.stream_id 完全匹配
  -> expectedScope 不存在时，允许全局流包含任意 scoped task
  -> mismatch 返回 { kind: 'malformed', reason: 'scope' }
```

`decodeBackgroundTaskStreamMessage` 把 `expectedScope` 继续传给 task decoder。契约失败沿用
现有“同 scope snapshot 恢复一次，仍失败则退回 polling”的机制；不添加新的错误类型、
状态或重连策略。

改动范围：

- `frontend/src/api/tasks.ts`
- `frontend/src/queries/__tests__/tasks.spec.ts`
- `.trellis/spec/backend/transport-contracts.md`（若需把 task event 规则写得更明确）

验收覆盖：匹配 scope 接受、stream type 不同拒绝、stream id 不同拒绝、unscoped 流仍接受
scoped task、拒绝事件不调用 `onTask`、恢复请求继续携带原 expected scope。

## 12. 全量验收与发布准入

所有工作包合并后执行以下质量门。命令必须在各自目录运行，不能用局部通过代替全量：

```bash
cd backend
python -m pytest -q
python -m ruff check app tests
python -m black --check app tests
python -m mypy
python -m compileall -q app
pip-audit -r requirements.txt

cd ../frontend
npm ci
npm run api:check
npm run lint
npm run type-check
npm run test:unit
npm run build
npm audit --omit=dev --audit-level=high
npx playwright install --with-deps chromium
npm run test:e2e
```

发布 workflow 另行验证：

- 候选镜像 Trivy high/critical 为 0。
- 镜像版本 tag 的 digest 与 `latest` promotion digest 一致。
- 候选逐平台 OCI labels 与 provenance 的 source/revision 绑定构建 source SHA。
- Git tag 指向被质量门验证的 source commit。
- `release-metadata/version-info.json` 的 version、git_tag、image tag、digest 和 source SHA
  一致。
- 用空 PostgreSQL 和生产恢复副本分别运行 `db-migrate -> db-bootstrap -> db-check`；本轮
  无 schema migration，但仍验证 release binary 与当前 ledger/head 兼容。

## 13. 上线与回滚

### 13.1 上线顺序

1. 合并 A1，执行一次 bootstrap 回归；已有数据库值不被重写。
2. 为启用 Linux.do 的环境配置可用 Redis，再合并 A2。先验证 OAuth 登录，再开放流量。
3. 完成 Q1，使所有拟加入的 gate 达到零失败。
4. 完成依赖升级和 lock 迁移，重新执行全量测试及审计。
5. 合并 R1，并用一次不更新正式 tag 的 dry run 验证 candidate build、扫描和 digest。
6. 合并 U1、D1、T1，完成 desktop/mobile 浏览器验收。
7. 恢复自动发布，执行首个受门禁保护的正式版本。

### 13.2 回滚

- A1：回滚代码不会恢复已错误写入的数据库值；上线前需记录
  `auth.allow_registration`，必要时通过管理配置显式纠正。
- A2：可通过 `ENABLE_LINUXDO_LOGIN=false` 立即关闭 provider 登录；不影响密码登录，无
  数据库迁移可回滚。
- R1：锁文件和 workflow 可按提交回滚；已推 Git tag 和不可变镜像不回写，只发布修复版。
- U1/T1：纯前端回滚。modal 回滚会失去焦点修复但不改变持久数据；SSE 回滚仍受服务端
  scope 过滤保护。
- D1：纯文档回滚，无运行时影响。

## 14. 可观测性与隐私

- OAuth 仅记录启用状态、provider 阶段和错误类别，不记录 code、state、cookie、token、
  provider profile 或 Redis key 后缀。
- 发布 summary 记录 gate 结果、工具版本、source SHA、镜像 digest 和 advisory 数量，不
  输出 registry token、环境变量值或完整依赖缓存路径。
- E2E trace、截图和视频只在失败时保留为 CI artifact，设置有限保留期；fixture 不使用
  真实 token、邮箱或项目数据。
- 本地审计虚拟环境、Playwright report、截图、trace 和测试容器不进入仓库。

## 15. 已知剩余风险

- Redis 成为启用 Linux.do OAuth 的可用性前置条件；这是为了多 worker 下的安全一致性，
  不做不安全降级。
- Registry 与 Git 无分布式事务，R1 只能通过状态排序和恢复步骤缩小部分发布窗口。
- OCI registry tag 更新不保证原子 compare-and-swap；R1 依赖 workflow 串行、唯一写入凭据
  和 promotion 前后校验。若平台不能保证唯一 writer，自动发布必须保持暂停。
- 同一浏览器同时发起多个 Linux.do 登录时，单个 HostOnly cookie 只保留最后一次 state；
  较早的 callback 会安全失败，需要用户重新发起。
- `useDialogA11y` 没有全局 topmost modal stack；本设计保持“同一产品流程只打开一个
  GlobalModal”约束，不为理论嵌套场景增加管理器。
- Python 全量 hash lock 会放大依赖升级 diff，必须作为独立机械提交审查。
- GitHub branch protection、environment approval、Docker Hub 保留策略和真实生产 OAuth
  往返无法通过本地测试证明，需要仓库和部署环境验收。

## 16. 完成定义

只有同时满足以下条件，整改才可关闭：

- A1-A2、Q1、R1、U1、D1、T1 的验收项全部通过。
- 所有发布门禁在 main 和一次正式发布中实际阻断/放行符合预期。
- 没有 `continue-on-error`、永久 audit ignore、跳过测试或仅文档声明的假门禁。
- 独立复核确认 Git tag、镜像 digest、metadata 三者一致。
- 工作树无审计临时文件、真实凭据、截图、trace、Playwright report 或测试容器残留。
