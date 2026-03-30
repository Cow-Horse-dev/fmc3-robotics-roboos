#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fourier GR2 green-yellow bottle sorting skill server for RoboOS.

Exposes MCP tools for moving a black-capped bottle between the green and
yellow areas. Internally forwards requests to the dual PI0 RGB wrist
inference server over a Unix socket.
"""

import asyncio
import json
import os
import shlex
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


DEFAULT_UNIX_SOCKET_PATH = "/tmp/gr2_dual_pi0_rgb_wrist.sock"
DEFAULT_DUAL_PI0_CONDA_ENV = os.getenv("FOURIER_GR2_DUAL_PI0_CONDA_ENV", "lerobot-pi0")
DEFAULT_DUAL_PI0_SERVICE_SCRIPT_CANDIDATES = (
    os.getenv("FOURIER_GR2_DUAL_PI0_SERVICE_SCRIPT", "").strip(),
    "/home/phl/workspace/lerobot-versions/fmc3-lerobot/scripts/inference/gr2_dual_pi0_rgb_wrist_inference_server.py",
)


def _resolve_server_host_port() -> tuple[str, int]:
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
DEFAULT_TIMEOUT_S = float(os.getenv("FOURIER_GR2_SOCKET_TIMEOUT_S", "30.0"))


def _resolve_dual_pi0_script() -> str:
    for candidate in DEFAULT_DUAL_PI0_SERVICE_SCRIPT_CANDIDATES:
        if not candidate:
            continue
        resolved = Path(candidate).expanduser()
        if resolved.exists():
            return str(resolved)
    fallback = next(
        (c for c in DEFAULT_DUAL_PI0_SERVICE_SCRIPT_CANDIDATES if c), ""
    )
    return str(Path(fallback).expanduser()) if fallback else ""


DUAL_PI0_SERVICE_SCRIPT = _resolve_dual_pi0_script()
DUAL_PI0_SERVICE_WORKDIR = (
    str(Path(DUAL_PI0_SERVICE_SCRIPT).resolve().parents[2])
    if DUAL_PI0_SERVICE_SCRIPT and Path(DUAL_PI0_SERVICE_SCRIPT).expanduser().exists()
    else None
)
DUAL_PI0_UNIX_SOCKET_PATH = str(
    Path(
        os.getenv(
            "FOURIER_GR2_DUAL_PI0_SOCKET",
            os.getenv("UNIX_SOCKET_PATH", DEFAULT_UNIX_SOCKET_PATH),
        )
    ).expanduser()
)
DUAL_PI0_EXTRA_ARGS = shlex.split(os.getenv("FOURIER_GR2_DUAL_PI0_EXTRA_ARGS", ""))
_service_proc: subprocess.Popen | None = None
_service_lock = asyncio.Lock()

mcp = FastMCP("fourier_gr2_green_yellow", stateless_http=True, host=SERVER_HOST, port=SERVER_PORT)


def _unix_socket_request(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    socket_path: str = DUAL_PI0_UNIX_SOCKET_PATH,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    request = {"method": method, "payload": payload or {}}
    resolved_socket_path = str(Path(socket_path).expanduser())

    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout_s)
        sock.connect(resolved_socket_path)
        sock.sendall((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        chunks: list[bytes] = []
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            chunks.append(chunk)

    if not chunks:
        raise RuntimeError("server returned an empty response")

    raw = b"".join(chunks).decode("utf-8").strip()
    response = json.loads(raw)
    if not isinstance(response, dict) or "code" not in response or "data" not in response:
        raise RuntimeError(f"unexpected response payload: {response}")

    code = int(response["code"])
    data = response["data"]
    if not isinstance(data, dict):
        data = {"ok": code < 400, "message": str(data)}

    data.setdefault("code", code)
    data.setdefault("socket_path", resolved_socket_path)
    data.setdefault("ok", code < 400)
    return data


def _is_proc_running(proc: subprocess.Popen | None) -> bool:
    return proc is not None and proc.poll() is None


def _wait_service_health(
    socket_path: str,
    *,
    timeout_s: float = 90.0,
    poll_interval_s: float = 1.0,
) -> dict[str, Any]:
    deadline = time.time() + max(1.0, timeout_s)
    last: dict[str, Any] = {"ok": False, "message": "dual PI0 service not ready"}

    while time.time() < deadline:
        try:
            health = _unix_socket_request(
                "health",
                payload=None,
                socket_path=socket_path,
                timeout_s=min(DEFAULT_TIMEOUT_S, 5.0),
            )
            if bool(health.get("ok")):
                return health
            last = health
        except Exception as exc:
            last = {
                "ok": False,
                "message": f"health probe failed: {exc}",
                "socket_path": str(Path(socket_path).expanduser()),
            }
        time.sleep(max(0.1, poll_interval_s))

    raise RuntimeError(f"dual PI0 service health check timeout: {last}")


def _start_dual_pi0_service(
    socket_path: str = DUAL_PI0_UNIX_SOCKET_PATH,
) -> tuple[subprocess.Popen, list[str]]:
    script_path = Path(DUAL_PI0_SERVICE_SCRIPT).expanduser()
    if not script_path.exists():
        raise FileNotFoundError(f"dual PI0 service script not found: {script_path}")

    cmd = [
        "conda",
        "run",
        "--no-capture-output",
        "-n",
        DEFAULT_DUAL_PI0_CONDA_ENV,
        "python",
        str(script_path),
        "--unix-socket-path",
        str(Path(socket_path).expanduser()),
        "--no-gui",
    ]
    if DUAL_PI0_EXTRA_ARGS:
        cmd.extend(DUAL_PI0_EXTRA_ARGS)

    env = os.environ.copy()
    env.setdefault("HF_HUB_OFFLINE", "1")
    env.setdefault("TRANSFORMERS_OFFLINE", "1")
    env.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")

    proc = subprocess.Popen(
        cmd,
        cwd=DUAL_PI0_SERVICE_WORKDIR or None,
        env=env,
    )
    return proc, cmd


def _terminate_proc(proc: subprocess.Popen | None, timeout_s: float = 8.0) -> None:
    if proc is None or proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=max(0.1, timeout_s))
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=3.0)


async def _ensure_dual_pi0_service_ready() -> dict[str, Any]:
    global _service_proc

    try:
        health = await asyncio.to_thread(
            _unix_socket_request,
            "health",
            None,
            socket_path=DUAL_PI0_UNIX_SOCKET_PATH,
            timeout_s=min(DEFAULT_TIMEOUT_S, 5.0),
        )
        if bool(health.get("ok")):
            return {
                "ok": True,
                "message": "dual PI0 service is ready",
                "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
                "health": health,
                "started_by_skill": False,
            }
    except Exception:
        pass

    async with _service_lock:
        try:
            health = await asyncio.to_thread(
                _unix_socket_request,
                "health",
                None,
                socket_path=DUAL_PI0_UNIX_SOCKET_PATH,
                timeout_s=min(DEFAULT_TIMEOUT_S, 5.0),
            )
            if bool(health.get("ok")):
                return {
                    "ok": True,
                    "message": "dual PI0 service is ready",
                    "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
                    "health": health,
                    "started_by_skill": False,
                }
        except Exception:
            health = None

        if _service_proc is not None and _service_proc.poll() is not None:
            _service_proc = None

        if _is_proc_running(_service_proc):
            return {
                "ok": False,
                "message": "dual PI0 process exists but service is still unavailable",
                "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
                "health": health,
                "started_by_skill": False,
            }

        try:
            proc, cmd = await asyncio.to_thread(_start_dual_pi0_service, DUAL_PI0_UNIX_SOCKET_PATH)
        except Exception as exc:
            return {
                "ok": False,
                "message": f"failed to start dual PI0 service: {exc}",
                "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
                "service_script": DUAL_PI0_SERVICE_SCRIPT,
            }

        _service_proc = proc

    try:
        health = await asyncio.to_thread(
            _wait_service_health,
            DUAL_PI0_UNIX_SOCKET_PATH,
            timeout_s=90.0,
            poll_interval_s=1.0,
        )
        return {
            "ok": True,
            "message": "dual PI0 service started successfully",
            "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
            "service_script": DUAL_PI0_SERVICE_SCRIPT,
            "pid": proc.pid,
            "command": cmd,
            "health": health,
            "started_by_skill": True,
        }
    except Exception as exc:
        await asyncio.to_thread(_terminate_proc, proc, 3.0)
        async with _service_lock:
            if _service_proc is proc:
                _service_proc = None
        return {
            "ok": False,
            "message": f"dual PI0 service started but never became healthy: {exc}",
            "socket_path": DUAL_PI0_UNIX_SOCKET_PATH,
            "service_script": DUAL_PI0_SERVICE_SCRIPT,
        }


def _build_start_payload(
    *,
    max_steps: int | None = None,
    fps: float | None = None,
    fsm_state: int | None = None,
    stop_timeout_s: float | None = None,
    restart: bool = False,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"restart": restart}
    if max_steps is not None:
        payload["max_steps"] = int(max_steps)
    if fps is not None:
        payload["fps"] = float(fps)
    if fsm_state is not None:
        payload["fsm_state"] = int(fsm_state)
    if stop_timeout_s is not None:
        payload["stop_timeout_s"] = float(stop_timeout_s)
    return payload


def _error_response(
    method: str,
    message: str,
    *,
    code: int = 500,
    socket_path: str = DUAL_PI0_UNIX_SOCKET_PATH,
) -> dict[str, Any]:
    return {
        "ok": False,
        "code": int(code),
        "message": message,
        "method": method,
        "socket_path": str(Path(socket_path).expanduser()),
    }


async def _forward_to_dual_pi0(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    ensure_service: bool = False,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    boot = None
    if ensure_service:
        boot = await _ensure_dual_pi0_service_ready()
        if not bool(boot.get("ok")):
            return {
                **_error_response(method, str(boot.get("message", "service unavailable"))),
                "boot": boot,
            }

    try:
        response = await asyncio.to_thread(
            _unix_socket_request,
            method,
            payload,
            socket_path=DUAL_PI0_UNIX_SOCKET_PATH,
            timeout_s=timeout_s,
        )
    except Exception as exc:
        return {
            **_error_response(method, f"socket request failed: {exc}"),
            **({"boot": boot} if boot is not None else {}),
        }

    response.setdefault("method", method)
    if boot is not None:
        response.setdefault("boot", boot)
    return response


@mcp.tool()
async def move_bottle_green_to_yellow(
    max_steps: int = -1,
    fps: float = -1.0,
    fsm_state: int = -1,
    stop_timeout_s: float = -1.0,
    restart: bool = False,
) -> dict:
    """Move the black-capped bottle from the green area to the yellow area.
    把黑盖瓶子从绿色区域移动到黄色区域。绿到黄。从绿区拿到黄区。
    Internally forwards to the dual PI0 RGB wrist inference server.
    """
    print("[GreenYellow] Forwarding move_bottle_green_to_yellow to dual PI0 server...", flush=True)
    payload = _build_start_payload(
        max_steps=None if max_steps < 0 else max_steps,
        fps=None if fps < 0 else fps,
        fsm_state=None if fsm_state < 0 else fsm_state,
        stop_timeout_s=None if stop_timeout_s < 0 else stop_timeout_s,
        restart=restart,
    )
    response = await _forward_to_dual_pi0(
        "start_green_to_yellow",
        payload,
        ensure_service=True,
        timeout_s=max(DEFAULT_TIMEOUT_S, 60.0),
    )
    response.setdefault("tool", "move_bottle_green_to_yellow")
    return response


@mcp.tool()
async def move_bottle_yellow_to_green(
    max_steps: int = -1,
    fps: float = -1.0,
    fsm_state: int = -1,
    stop_timeout_s: float = -1.0,
    restart: bool = False,
) -> dict:
    """Move the black-capped bottle from the yellow area to the green area.
    把黑盖瓶子从黄色区域移动到绿色区域。黄到绿。从黄区拿到绿区。
    Internally forwards to the dual PI0 RGB wrist inference server.
    """
    print("[GreenYellow] Forwarding move_bottle_yellow_to_green to dual PI0 server...", flush=True)
    payload = _build_start_payload(
        max_steps=None if max_steps < 0 else max_steps,
        fps=None if fps < 0 else fps,
        fsm_state=None if fsm_state < 0 else fsm_state,
        stop_timeout_s=None if stop_timeout_s < 0 else stop_timeout_s,
        restart=restart,
    )
    response = await _forward_to_dual_pi0(
        "start_yellow_to_green",
        payload,
        ensure_service=True,
        timeout_s=max(DEFAULT_TIMEOUT_S, 60.0),
    )
    response.setdefault("tool", "move_bottle_yellow_to_green")
    return response


@mcp.tool()
async def stop_task(wait_timeout_s: float = 5.0, timeout_s: float = 30.0) -> dict:
    """Stop the current running task on the dual PI0 inference server."""
    return await _forward_to_dual_pi0(
        "stop",
        {"timeout_s": float(wait_timeout_s)},
        timeout_s=timeout_s,
    )


@mcp.tool()
async def get_task_status(timeout_s: float = 10.0) -> dict:
    """Get the current task status from the dual PI0 inference server."""
    return await _forward_to_dual_pi0("status", timeout_s=timeout_s)


@mcp.tool()
async def check_service_health(timeout_s: float = 10.0) -> dict:
    """Check whether the dual PI0 RGB wrist inference server is healthy."""
    return await _forward_to_dual_pi0("health", timeout_s=timeout_s)


if __name__ == "__main__":
    print(f"Starting Fourier GR2 green-yellow skill server on {SERVER_HOST}:{SERVER_PORT}...")
    print(f"Forwarding dual PI0 requests to socket: {DUAL_PI0_UNIX_SOCKET_PATH}")
    if DUAL_PI0_SERVICE_SCRIPT:
        print(f"Auto-start dual PI0 backend script: {DUAL_PI0_SERVICE_SCRIPT}")
    mcp.run(transport="streamable-http")
