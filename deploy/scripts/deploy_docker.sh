#!/usr/bin/env bash
# Docker 部署脚本

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="$PROJECT_ROOT/deploy/docker-compose.yml"

if [ -n "${ENV_FILE:-}" ]; then
    case "$ENV_FILE" in
        /*) DEPLOY_ENV_FILE="$ENV_FILE" ;;
        *) DEPLOY_ENV_FILE="$PROJECT_ROOT/$ENV_FILE" ;;
    esac
elif [ -f "$PROJECT_ROOT/deploy/.env" ]; then
    DEPLOY_ENV_FILE="$PROJECT_ROOT/deploy/.env"
elif [ -f "$PROJECT_ROOT/.env" ]; then
    DEPLOY_ENV_FILE="$PROJECT_ROOT/.env"
else
    DEPLOY_ENV_FILE="$PROJECT_ROOT/deploy/.env"
fi

echo "========================================="
echo "MoFeng Docker 部署脚本"
echo "========================================="

if [ ! -f "$COMPOSE_FILE" ]; then
    echo -e "${RED}错误：未找到 deploy/docker-compose.yml${NC}"
    exit 1
fi

if [ ! -f "$DEPLOY_ENV_FILE" ]; then
    echo -e "${YELLOW}未找到部署环境文件：$DEPLOY_ENV_FILE${NC}"
    echo "请先从 deploy/.env.example 创建并填写配置。"
    exit 1
fi

set -a
# shellcheck disable=SC1090
source "$DEPLOY_ENV_FILE"
set +a

REQUIRED_VARS=(SECRET_KEY POSTGRES_PASSWORD)
if [ "${BOOTSTRAP_CREATE_DEFAULT_ADMIN:-true}" != "false" ]; then
    REQUIRED_VARS+=(ADMIN_DEFAULT_PASSWORD)
fi
for variable_name in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!variable_name:-}" ]; then
        echo -e "${RED}错误：缺少环境变量 $variable_name${NC}"
        exit 1
    fi
done

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}错误：未安装 Docker${NC}"
    exit 1
fi

if docker compose version >/dev/null 2>&1; then
    COMPOSE=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE=(docker-compose)
else
    echo -e "${RED}错误：未安装 Docker Compose${NC}"
    exit 1
fi

PROFILE_ARGS=()
if [ "${POSTGRES_HOST:-pg}" = "pg" ]; then
    PROFILE_ARGS=(--profile postgres)
    echo "数据库模式：内置 PostgreSQL"
else
    echo "数据库模式：外部 PostgreSQL (${POSTGRES_HOST})"
fi

COMPOSE_ARGS=(--env-file "$DEPLOY_ENV_FILE" -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}")

echo "停止旧容器..."
"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" down || true

echo "构建应用镜像..."
"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" build --no-cache migrate

echo "执行 migrate -> bootstrap -> app 启动链..."
"${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" up -d

echo "检查服务 readiness..."
MAX_RETRIES=30
RETRY_COUNT=0
until curl -fsS "http://127.0.0.1:${APP_PORT:-6100}/api/ready" >/dev/null 2>&1; do
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ "$RETRY_COUNT" -ge "$MAX_RETRIES" ]; then
        echo -e "${RED}服务 readiness 检查失败${NC}"
        "${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" ps
        "${COMPOSE[@]}" "${COMPOSE_ARGS[@]}" logs --tail=80 migrate bootstrap app
        exit 1
    fi
    sleep 2
done

echo -e "${GREEN}部署完成，schema、bootstrap 与应用 readiness 均已通过。${NC}"
echo "访问地址：http://localhost:${APP_PORT:-6100}"
echo "查看日志：docker compose --env-file $DEPLOY_ENV_FILE -f $COMPOSE_FILE logs -f"
