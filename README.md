# Arboris Novel

> 面向长篇小说创作的 AI 辅助系统，覆盖灵感构思、蓝图生成、章节写作、评审与后台管理。

中文 | [English](./README-en.md)

## 项目简介

Arboris Novel 是一个用于长篇小说创作的全栈应用，支持从概念对话到蓝图确认、章节生成、版本评审、伏笔追踪与项目管理的完整流程。

当前技术栈：

- 前端：Vue 3 + Vite + TypeScript + TanStack Query for Vue + Pinia + Vue Router + Naive UI
- 后端：FastAPI + SQLAlchemy + Pydantic Settings
- 存储：SQLite / MySQL + libsql 向量检索
- AI：OpenAI 兼容接口 + OpenAI / Ollama Embedding

## 前端状态管理

前端已经完成 TanStack Query for Vue 改造：

- 接口请求、服务端缓存、刷新、重试、loading / error 状态由 TanStack Query 管理
- 小说项目、章节、详情页材料、管理后台、LLM 设置、登录注册与更新日志均通过 Query 组合函数访问
- Pinia 只保留客户端状态，例如登录令牌、当前用户、灵感流程临时会话状态
- 全局 Query 策略位于 `frontend/src/lib/queryClient.ts`
- 业务 Query 组合函数位于 `frontend/src/queries/`

## 核心创作流程

1. 登录或注册
2. 在设置页配置个人 LLM / Embedding 模型
3. 在灵感模式中进行多轮概念对话，创建项目
4. 生成并确认结构化蓝图
5. 在工作区管理项目
6. 在详情页查看设定、角色、纲要、章节与分析结果
7. 在写作台生成、评审、选版与编辑章节内容
8. 在后台管理用户、Prompt、更新日志与系统配置

## 功能特性

- 灵感模式多轮对话共创
- 蓝图生成与保存
- 章节生成、评审、选版、编辑
- 章节纲要生成与维护
- 伏笔追踪与状态同步
- 情绪曲线与分析视图
- `.txt` 小说导入
- 用户、Prompt、更新日志、系统配置管理

## 快速开始

### 本地开发

后端：

```bash
cd backend
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
# Windows
copy env.example .env
# macOS / Linux
# cp env.example .env

uvicorn app.main:app --reload
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认访问地址：

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8000`
- Swagger：`http://127.0.0.1:8000/docs`

也可以在仓库根目录使用辅助脚本：

- Windows CMD：`dev.bat`
- PowerShell：`powershell -ExecutionPolicy Bypass -File .\dev.ps1`
- Bash：`bash ./dev.sh`

辅助脚本行为：

- 若 `frontend/node_modules` 不存在，会自动执行依赖安装
- 若 `backend/.venv` 不存在，会自动创建虚拟环境
- 若当前 Python 环境缺少 `uvicorn`，会自动安装 `backend/requirements.txt`
- 若默认端口 `8000` 或 `5173` 已占用，会自动切换到可用端口
- 前后端开发服务默认监听 `0.0.0.0`，可通过局域网 IP 访问
- 脚本启动后会输出本机访问地址和实际 API 代理地址

### Docker（本地）

```bash
# Windows
copy deploy\.env.example deploy\.env
# macOS / Linux
# cp deploy/.env.example deploy/.env

docker compose --env-file deploy/.env -f deploy/docker-compose.yml up -d --build
```

默认访问地址：

- `http://127.0.0.1:8088`

如需使用内置 MySQL：

```bash
docker compose --env-file deploy/.env -f deploy/docker-compose.yml --profile mysql up -d --build
```

## 配置说明

本地开发使用 `backend/env.example` 作为 `backend/.env` 模板。

最低可启动配置：

- `SECRET_KEY`
- `DB_PROVIDER`
- 使用 SQLite 时的 `SQLITE_DB_PATH`

建议补齐以正常使用创作能力：

- `OPENAI_API_KEY`
- `OPENAI_API_BASE_URL`
- `OPENAI_MODEL_NAME`
- `EMBEDDING_PROVIDER`
- `EMBEDDING_MODEL`
- `VECTOR_DB_URL`
- `ADMIN_DEFAULT_USERNAME`
- `ADMIN_DEFAULT_PASSWORD`

Docker 部署使用 `deploy/.env.example` 作为 `deploy/.env` 模板。

## 初始化行为

后端首次启动时会自动：

1. 确保数据库存在
2. 创建缺失表结构
3. 补齐历史缺失字段
4. 在没有管理员时创建默认管理员账号
5. 将 `backend/prompts/*.md` 导入数据库
6. 同步默认系统配置

## 目录结构

```text
.
├─ backend/                  # FastAPI 后端
│  ├─ app/
│  │  ├─ api/                # 路由层
│  │  ├─ core/               # 配置、安全、依赖
│  │  ├─ db/                 # 数据库初始化与连接
│  │  ├─ models/             # ORM 模型
│  │  ├─ repositories/       # 数据访问层
│  │  ├─ schemas/            # Pydantic Schema
│  │  └─ services/           # 业务服务层
│  ├─ prompts/               # 默认 Prompt 模板
│  └─ env.example
├─ frontend/                 # Vue 前端
│  ├─ src/
│  │  ├─ api/                # API 客户端与类型
│  │  ├─ components/
│  │  ├─ lib/                # Query Client 等前端基础设施
│  │  ├─ queries/            # TanStack Query 组合函数
│  │  ├─ router/
│  │  ├─ stores/             # Pinia 客户端状态
│  │  └─ views/
├─ deploy/                   # Docker / Nginx / Compose
├─ docs/                     # 补充文档
├─ dev.bat
├─ dev.ps1
└─ dev.sh
```

## 二开说明

当前仓库已按二开场景整理。准备发布你自己的版本时，至少应检查以下配置：

- `VERSION_INFO_URL`
- `IMAGE_REPO`
- `EMAIL_FROM`
- Linux.do OAuth 相关配置（如启用）
- 默认管理员账号密码

更完整的部署与二开说明见 [docs/DEPLOYMENT.md](./docs/DEPLOYMENT.md)。

## 许可

请以仓库中的实际 `LICENSE` 文件或你的发布策略为准。
