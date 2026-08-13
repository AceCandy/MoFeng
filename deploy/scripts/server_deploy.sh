#!/bin/bash
# 服务器端一键部署脚本
# 使用方法：
# 1. SSH 登录服务器: ssh root@45.15.185.52
# 2. 下载并执行: curl -fsSL https://raw.githubusercontent.com/all666666all/MoFeng/main/deploy/scripts/server_deploy.sh | bash

set -e

echo "========================================="
echo "MoFeng 服务器端一键部署脚本"
echo "========================================="

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 1. 检查系统
echo ""
echo -e "${BLUE}1. 检查系统环境...${NC}"
if [ "$(id -u)" != "0" ]; then
   echo -e "${RED}错误：此脚本需要 root 权限${NC}"
   exit 1
fi

echo "系统信息："
uname -a
echo ""

# 2. 安装必需软件
echo -e "${BLUE}2. 安装必需软件...${NC}"

# 安装 Git
if ! command -v git &> /dev/null; then
    echo "安装 Git..."
    apt-get update
    apt-get install -y git
fi
echo -e "${GREEN}✓ Git 已安装${NC}"

# 安装 curl
if ! command -v curl &> /dev/null; then
    echo "安装 curl..."
    apt-get install -y curl
fi
echo -e "${GREEN}✓ curl 已安装${NC}"

# 安装 Docker
if ! command -v docker &> /dev/null; then
    echo "安装 Docker..."
    curl -fsSL https://get.docker.com | bash
    systemctl start docker
    systemctl enable docker
    echo -e "${GREEN}✓ Docker 已安装${NC}"
else
    echo -e "${GREEN}✓ Docker 已存在${NC}"
fi

# 检查 Docker Compose
if ! docker compose version &> /dev/null; then
    echo -e "${YELLOW}⚠ Docker Compose 插件未安装，尝试安装...${NC}"
    apt-get update
    apt-get install -y docker-compose-plugin
fi
echo -e "${GREEN}✓ Docker Compose 已就绪${NC}"

# 3. 克隆或更新项目
echo ""
echo -e "${BLUE}3. 获取项目代码...${NC}"
cd /root

if [ -d "MoFeng" ]; then
    echo "项目目录已存在，更新代码..."
    cd MoFeng
    git fetch origin
    git reset --hard origin/main
    git pull origin main
    echo -e "${GREEN}✓ 代码已更新到最新版本${NC}"
else
    echo "克隆项目..."
    git clone https://github.com/all666666all/MoFeng.git
    cd MoFeng
    echo -e "${GREEN}✓ 项目已克隆${NC}"
fi

# 4. 配置环境变量
echo ""
echo -e "${BLUE}4. 配置环境变量...${NC}"

if [ ! -f ".env" ]; then
    echo "创建 .env 文件..."

    # 生成随机密钥
    SECRET_KEY=$(openssl rand -hex 32)

    cat > .env << ENVEOF
# 应用配置
SECRET_KEY=${SECRET_KEY}
ENVIRONMENT=production
DEBUG=false
LOGGING_LEVEL=INFO
APP_PORT=6100

# 数据库配置（PostgreSQL，启用 profile postgres）
POSTGRES_HOST=pg
POSTGRES_PORT=5432
POSTGRES_USER=mofeng
POSTGRES_PASSWORD=MoFeng-PG-$(openssl rand -hex 16)
POSTGRES_DATABASE=mofeng

# 管理员账号
BOOTSTRAP_CREATE_DEFAULT_ADMIN=true
ADMIN_DEFAULT_USERNAME=admin
ADMIN_DEFAULT_PASSWORD=MoFeng-$(openssl rand -hex 12)
ADMIN_DEFAULT_EMAIL=admin@mofeng.com

# OpenAI API（请手动配置）
OPENAI_API_KEY=sk-placeholder-please-replace-with-real-key
OPENAI_API_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL_NAME=gpt-4
WRITER_CHAPTER_VERSION_COUNT=2
# 向量检索配置（pgvector，与主库共用 PostgreSQL）
VECTOR_STORE_ENABLED=true
VECTOR_TOP_K_CHUNKS=5
VECTOR_TOP_K_SUMMARIES=3
VECTOR_CHUNK_SIZE=480
VECTOR_CHUNK_OVERLAP=120

# 用户注册
ALLOW_USER_REGISTRATION=true
ENABLE_LINUXDO_LOGIN=false

# SMTP 配置（可选）
SMTP_SERVER=smtp.example.com
SMTP_PORT=465
SMTP_USERNAME=no-reply@example.com
SMTP_PASSWORD=
EMAIL_FROM=MoFeng
ENVEOF

    echo -e "${GREEN}✓ .env 文件已创建${NC}"
    echo -e "${YELLOW}⚠ 请编辑 .env 文件，配置你的 OPENAI_API_KEY${NC}"
    echo -e "${YELLOW}   执行: nano /root/MoFeng/.env${NC}"
else
    echo -e "${GREEN}✓ .env 文件已存在${NC}"
fi

# 5. 部署 Docker 容器
echo ""
echo -e "${BLUE}5. 部署 Docker 容器...${NC}"
bash deploy/scripts/deploy_docker.sh

# 6. 显示部署信息
echo ""
echo "========================================="
echo -e "${GREEN}部署成功！${NC}"
echo "========================================="
echo ""
echo "访问信息："
echo "  前端地址: http://$(curl -s ifconfig.me)"
echo "  本地访问: http://localhost:6100"
echo "  API 文档: http://localhost:6100/api/docs"
echo ""
echo "管理员账号："
echo "  用户名: admin"
echo "  密码: 已随机生成（见 .env 中 ADMIN_DEFAULT_PASSWORD），请立即修改"
echo ""
echo -e "${YELLOW}重要提示：${NC}"
echo "1. 请立即修改管理员密码"
echo "2. 配置 OPENAI_API_KEY（如果还没有）："
echo "   nano /root/MoFeng/.env"
echo "   然后重建应用: cd /root/MoFeng && docker compose --env-file .env -f deploy/docker-compose.yml --profile postgres up -d --force-recreate app"
echo ""
echo "常用命令："
echo "  查看日志: cd /root/MoFeng && docker compose --env-file .env -f deploy/docker-compose.yml --profile postgres logs -f app"
echo "  重启服务: cd /root/MoFeng && docker compose --env-file .env -f deploy/docker-compose.yml --profile postgres restart app"
echo "  停止服务: cd /root/MoFeng && docker compose --env-file .env -f deploy/docker-compose.yml --profile postgres down"
echo ""
echo "如需帮助，请查看: /root/MoFeng/docs/DEPLOYMENT.md"
echo ""
