#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fourier GR2 mock skill server for RoboOS.

This server keeps the legacy RoboOS tool names, but internally forwards
requests to the dual PI0 RGB wrist inference server over a Unix socket.
"""

import asyncio
import json
import os
import socket
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP


DEFAULT_UNIX_SOCKET_PATH = "/tmp/gr2_dual_pi0_rgb_wrist.sock"


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
DUAL_PI0_UNIX_SOCKET_PATH = str(
    Path(
        os.getenv(
            "FOURIER_GR2_DUAL_PI0_SOCKET",
            os.getenv("UNIX_SOCKET_PATH", DEFAULT_UNIX_SOCKET_PATH),
        )
    ).expanduser()
)

# FastMCP server
mcp = FastMCP("fourier_gr2", stateless_http=True, host=SERVER_HOST, port=SERVER_PORT)


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


async def _request_safe(
    method: str,
    payload: dict[str, Any] | None = None,
    *,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> dict[str, Any]:
    try:
        return await asyncio.to_thread(
            _unix_socket_request,
            method,
            payload,
            socket_path=DUAL_PI0_UNIX_SOCKET_PATH,
            timeout_s=timeout_s,
        )
    except Exception as exc:
        return _error_response(method, f"socket request failed: {exc}")


@mcp.tool()
async def take_bottle_out_of_box(
    max_steps: int = -1,
    fps: float = -1.0,
    fsm_state: int = -1,
    stop_timeout_s: float = -1.0,
    restart: bool = False,
) -> dict:
    """Take a bottle out of the large box and hold it.
    从大盒子里拿出一个瓶子并抓握。拿出来。取出来。拿出瓶子。
    Internally forwards to the dual PI0 RGB wrist inference server.
    """
    print("[MOCK->PI0] Forwarding take_bottle_out_of_box to dual PI0 server...", flush=True)
    payload = _build_start_payload(
        max_steps=None if max_steps < 0 else max_steps,
        fps=None if fps < 0 else fps,
        fsm_state=None if fsm_state < 0 else fsm_state,
        stop_timeout_s=None if stop_timeout_s < 0 else stop_timeout_s,
        restart=restart,
    )
    response = await _request_safe("start_take_out", payload)
    response.setdefault("tool", "take_bottle_out_of_box")
    return response


@mcp.tool()
async def put_bottle_into_box(
    max_steps: int = -1,
    fps: float = -1.0,
    fsm_state: int = -1,
    stop_timeout_s: float = -1.0,
    restart: bool = False,
) -> dict:
    """Put the bottle currently held by the robot into the large box.
    把瓶子放入大盒子。放进去。放进盒子。放回盒子。
    Internally forwards to the dual PI0 RGB wrist inference server.
    """
    print("[MOCK->PI0] Forwarding put_bottle_into_box to dual PI0 server...", flush=True)
    payload = _build_start_payload(
        max_steps=None if max_steps < 0 else max_steps,
        fps=None if fps < 0 else fps,
        fsm_state=None if fsm_state < 0 else fsm_state,
        stop_timeout_s=None if stop_timeout_s < 0 else stop_timeout_s,
        restart=restart,
    )
    response = await _request_safe("start_put_in", payload)
    response.setdefault("tool", "put_bottle_into_box")
    return response


@mcp.tool()
async def get_task_status(timeout_s: float = 10.0) -> dict:
    """Get the current task status from the dual PI0 RGB wrist server."""
    return await _request_safe("status", timeout_s=timeout_s)


@mcp.tool()
async def check_service_health(timeout_s: float = 10.0) -> dict:
    """Check whether the dual PI0 RGB wrist inference server is healthy."""
    return await _request_safe("health", timeout_s=timeout_s)


@mcp.tool()
async def stop_task(wait_timeout_s: float = 5.0, timeout_s: float = 30.0) -> dict:
    """Stop the current task on the dual PI0 RGB wrist inference server."""
    return await _request_safe(
        "stop",
        {"timeout_s": float(wait_timeout_s)},
        timeout_s=timeout_s,
    )


if __name__ == "__main__":
    print(f"Starting Fourier GR2 mock skill server on {SERVER_HOST}:{SERVER_PORT}...")
    print(f"Forwarding dual PI0 requests to socket: {DUAL_PI0_UNIX_SOCKET_PATH}")
    mcp.run(transport="streamable-http")
