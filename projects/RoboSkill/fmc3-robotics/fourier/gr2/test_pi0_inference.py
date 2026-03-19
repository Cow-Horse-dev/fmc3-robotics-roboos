#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 PI0 推理服务的脚本
直接通过 Unix Socket 发送命令
"""

import socket
import json
import sys
import argparse


def send_command(method: str, payload: dict = None, socket_path: str = "/tmp/gr2_pi0_inference_service.sock"):
    """发送命令到 PI0 推理服务

    Args:
        method: 命令方法 (health, status, start, stop)
        payload: 命令参数
        socket_path: Unix Socket 路径

    Returns:
        dict: 响应数据
    """
    try:
        # 连接到 Unix Socket
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.settimeout(10.0)
        sock.connect(socket_path)

        # 构造请求
        request = {
            "method": method,
            "payload": payload or {}
        }

        # 发送请求
        sock.sendall((json.dumps(request) + "\n").encode("utf-8"))
        sock.shutdown(socket.SHUT_WR)

        # 接收响应
        response = b""
        while True:
            data = sock.recv(65536)
            if not data:
                break
            response += data

        sock.close()

        # 解析响应
        result = json.loads(response.decode("utf-8"))
        return result

    except FileNotFoundError:
        return {
            "code": 500,
            "data": {
                "ok": False,
                "message": f"Socket not found: {socket_path}. Is the service running?"
            }
        }
    except ConnectionRefusedError:
        return {
            "code": 500,
            "data": {
                "ok": False,
                "message": "Connection refused. Is the service running?"
            }
        }
    except Exception as e:
        return {
            "code": 500,
            "data": {
                "ok": False,
                "message": f"Error: {str(e)}"
            }
        }


def main():
    parser = argparse.ArgumentParser(description="Test PI0 inference service")
    parser.add_argument(
        "command",
        choices=["health", "status", "start", "stop"],
        help="Command to send"
    )
    parser.add_argument(
        "--task",
        type=str,
        default="pick bottle and place into box",
        help="Task description (for start command)"
    )
    parser.add_argument(
        "--max-steps",
        type=int,
        default=0,
        help="Maximum steps (0 = run until completion)"
    )
    parser.add_argument(
        "--fps",
        type=float,
        default=30.0,
        help="Control frequency"
    )
    parser.add_argument(
        "--fsm-state",
        type=int,
        default=11,
        help="FSM state (11 = UpperBodyCmd)"
    )
    parser.add_argument(
        "--socket",
        type=str,
        default="/tmp/gr2_pi0_inference_service.sock",
        help="Unix socket path"
    )

    args = parser.parse_args()

    # 构造 payload
    payload = None
    if args.command == "start":
        payload = {
            "task": args.task,
            "max_steps": args.max_steps,
            "fps": args.fps,
            "fsm_state": args.fsm_state
        }
    elif args.command == "stop":
        payload = {"timeout_s": 5.0}

    # 发送命令
    print(f"📤 Sending command: {args.command}")
    if payload:
        print(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print()

    result = send_command(args.command, payload, args.socket)

    # 打印结果
    print(f"📥 Response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    # 返回状态码
    code = result.get("code", 500)
    data = result.get("data", {})
    ok = data.get("ok", False)

    if code == 200 and ok:
        print("\n✅ Success!")
        return 0
    else:
        print("\n❌ Failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
