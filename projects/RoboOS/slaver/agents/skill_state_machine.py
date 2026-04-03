# -*- coding: utf-8 -*-
"""
Skill Sequence State Machine for Slaver Agent.

When a task specifies an ordered skill sequence (e.g. "Execute the following
skills strictly in order: skill_a, skill_b, skill_c"), this executor replaces
the free-form ReAct loop with deterministic sequential execution plus
retry / rollback logic:

  1. Execute each skill in order.
  2. If a skill returns a "not completed" / failure result, RETRY it
     (up to MAX_RETRIES times).
  3. If MAX_RETRIES consecutive failures occur, ROLLBACK to the previous
     skill and re-execute from there.
  4. If the rolled-back skill also fails MAX_RETRIES times (or there is
     no previous skill to roll back to), the entire sequence is marked FAILED.
"""

import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

class StepState(Enum):
    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    RETRYING = "retrying"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass
class SkillStep:
    """Tracks the execution state of a single skill in the sequence."""
    index: int
    skill_name: str
    state: StepState = StepState.PENDING
    retry_count: int = 0
    last_observation: str = ""


class SequenceResult(Enum):
    SUCCESS = "success"
    FAILED = "failed"


# ---------------------------------------------------------------------------
# Failure detection
# ---------------------------------------------------------------------------

# Keywords that indicate a skill did NOT complete successfully.
# RoboSkill functions should include one of these in their return string
# when the action fails or is incomplete.
FAILURE_KEYWORDS = [
    "failed",
    "not completed",
    "error",
    "unable",
    "timeout",
    "unreachable",
    "aborted",
]


def is_failure(observation: str) -> bool:
    """Return True if the observation text signals a failed / incomplete skill."""
    obs_lower = observation.lower()
    return any(kw in obs_lower for kw in FAILURE_KEYWORDS)


# ---------------------------------------------------------------------------
# Skill sequence parser
# ---------------------------------------------------------------------------

# Pattern 1: canonical "Execute the following skills strictly in order: a, b, c"
_SEQ_PATTERN = re.compile(
    r"Execute the following skills strictly in order:\s*(.+)",
    re.IGNORECASE,
)

# Pattern 2: LLM rewrites like "using skill_a, skill_b, skill_c"
_USING_PATTERN = re.compile(
    r"\busing\s+(.+)",
    re.IGNORECASE,
)

# All known skill names — used for fallback extraction from free-form text.
# This list MUST stay in sync with the MCP tools registered in RoboSkill.
KNOWN_SKILLS = {
    "visual_localize", "visual_inspect", "qr_code_recognize", "read_screen_result",
    "move_to_position", "bimanual_sync_move", "set_orientation", "plan_path",
    "open_hand", "precision_pinch", "force_controlled_grasp", "lift_object",
    "place_object", "press_dual_buttons", "lens_cap_operation", "fine_align",
    "hand_transfer", "wait_for_signal", "coordinate_transform",
}


def parse_skill_sequence(task: str) -> Optional[List[str]]:
    """Extract an ordered list of skill names from the task description.

    Supports multiple formats:
      1. "Execute the following skills strictly in order: a, b, c"
      2. "... using a, b, c"  (LLM rewrite)
      3. Fallback: scan the entire task for known skill names in order of
         appearance (triggers only if >= 2 known skills are found).

    Returns None if no skill sequence can be identified.
    """
    # --- Pattern 1: canonical ---
    match = _SEQ_PATTERN.search(task)
    if match:
        return _split_skills(match.group(1))

    # --- Pattern 2: "using ..." ---
    match = _USING_PATTERN.search(task)
    if match:
        candidates = _split_skills(match.group(1))
        # Only accept if all tokens are known skills (avoid false positives
        # like "using the left hand")
        if candidates and all(s in KNOWN_SKILLS for s in candidates):
            return candidates

    # --- Pattern 3: fallback — extract known skills by order of appearance ---
    found: List[str] = []
    for m in re.finditer(r'\b(' + '|'.join(KNOWN_SKILLS) + r')\b', task):
        name = m.group(1)
        if name not in found:          # deduplicate, keep first occurrence
            found.append(name)
    if len(found) >= 2:
        return found

    return None


def _split_skills(raw: str) -> List[str]:
    """Split a comma-/space-separated skill list and clean up."""
    # Handle both "a, b, c" and "a b c" styles
    parts = re.split(r'[,\s]+', raw.strip().rstrip("."))
    return [p for p in parts if p]


