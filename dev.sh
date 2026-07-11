#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_HOST="0.0.0.0"
BACKEND_PROXY_HOST="127.0.0.1"
BACKEND_DEFAULT_PORT=6101
FRONTEND_HOST="0.0.0.0"
FRONTEND_HMR_HOST="localhost"
FRONTEND_DEFAULT_PORT=6100

if [ ! -d "$BACKEND_DIR" ] || [ ! -d "$FRONTEND_DIR" ]; then
  echo "未找到 backend 或 frontend 目录。"
  exit 1
fi

cleanup() {
  local exit_code=$?
  trap - INT TERM EXIT

  if [ -n "${BACKEND_PID:-}" ] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi

  if [ -n "${FRONTEND_PID:-}" ] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi

  wait 2>/dev/null || true
  exit "$exit_code"
}

resolve_venv_python() {
  if [ -x "$BACKEND_DIR/.venv/bin/python" ]; then
    printf '%s\n' "$BACKEND_DIR/.venv/bin/python"
    return
  fi

  if [ -x "$BACKEND_DIR/.venv/Scripts/python.exe" ]; then
    printf '%s\n' "$BACKEND_DIR/.venv/Scripts/python.exe"
    return
  fi

  return 1
}

resolve_bootstrap_python() {
  if resolve_venv_python >/dev/null 2>&1; then
    resolve_venv_python
    return
  fi

  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return
  fi

  echo "未找到 Python，请先安装 Python 3.10+。" >&2
  exit 1
}

ensure_frontend_dependencies() {
  if [ -d "$FRONTEND_DIR/node_modules" ]; then
    return
  fi

  echo "frontend/node_modules 不存在，正在执行 npm install..."
  (
    cd "$FRONTEND_DIR"
    npm install
  )
}

ensure_backend_environment() {
  local bootstrap_python requirements_file
  bootstrap_python="$(resolve_bootstrap_python)"
  requirements_file="$BACKEND_DIR/requirements.txt"

  if [ ! -d "$BACKEND_DIR/.venv" ]; then
    echo "backend/.venv 不存在，正在创建虚拟环境..."
    "$bootstrap_python" -m venv "$BACKEND_DIR/.venv"
  fi

  BACKEND_PYTHON="$(resolve_venv_python || true)"
  if [ -z "$BACKEND_PYTHON" ]; then
    BACKEND_PYTHON="$bootstrap_python"
  fi

  if "$BACKEND_PYTHON" -c "import uvicorn" >/dev/null 2>&1; then
    return
  fi

  if [ ! -f "$requirements_file" ]; then
    echo "未找到 backend/requirements.txt，无法自动安装后端依赖。" >&2
    exit 1
  fi

  echo "当前 Python 环境缺少 uvicorn，正在安装 backend 依赖..."
  "$BACKEND_PYTHON" -m pip install -r "$requirements_file"
}

python_for_port_check() {
  if command -v python3 >/dev/null 2>&1; then
    printf '%s\n' "python3"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    printf '%s\n' "python"
    return
  fi

  echo "未找到可用于端口检测的 Python。" >&2
  exit 1
}

is_port_available() {
  local host=$1
  local port=$2

  # 优先用 ss 查 LISTEN：有进程监听才算占用，TIME_WAIT 等残留不算（与 vite/uvicorn 实际 listen 行为一致）
  if command -v ss >/dev/null 2>&1; then
    if ss -tlnH 2>/dev/null | awk -v p="${port}" '$4 ~ ":"p"([^0-9]|$)"' | grep -q .; then
      return 1   # 存在 LISTEN → 端口被占
    fi
    return 0
  fi

  # 无 ss（如 macOS）降级为 bind 探测；不开 SO_REUSEADDR，避免 macOS 把 127.0.0.1 监听误判为 0.0.0.0 可用
  local port_check_python
  port_check_python="$(python_for_port_check)"

  if "$port_check_python" - <<PY >/dev/null 2>&1
import socket
sock = socket.socket()
try:
    sock.bind(("$host", $port))
except OSError:
    raise SystemExit(1)
finally:
    sock.close()
PY
  then
    return 0
  fi

  return 1
}

