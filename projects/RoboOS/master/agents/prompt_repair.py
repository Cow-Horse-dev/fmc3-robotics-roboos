# -*- coding: utf-8 -*-
"""
Prompt Repair Engine for Master Agent.

When a subtask fails (after the slaver's SkillSequenceExecutor exhausts all
retries and rollbacks), this engine builds a context-rich repair prompt that
is fed back to the planner (RoboBrain) so it can generate a NEW plan that
avoids the same failure.

Flow:
    failure_info (from slaver)
        → PromptRepairEngine.build_repair_prompt()
            → planner.repair_forward(repair_prompt)
                → new subtask plan
"""

import json
import logging
from typing import Dict, List, Optional

from agents.prompts import REPAIR_PLANNING_PROMPT

logger = logging.getLogger(__name__)


class PromptRepairEngine:
    """Generates repair prompts from failure context.

    Parameters
    ----------
    max_replan : int
        Maximum number of replan attempts per task (default 3).
    """

    def __init__(self, max_replan: int = 3):
        self.max_replan = max_replan

    def build_repair_prompt(
        self,
        original_task: str,
        failed_subtask: str,
        failed_robot: str,
        failure_info: Dict,
        completed_subtasks: List[Dict],
        replan_attempt: int,
        robot_name_list: str,
        robot_tools_info: str,
        scene_info: str,
    ) -> str:
        """Build a structured repair prompt from failure context.

        Parameters
        ----------
        original_task : str
            The root task description (e.g. from the web UI workflow card).
        failed_subtask : str
            The subtask description that failed.
        failed_robot : str
            The robot that was executing when failure occurred.
        failure_info : dict
            Failure details from slaver's SkillSequenceExecutor, containing:
              - type: "skill_execution_failure"
              - reason: observation text from the failed skill
              - completed_steps: list of skill names that succeeded
              - failed_step: {step: int, tool_name: str}
              - suggestion: text suggestion from slaver
        completed_subtasks : list[dict]
            Subtasks that completed successfully before this failure,
            each with keys: robot_name, subtask.
        replan_attempt : int
            Current replan attempt number (1-based).
        robot_name_list, robot_tools_info, scene_info : str
            System context strings for the prompt template.

        Returns
        -------
        str
            A fully formatted repair prompt ready for planner.repair_forward().
        """
        fi = failure_info or {}
        failed_step = fi.get("failed_step", {})

        # -- Completed subtasks summary --
        if completed_subtasks:
            completed_summary = "\n".join(
                f"  - [{s.get('robot_name', '?')}] {s.get('subtask', '?')}"
                for s in completed_subtasks
            )
        else:
            completed_summary = "  (none — this was the first subtask)"

        # -- Completed skills within the failed sequence --
        completed_skills = fi.get("completed_steps", [])
        if completed_skills:
            completed_skills_str = ", ".join(completed_skills)
        else:
            completed_skills_str = "(none — failed at the first skill)"

        prompt = REPAIR_PLANNING_PROMPT.format(
            robot_name_list=robot_name_list,
            robot_tools_info=robot_tools_info,
            scene_info=scene_info,
            replan_attempt=replan_attempt,
            max_replan=self.max_replan,
            original_task=original_task,
            completed_summary=completed_summary,
            failed_subtask=failed_subtask,
            failed_robot=failed_robot,
            failed_skill=failed_step.get("tool_name", "unknown"),
            failed_step_index=failed_step.get("step", "?"),
            completed_skills_in_sequence=completed_skills_str,
            failure_reason=fi.get("reason", "unknown"),
            total_rollbacks=fi.get("total_rollbacks", 0)
            if "total_rollbacks" in fi
            else "unknown",
        )

        logger.info(
            f"[PromptRepairEngine] Built repair prompt for replan "
            f"#{replan_attempt}/{self.max_replan}  "
            f"failed_skill={failed_step.get('tool_name')}  "
            f"reason={fi.get('reason', '')[:100]}"
        )

        return prompt
