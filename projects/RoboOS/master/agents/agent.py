import asyncio
import json
import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from typing import Any, Dict

import yaml
from agents.planner import GlobalTaskPlanner
from flag_scale.flagscale.agent.collaboration import Collaborator


class GlobalAgent:
    def __init__(self, config_path="config.yaml"):
        """Initialize GlobalAgent"""
        self._init_config(config_path)
        self._init_logger(self.config["logger"])
        self.collaborator = Collaborator.from_config(self.config["collaborator"])
        self.planner = GlobalTaskPlanner(self.config)

        self.logger.info(f"Configuration loaded from {config_path} ...")
        self.logger.info(f"Master Configuration:\n{self.config}")

        self._init_scene(self.config["profile"])
        self._start_listener()

    def _init_logger(self, logger_config):
        """Initialize an independent logger for GlobalAgent"""
        self.logger = logging.getLogger(logger_config["master_logger_name"])
        logger_file = logger_config["master_logger_file"]
        os.makedirs(os.path.dirname(logger_file), exist_ok=True)
        file_handler = logging.FileHandler(logger_file)

        # Set the logging level
        if logger_config["master_logger_level"] == "DEBUG":
            self.logger.setLevel(logging.DEBUG)
            file_handler.setLevel(logging.DEBUG)
        elif logger_config["master_logger_level"] == "INFO":
            self.logger.setLevel(logging.INFO)
            file_handler.setLevel(logging.INFO)
        elif logger_config["master_logger_level"] == "WARNING":
            self.logger.setLevel(logging.WARNING)
            file_handler.setLevel(logging.WARNING)
        elif logger_config["master_logger_level"] == "ERROR":
            self.logger.setLevel(logging.ERROR)
            file_handler.setLevel(logging.ERROR)

        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _init_config(self, config_path="config.yaml"):
        """Initialize configuration"""
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def _init_scene(self, scene_config):
        """Initialize scene object"""
        path = scene_config["path"]
        if not os.path.exists(path):
            self.logger.error(f"Scene config file {path} does not exist.")
            raise FileNotFoundError(f"Scene config file {path} not found.")
        with open(path, "r", encoding="utf-8") as f:
            self.scene = yaml.safe_load(f)

        scenes = self.scene.get("scene", [])
        for scene_info in scenes:
            scene_name = scene_info.pop("name", None)
            if scene_name:
                self.collaborator.record_environment(scene_name, json.dumps(scene_info))
            else:
                print("Warning: Missing 'name' in scene_info:", scene_info)

    def _handle_register(self, robot_name: Dict) -> None:
        """Listen for robot registrations."""
        robot_info = self.collaborator.read_agent_info(robot_name)
        self.logger.info(
            f"AGENT_REGISTRATION: {robot_name} \n {json.dumps(robot_info)}"
        )

        # Register functions for processing robot execution results in the brain
        channel_r2b = f"{robot_name}_to_RoboOS"
        threading.Thread(
            target=lambda: self.collaborator.listen(channel_r2b, self._handle_result),
            daemon=True,
            name=channel_r2b,
        ).start()

        self.logger.info(
            f"RoboOS has listened to [{robot_name}] by channel [{channel_r2b}]"
        )

    def _handle_result(self, data: str):
        data = json.loads(data)

        """Handle results from agents."""
        robot_name = data.get("robot_name")
        subtask_handle = data.get("subtask_handle")
        subtask_result = data.get("subtask_result")

        # TODO: Task result should be refered to the next step determination.
        if robot_name and subtask_handle and subtask_result:
            self.logger.info(
                f"================ Received result from {robot_name} ================"
            )
            self.logger.info(f"Subtask: {subtask_handle}\nResult: {subtask_result}")
            self.logger.info(
                "===================================================================="
            )
            self.collaborator.update_agent_busy(robot_name, False)

        else:
            self.logger.warning("[WARNING] Received incomplete result data")
            self.logger.info(
                f"================ Received result from {robot_name} ================"
            )
            self.logger.info(f"Subtask: {subtask_handle}\nResult: {subtask_result}")
            self.logger.info(
                "===================================================================="
            )

    def _extract_json(self, input_string):
        """Extract JSON from a string."""
        try:
            # Try to find markdown code block first
            start_marker = "```json"
            end_marker = "```"
            start_idx = input_string.find(start_marker)
            if start_idx != -1:
                end_idx = input_string.find(end_marker, start_idx + len(start_marker))
                if end_idx != -1:
                    json_str = input_string[start_idx + len(start_marker) : end_idx].strip()
                    return json.loads(json_str)

            # Fallback: try to find JSON object directly
            start_idx = input_string.find("{")
            end_idx = input_string.rfind("}")
            if start_idx != -1 and end_idx != -1:
                json_str = input_string[start_idx : end_idx + 1]
                return json.loads(json_str)

            self.logger.warning("[WARNING] JSON markers/object not found in the string.")
            return None
        except json.JSONDecodeError as e:
            self.logger.warning(
                f"[WARNING] JSON cannot be extracted from the string.\n{e}"
            )
            return None

    def _group_tasks_by_order(self, tasks):
        """Group tasks by topological order."""
        grouped = defaultdict(list)
        for task in tasks:
            grouped[int(task.get("subtask_order", 0))].append(task)
        return dict(sorted(grouped.items()))

    @staticmethod
    def _normalize_task_text(task: str) -> str:
        if not isinstance(task, str):
            return ""
        return " ".join(task.strip().lower().split())

    def _is_pick_bottle_atomic_task(self, task: str) -> bool:
        text = self._normalize_task_text(task)
        if not text:
            return False

        fixed_aliases = {
            "pick bottle and place into box",
            "pick bottle and place it into box",
            "pick bottle and place in box",
            "pick_bottle_and_place_into_box",
            "抓瓶子放进箱子",
            "抓瓶子放到箱子",
        }
        if text in fixed_aliases:
            return True

        return (
            ("pick" in text or "grab" in text)
            and "bottle" in text
            and ("place" in text or "put" in text)
            and "box" in text
        )

    def _is_atomic_manipulation_task(self, task: str) -> bool:
        """Conservative heuristic for single-object pick-and-place intents."""
        text = self._normalize_task_text(task)
        if not text:
            return False

        if "execute_manipulation_task" in text:
            return True

        semantic_text = text.replace("_", " ")

        # Avoid over-triggering for non-manipulation requests that include generic words like "take" or "move".
        non_manipulation_keywords = (
            "photo",
            "image",
            "video",
            "report",
            "status",
            "health",
            "diagnose",
            "diagnostic",
            "inspect",
            "startup",
            "shutdown",
            "service",
            "log",
            "连接测试",
            "状态",
            "健康检查",
            "诊断",
            "巡检",
            "日志",
            "启动",
            "停止服务",
        )
        if any(keyword in semantic_text for keyword in non_manipulation_keywords):
            return False

        en_pick_pattern = r"\b(pick|grab|grasp|take|lift)\b"
        en_place_pattern = r"\b(place|put|set|drop)\b"
        has_en_pick_and_place = bool(
            re.search(en_pick_pattern, semantic_text)
            and re.search(en_place_pattern, semantic_text)
        )
        has_en_destination = any(
            marker in f" {semantic_text} "
            for marker in (" into ", " onto ", " in ", " on ", " to ")
        )

        cn_pick_verbs = ("抓", "拿", "取", "提")
        cn_place_verbs = ("放", "摆", "置")
        cn_destination_markers = ("放到", "放进", "放在", "放入", "放至", "到", "至")
        has_cn_pick_and_place = any(v in text for v in cn_pick_verbs) and any(
            v in text for v in cn_place_verbs
        )
        has_cn_destination = any(marker in text for marker in cn_destination_markers)

        return (has_en_pick_and_place and has_en_destination) or (
            has_cn_pick_and_place and has_cn_destination
        )

    @staticmethod
    def _extract_tool_names(robot_info: Any) -> set[str]:
        if isinstance(robot_info, str):
            try:
                robot_info = json.loads(robot_info)
            except Exception:
                return set()
        if not isinstance(robot_info, dict):
            return set()

        out: set[str] = set()
        for tool in robot_info.get("robot_tool", []) or []:
            if isinstance(tool, dict):
                func = tool.get("function", {})
                if isinstance(func, dict):
                    name = func.get("name")
                    if isinstance(name, str) and name.strip():
                        out.add(name.strip())
                name = tool.get("name")
                if isinstance(name, str) and name.strip():
                    out.add(name.strip())
        return out

    def _select_robot_for_tool(self, tool_name: str) -> str | None:
        all_agents_info = self.collaborator.read_all_agents_info() or {}
        candidates = []
        for robot_name, raw_info in all_agents_info.items():
            tools = self._extract_tool_names(raw_info)
            if tool_name in tools:
                candidates.append(robot_name)

        if not candidates:
            return None

        # Prioritize the GR2 robot naming convention, then lexicographic fallback.
        for preferred in ("fourier_gr2", "gr2"):
            if preferred in candidates:
                return preferred
        return sorted(candidates)[0]

    def _select_default_robot(self) -> str | None:
        robots = self.collaborator.read_all_agents_name() or []
        if not robots:
            return None
        for preferred in ("fourier_gr2", "gr2"):
            if preferred in robots:
                return preferred
        return sorted(robots)[0]

    def _build_direct_subtask_plan(self, task: str) -> Dict | None:
        task_text = task.strip() if isinstance(task, str) else ""
        if not task_text:
            return None

        # DISABLED: Atomic manipulation routing - force VLM decomposition for bottle task
        # # Preferred atomic tool for end-to-end manipulation.
        # execute_tool = "execute_manipulation_task"
        # execute_robot = self._select_robot_for_tool(execute_tool)
        # if execute_robot and self._is_atomic_manipulation_task(task_text):
        #     plan = {
        #         "reasoning_explanation": (
        #             "Task matched atomic manipulation routing. "
        #             "Dispatch a single end-to-end subtask to execute_manipulation_task."
        #         ),
        #         "subtask_list": [
        #             {
        #                 "robot_name": execute_robot,
        #                 "subtask": f"{execute_tool}: {task_text}",
        #                 "subtask_order": 1,
        #             }
        #         ],
        #     }
        #     self.logger.info("[ROUTER] Using atomic execute routing for task '%s': %s", task, plan)
        #     return plan

        # DISABLED: Fallback atomic routing - force VLM decomposition for bottle task
        # # Fallback: still keep the task atomic (single subtask), avoid planner decomposition/empty plans.
        # if self._is_atomic_manipulation_task(task_text):
        #     fallback_robot = self._select_default_robot()
        #     if fallback_robot:
        #         plan = {
        #             "reasoning_explanation": (
        #                 "Task matched atomic manipulation intent. "
        #                 "execute_manipulation_task is not registered, so dispatch one direct subtask to a robot."
        #             ),
        #             "subtask_list": [
        #                 {
        #                     "robot_name": fallback_robot,
        #                     "subtask": task_text,
        #                     "subtask_order": 1,
        #                 }
        #             ],
        #         }
        #         self.logger.info(
        #             "[ROUTER] Using atomic direct fallback for task '%s': %s", task, plan
        #         )
        #         return plan

        # DISABLED: Backward-compatible fallback for older single-purpose pick tool
        # # Backward-compatible fallback for older single-purpose pick tool.
        # if self._is_pick_bottle_atomic_task(task_text):
        #     tool_name = "pick_bottle_and_place_into_box"
        #     robot_name = self._select_robot_for_tool(tool_name)
        #     if robot_name:
        #         plan = {
        #             "reasoning_explanation": (
        #                 "Task matched atomic GR2 pick-bottle skill. "
        #                 "Use only one executable subtask to avoid unsupported decomposition."
        #             ),
        #             "subtask_list": [
        #                 {
        #                     "robot_name": robot_name,
        #                     "subtask": tool_name,
        #                     "subtask_order": 1,
        #                 }
        #             ],
        #         }
        #         self.logger.info("[ROUTER] Using atomic fallback routing for task '%s': %s", task, plan)
        #         return plan

        return None

    def _start_listener(self):
        """Start listen in a background thread."""
        threading.Thread(
            target=lambda: self.collaborator.listen(
                "AGENT_REGISTRATION", self._handle_register
            ),
            daemon=True,
        ).start()
        self.logger.info("Started listening for robot registrations...")

    def reasoning_and_subtasks_is_right(self, reasoning_and_subtasks: dict) -> bool:
        """
        Verify if all robots mentioned in the task decomposition exist in the system registry

        Args:
            reasoning_and_subtasks: Task decomposition dictionary with format:
                {
                    "reasoning_explanation": "...",
                    "subtask_list": [
                        {"robot_name": "xxx", ...},
                        {"robot_name": "xxx", ...}
                    ]
                }

        Returns:
            bool: True if all robots are registered, False if any invalid robots found
        """
        # Check if input has correct structure
        if not isinstance(reasoning_and_subtasks, dict):
            return False

        if "subtask_list" not in reasoning_and_subtasks:
            return False

        # Extract all unique robot names from subtask_list
        try:
            worker_list = {
                subtask["robot_name"]
                for subtask in reasoning_and_subtasks["subtask_list"]
                if isinstance(subtask, dict) and "robot_name" in subtask
            }

            # Read list of all registered robots from the collaborator
            robots_list = set(self.collaborator.read_all_agents_name())

            # Check if all workers are registered
            return worker_list.issubset(robots_list)

        except (TypeError, KeyError):
            return False

    def publish_global_task(self, task: str, refresh: bool, task_id: str) -> Dict:
        """Publish a global task to all Agents"""
        self.logger.info(f"Publishing global task: {task}")

        reasoning_and_subtasks = self._build_direct_subtask_plan(task)
        if reasoning_and_subtasks is None:
            response = self.planner.forward(task)
            reasoning_and_subtasks = self._extract_json(response)

            # Retry if JSON extraction fails
            attempt = 0
            while (not self.reasoning_and_subtasks_is_right(reasoning_and_subtasks)) and (
                attempt < self.config["model"]["model_retry_planning"]
            ):
                self.logger.warning(
                    f"[WARNING] JSON extraction failed after {self.config['model']['model_retry_planning']} attempts."
                )
                self.logger.error(
                    f"[ERROR] Task ({task}) failed to be decomposed into subtasks, it will be ignored."
                )
                self.logger.warning(
                    f"Attempt {attempt + 1} to extract JSON failed. Retrying..."
                )
                response = self.planner.forward(task)
                reasoning_and_subtasks = self._extract_json(response)
                attempt += 1

        self.logger.info(f"Received reasoning and subtasks:\n{reasoning_and_subtasks}")

        if reasoning_and_subtasks is None:
            self.logger.error("[ERROR] Failed to obtain valid JSON plan from model.")
            return {
                "reasoning_explanation": "Failed to decompose task: Model output invalid or empty.",
                "subtask_list": []
            }

        subtask_list = reasoning_and_subtasks.get("subtask_list", [])
        grouped_tasks = self._group_tasks_by_order(subtask_list)

        task_id = task_id or str(uuid.uuid4()).replace("-", "")

        threading.Thread(
            target=asyncio.run,
            args=(self._dispath_subtasks_async(task, task_id, grouped_tasks, refresh),),
            daemon=True,
        ).start()

        return reasoning_and_subtasks

    async def _dispath_subtasks_async(
        self, task: str, task_id: str, grouped_tasks: Dict, refresh: bool
    ):
        order_flag = "false" if len(grouped_tasks.keys()) == 1 else "true"
        for task_count, (order, group_task) in enumerate(grouped_tasks.items()):
            self.logger.info(f"Sending task group {order}:\n{group_task}")
            working_robots = []
            for tasks in group_task:
                robot_name = tasks.get("robot_name")
                subtask_data = {
                    "task_id": task_id,
                    "task": tasks["subtask"],
                    "order": order_flag,
                }
                if refresh:
                    self.collaborator.clear_agent_status(robot_name)
                self.collaborator.send(
                    f"roboos_to_{robot_name}", json.dumps(subtask_data)
                )
                working_robots.append(robot_name)
                self.collaborator.update_agent_busy(robot_name, True)
            self.collaborator.wait_agents_free(working_robots)
        self.logger.info(f"Task_id ({task_id}) [{task}] has been sent to all agents.")
