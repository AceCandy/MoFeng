# ============================================
# 第一阶段：构建前端静态资源
# ============================================
ARG APP_VERSION=dev
FROM node:20-slim AS frontend-builder

WORKDIR /frontend
ARG APP_VERSION
ENV VITE_APP_VERSION=${APP_VERSION}

# 配置 npm 使用中国镜像源
RUN npm config set registry https://registry.npmmirror.com

# 复制前端依赖文件
COPY frontend/package*.json ./

# 安装前端依赖
RUN npm ci --prefer-offline --no-audit --no-fund

# 复制前端源码
COPY frontend/ ./

# 构建前端
RUN npm run build

# ============================================
# 第二阶段：构建 Python 依赖（仅构建层保留编译工具）
# ============================================
FROM python:3.11-alpine AS python-builder
ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}

WORKDIR /build

# 仅在构建阶段安装编译依赖，避免进入最终运行镜像
RUN apk add --no-cache \
    gcc \
    musl-dev \
    pkgconf

# 配置 pip 使用中国镜像源
RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

# 创建虚拟环境并安装依赖
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:${PATH}"

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --no-compile --require-hashes -r requirements.txt && \
    /opt/venv/bin/python -m uvicorn --version >/dev/null && \
    python -m pip uninstall -y pip setuptools wheel && \
    find /opt/venv -type d \( -name "tests" -o -name "test" -o -name "__pycache__" \) -prune -exec rm -rf {} + && \
    find /opt/venv -type f \( -name "*.pyc" -o -name "*.pyo" -o -name "*.a" \) -delete

# ============================================
# 第三阶段：构建最终镜像（后端 + nginx）
# ============================================
FROM python:3.11-alpine AS runtime
ARG APP_VERSION
ENV APP_VERSION=${APP_VERSION}
ENV PATH="/opt/venv/bin:${PATH}"

WORKDIR /app

# 安装运行时依赖：不再包含编译工具链，降低最终镜像体积
RUN apk add --no-cache \
    nginx \
    supervisor \
    curl && \
    python -m pip uninstall -y pip setuptools wheel

# 从构建阶段复制 Python 依赖环境
COPY --from=python-builder /opt/venv /opt/venv

# 仅复制运行时必需的后端代码与内置提示词，避免无关文件进入镜像
COPY backend/app ./app
COPY backend/prompts ./prompts
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic

# 清理可能残留的本地数据文件，确保首次启动时根据环境变量初始化管理员密码
RUN rm -rf /app/storage && mkdir -p /app/storage

# 从前端构建阶段复制静态资源到 nginx 默认目录
COPY --from=frontend-builder /frontend/dist /usr/share/nginx/html

# 复制部署配置
COPY deploy/nginx.conf /etc/nginx/http.d/default.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY deploy/docker-entrypoint.sh /app/docker-entrypoint.sh

# 允许入口脚本在启动时修正宿主机挂载目录权限
RUN chmod +x /app/docker-entrypoint.sh

# 创建非 root 用户（供 supervisor 使用）
RUN adduser -D -u 1000 appuser && \
    chown -R appuser:appuser /app

# 暴露端口（nginx 前端入口 6100 端口）
EXPOSE 6100

# 使用 supervisor 启动 nginx 和 uvicorn
# 注意：容器以 root 启动，supervisor 会根据配置降权运行各个进程
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]
