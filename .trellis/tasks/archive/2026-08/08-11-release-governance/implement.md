# 实施计划

## 1. 依赖输入、JWT 兼容与审计收敛

- 新增 runtime/dev input，把测试工具移出 runtime，加入 dev 审计工具。
- 先补 JWT encode/decode、过期、篡改、缺失 subject 的 focused tests，再把
  `python-jose` 换成 PyJWT。
- 升级 Python advisory 相关直接依赖；更新前端依赖根和 lock，避免长期 override。
- 用固定版本 pip-tools 生成两个 hash lock：

```bash
cd backend
lock_venv="$(mktemp -d)"
runtime_venv="$(mktemp -d)"
dev_venv="$(mktemp -d)"
trap 'rm -rf "${lock_venv}" "${runtime_venv}" "${dev_venv}"' EXIT
python3.11 -m venv "${lock_venv}"
"${lock_venv}/bin/python" -m pip install 'pip==24.3.1' 'pip-tools==7.6.0'
"${lock_venv}/bin/pip-compile" --generate-hashes --strip-extras \
  --no-emit-index-url --no-emit-trusted-host -o requirements.txt requirements.in
"${lock_venv}/bin/pip-compile" --generate-hashes --strip-extras --allow-unsafe \
  --no-emit-index-url --no-emit-trusted-host -o requirements-dev.txt requirements-dev.in
python3.11 -m venv "${runtime_venv}"
"${runtime_venv}/bin/python" -m pip install --require-hashes -r requirements.txt
"${runtime_venv}/bin/python" -c 'import fastapi, jwt, sqlalchemy, uvicorn'
python3.11 -m venv "${dev_venv}"
"${dev_venv}/bin/python" -m pip install --require-hashes -r requirements-dev.txt
"${dev_venv}/bin/python" -m pytest --version
"${dev_venv}/bin/python" -m pip_audit -r requirements.txt
```

回滚点：依赖 input/lock 与 JWT 兼容测试单独提交；任何行为回归先回退依赖批次，不进入
workflow 改造。

## 2. 安装门禁

- Docker runtime 安装改为 `--require-hashes`。
- CI backend 安装统一使用 dev hash lock；paths/cache 同时覆盖 `.in` 与 `.txt`。
- 保持 Docker 只复制 runtime lock，不把 test/audit 工具带入生产镜像。
- 验证 Docker runtime build、`uvicorn --version` 和静态部署契约测试。

回滚点：hash 安装与 Dockerfile 单独提交；锁不完整时构建必须明确失败。

## 3. 候选镜像 smoke

- 新增最小 shell 脚本，严格校验 digest 输入，复用现有 Compose/DB/worker 命令。
- 使用 trap 清理隔离容器、network、volume 和临时本地 tag；失败时仅输出有界日志。
- 增加脚本语法、输入拒绝和部署契约测试；有 Docker 时执行真实本地 smoke。

验证：

```bash
bash -n deploy/scripts/smoke_release_image.sh
cd backend
python -m pytest -q tests/test_database_readiness.py tests/test_dev_script_static.py
```

## 4. 发布 workflow 状态机

- 保留现有“排除 release-metadata 后检查新提交”和 patch 版本计算逻辑。
- 按设计拆分 gate、凭据、candidate build、digest capture、逐平台 scan、smoke、version
  promotion、Git tag、latest promotion、metadata jobs。
- 固定 Actions SHA，收窄权限，关闭 cancel-in-progress；加入默认 dry-run dispatch。
- 在产生正式状态前捕获 metadata blob 与 `latest`；实现 normal baseline 和仅限 pre-R1
  metadata 的 legacy baseline，并静态/隔离测试四方一致、任一漂移、schema 生效后禁用回退。
- 将 workflow 是正式 tag 唯一写入方列为启用自动发布前的管理员确认项。
- version/Git tag 实现“同 source/digest 幂等成功、冲突失败且不删除”；`latest` 只允许
  从记录的前一 digest 前进到目标 digest，并在 promotion 后验证。
- metadata 增加 `image_digest`，并保持 `commit_sha` 指向 source commit。
- metadata 写入基于远端文件 blob 乐观锁；目标身份相同幂等成功，metadata 已被其他发布
  修改则停止，只有无关 main 提交可在重新核对 blob 后有界重试普通 push。
- 用 `docker buildx imagetools inspect --format '{{json .Image.Config.Labels}}'` 读取每个平台
  digest 的 OCI labels，用 `--format '{{json .Provenance.SLSA}}'` 读取候选 provenance；以
  结构化 JSON 断言 source/revision/version，字段缺失、平台缺失或值不一致均失败。
- 用结构化 YAML 解析测试 job `needs` 图、权限、dry-run 边界和不可逆顺序，并覆盖 version
  孤立恢复、normal/legacy provenance 漂移、`latest` 前置 digest 冲突、metadata 并发冲突；
  用 actionlint 校验表达式与 schema。

回滚点：workflow 与 metadata schema 单独提交；正式发布前只允许 dry-run。

## 5. 全量验证与独立复核

```bash
cd backend
python -m pytest -q
python -m ruff check app tests
python -m black --check app tests
python -m mypy
python -m compileall -q app
python -m pip_audit -r requirements.txt

cd ../frontend
npm ci
npm run api:check
npm run lint
npm run type-check
npm run test:unit
npm run build
npm audit --omit=dev --audit-level=high
npm run test:e2e
```

- 再执行 Docker build、候选 digest 本地 smoke、`actionlint` 和 `git diff --check`。
- 独立复核依赖锁来源、逐平台 OCI labels/provenance、job needs 图、权限、secret 输出、失败
  恢复、metadata 乐观锁和本地资源清理路径。
- 本地全绿后，在 GitHub 仓库环境运行一次 dry-run；确认无正式 tag/latest/metadata 变更。
- 首个正式发布先确认正式镜像 tag 只有该 workflow 可写，再核对 Git tag、version/latest
  manifest digest、metadata source SHA/digest；人工制造冲突只在隔离测试仓库执行。
- 未完成仓库环境 dry-run 与正式发布一致性验证前，不归档 R1 或父任务。
