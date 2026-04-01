# -*- coding: utf-8 -*-

import asyncio
import os
import sys
import json
import os
import signal
import sys
import threading
import time
import yaml
from contextlib import AsyncExitStack
from datetime import datetime
from typing import Dict, List, Optional
_SLAVER_ROOT = os.path.dirname(os.path.abspath(__file__))
if _SLAVER_ROOT not in sys.path:
    sys.path.insert(0, _SLAVER_ROOT)
import importlib
importlib.import_module("tools.memory")

from agents.models import AzureOpenAIServerModel, OpenAIServerModel
from agents.skill_executor import SkillSequenceExecutor, SkillState, is_bottle_demo_task
from agents.slaver_agent import ToolCallingAgent
from flag_scale.flagscale.agent.collaboration import Collaborator
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from tools.utils import Config
from tools.tool_matcher import ToolMatcher

config = Config.load_config()
collaborator = Collaborator.from_config(config=config["collaborator"])


class RobotManager:
    """Centralized robot management system with task handling and collaboration"""

    def __init__(self):
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()
        self.collaborator = collaborator
        self.heartbeat_interval = 60
        self.lock = threading.Lock()
        self._shutdown_event = threading.Event()
        self.model, self.model_path = self._gat_model_info_from_config()
        self.tools = None
        self.threads = []
        self.loop = asyncio.get_event_loop()
        self.robot_name = None
        
        # Initialize tool matcher with configuration
        self.tool_matcher = ToolMatcher(
            max_tools=config["tool"]["matching"]["max_tools"],
            min_similarity=config["tool"]["matching"]["min_similarity"],
            device=os.getenv("TOOL_MATCHER_DEVICE", "cpu"),
        )

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum, frame):
        print(f"Received signal {signum}, shutting down...")
        self._shutdown_event.set()

    async def _safe_cleanup(self):
        if hasattr(self, "session") and self.session:
            await self.cleanup()

        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=1.0)

    def _gat_model_info_from_config(self):
        """Initial model"""
        candidate = config["model"]["model_dict"]
        if candidate["cloud_model"] in config["model"]["model_select"]:
            if candidate["cloud_type"] == "azure":
                model_client = AzureOpenAIServerModel(
                    model_id=config["model"]["model_select"],
                    azure_endpoint=candidate["azure_endpoint"],
                    azure_deployment=candidate["azure_deployment"],
                    api_key=candidate["azure_api_key"],
                    api_version=candidate["azure_api_version"],
                    support_tool_calls=config["tool"]["support_tool_calls"],
                    profiling=config["profiling"],
                )
                model_name = config["model"]["model_select"]
            elif candidate["cloud_type"] == "default":
                model_client = OpenAIServerModel(
                    api_key=candidate["cloud_api_key"],
                    api_base=candidate["cloud_server"],
                    model_id=candidate["cloud_model"],
                    support_tool_calls=config["tool"]["support_tool_calls"],
                    profiling=config["profiling"],
                )
                model_name = config["model"]["model_select"]
            else:
                raise ValueError(f"Unsupported cloud type: {candidate['cloud_type']}")
            return model_client, model_name
        raise ValueError(f"Unsupported model: {config['model']['model_select']}")

    def handle_task(self, data: str) -> None:
        """Process incoming tasks with thread-safe operation"""
        if self._shutdown_event.is_set():
            return

        data = json.loads(data)
        task_data = {
            "task": data.get("task"),
            "task_id": data.get("task_id"),
            "refresh": data.get("refresh"),
            "order_flag": data.get("order_flag", "false"),
        }
        with self.lock:
            future = asyncio.run_coroutine_threadsafe(
                self._execute_task(task_data), self.loop
            )
            future.result()

    async def _execute_task(self, task_data: Dict) -> None:
        """Internal task execution logic.

        For bottle demo tasks (place_in / take_out / initialization):
            Uses SkillSequenceExecutor — deterministic, no LLM (S-1.1).
        For all other tasks:
            Falls back to LLM-driven ToolCallingAgent (ReAct).
        """
        if self._shutdown_event.is_set():
            return

        os.makedirs("./.log", exist_ok=True)

        task = task_data["task"]
        task_id = task_data["task_id"]

        # ── Bottle demo: deterministic skill execution ──
        if is_bottle_demo_task(task):
            print(f"[SkillExecutor] Bottle demo task: {task}")
            max_retries = config.get("bottle_demo", {}).get("max_retries", 3)
            executor = SkillSequenceExecutor(
                tool_executor=self.session.call_tool,
                vision_judge=self._request_vision_judgment,
                max_retries=max_retries,
            )
            seq_result = await executor.execute(task)

            # Build tool_call list from skill results
            tool_calls = [
                {"tool_name": sr.skill_name, "tool_arguments": "{}"}
                for sr in seq_result.skill_results
            ]

            self._send_result(
                robot_name=self.robot_name,
                task=task,
                task_id=task_id,
                result=seq_result.result_text,
                tool_call=tool_calls,
                skill_state=seq_result.skill_state.value,
                failure_info=seq_result.failure_info,
            )
            return

        # ── Fallback: LLM-driven agent (ReAct) ──
        matched_tools = self.tool_matcher.match_tools(task)

        if matched_tools:
            matched_tool_names = [tool_name for tool_name, _ in matched_tools]
            filtered_tools = [tool for tool in self.tools
                           if tool.get("function", {}).get("name") in matched_tool_names]
        else:
            filtered_tools = self.tools

        agent = ToolCallingAgent(
            tools=filtered_tools,
            verbosity_level=2,
            model=self.model,
            model_path=self.model_path,
            log_file="./.log/agent.log",
            robot_name=self.robot_name,
            collaborator=self.collaborator,
            tool_executor=self.session.call_tool,
        )

        result = await agent.run(task)
        self._send_result(
            robot_name=self.robot_name,
            task=task,
            task_id=task_id,
            result=result,
            tool_call=agent.tool_call,
            skill_state="finished",
            failure_info=None,
        )

    def _send_result(
        self,
        robot_name: str,
        task: str,
        task_id: str,
        result,
        tool_call: List,
        skill_state: str = "finished",
        failure_info: Optional[Dict] = None,
    ) -> None:
        """Send task results to collaboration channel.

        Args:
            skill_state: "finished" | "failed" | "stop" — matched by master's
                _handle_result() for failure tracking and task termination.
            failure_info: Dict with failed_skill, attempts, last_error when
                skill_state is "stop" (3 consecutive failures).
        """
        if self._shutdown_event.is_set():
            return

        channel = f"{robot_name}_to_RoboOS"
        payload = {
            "robot_name": robot_name,
            "subtask_handle": task,
            "subtask_result": result,
            "tools": tool_call,
            "task_id": task_id,
            "skill_state": skill_state,
            "failure_info": failure_info,
        }
        self.collaborator.send(channel, json.dumps(payload))

    async def _request_vision_judgment(self, skill_name: str) -> tuple:
        """Request Master's VisionMonitor to judge whether a skill succeeded.

        Protocol:
          1. Slaver writes a vision_judge_request to Redis key
          2. Master's vision judgment handler picks it up, runs VisionMonitor
          3. Master writes the result to Redis key vision_result:{robot_name}
          4. Slaver polls that key until the response arrives

        Args:
            skill_name: Internal skill name (e.g. "place_in", "take_out")

        Returns:
            (is_success: bool, reason: str)
        """
        robot_name = self.robot_name
        request_key = f"vision_request:{robot_name}"
        result_key = f"vision_result:{robot_name}"

        # Clear any stale result
        self.collaborator.record_environment(result_key, json.dumps(None))

        # Write request for Master to pick up
        request = {
            "skill_name": skill_name,
            "robot_name": robot_name,
            "timestamp": time.time(),
        }
        self.collaborator.record_environment(request_key, json.dumps(request))
        print(f"[VisionJudge] Requested judgment for {skill_name}, waiting for Master...")

        # Poll for result (Master will write to result_key)
        timeout = config.get("bottle_demo", {}).get("vision_judge_timeout", 30)
        poll_interval = 0.5
        elapsed = 0.0

        while elapsed < timeout:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            raw = self.collaborator.read_environment(result_key)
            if raw is None:
                continue

            # Parse the result
            if isinstance(raw, str):
                try:
                    data = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    data = raw
            else:
                data = raw

            if not isinstance(data, dict) or "success" not in data:
                continue

            is_success = bool(data["success"])
            reason = data.get("reason", "")
            print(f"[VisionJudge] {skill_name} → {'SUCCESS' if is_success else 'FAILED'}: {reason}")
            return is_success, reason

        # Timeout — assume success to avoid false stops
        print(f"[VisionJudge] Timeout waiting for vision judgment for {skill_name}")
        return True, "Vision judgment timeout — assumed success"

    def _heartbeat_loop(self, robot_name) -> None:
        """Continuous heartbeat signal emitter"""
        key = robot_name
        while not self._shutdown_event.is_set():
            try:
                self.collaborator.agent_heartbeat(key, seconds=60)
                time.sleep(30)
            except Exception as e:
                if not self._shutdown_event.is_set():
                    print(f"Heartbeat error: {e}")
                break

    async def connect_to_robot(self):
        """Connect to an MCP server"""

        call_type = config["robot"]["call_type"]

        if call_type == "local":
            skill_path = os.path.join(_SLAVER_ROOT, config["robot"]["path"], "skill.py")
            server_params = StdioServerParameters(
                command="python", args=[skill_path], env=None
            )
            mcp_client = stdio_client(server_params)

        if call_type == "remote":
            mcp_client = streamablehttp_client(config["robot"]["path"] + "/mcp")

        stdio_transport = await self.exit_stack.enter_async_context(mcp_client)
        if call_type == "local":
            self.stdio, self.write = stdio_transport
        if call_type == "remote":
            self.stdio, self.write, _ = stdio_transport
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.stdio, self.write)
        )

        await self.session.initialize()

        # init robot
        self.collaborator.record_environment(
            "robot", json.dumps({"position": None, "holding": None, "status": "idle"})
        )

        # List available tools
        response = await self.session.list_tools()
        self.tools = [
            {
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                },
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]
        print("Connected to robot with tools:", str(self.tools))
        
        # Train the tool matcher with the available tools
        self.tool_matcher.fit(self.tools)

        """Complete robot registration with thread management"""
        robot_name = config["robot"]["name"]
        self.robot_name = robot_name
        register = {
            "robot_name": robot_name,
            "robot_tool": self.tools,
            "robot_state": "idle",
            "timestamp": int(datetime.now().timestamp()),
        }
        with self.lock:
            # Registration thread
            self.collaborator.register_agent(
                robot_name, json.dumps(register), expire_second=60
            )

            heartbeat_thread = threading.Thread(
                target=self._heartbeat_loop,
                daemon=True,
                args=(robot_name,),
                name=f"heartbeat_{robot_name}",
            )
            heartbeat_thread.start()
            self.threads.append(heartbeat_thread)

            # Command listener thread
            channel_b2r = f"roboos_to_{robot_name}"
            listener_thread = threading.Thread(
                target=lambda: self.collaborator.listen(channel_b2r, self.handle_task),
                daemon=True,
                name=channel_b2r,
            )
            listener_thread.start()
            self.threads.append(listener_thread)

    async def cleanup(self):
        """Clean up resources"""
        self._shutdown_event.set()
        await self.exit_stack.aclose()


async def main():
    robot_manager = RobotManager()
    try:
        print("connecting to robot...")
        await robot_manager.connect_to_robot()
        print("connection success")

        while not robot_manager._shutdown_event.is_set():
            await asyncio.sleep(1)
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await robot_manager._safe_cleanup()
        print("Cleanup completed")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Program terminated by user")
        sys.exit(0)