# 端口判定不可用时打印占用诊断：优先列出 LISTEN 进程，否则提示残留 socket（如 TIME_WAIT）
show_port_occupant() {
  local port=$1
  echo "  >> 端口 ${port} 判定为不可用，排查占用源：" >&2
  if ! command -v ss >/dev/null 2>&1; then
    echo "    未找到 ss，可手动排查：lsof -i:${port} 或 sudo netstat -tlnp | grep :${port}" >&2
    return
  fi
  if ss -tlnH 2>/dev/null | awk -v p="${port}" '$4 ~ ":"p"([^0-9]|$)"' | grep -q .; then
    echo "    [LISTEN] 占用 ${port} 的监听（进程名需 root 权限）：" >&2
    ss -tlnp 2>/dev/null | awk -v p="${port}" 'NR==1 || $4 ~ ":"p"([^0-9]|$)"' | sed 's/^/      /' >&2 || true
  else
    echo "    无 LISTEN 占用，可能是 TIME_WAIT 等残留 socket：" >&2
    ss -tan 2>/dev/null | awk -v p="${port}" '$4 ~ ":"p"([^0-9]|$)" {print $1}' | sort | uniq -c | sed 's/^/      /' >&2 || true
  fi
}

find_available_port() {
  local host=$1
  local start_port=$2
  local port=$start_port

  while [ "$port" -le 65535 ]; do
    if is_port_available "$host" "$port"; then
      printf '%s\n' "$port"
      return
    fi
    # 默认端口不可用时打印一次占用诊断，便于定位"查不到占用却切换"的情况
    if [ "$port" = "$start_port" ]; then
      show_port_occupant "$port"
    fi
    port=$((port + 1))
  done

  echo "未找到可用端口：$host:$start_port-65535" >&2
  exit 1
}

resolve_frontend_node_options() {
  local existing_options="${NODE_OPTIONS:-}"
  local node_major

  node_major="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || printf '0')"

  if [ "$node_major" -lt 22 ] 2>/dev/null; then
    printf '%s\n' "$existing_options"
    return
  fi

  case " $existing_options " in
    *" --no-experimental-webstorage "*|*" --localstorage-file="*)
      printf '%s\n' "$existing_options"
      ;;
    *)
      # Node 22+ 会暴露实验性 WebStorage；未配置持久化文件时会让 Vue DevTools 在 Vite 配置加载阶段崩溃。
      printf '%s\n' "${existing_options:+$existing_options }--no-experimental-webstorage"
      ;;
  esac
}

trap cleanup INT TERM EXIT

if ! command -v npm >/dev/null 2>&1; then
  echo "未找到 npm，请先安装 Node.js 18+。"
  exit 1
fi

ensure_frontend_dependencies
ensure_backend_environment

BACKEND_PORT="$(find_available_port "$BACKEND_HOST" "$BACKEND_DEFAULT_PORT")"
FRONTEND_PORT="$(find_available_port "$FRONTEND_HOST" "$FRONTEND_DEFAULT_PORT")"
FRONTEND_NODE_OPTIONS="$(resolve_frontend_node_options)"

if [ "$BACKEND_PORT" != "$BACKEND_DEFAULT_PORT" ]; then
  echo "检测到后端默认端口 ${BACKEND_DEFAULT_PORT} 已占用，自动切换到 ${BACKEND_PORT}。"
fi

if [ "$FRONTEND_PORT" != "$FRONTEND_DEFAULT_PORT" ]; then
  echo "检测到前端默认端口 ${FRONTEND_DEFAULT_PORT} 已占用，自动切换到 ${FRONTEND_PORT}。"
fi

if [ ! -f "$BACKEND_DIR/.env" ] && [ -f "$BACKEND_DIR/env.example" ]; then
  echo "提示：backend/.env 不存在，可参考 backend/env.example 创建。"
fi

echo "启动后端开发服务..."
(
  cd "$BACKEND_DIR"
  exec "$BACKEND_PYTHON" -m uvicorn app.main:app --reload --host "$BACKEND_HOST" --port "$BACKEND_PORT"
) &
BACKEND_PID=$!

echo "启动前端开发服务..."
(
  cd "$FRONTEND_DIR"
  exec env NODE_OPTIONS="$FRONTEND_NODE_OPTIONS" BACKEND_PROXY_HOST="$BACKEND_PROXY_HOST" BACKEND_PORT="$BACKEND_PORT" FRONTEND_HOST="$FRONTEND_HOST" FRONTEND_PORT="$FRONTEND_PORT" FRONTEND_HMR_HOST="$FRONTEND_HMR_HOST" npm run dev
) &
FRONTEND_PID=$!

echo ""
echo "开发环境已启动："
echo "- 后端监听: http://$BACKEND_HOST:$BACKEND_PORT"
echo "- 前端监听: http://$FRONTEND_HOST:$FRONTEND_PORT"
echo "- 本机访问前端: http://127.0.0.1:$FRONTEND_PORT"
echo "- 本机 API 代理: http://$BACKEND_PROXY_HOST:$BACKEND_PORT/api"
echo "按 Ctrl+C 可同时停止前后端。"
echo ""

wait -n "$BACKEND_PID" "$FRONTEND_PID"
