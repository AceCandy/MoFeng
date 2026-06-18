#!/usr/bin/env python
"""Unified dev server manager.

Usage:
  python dev_servers.py

Then choose:
  1 -> start backend + frontend
  2 -> stop backend + frontend
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_HOST = "0.0.0.0"
BACKEND_PROXY_HOST = "127.0.0.1"
BACKEND_DEFAULT_PORT = 6101
FRONTEND_HOST = "0.0.0.0"
FRONTEND_HMR_HOST = "localhost"
FRONTEND_DEFAULT_PORT = 6100


def _powershell_executable() -> str:
    win_root = os.environ.get("SystemRoot", r"C:\Windows")
    candidate = Path(win_root) / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
    if candidate.exists():
        return str(candidate)
    return "powershell"


def _resolve_venv_python(repo_root: Path) -> str | None:
    candidates = [
        repo_root / "backend" / ".venv" / "Scripts" / "python.exe",
        repo_root / "backend" / ".venv" / "bin" / "python",
        repo_root / ".venv" / "Scripts" / "python.exe",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _resolve_bootstrap_python(repo_root: Path) -> str:
    venv_python = _resolve_venv_python(repo_root)
    if venv_python:
        return venv_python

    if shutil.which("python"):
        return "python"
    if shutil.which("python3"):
        return "python3"
    raise RuntimeError("Python executable not found. Please install Python 3.10+.")


def _run_checked(command: list[str], *, cwd: Path, failure_message: str) -> None:
    result = subprocess.run(command, cwd=cwd, check=False)
    if result.returncode != 0:
        raise RuntimeError(failure_message)


def _test_python_module(python_exe: str, module_name: str) -> bool:
    try:
        result = subprocess.run(
            [python_exe, "-c", f"import {module_name}"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except OSError:
        return False


def _ensure_frontend_dependencies(frontend_dir: Path) -> None:
    if (frontend_dir / "node_modules").exists():
        return

    npm_exe = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm_exe:
        raise RuntimeError("npm executable not found. Please install Node.js 18+.")

    print("[frontend] node_modules missing. Installing frontend dependencies...")
    _run_checked([npm_exe, "install"], cwd=frontend_dir, failure_message="Failed to install frontend dependencies.")


def _ensure_backend_environment(repo_root: Path, backend_dir: Path) -> str:
    bootstrap_python = _resolve_bootstrap_python(repo_root)
    venv_dir = backend_dir / ".venv"
    requirements = backend_dir / "requirements.txt"

    if not venv_dir.exists():
        print("[backend] .venv missing. Creating virtual environment...")
        _run_checked(
            [bootstrap_python, "-m", "venv", str(venv_dir)],
            cwd=repo_root,
            failure_message="Failed to create backend virtual environment.",
        )

    python_exe = _resolve_venv_python(repo_root) or bootstrap_python
    if _test_python_module(python_exe, "uvicorn"):
        return python_exe

    if not requirements.exists():
        raise RuntimeError(f"uvicorn is missing and requirements.txt not found: {requirements}")

    print(f"[backend] uvicorn not found in '{python_exe}'. Installing backend requirements...")
    _run_checked(
        [python_exe, "-m", "pip", "install", "-r", str(requirements)],
        cwd=backend_dir,
        failure_message=f"Failed to install backend requirements with {python_exe}",
    )

    if not _test_python_module(python_exe, "uvicorn"):
        raise RuntimeError(f"uvicorn still missing after install. Please check Python environment: {python_exe}")

    return python_exe


def _is_port_available(host: str, port: int) -> bool:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # 不启用 SO_REUSEADDR，避免 macOS 上把已有 127.0.0.1 监听误判为 0.0.0.0 可用。
    try:
        sock.bind((host, port))
    except OSError:
        return False
    finally:
        sock.close()
    return True


def _find_available_port(host: str, start_port: int) -> int:
    port = start_port
    while port <= 65535:
        if _is_port_available(host, port):
            return port
        port += 1
    raise RuntimeError(f"No available port found for {host}:{start_port}-65535")


def _load_state(state_file: Path) -> dict[str, Any] | None:
    if not state_file.exists():
        return None
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        state_file.unlink(missing_ok=True)
        print(f"State file invalid and removed: {state_file}")
        return None


def _stop_pid_tree(pid: int, name: str) -> None:
    result = subprocess.run(
        ["taskkill", "/PID", str(pid), "/T", "/F"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        print(f"Stopped {name} (PID: {pid}).")
        return

    output = (result.stdout + result.stderr).strip().lower()
    if "not found" in output or "没有运行的实例" in output or "no running instance" in output:
        print(f"{name} already stopped (PID: {pid}).")
    else:
        print(f"Failed to stop {name} (PID: {pid}): {(result.stdout + result.stderr).strip()}")


def stop_servers(repo_root: Path, *, quiet_when_missing: bool = False) -> None:
    state_file = repo_root / ".dev-servers.json"
    state = _load_state(state_file)
    if not state:
        if not quiet_when_missing:
            print(f"No running dev state found ({state_file}).")
        return

    for key in ("backend_pid", "frontend_pid"):
        value = state.get(key)
        if value is None:
            continue
        try:
            pid = int(value)
        except (TypeError, ValueError):
            continue
        _stop_pid_tree(pid, key)

    state_file.unlink(missing_ok=True)
    print(f"Removed state file: {state_file}")


def start_servers(repo_root: Path) -> None:
    backend_dir = repo_root / "backend"
    frontend_dir = repo_root / "frontend"
    state_file = repo_root / ".dev-servers.json"

    if not backend_dir.exists():
        raise RuntimeError(f"Missing backend directory: {backend_dir}")
    if not frontend_dir.exists():
        raise RuntimeError(f"Missing frontend directory: {frontend_dir}")

    stop_servers(repo_root, quiet_when_missing=True)

    _ensure_frontend_dependencies(frontend_dir)
    python_exe = _ensure_backend_environment(repo_root, backend_dir)
    backend_port = _find_available_port(BACKEND_HOST, BACKEND_DEFAULT_PORT)
    frontend_port = _find_available_port(FRONTEND_HOST, FRONTEND_DEFAULT_PORT)
    ps_exe = _powershell_executable()

    if backend_port != BACKEND_DEFAULT_PORT:
        print(f"[backend] default port {BACKEND_DEFAULT_PORT} is in use. Switching to {backend_port}.")
    if frontend_port != FRONTEND_DEFAULT_PORT:
        print(f"[frontend] default port {FRONTEND_DEFAULT_PORT} is in use. Switching to {frontend_port}.")
    if not (backend_dir / ".env").exists() and (backend_dir / "env.example").exists():
        print("[backend] Hint: backend/.env not found. You can create it from backend/env.example.")

    backend_command = f"""