# ---------------------------------------------------------------------------
# Argument resolver
# ---------------------------------------------------------------------------

def resolve_arguments(
    skill_name: str,
    task_context: str,
    tools: List[Dict],
) -> dict:
    """Build a best-effort argument dict for *skill_name* from the task context.

    This mirrors the heuristic used by RoboBrain2.0's _extract_tool_args but
    is local to the slaver — no round-trip to the inference server needed.
    """
    # Find the tool definition
    schema = None
    for tool in tools:
        if tool.get("function", {}).get("name") == skill_name:
            schema = tool.get("input_schema", {})
            break

    if not schema:
        return {}

    properties = schema.get("properties", {})
    required = set(schema.get("required", []))
    args: dict = {}

    for param_name, param_def in properties.items():
        description = param_def.get("description", "")
        param_type = param_def.get("type", "string")

        # Try to extract a value from the task text
        value = _extract_param_value(param_name, description, param_type, task_context)

        if value is not None:
            args[param_name] = value
        elif param_name in required:
            # Use a sensible fallback so MCP validation doesn't reject the call
            args[param_name] = _default_for_type(param_type)

    return args


def _extract_param_value(name: str, description: str, ptype: str, context: str):
    """Attempt to pull a parameter value out of the task context string."""
    ctx_lower = context.lower()

    # ---- Common semantic mappings ----
    if name == "target":
        for kw in ["camera", "fixture_slot", "lens_cap", "transferBoxIn",
                    "transferBoxOut", "inspectionStation", "qrScanner",
                    "qr_scanner_beam"]:
            if kw.lower() in ctx_lower:
                return kw
        return "camera"  # safe default for inspection tasks

    if name == "hand":
        if "left" in ctx_lower:
            return "left"
        if "right" in ctx_lower:
            return "right"
        return "right"  # default hand

    if name in ("object", "object_name"):
        for kw in ["camera", "lens_cap"]:
            if kw in ctx_lower:
                return kw
        return "camera"

    if name == "action":
        if "pull" in ctx_lower or "remove" in ctx_lower:
            return "pull"
        return "insert"

    if name == "signal":
        return "airtightness_test_complete"

    if name in ("left_target", "left_button"):
        return "green_button_left"

    if name in ("right_target", "right_button"):
        return "green_button_right"

    if name == "from_hand":
        return "right"

    if name == "to_hand":
        return "left"

    if name == "reference_point":
        return "transferBoxOut_slot_0_0"

    if name == "offset_index":
        return 0

    if name == "orientation":
        for kw in ["lens_up", "lens_down", "qr_code_toward_scanner",
                    "lens_toward_person"]:
            if kw.lower() in ctx_lower:
                return kw
        return "lens_up"

    if name == "force_n":
        return 1.0

    if name == "timeout_s":
        return 60

    return None


def _default_for_type(ptype: str):
    """Return a safe default value for a JSON-schema type."""
    return {
        "string": "unknown",
        "integer": 0,
        "number": 0.0,
        "boolean": False,
    }.get(ptype, "unknown")


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

