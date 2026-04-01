import asyncio
import json
import logging
import os
import re
import threading
import uuid
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

import yaml
from agents.planner import GlobalTaskPlanner
from agents.vision_monitor import MonitorState, SceneState, VisionMonitor
from flag_scale.flagscale.agent.collaboration import Collaborator


# ─── Bottle Demo: Deterministic Command Parser ──────────────────────────────

# Patterns for the 4 supported user commands (Chinese + English)
# Each pattern maps to a skill sequence
_PLACE_IN_PATTERNS = [
    r"放入|放进|放到.*盒",
    r"put.*(?:cup|bottle).*(?:in|into).*box",
    r"place.*(?:cup|bottle).*(?:in|into)",
]
_TAKE_OUT_PATTERNS = [
    r"拿出|取出|从.*盒.*拿",
    r"take.*(?:cup|bottle).*out",
    r"remove.*(?:cup|bottle).*from",
]
_PLACE_THEN_TAKE_PATTERNS = [
    r"先.*放入.*再.*拿出",
    r"先.*放进.*再.*拿出",
    r"先.*放.*再.*取",
    r"put.*in.*then.*take.*out",
    r"place.*in.*then.*take.*out",
]
_TAKE_THEN_PLACE_PATTERNS = [
    r"先.*拿出.*再.*放入",
    r"先.*拿出.*再.*放进",
    r"先.*取.*再.*放",
    r"take.*out.*then.*put.*in",
    r"take.*out.*then.*place.*in",
]


def parse_bottle_demo_task(task: str, robot_name: str) -> Optional[Dict]:
    """Parse a bottle demo user command into a deterministic skill sequence.

    Returns a reasoning_and_subtasks dict if the command is recognized,
    or None if it should fall through to the LLM planner.
    """
    task_lower = task.lower().strip()

    # Check combined commands FIRST (they contain both "放入" and "拿出")
    for pattern in _PLACE_THEN_TAKE_PATTERNS:
        if re.search(pattern, task_lower):
            return _build_subtask_plan(
                robot_name,
                ["place_in", "initialization", "take_out"],
                "User wants to place cup into box then take it out. "
                "Sequence: place_in → initialization (return to init) → take_out.",
            )

    for pattern in _TAKE_THEN_PLACE_PATTERNS:
        if re.search(pattern, task_lower):
            return _build_subtask_plan(
                robot_name,
                ["take_out", "initialization", "place_in"],
                "User wants to take cup out of box then put it back. "
                "Sequence: take_out → initialization (return to init) → place_in.",
            )

    # Check single commands
    for pattern in _PLACE_IN_PATTERNS:
        if re.search(pattern, task_lower):
            return _build_subtask_plan(
                robot_name,
                ["place_in"],
                "User wants to place the cup into the box. Single skill: place_in.",
            )

    for pattern in _TAKE_OUT_PATTERNS:
        if re.search(pattern, task_lower):
            return _build_subtask_plan(
                robot_name,
                ["take_out"],
                "User wants to take the cup out of the box. Single skill: take_out.",
            )

    # Check for multi-step chain patterns (challenge goal: 3+ steps)
    # e.g., "放入-拿出-放入" or "place-take-place-take"
    chain = _parse_chain_task(task_lower)
    if chain and len(chain) >= 2:
        # Insert initialization between each skill
        full_sequence = []
        for i, skill in enumerate(chain):
            if i > 0:
                full_sequence.append("initialization")
            full_sequence.append(skill)
        return _build_subtask_plan(
            robot_name,
            full_sequence,
            f"Multi-step chain task with {len(chain)} operations. "
            f"initialization() inserted between each step.",
        )

    return None  # Not a recognized bottle demo command


def _parse_chain_task(task: str) -> Optional[List[str]]:
    """Parse a chain command like '放入-拿出-放入' into a list of skills."""
    chain = []

    # Try splitting by common delimiters
    for delimiter in ["-", "→", "->", "，", ",", "、", " then "]:
        if delimiter in task:
            parts = [p.strip() for p in task.split(delimiter) if p.strip()]
            if len(parts) >= 2:
                for part in parts:
                    if re.search(r"放入|放进|place_in|place in|put in", part):
                        chain.append("place_in")
                    elif re.search(r"拿出|取出|take_out|take out", part):
                        chain.append("take_out")
                    elif re.search(r"初始化|init", part):
                        chain.append("initialization")
                if len(chain) >= 2:
                    return chain
                chain = []

    return None


