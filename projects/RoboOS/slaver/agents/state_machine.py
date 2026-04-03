import asyncio
import json
import logging
import os
import threading
import uuid
from collections import defaultdict
from typing import Dict

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
        # Per-task replan counter — prevents infinite replan loops.
        self._replan_counts: dict = {}
        self._replan_lock = threading.Lock()
        # Task registry: stores the original task description and tracks
        # which subtasks have already completed successfully.
        # Key: task_id  Value: {original_task, completed_subtasks: []}
        self._task_registry: dict = {}
        self._registry_lock = threading.Lock()

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

    # Maximum replan attempts per task_id before giving up.
    MAX_REPLAN_PER_TASK = 3

    def _handle_result(self, data: str):
        """Handle subtask results from slaver agents.

        Success path  : free the robot, let _dispath_subtasks_async continue.
        Failure path  :
          1. Parse failure_info: type / skill / reason / suggestion /
             completed_steps / failed_step (exact breakpoint).
          2. Build a context-rich repair prompt so the LLM knows exactly
             where the chain broke and what had already succeeded.
          3. Guard against infinite loops with _replan_counts[task_id].
          4. Fire publish_global_task in a daemon thread — never blocks the
             listener or _dispath_subtasks_async.
        """
        data = json.loads(data)

        robot_name     = data.get("robot_name")
        subtask_handle = data.get("subtask_handle")
        subtask_result = data.get("subtask_result")
        subtask_status = data.get("subtask_status", "success")
        failure_info   = data.get("failure_info")
        task_id        = data.get("task_id", "")

        if not (robot_name and subtask_handle and subtask_result):
            self.logger.warning("[WARNING] Received incomplete result data")
            self.logger.info(f"subtask_handle={subtask_handle} result={subtask_result}")
            return

        self.logger.info(
            f"================ Received result from {robot_name} ================"
        )
        self.logger.info(f"Subtask : {subtask_handle}")
        self.logger.info(f"Result  : {subtask_result}")
        self.logger.info(f"Status  : {subtask_status}")
        if failure_info:
            self.logger.info(f"Failure : {json.dumps(failure_info, ensure_ascii=False)}")
        self.logger.info("====================================================================")

        self.collaborator.update_agent_busy(robot_name, False)

        if subtask_status != "failure":
            self.logger.info(f"[SUCCESS] task_id={task_id} subtask completed.")
            # Track completed subtasks so the repair prompt can skip them.
            with self._registry_lock:
                reg = self._task_registry.get(task_id)
                if reg:
                    reg["completed_subtasks"].append({
                        "robot_name": robot_name,
                        "subtask":    subtask_handle,
                    })
            return

        # ── Replan guard ───────────────────────────────────────────────────────
        with self._replan_lock:
            count = self._replan_counts.get(task_id, 0)
            if count >= self.MAX_REPLAN_PER_TASK:
                self.logger.error(
                    f"[GIVE UP] task_id={task_id} replanned {count} times. "
                    f"Abandoning: {subtask_handle}"
                )
                return
            self._replan_counts[task_id] = count + 1

        # ── Build context-aware repair prompt ────────────────────────────────
        fi          = failure_info or {}
        ftype       = fi.get("type", "")
        reason      = fi.get("reason", "unknown")
        suggestion  = fi.get("suggestion", "")
        completed_steps = fi.get("completed_steps", [])
        failed_step = fi.get("failed_step") or {}

        with self._registry_lock:
            reg = self._task_registry.get(task_id, {})
        original_task       = reg.get("original_task", subtask_handle)
        completed_subtasks  = reg.get("completed_subtasks", [])

        # Repair prompt includes:
        #   1. The original root task — planner always keeps the big picture.
        #   2. Already-completed subtasks — planner must NOT redo these.
        #   3. The failed subtask with exact breakpoint (step, tool, args).
        #   4. Failure reason + suggestion from the skill.
        completed_summary = (
            ", ".join(f"{s['robot_name']}:{s['subtask']}" for s in completed_subtasks)
            if completed_subtasks else "none"
        )

        if ftype == "skill_execution_failure" and failed_step:
            repair_task = (
                f"[REPLAN {count + 1}/{self.MAX_REPLAN_PER_TASK}] "
                f"Original task: '{original_task}'. "
                f"Subtasks already completed (do NOT repeat): {completed_summary}. "
                f"The subtask '{subtask_handle}' failed at step {failed_step.get('step')} "
                f"when calling '{failed_step.get('tool_name')}' "
                f"with args {failed_step.get('tool_arguments')}. "
                f"Failure reason: {reason}. "
                f"{('Hint: ' + suggestion) if suggestion else ''} "
                f"Re-plan ONLY the remaining work needed to complete the original task, "
                f"using a different approach or robot for the failed step."
            )
        else:
            repair_task = (
                f"[REPLAN {count + 1}/{self.MAX_REPLAN_PER_TASK}] "
                f"Original task: '{original_task}'. "
                f"Subtasks already completed (do NOT repeat): {completed_summary}. "
                f"The subtask '{subtask_handle}' failed ({ftype}). "
                f"Reason: {reason}. "
                f"{('Hint: ' + suggestion) if suggestion else ''} "
                f"Re-plan ONLY the remaining work to complete the original task."
            )

        self.logger.warning(f"[REPLAN #{count + 1}] task_id={task_id}: {repair_task}")

        threading.Thread(
            target=self.publish_global_task,
            args=(repair_task, True, task_id),
            kwargs={"original_task": original_task},
            daemon=True,
        ).start()


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

    def publish_global_task(self, task: str, refresh: bool, task_id: str,
                             original_task: str = None) -> Dict:
        """Publish a global task to all Agents.

        original_task: the root task description. On first call this equals
        `task`. On replan calls the repair prompt is passed as `task` but the
        root task is preserved here so the LLM always has full context.
        """
        self.logger.info(f"Publishing global task: {task}")

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

        # Register the root task so _handle_result can reference it during replan.
        with self._registry_lock:
            if task_id not in self._task_registry:
                self._task_registry[task_id] = {
                    "original_task":      original_task or task,
                    "completed_subtasks": [],
                }

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
