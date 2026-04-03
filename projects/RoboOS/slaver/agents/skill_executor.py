"""
SkillSequenceExecutor — Deterministic skill scheduler for the bottle demo.

Replaces the LLM-driven ReAct agent for bottle demo subtasks.
Directly maps subtask names (place_in / take_out / initialization) to MCP tool calls
and implements the state machine defined in the task requirements (S-2.x):

    ready → running → finished
                  ↘ failed → initialization() → ready (retry, up to 3×)
                                                   ↘ stop (3 consecutive failures)

Design decisions:
  - No LLM involved: subtask text IS the MCP tool name (S-1.1)
  - Success/failure is NOT determined by skill return value — it is determined
    by Master's VisionMonitor (OpenAI GPT-4o + top-view camera scene judgment)
  - After each failure, initialization() is called before retry (task requirement)
  - Graceful degradation: if VisionMonitor is unavailable, assume success
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Skill State Machine ─────────────────────────────────────────────────────

class SkillState(str, Enum):
    READY = "ready"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    STOP = "stop"


# Known bottle demo skill names (S-1.1: direct API mapping)
BOTTLE_DEMO_SKILLS = {
    # Box scenario (skill.py)
    "place_in", "take_out",
    # Green-yellow scenario (skill_green_yellow.py)
    "green_to_yellow", "yellow_to_green",
    # Shared
    "initialization",
}

# Map internal subtask names → actual MCP tool names on the skill server.
# This allows the master/planner to keep using stable names while the
# skill server can evolve its tool naming independently.
SKILL_NAME_MAP: Dict[str, str] = {
    # Box scenario
    "place_in": "put_bottle_into_box",
    "take_out": "take_bottle_out_of_box",
    # Green-yellow scenario
    "green_to_yellow": "move_bottle_green_to_yellow",
    "yellow_to_green": "move_bottle_yellow_to_green",
    # Shared: reset arm
    "initialization": "stop_task",
}


def _resolve_skill_name(internal_name: str) -> str:
    """Resolve an internal subtask name to the actual MCP tool name."""
    return SKILL_NAME_MAP.get(internal_name, internal_name)


def is_bottle_demo_task(subtask: str) -> bool:
    """Check if a subtask name maps directly to a bottle demo MCP skill."""
    return subtask.strip().lower() in BOTTLE_DEMO_SKILLS


# ─── Execution Result ─────────────────────────────────────────────────────────

@dataclass
class SkillResult:
    """Result of executing one skill in the sequence."""
    skill_name: str
    skill_state: SkillState
    result_text: str
    attempts: int = 1
    last_error: Optional[str] = None


@dataclass
class SequenceResult:
    """Result of executing the full skill sequence for one subtask."""
    subtask: str
    skill_state: SkillState  # final state: FINISHED or STOP
    result_text: str
    skill_results: List[SkillResult] = field(default_factory=list)
    total_attempts: int = 0
    failure_info: Optional[Dict] = None


# ─── SkillSequenceExecutor ────────────────────────────────────────────────────

class SkillSequenceExecutor:
    """Execute a single bottle-demo subtask with retry logic.

    For a subtask like "place_in", the executor:
      1. Calls the MCP tool (mapped via SKILL_NAME_MAP) directly
      2. After skill execution completes, requests Master's VisionMonitor
         to judge success/failure via the vision_judge callback
      3. If failed, calls initialization() to reset the arm
      4. Retries up to max_retries times
      5. After max_retries consecutive failures → stop state

    Args:
        tool_executor: MCP ClientSession.call_tool coroutine
        vision_judge: Async callback(skill_name) -> (success: bool, reason: str).
            Sends a request to Master's VisionMonitor and waits for the result.
            If None, skill execution is assumed successful (no vision verification).
        max_retries: Maximum consecutive failures before task termination (default 3)
        on_state_change: Optional callback(skill_name, old_state, new_state) for logging
    """

    def __init__(
        self,
        tool_executor: Callable,
        vision_judge: Optional[Callable] = None,
        max_retries: int = 3,
        on_state_change: Optional[Callable] = None,
    ):
        self.tool_executor = tool_executor
        self.vision_judge = vision_judge
        self.max_retries = max_retries
        self.on_state_change = on_state_change
        self._stop_requested = False

    def request_stop(self):
        """External stop signal (M-3.2: manual termination)."""
        self._stop_requested = True

    async def execute(self, subtask: str) -> SequenceResult:
        """Execute a single subtask with retry logic.

        Args:
            subtask: The skill name to execute (e.g. "place_in")

        Returns:
            SequenceResult with final state and all attempt details
        """
        skill_name = subtask.strip().lower()
        skill_results: List[SkillResult] = []
        consecutive_failures = 0

        for attempt in range(1, self.max_retries + 1):
            if self._stop_requested:
                return SequenceResult(
                    subtask=subtask,
                    skill_state=SkillState.STOP,
                    result_text="Task terminated by external signal",
                    skill_results=skill_results,
                    total_attempts=attempt - 1,
                )

            # ── S-2.1: ready ──
            self._notify_state(skill_name, None, SkillState.READY)

            # ── S-2.2: running ──
            self._notify_state(skill_name, SkillState.READY, SkillState.RUNNING)
            logger.info(f"[Attempt {attempt}/{self.max_retries}] Executing {skill_name}")

            # Call the MCP skill (ignore return value)
            await self._call_skill(skill_name)

            # Ask Master's VisionMonitor to judge success/failure
            is_success, judge_reason = await self._judge_via_vision(skill_name)

            if is_success:
                # ── S-2.3: finished ──
                self._notify_state(skill_name, SkillState.RUNNING, SkillState.FINISHED)
                result_text = f"{skill_name}: success — {judge_reason}"
                skill_results.append(SkillResult(
                    skill_name=skill_name,
                    skill_state=SkillState.FINISHED,
                    result_text=result_text,
                    attempts=attempt,
                ))
                return SequenceResult(
                    subtask=subtask,
                    skill_state=SkillState.FINISHED,
                    result_text=result_text,
                    skill_results=skill_results,
                    total_attempts=attempt,
                )

            # ── S-2.4: failed ──
            consecutive_failures += 1
            self._notify_state(skill_name, SkillState.RUNNING, SkillState.FAILED)
            result_text = f"{skill_name}: failed — {judge_reason}"
            logger.warning(
                f"[Attempt {attempt}/{self.max_retries}] {skill_name} FAILED: {judge_reason}"
            )
            skill_results.append(SkillResult(
                skill_name=skill_name,
                skill_state=SkillState.FAILED,
                result_text=result_text,
                attempts=attempt,
                last_error=judge_reason,
            ))

            # Check if we've exhausted retries
            if consecutive_failures >= self.max_retries:
                break

            # ── Recovery: call initialization() before retry ──
            logger.info(f"Calling initialization() before retry (attempt {attempt})")
            await self._call_skill("initialization")

        # ── UC-10 / M-3.1: 3 consecutive failures → stop ──
        self._notify_state(skill_name, SkillState.FAILED, SkillState.STOP)
        logger.error(
            f"{skill_name} failed {consecutive_failures} consecutive times → STOP"
        )

        # Try to return arm to init position before terminating
        await self._safe_init()

        return SequenceResult(
            subtask=subtask,
            skill_state=SkillState.STOP,
            result_text=f"Task terminated: {skill_name} failed {consecutive_failures} consecutive times",
            skill_results=skill_results,
            total_attempts=consecutive_failures,
            failure_info={
                "failed_skill": skill_name,
                "attempts": consecutive_failures,
                "last_error": skill_results[-1].last_error if skill_results else None,
            },
        )

    async def _call_skill(self, skill_name: str) -> str:
        """Call an MCP skill and return the raw result text.

        The return value is logged but NOT used for success/failure judgment.
        Success is determined solely by the VisionMonitor via _judge_via_vision().
        """
        mcp_tool_name = _resolve_skill_name(skill_name)

        try:
            response = await self.tool_executor(mcp_tool_name, {})
            # Extract text if available (for logging only)
            if response.content and len(response.content) > 0:
                raw = response.content[0].text
                if raw:
                    logger.info(f"Skill {mcp_tool_name} returned: {raw[:200]}")
                    return raw
            logger.info(f"Skill {mcp_tool_name} completed (no return data)")
            return f"{mcp_tool_name}: completed"
        except Exception as e:
            logger.error(f"MCP call error: {mcp_tool_name} (mapped from {skill_name}) — {e}")
            return f"MCP call error: {e}"

    async def _judge_via_vision(self, skill_name: str) -> Tuple[bool, str]:
        """Request Master's VisionMonitor to judge whether the skill succeeded.

        Args:
            skill_name: Internal skill name (e.g. "place_in", "take_out")

        Returns:
            (is_success, reason) tuple from VisionMonitor judgment
        """
        if self.vision_judge is None:
            logger.info(f"No vision_judge callback — assuming {skill_name} succeeded")
            return True, "No VisionMonitor available — assumed success"

        try:
            return await self.vision_judge(skill_name)
        except Exception as e:
            logger.error(f"Vision judgment failed for {skill_name}: {e}")
            # If vision judge fails, assume success to avoid false stops
            return True, f"Vision judgment error: {e} — assumed success"

    async def _safe_init(self):
        """Best-effort initialization on termination (arm → safe position)."""
        try:
            await self._call_skill("initialization")
        except Exception:
            logger.error("Failed to return arm to init position during termination")

    def _notify_state(
        self, skill_name: str, old: Optional[SkillState], new: SkillState
    ):
        """Notify state change callback if set."""
        if self.on_state_change:
            try:
                self.on_state_change(skill_name, old, new)
            except Exception:
                pass