class SkillSequenceExecutor:
    """Deterministic skill-sequence runner with retry and rollback.

    Parameters
    ----------
    tool_executor : async callable
        Typically ``mcp.ClientSession.call_tool(name, arguments)``.
    tools : list[dict]
        Available tool definitions (with input_schema) from MCP server.
    log_file : str, optional
        Path to an agent-style log file.
    max_retries : int
        Max consecutive retries per skill before rolling back (default 3).
    max_rollbacks : int
        Max total rollbacks before giving up the whole sequence (default 3).
    """

    MAX_RETRIES = 3
    MAX_ROLLBACKS = 3

    def __init__(
        self,
        tool_executor: Callable,
        tools: List[Dict],
        log_file: Optional[str] = None,
        max_retries: int = 3,
        max_rollbacks: int = 3,
    ):
        self.tool_executor = tool_executor
        self.tools = tools
        self.MAX_RETRIES = max_retries
        self.MAX_ROLLBACKS = max_rollbacks

        # Logging
        self.logger = logging.getLogger("SkillSequenceExecutor")
        if log_file:
            handler = logging.FileHandler(log_file, mode="a")
            handler.setFormatter(
                logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            )
            self.logger.addHandler(handler)
        self.logger.setLevel(logging.DEBUG)

        # Execution state
        self.steps: List[SkillStep] = []
        self.execution_log: List[dict] = []  # full history for reporting
        self.total_rollbacks = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute(
        self, skill_names: List[str], task_context: str
    ) -> Dict:
        """Run the skill sequence and return a structured result dict.

        Returns
        -------
        dict with keys:
            status        : "success" | "failed"
            completed     : list of skill names that succeeded
            failed_skill  : name of the skill that ultimately failed (if any)
            execution_log : list of per-step records
        """
        self.steps = [
            SkillStep(index=i, skill_name=name)
            for i, name in enumerate(skill_names)
        ]
        self.execution_log = []
        self.total_rollbacks = 0
        current = 0

        self.logger.info(
            f"=== Skill Sequence Start === "
            f"skills={[s.skill_name for s in self.steps]}"
        )

        while current < len(self.steps):
            step = self.steps[current]
            step.state = StepState.EXECUTING

            # Resolve arguments for this skill
            args = resolve_arguments(step.skill_name, task_context, self.tools)

            self.logger.info(
                f"[Step {current}] Executing '{step.skill_name}' "
                f"(attempt {step.retry_count + 1}) args={args}"
            )

            # ----- Execute via MCP -----
            try:
                result = await self.tool_executor(step.skill_name, args)
                observation = result.content[0].text
            except Exception as exc:
                observation = f"FAILED: MCP call error — {exc}"
                self.logger.error(
                    f"[Step {current}] MCP exception: {exc}"
                )

            step.last_observation = observation
            self._record(step, args, observation)

            # ----- Check outcome -----
            if is_failure(observation):
                step.retry_count += 1
                self.logger.warning(
                    f"[Step {current}] '{step.skill_name}' FAILED "
                    f"(attempt {step.retry_count}/{self.MAX_RETRIES}): "
                    f"{observation}"
                )

                if step.retry_count < self.MAX_RETRIES:
                    # ---- RETRY same skill ----
                    step.state = StepState.RETRYING
                    continue

                # ---- 3 failures → ROLLBACK ----
                step.state = StepState.FAILED
                self.total_rollbacks += 1

                if self.total_rollbacks > self.MAX_ROLLBACKS:
                    self.logger.error(
                        f"[ABORT] Total rollbacks ({self.total_rollbacks}) "
                        f"exceeded limit ({self.MAX_ROLLBACKS}). Giving up."
                    )
                    return self._build_result(SequenceResult.FAILED, step)

                if current == 0:
                    # No previous skill to roll back to
                    self.logger.error(
                        f"[ABORT] First skill '{step.skill_name}' failed "
                        f"{self.MAX_RETRIES} times with no rollback target."
                    )
                    return self._build_result(SequenceResult.FAILED, step)

                # Roll back to previous skill
                prev = self.steps[current - 1]
                prev.retry_count = 0
                prev.state = StepState.ROLLED_BACK
                # Also reset current skill so it gets fresh retries after
                # the previous skill re-executes.
                step.retry_count = 0
                step.state = StepState.PENDING

                self.logger.warning(
                    f"[ROLLBACK #{self.total_rollbacks}] "
                    f"'{step.skill_name}' exhausted retries → "
                    f"rolling back to '{prev.skill_name}'"
                )
                current -= 1
                continue
            else:
                # ---- SUCCESS ----
                step.state = StepState.SUCCESS
                step.retry_count = 0
                self.logger.info(
                    f"[Step {current}] '{step.skill_name}' SUCCESS: "
                    f"{observation[:120]}"
                )
                current += 1

        # All steps completed
        self.logger.info("=== Skill Sequence Complete (all skills succeeded) ===")
        return self._build_result(SequenceResult.SUCCESS)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _record(self, step: SkillStep, args: dict, observation: str):
        """Append an entry to the execution log."""
        self.execution_log.append({
            "step_index": step.index,
            "skill_name": step.skill_name,
            "attempt": step.retry_count + 1,
            "arguments": args,
            "observation": observation,
            "state": step.state.value,
        })

    def _build_result(
        self, outcome: SequenceResult, failed_step: Optional[SkillStep] = None
    ) -> Dict:
        completed = [s.skill_name for s in self.steps if s.state == StepState.SUCCESS]
        result = {
            "status": outcome.value,
            "completed_skills": completed,
            "total_steps": len(self.steps),
            "completed_count": len(completed),
            "total_rollbacks": self.total_rollbacks,
            "execution_log": self.execution_log,
        }
        if failed_step:
            result["failed_skill"] = failed_step.skill_name
            result["failed_step_index"] = failed_step.index
            result["last_observation"] = failed_step.last_observation
        return result