def _build_subtask_plan(
    robot_name: str, skills: List[str], reasoning: str
) -> Dict:
    """Build a subtask plan dict from a skill sequence."""
    return {
        "reasoning_explanation": reasoning,
        "subtask_list": [
            {
                "robot_name": robot_name,
                "subtask": skill,
                "subtask_order": i + 1,
            }
            for i, skill in enumerate(skills)
        ],
    }


# ─── GlobalAgent ─────────────────────────────────────────────────────────────

class GlobalAgent:
    def __init__(self, config_path="config.yaml", on_frontend_update=None):
        """Initialize GlobalAgent

        Args:
            config_path: Path to the YAML config file.
            on_frontend_update: Optional callback ``f(text: str)`` that pushes
                a message to the web frontend (e.g. via SocketIO).
        """
        self._init_config(config_path)
        self._init_logger(self.config["logger"])
        self.collaborator = Collaborator.from_config(self.config["collaborator"])
        self.planner = GlobalTaskPlanner(self.config)

        # Frontend push callback (set by run.py)
        self._on_frontend_update = on_frontend_update

        # Vision monitor (GPT-4o top-view camera)
        vm_config = self.config.get("vision_monitor", {})
        if vm_config.get("enable", False):
            self.vision_monitor = VisionMonitor(vm_config)
            self.vision_monitor.open_camera()
            self.logger.info("VisionMonitor enabled")
        else:
            self.vision_monitor = None
            self.logger.info("VisionMonitor disabled")

        self.logger.info(f"Configuration loaded from {config_path} ...")
        self.logger.info(f"Master Configuration:\n{self.config}")

        self._init_scene(self.config["profile"])
        self._start_listener()

        # Task state: init → waiting → ready → running → stop
        self._task_state = "init"
        self._task_state_lock = threading.Lock()

        # Track failure counts per task_id for termination logic (M-3.1)
        self._failure_counts: Dict[str, int] = {}
        self._failure_lock = threading.Lock()

        # Execution event log — queryable via /task_state API
        self._exec_log: List[Dict] = []
        self._exec_log_lock = threading.Lock()

    def _init_logger(self, logger_config):
        """Initialize an independent logger for GlobalAgent"""
        self.logger = logging.getLogger(logger_config["master_logger_name"])
        logger_file = logger_config["master_logger_file"]
        os.makedirs(os.path.dirname(logger_file), exist_ok=True)
        file_handler = logging.FileHandler(logger_file)

        level = getattr(logging, logger_config["master_logger_level"], logging.INFO)
        self.logger.setLevel(level)
        file_handler.setLevel(level)

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

    # ── Execution event log & frontend notification ──

    def _log_event(self, event_type: str, message: str) -> None:
        """Append an event to the execution log (queryable via /task_state API)."""
        entry = {
            "time": datetime.now().strftime("%H:%M:%S"),
            "type": event_type,
            "message": message,
        }
        with self._exec_log_lock:
            self._exec_log.append(entry)

    def get_task_progress(self) -> Dict:
        """Return current task state + execution event log (for API response)."""
        with self._exec_log_lock:
            events = list(self._exec_log)
        return {
            "task_state": self.task_state,
            "events": events,
        }

    def _clear_exec_log(self) -> None:
        """Clear execution log (called at start of each new task)."""
        with self._exec_log_lock:
            self._exec_log.clear()

    @property
    def task_state(self) -> str:
        with self._task_state_lock:
            return self._task_state

    @task_state.setter
    def task_state(self, value: str):
        with self._task_state_lock:
            old = self._task_state
            self._task_state = value
            self.logger.info(f"Task state: {old} → {value}")
        self._log_event("state", f"{old} → {value}")

    def _handle_register(self, robot_name: str) -> None:
        """Listen for robot registrations."""
        robot_info = self.collaborator.read_agent_info(robot_name)
        self.logger.info(
            f"AGENT_REGISTRATION: {robot_name} \n {json.dumps(robot_info)}"
        )

        # Register functions for processing robot execution results
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
        """Handle results from agents, including failure detection."""
        data = json.loads(data)

        robot_name = data.get("robot_name")
        subtask_handle = data.get("subtask_handle")
        subtask_result = data.get("subtask_result")
        task_id = data.get("task_id")
        skill_state = data.get("skill_state")  # finished / failed / stop
        failure_info = data.get("failure_info")

        self.logger.info(
            f"================ Received result from {robot_name} ================\n"
            f"Subtask: {subtask_handle}\n"
            f"Result: {subtask_result}\n"
            f"Skill state: {skill_state}\n"
            f"===================================================================="
        )

        # Log skill result to execution log
        if skill_state == "finished":
            self._log_event(
                "skill_done",
                f"{robot_name}: {subtask_handle} → {subtask_result}",
            )
        elif skill_state == "failed":
            self._log_event(
                "skill_fail",
                f"{robot_name}: {subtask_handle} → {subtask_result}",
            )

        # Handle task termination from slaver (M-3.1: 3 consecutive failures)
        if skill_state == "stop":
            self.logger.warning(
                f"TASK TERMINATED: {robot_name} reported skill termination "
                f"(3 consecutive failures). Failure info: {failure_info}"
            )
            self._log_event(
                "task_stop",
                f"{robot_name} 连续失败导致任务终止: {failure_info}",
            )
            self.task_state = "stop"

        # Track failure counts
        if skill_state == "failed" and task_id:
            with self._failure_lock:
                self._failure_counts[task_id] = (
                    self._failure_counts.get(task_id, 0) + 1
                )
                count = self._failure_counts[task_id]
            self.logger.warning(
                f"Failure #{count} for task_id={task_id}, skill={subtask_handle}"
            )

        if robot_name and subtask_handle and subtask_result:
            self.collaborator.update_agent_busy(robot_name, False)
        else:
            self.logger.warning("[WARNING] Received incomplete result data")
            if robot_name:
                self.collaborator.update_agent_busy(robot_name, False)

    def _extract_json(self, input_string):
        """Extract JSON from a string — supports ```json fences and raw JSON."""
        # Try markdown fenced JSON first
        start_marker = "```json"
        end_marker = "```"
        try:
            start_idx = input_string.find(start_marker)
            if start_idx != -1:
                end_idx = input_string.find(
                    end_marker, start_idx + len(start_marker)
                )
                if end_idx != -1:
                    json_str = input_string[
                        start_idx + len(start_marker) : end_idx
                    ].strip()
                    return json.loads(json_str)

            # Try raw JSON (find first { to last })
            first_brace = input_string.find("{")
            last_brace = input_string.rfind("}")
            if first_brace != -1 and last_brace != -1:
                json_str = input_string[first_brace : last_brace + 1]
                return json.loads(json_str)

            self.logger.warning("[WARNING] No JSON found in the string.")
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
        """Verify if all robots mentioned in the task decomposition exist in the system registry."""
        if not isinstance(reasoning_and_subtasks, dict):
            return False

        if "subtask_list" not in reasoning_and_subtasks:
            return False

        try:
            worker_list = {
                subtask["robot_name"]
                for subtask in reasoning_and_subtasks["subtask_list"]
                if isinstance(subtask, dict) and "robot_name" in subtask
            }
            robots_list = set(self.collaborator.read_all_agents_name())
            return worker_list.issubset(robots_list)
        except (TypeError, KeyError):
            return False

    def _get_default_robot_name(self) -> Optional[str]:
        """Get the first registered robot name (for single-robot bottle demo)."""
        robots = self.collaborator.read_all_agents_name()
        if robots:
            return robots[0]
        return None

    def publish_global_task(self, task: str, refresh: bool, task_id: str) -> Dict:
        """Publish a global task to all Agents.

        For bottle demo commands, uses deterministic command parsing (no LLM).
        Falls back to LLM planner for unrecognized commands.
        """
        self.logger.info(f"Publishing global task: {task}")

        # Clear execution log for new task
        self._clear_exec_log()
        self._log_event("task_start", f"收到指令: {task}")

        # Validate task state (M-1.1: only accept commands when not init/stop)
        if self.task_state in ("init", "stop"):
            self.logger.warning(
                f"Cannot accept task — current state is '{self.task_state}'"
            )
            return {
                "reasoning_explanation": f"Task rejected: system state is '{self.task_state}'",
                "subtask_list": [],
            }

        # Try deterministic bottle demo parsing first
        robot_name = self._get_default_robot_name()
        task_text = task if isinstance(task, str) else str(task)

        if robot_name:
            direct_plan = parse_bottle_demo_task(task_text, robot_name)
            if direct_plan:
                self.logger.info(
                    f"[DIRECT DISPATCH] Recognized bottle demo command → "
                    f"{[s['subtask'] for s in direct_plan['subtask_list']]}"
                )
                reasoning_and_subtasks = direct_plan
            else:
                # Fall through to LLM planner (v2: classify → plan)
                self.logger.info(
                    "[LLM PLANNER] Command not recognized as bottle demo — using v2 classify+plan"
                )
                reasoning_and_subtasks = self._plan_with_llm(task_text)
        else:
            self.logger.warning("No registered robots found — using LLM planner")
            reasoning_and_subtasks = self._plan_with_llm(task_text)

        if not reasoning_and_subtasks:
            self.logger.error(f"Failed to plan task: {task}")
            self._log_event("plan_fail", f"无法为指令 '{task}' 生成执行计划")
            return {
                "reasoning_explanation": "Planning failed",
                "subtask_list": [],
            }

        self.logger.info(
            f"Received reasoning and subtasks:\n{reasoning_and_subtasks}"
        )

        # Log plan to execution log
        subtask_names = [s.get("subtask", "?") for s in reasoning_and_subtasks.get("subtask_list", [])]
        self._log_event(
            "plan_done",
            f"指令 '{task}' → {len(subtask_names)} 个子任务: {' → '.join(subtask_names)}",
        )
        subtask_list = reasoning_and_subtasks.get("subtask_list", [])
        grouped_tasks = self._group_tasks_by_order(subtask_list)

        task_id = task_id or str(uuid.uuid4()).replace("-", "")

        # Reset failure counter for new task
        with self._failure_lock:
            self._failure_counts[task_id] = 0

        self.task_state = "running"

        threading.Thread(
            target=asyncio.run,
            args=(
                self._dispatch_subtasks_async(
                    task_text, task_id, grouped_tasks, refresh
                ),
            ),
            daemon=True,
        ).start()

        return reasoning_and_subtasks

    def _plan_with_llm(self, task: str) -> Optional[Dict]:
        """Use LLM planner (v2 two-stage) to decompose task into subtasks.

        Stage 1: classify(task) → intent (PUT/TAKE/PUT_THEN_TAKE/TAKE_THEN_PUT/INVALID)
        Stage 2: plan(intent)   → subtask_list JSON
        """
        # Stage 1: Classify intent (M-1.1 / M-1.2)
        intent = self.planner.classify(task)
        self.logger.info(f"[LLM classify] '{task}' → intent={intent}")

        if intent == "INVALID":
            self.logger.warning(f"[LLM classify] Invalid command rejected: {task}")
            return {
                "reasoning_explanation": f"指令无效: '{task}' 不属于已知任务类型",
                "subtask_list": [],
            }

        # Stage 2: Plan subtasks (M-2.x)
        max_retries = self.config["model"]["model_retry_planning"]
        reasoning_and_subtasks = None

        for attempt in range(max_retries):
            reasoning_and_subtasks = self.planner.plan(intent)

            if self.reasoning_and_subtasks_is_right(reasoning_and_subtasks):
                return reasoning_and_subtasks

            self.logger.warning(
                f"Attempt {attempt + 1} to get valid plan failed. Retrying..."
            )

        self.logger.error(
            f"Task ({task}, intent={intent}) failed to plan after {max_retries} attempts."
        )
        return None

    # ── Vision judgment: success criteria per skill ──

    # Maps internal skill name → expected scene state for "success"
    SKILL_SUCCESS_CRITERIA = {
        "place_in": lambda scene: scene.bottle_in_box is True,
        "take_out": lambda scene: scene.bottle_in_box is False,
    }

    def _judge_skill_success(self, skill_name: str, scene: SceneState) -> tuple:
        """Determine if a skill succeeded based on VisionMonitor scene state.

        Args:
            skill_name: Internal skill name (e.g. "place_in", "take_out")
            scene: SceneState from VisionMonitor

        Returns:
            (is_success: bool, reason: str)
        """
        criteria = self.SKILL_SUCCESS_CRITERIA.get(skill_name)
        if criteria is None:
            # Unknown skill — no criteria, assume success
            return True, f"No vision criteria for '{skill_name}' — assumed success"

        if scene.confidence < self.config.get("vision_monitor", {}).get("confidence_threshold", 0.7):
            # Low confidence — cannot make a reliable judgment, assume success
            return True, f"Low confidence ({scene.confidence:.0%}) — assumed success: {scene.reason}"

        is_success = criteria(scene)
        box_status = "in box" if scene.bottle_in_box else "not in box" if scene.bottle_in_box is False else "box status unclear"
        paper_status = f"on {scene.bottle_on_paper} paper" if scene.bottle_on_paper else "not on colored paper"
        reason = f"bottle {box_status}, {paper_status} (confidence: {scene.confidence:.0%}): {scene.reason}"
        return is_success, reason

    def _handle_vision_judgment_request(self, robot_name: str) -> None:
        """Check for a pending vision judgment request and respond.

        Protocol:
          - Slaver writes request to Redis key: vision_request:{robot_name}
          - Master reads it, runs VisionMonitor, writes result to: vision_result:{robot_name}
        """
        request_key = f"vision_request:{robot_name}"
        result_key = f"vision_result:{robot_name}"

        raw = self.collaborator.read_environment(request_key)
        if raw is None:
            return

        if isinstance(raw, str):
            try:
                request = json.loads(raw)
            except (json.JSONDecodeError, ValueError):
                return
        else:
            request = raw

        if not isinstance(request, dict) or "skill_name" not in request:
            return

        skill_name = request["skill_name"]
        self.logger.info(f"[VisionJudge] Received judgment request: {skill_name} from {robot_name}")
        self._log_event("vision_judge_request", f"{robot_name} 请求视觉判定: {skill_name}")

        # Clear the request so we don't process it again
        self.collaborator.record_environment(request_key, json.dumps(None))

        # Run VisionMonitor judgment
        if self.vision_monitor is not None:
            scene = self.vision_monitor.judge_final_state(skill_name)
            is_success, reason = self._judge_skill_success(skill_name, scene)
        else:
            is_success = True
            reason = "VisionMonitor disabled — assumed success"

        self.logger.info(f"[VisionJudge] {skill_name} → {'SUCCESS' if is_success else 'FAILED'}: {reason}")
        self._log_event(
            "vision_judge_result",
            f"{skill_name} → {'成功' if is_success else '失败'}: {reason}",
        )

        # Write result for Slaver to pick up
        result = {
            "success": is_success,
            "reason": reason,
            "skill_name": skill_name,
        }
        self.collaborator.record_environment(result_key, json.dumps(result))

    async def _dispatch_subtasks_async(
        self, task: str, task_id: str, grouped_tasks: Dict, refresh: bool
    ):
        """Dispatch subtasks to robots sequentially by order group.

        When VisionMonitor is enabled:
          - Background monitoring thread captures frames every N seconds
          - When Slaver requests a vision judgment (after skill execution),
            Master runs VisionMonitor to determine success/failure
          - Result is written to Redis for Slaver to read
        """
        total = sum(len(g) for g in grouped_tasks.values())
        order_flag = "false" if len(grouped_tasks.keys()) == 1 else "true"

        for task_count, (order, group_task) in enumerate(grouped_tasks.items()):
            # Check if task was terminated (M-3.1)
            if self.task_state == "stop":
                self.logger.warning(
                    f"Task {task_id} terminated — skipping remaining subtasks."
                )
                self._log_event("dispatch_abort", f"任务 {task_id} 已终止，跳过剩余子任务")
                break

            self.logger.info(f"Sending task group {order}:\n{group_task}")
            working_robots = []

            for tasks in group_task:
                robot_name = tasks.get("robot_name")
                subtask_name = tasks["subtask"]
                subtask_data = {
                    "task_id": task_id,
                    "task": subtask_name,
                    "order": order_flag,
                }

                if refresh:
                    self.collaborator.clear_agent_status(robot_name)

                # ── Start vision monitoring (if enabled) ──
                monitor_state = None
                if self.vision_monitor is not None:
                    monitor_state = MonitorState()
                    subtask_context = (
                        f"{subtask_name} (robot={robot_name}, "
                        f"subtask {task_count + 1}/{total})"
                    )
                    self.vision_monitor.start_monitoring(
                        subtask_context=subtask_context,
                        state=monitor_state,
                        on_event=self._log_event,
                    )

                # ── Dispatch subtask to slaver ──
                self.collaborator.send(
                    f"roboos_to_{robot_name}", json.dumps(subtask_data)
                )
                working_robots.append(robot_name)
                self.collaborator.update_agent_busy(robot_name, True)

                self._log_event(
                    "dispatch",
                    f"子任务 {task_count + 1}/{total}: {subtask_name} → {robot_name}",
                )

            # ── Wait for slaver to finish ──
            # While waiting, poll for vision judgment requests from Slaver
            while True:
                # Check if all robots are free
                all_free = all(
                    not self.collaborator.agent_is_busy(r) for r in working_robots
                )
                if all_free:
                    break

                # Handle any pending vision judgment requests
                for r in working_robots:
                    self._handle_vision_judgment_request(r)

                await asyncio.sleep(0.5)

            # ── Stop vision monitoring ──
            if monitor_state is not None:
                monitor_state.stop()

        if self.task_state != "stop":
            self.task_state = "waiting"

        self.logger.info(
            f"Task_id ({task_id}) [{task}] dispatch completed. "
            f"Final state: {self.task_state}"
        )
        self._log_event("task_done", f"任务 '{task}' 调度结束，当前状态: {self.task_state}")
