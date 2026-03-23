#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fourier GR2 PI0 Inference Skill
专门用于触发 PI0 推理任务的 MCP 技能服务
"""

import asyncio
import json
import os
import socket
import subprocess
import time
from pathlib import Path
from mcp.server.fastmcp import FastMCP


# ============ 服务器配置 ============

def _resolve_server_host_port() -> tuple[str, int]:
    """解析服务器地址和端口"""
    host = os.getenv("FOURIER_GR2_HOST", "0.0.0.0").strip() or "0.0.0.0"
    raw_port = os.getenv("FOURIER_GR2_PORT", "").strip() or os.getenv("PORT", "").strip()
    if not raw_port:
        return host, 8000

    try:
        port = int(raw_port)
    except ValueError as exc:
        raise ValueError(f"Invalid server port value: {raw_port}") from exc
    if not (1 <= port <= 65535):
        raise ValueError(f"Server port out of range (1-65535): {port}")
    return host, port


SERVER_HOST, SERVER_PORT = _resolve_server_host_port()

# FastMCP 服务器
mcp = FastMCP("fourier_gr2_pi0", stateless_http=True, host=SERVER_HOST, port=SERVER_PORT)

# 全局锁
_lock = asyncio.Lock()

# PI0 服务配置
DEFAULT_PI0_TASK = "pick bottle and place into box"
DEFAULT_PI0_CHECKPOINT_PATH = (
    "/home/phl/workspace/lerobot-versions/lerobot/outputs/train/"
    "pi0_gr2_pick_3_4_20260304_172720/checkpoints/111000/pretrained_model"
)
DEFAULT_PI0_SERVICE_SCRIPT = (
    "/home/phl/workspace/lerobot-versions/lerobot/scripts/gr2_pi0_inference_service.py"
)
DEFAULT_PI0_SERVICE_WORKDIR = "/home/phl/workspace/lerobot-versions/lerobot"
DEFAULT_PI0_CONDA_ENV = "lerobot-pi0"
DEFAULT_PI0_SERVICE_UNIX_SOCKET = "/tmp/gr2_pi0_inference_service.sock"
DOMAIN_ID = 123
ROBOT_NAME = "gr2"

# 全局变量
_pi0_service_proc = None
_pi0_service_socket = DEFAULT_PI0_SERVICE_UNIX_SOCKET


# ============ Unix Socket 通信 ============

def _unix_socket_request(
    method: str,
    payload: dict | None = None,
    socket_path: str = DEFAULT_PI0_SERVICE_UNIX_SOCKET,
    timeout: float = 5.0,
) -> tuple[int, dict]:
    """通过 Unix Socket 发送请求到 PI0 推理服务

    Args:
        method: 方法名 (health, status, start, stop)
        payload: 请求参数
        socket_path: Unix Socket 路径
        timeout: 超时时间（秒）

    Returns:
        (status_code, response_data)
    """
    req = {"method": method, "payload": payload or {}}

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(socket_path)
        sock.sendall(json.dumps(req).encode("utf-8") + b"\n")
        sock.shutdown(socket.SHUT_WR)

        chunks = []
        while True:
            data = sock.recv(65536)
            if not data:
                break
            chunks.append(data)

    raw = b"".join(chunks).decode("utf-8").strip()
    parsed = json.loads(raw) if raw else {"ok": False, "message": "empty response"}
    code = int(parsed.get("code", 200))

    if isinstance(parsed.get("data"), dict):
        return code, parsed["data"]
    return code, parsed


def _is_proc_running(proc) -> bool:
    """检查进程是否在运行"""
    return proc is not None and proc.poll() is None


def _wait_service_health(timeout_s: float = 40.0, poll_interval_s: float = 0.5) -> dict:
    """等待服务健康检查通过"""
    deadline = time.time() + max(1.0, timeout_s)
    last = {"ok": False, "message": "service not ready"}

    while time.time() < deadline:
        try:
            code, resp = _unix_socket_request("health", payload=None, timeout=2.0)
            last = resp if isinstance(resp, dict) else {"ok": False, "message": str(resp)}
            if code == 200 and bool(last.get("ok")):
                return last
        except Exception as exc:
            last = {"ok": False, "message": str(exc)}
        time.sleep(max(0.05, poll_interval_s))

    raise RuntimeError(f"PI0 service health check timeout: {last}")


def _start_service_proc(
    *,
    socket_path: str,
    checkpoint_path: str,
    robot_name: str,
    domain_id: int,
) -> tuple:
    """启动 PI0 推理服务进程"""
    script_path = Path(DEFAULT_PI0_SERVICE_SCRIPT).expanduser().resolve()
    if not script_path.exists():
        raise FileNotFoundError(f"PI0 service script not found: {script_path}")

    cmd = [
        "conda",
        "run",
        "--no-capture-output",
        "-n",
        DEFAULT_PI0_CONDA_ENV,
        "python",
        str(script_path),
        "--unix-socket-path",
        str(socket_path),
        "--checkpoint-path",
        str(checkpoint_path),
        "--robot-name",
        str(robot_name),
        "--domain-id",
        str(int(domain_id)),
    ]
    env = os.environ.copy()
    # In offline/air-gapped deployments, avoid repeated HF online retries.
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    proc = subprocess.Popen(cmd, cwd=DEFAULT_PI0_SERVICE_WORKDIR, env=env)
    return proc, cmd


def _terminate_proc(proc, timeout_s: float = 8.0) -> None:
    """终止进程"""
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=max(0.1, timeout_s))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3.0)


async def _ensure_pi0_service_ready() -> dict:
    """确保 PI0 服务就绪，如果未运行则自动启动"""
    global _pi0_service_proc, _pi0_service_socket

    async with _lock:
        socket_path = _pi0_service_socket

    # 检查服务是否已运行
    try:
        code, health = await asyncio.to_thread(
            _unix_socket_request, "health", None, socket_path, 2.0
        )
        if code == 200 and isinstance(health, dict) and bool(health.get("ok")):
            return {
                "ok": True,
                "message": "PI0 service is ready",
                "service_socket": socket_path,
                "health": health,
                "started_by_skill": False,
            }
    except Exception:
        pass

    # 服务未运行，启动它
    print("[Skill][PI0] Service not running, starting it...")

    async with _lock:
        if _pi0_service_proc is not None and _pi0_service_proc.poll() is not None:
            _pi0_service_proc = None

        already_running = _is_proc_running(_pi0_service_proc)

    if already_running:
        return {
            "ok": False,
            "message": "Service process exists but not responding",
        }

    try:
        proc, cmd = await asyncio.to_thread(
            _start_service_proc,
            socket_path=socket_path,
            checkpoint_path=DEFAULT_PI0_CHECKPOINT_PATH,
            robot_name=ROBOT_NAME,
            domain_id=DOMAIN_ID,
        )
    except Exception as exc:
        return {"ok": False, "message": f"Failed to start service: {exc}"}

    async with _lock:
        _pi0_service_proc = proc
        _pi0_service_socket = socket_path

    try:
        health = await asyncio.to_thread(_wait_service_health, 45.0, 0.5)
        return {
            "ok": True,
            "message": "PI0 service started successfully",
            "service_socket": socket_path,
            "pid": proc.pid,
            "command": cmd,
            "health": health,
            "started_by_skill": True,
        }
    except Exception as exc:
        await asyncio.to_thread(_terminate_proc, proc, 3.0)
        async with _lock:
            if _pi0_service_proc is proc:
                _pi0_service_proc = None
        return {
            "ok": False,
            "message": f"Service started but not ready: {exc}",
        }


# ============ MCP 技能工具 ============

@mcp.tool()
async def execute_manipulation_task(task: str = DEFAULT_PI0_TASK) -> dict:
    """COMPLETE ATOMIC TASK: Pick bottle and place into box. This is a SINGLE COMPLETE manipulation task.

    ⚠️ IMPORTANT: This tool executes the ENTIRE task from start to finish in ONE CALL.
    DO NOT break this down into subtasks. DO NOT call multiple times.

    This tool handles COMPLETE manipulation tasks including:
    - "pick bottle and place into box" (COMPLETE TASK - do not decompose)
    - "pick bottle and place into basket" (COMPLETE TASK - do not decompose)
    - "pick up the apple" (COMPLETE TASK - do not decompose)
    - "grasp the cup and move it to the table" (COMPLETE TASK - do not decompose)

    The robot will autonomously:
    1. Locate the object
    2. Approach and grasp it
    3. Move to the target location
    4. Place the object

    All steps are handled internally by PI0 policy inference.

    Args:
        task: Complete task description (e.g., "pick bottle and place into box")

    Returns:
        dict: Execution status with 'ok', 'message', and task details
    """
    req_task = str(task or "").strip() or DEFAULT_PI0_TASK
    req_payload = {
        "task": req_task,
        "max_steps": 0,  # 0 表示运行直到完成
        "fps": 30.0,
        "fsm_state": 11,  # UpperBodyCmd 模式
    }

    print(f"[Skill][PI0] execute_manipulation_task called: '{req_task}'", flush=True)

    # 确保服务就绪
    boot = await _ensure_pi0_service_ready()
    if not bool(boot.get("ok")):
        return {
            "ok": False,
            "message": f"PI0 service is not ready: {boot.get('message', '')}",
            "boot": boot,
        }

    async with _lock:
        socket_path = _pi0_service_socket

    # 发送 start 命令
    try:
        code, resp = await asyncio.to_thread(
            _unix_socket_request, "start", req_payload, socket_path, 10.0
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to start inference: {exc}",
            "service_socket": socket_path,
            "boot": boot,
        }

    if not isinstance(resp, dict):
        resp = {"ok": False, "message": str(resp)}

    resp.setdefault("code", code)
    resp.setdefault("service_socket", socket_path)
    resp.setdefault("boot", boot)
    resp.setdefault("task", req_task)

    print(f"[Skill][PI0] Task '{req_task}' started successfully", flush=True)
    return resp


@mcp.tool()
async def take_bottle_out_of_box() -> dict:
    """Take a bottle out of the large box and hold it.

    中文别名：
    从盒子里拿出瓶子、把瓶子拿出来、取出瓶子、把瓶子拿出来拿给我。
    """
    return await execute_manipulation_task("take bottle out of the box")


@mcp.tool()
async def put_bottle_into_box() -> dict:
    """Put the bottle currently held by the robot back into the large box.

    中文别名：
    把瓶子放进盒子、把瓶子放回盒子、放进去、放入大盒子。
    """
    return await execute_manipulation_task("put bottle into the box")


@mcp.tool()
async def get_task_status() -> dict:
    """查询当前任务状态

    Returns:
        dict: 任务状态信息
            - ok: 是否成功获取状态
            - state: 当前状态 (idle, loading, running, stopping, error)
            - step: 当前步数
            - task: 任务描述
            - message: 状态消息
    """
    async with _lock:
        socket_path = _pi0_service_socket

    try:
        code, resp = await asyncio.to_thread(
            _unix_socket_request, "status", None, socket_path, 5.0
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to get status: {exc}",
            "service_socket": socket_path,
        }

    if not isinstance(resp, dict):
        resp = {"ok": False, "message": str(resp)}

    resp.setdefault("code", code)
    resp.setdefault("service_socket", socket_path)
    return resp


@mcp.tool()
async def stop_task(timeout_s: float = 5.0) -> dict:
    """停止当前正在执行的任务

    Args:
        timeout_s: 停止超时时间（秒）

    Returns:
        dict: 停止结果
            - ok: 是否成功停止
            - message: 结果消息
    """
    async with _lock:
        socket_path = _pi0_service_socket

    try:
        code, resp = await asyncio.to_thread(
            _unix_socket_request,
            "stop",
            {"timeout_s": float(timeout_s)},
            socket_path,
            max(2.0, float(timeout_s) + 2.0),
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Failed to stop task: {exc}",
            "service_socket": socket_path,
        }

    if not isinstance(resp, dict):
        resp = {"ok": False, "message": str(resp)}

    resp.setdefault("code", code)
    resp.setdefault("service_socket", socket_path)
    return resp


@mcp.tool()
async def check_service_health() -> dict:
    """检查 PI0 推理服务健康状态

    Returns:
        dict: 健康状态信息
            - ok: 服务是否健康
            - model_loaded: 模型是否已加载
            - state: 服务状态
            - message: 状态消息
    """
    async with _lock:
        socket_path = _pi0_service_socket

    try:
        code, resp = await asyncio.to_thread(
            _unix_socket_request, "health", None, socket_path, 3.0
        )
    except Exception as exc:
        return {
            "ok": False,
            "message": f"Service not reachable: {exc}",
            "service_socket": socket_path,
        }

    if not isinstance(resp, dict):
        resp = {"ok": False, "message": str(resp)}

    resp.setdefault("code", code)
    resp.setdefault("service_socket", socket_path)
    return resp


# ============ 主程序入口 ============

if __name__ == "__main__":
    print(f"🚀 Starting Fourier GR2 PI0 Skill Server on {SERVER_HOST}:{SERVER_PORT}...")
    print(f"📡 PI0 Service Socket: {DEFAULT_PI0_SERVICE_UNIX_SOCKET}")
    print(f"🤖 Robot: {ROBOT_NAME} (Domain ID: {DOMAIN_ID})")
    print(f"📦 Checkpoint: {DEFAULT_PI0_CHECKPOINT_PATH}")
    mcp.run(transport="streamable-http")