Set-Location -LiteralPath '{backend_dir}'
Write-Host '[backend] starting on http://{BACKEND_HOST}:{backend_port}'
Write-Host '[backend] python: {python_exe}'
& '{python_exe}' -m uvicorn app.main:app --reload --host {BACKEND_HOST} --port {backend_port}
"""

    frontend_command = f"""
Set-Location -LiteralPath '{frontend_dir}'
$env:BACKEND_PROXY_HOST = '{BACKEND_PROXY_HOST}'
$env:BACKEND_PORT = '{backend_port}'
$env:FRONTEND_HOST = '{FRONTEND_HOST}'
$env:FRONTEND_PORT = '{frontend_port}'
$env:FRONTEND_HMR_HOST = '{FRONTEND_HMR_HOST}'
Write-Host '[frontend] starting on http://{FRONTEND_HOST}:{frontend_port}'
npm run dev
"""

    create_console_flag = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)

    backend_proc = subprocess.Popen(
        [ps_exe, "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", backend_command],
        creationflags=create_console_flag,
    )
    frontend_proc = subprocess.Popen(
        [ps_exe, "-NoExit", "-ExecutionPolicy", "Bypass", "-Command", frontend_command],
        creationflags=create_console_flag,
    )

    state = {
        "backend_pid": backend_proc.pid,
        "frontend_pid": frontend_proc.pid,
        "backend_url": f"http://{BACKEND_HOST}:{backend_port}",
        "frontend_url": f"http://{FRONTEND_HOST}:{frontend_port}",
        "local_frontend_url": f"http://127.0.0.1:{frontend_port}",
        "local_api_proxy": f"http://{BACKEND_PROXY_HOST}:{backend_port}/api",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Backend started (PID: {backend_proc.pid}) -> http://{BACKEND_HOST}:{backend_port}")
    print(f"Frontend started (PID: {frontend_proc.pid}) -> http://{FRONTEND_HOST}:{frontend_port}")
    print(f"Local frontend -> http://127.0.0.1:{frontend_port}")
    print(f"Local API proxy -> http://{BACKEND_PROXY_HOST}:{backend_port}/api")
    print(f"State saved to: {state_file}")


def main() -> int:
    repo_root = Path(__file__).resolve().parent

    if len(sys.argv) >= 2:
        mode = sys.argv[1].strip().lower()
        if mode in {"1", "start"}:
            start_servers(repo_root)
            return 0
        if mode in {"2", "stop"}:
            stop_servers(repo_root)
            return 0

    print("请选择操作:")
    print("  1. 启动前后端开发服务")
    print("  2. 停止前后端开发服务")
    choice = input("请输入序号 (1/2): ").strip()

    if choice == "1":
        start_servers(repo_root)
        return 0
    if choice == "2":
        stop_servers(repo_root)
        return 0

    print("无效输入，请输入 1 或 2。")
    return 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nCanceled.")
        raise SystemExit(130)
