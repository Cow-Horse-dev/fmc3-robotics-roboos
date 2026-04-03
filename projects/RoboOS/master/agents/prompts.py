MASTER_PLANNING_PLANNING = """

## Robot Platform
- Robot: Fourier GR2 (dual-arm humanoid, 5-finger dexterous hands)
- Task domain: Industrial camera airtightness inspection (Hikvision)

## Atomic Skill Categories Available
- P (Perception): visual_localize, visual_inspect, qr_code_recognize, read_screen_result
- M (Motion): move_to_position, bimanual_sync_move, set_orientation, plan_path
- G (Grasping): open_hand, precision_pinch, force_controlled_grasp, lift_object
- O (Operation): place_object, press_dual_buttons, lens_cap_operation, fine_align
- C (Coordination): hand_transfer
- I (Interaction): wait_for_signal

## Reference Workflow (9 steps)
1. Pick up camera from transferBoxIn — use: visual_localize, plan_path, move_to_position, open_hand, precision_pinch, force_controlled_grasp, lift_object
2. Remove lens cap + inspect lens — use: hand_transfer, visual_localize, move_to_position, precision_pinch, lens_cap_operation, place_object, set_orientation, visual_inspect
3. Scan QR code at qrScanner — use: bimanual_sync_move, set_orientation, move_to_position, fine_align, qr_code_recognize, wait_for_signal
4. Place camera (lens up) into fixture_slot — use: set_orientation, visual_localize, plan_path, move_to_position, fine_align, place_object
5. Press green_button_left + green_button_right simultaneously, wait for test — use: visual_localize, bimanual_sync_move, press_dual_buttons, wait_for_signal
6. Remove camera from fixture + inspect lens — use: move_to_position, precision_pinch, lift_object, set_orientation, visual_inspect
7. Replace lens cap from lens_cap_area — use: visual_localize, move_to_position, precision_pinch, lens_cap_operation, place_object
8. Place camera (lens down) into transferBoxOut — use: visual_localize, plan_path, set_orientation, fine_align, place_object
9. Read airtightness result from screen — use: visual_localize, read_screen_result, visual_inspect

## Key Design Constraints
- Force-controlled grasps must stay within 0.5–2N to avoid lens damage
- All alignment operations require ±0.3mm precision
- Bimanual sync operations must maintain time offset < 100ms
- All grasp operations should be preceded by visual_localize

Please only use {robot_name_list} with skills {robot_tools_info}.
You must also consider the following scene information when decomposing the task:
{scene_info}

Please break down the given task into sub-tasks, each of which cannot be too complex, make sure that a single robot can do it.
It can't be too simple either, e.g. it can't be a sub-task that can be done by a single step robot tool.
Each sub-task in the output needs a concise name of the sub-task, which includes the robots that need to complete the sub-task.
Additionally you need to give a 200+ word reasoning explanation on subtask decomposition and analyze if each step can be done by a single robot based on each robot's tools!

IMPORTANT: If the user's task specifies a skill sequence (e.g. "Execute the following skills strictly in order: ..."), you MUST preserve that exact skill sequence in the subtask description. Include the full instruction "Execute the following skills strictly in order: skill1, skill2, ..." verbatim in the subtask field so the executing robot follows the correct order.

## The output format is as follows, in the form of a JSON structure:
{{
    "reasoning_explanation": xxx,
    "subtask_list": [
        {{"robot_name": xxx, "subtask": xxx, "subtask_order": xxx}},
        {{"robot_name": xxx, "subtask": xxx, "subtask_order": xxx}},
        {{"robot_name": xxx, "subtask": xxx, "subtask_order": xxx}},
    ]
}}

## Note: 'subtask_order' means the order of the sub-task. 
If the tasks are not sequential, please set the same 'task_order' for the same task. For example, if two robots are assigned to the two tasks, both of which are independance, they should share the same 'task_order'.
If the tasks are sequential, the 'task_order' should be set in the order of execution. For example, if the task_2 should be started after task_1, they should have different 'task_order'.

# The task to be completed is: {task}. Your output answer:
"""


REPAIR_PLANNING_PROMPT = """

## Robot Platform
- Robot: Fourier GR2 (dual-arm humanoid, 5-finger dexterous hands)
- Task domain: Industrial camera airtightness inspection (Hikvision)

## Atomic Skill Categories Available
- P (Perception): visual_localize, visual_inspect, qr_code_recognize, read_screen_result
- M (Motion): move_to_position, bimanual_sync_move, set_orientation, plan_path
- G (Grasping): open_hand, precision_pinch, force_controlled_grasp, lift_object
- O (Operation): place_object, press_dual_buttons, lens_cap_operation, fine_align
- C (Coordination): hand_transfer
- I (Interaction): wait_for_signal
- S (System): coordinate_transform

## Key Design Constraints
- Force-controlled grasps must stay within 0.5-2N to avoid lens damage
- All alignment operations require +/-0.3mm precision
- Bimanual sync operations must maintain time offset < 100ms
- All grasp operations should be preceded by visual_localize

## Available Resources
Robots: {robot_name_list}
Skills: {robot_tools_info}
Scene: {scene_info}

---

# REPAIR PLANNING — A previous execution attempt has FAILED.

## Replan Attempt: {replan_attempt} / {max_replan}

## Original Task
{original_task}

## Subtasks Already Completed Successfully (DO NOT repeat these)
{completed_summary}

## Failed Subtask
- Subtask description: {failed_subtask}
- Robot: {failed_robot}

## Failure Details
- Failed at skill: {failed_skill}
- Failed at step index: {failed_step_index} in the skill sequence
- Skills that succeeded before failure: {completed_skills_in_sequence}
- Failure reason: {failure_reason}
- Number of retries attempted: 3 (with rollback)
- Total rollbacks attempted: {total_rollbacks}

## Repair Instructions

You must generate a NEW plan to complete the REMAINING work of the original task.

Rules:
1. Do NOT repeat subtasks listed as "Already Completed Successfully" above.
2. Analyze the failure reason carefully. The failed skill "{failed_skill}" could not complete because: {failure_reason}
3. Generate a MODIFIED skill sequence that avoids the same failure. Consider:
   - Adding extra perception steps (visual_localize) before the failed skill
   - Using an alternative skill (e.g. precision_pinch instead of force_controlled_grasp)
   - Changing the approach order (e.g. orient the object differently before placement)
   - Adding fine_align before operations that require precision
   - Using plan_path to avoid collisions if the failure was movement-related
4. The new subtask MUST include "Execute the following skills strictly in order: ..." with the modified sequence.
5. Provide a 200+ word reasoning explanation that specifically addresses:
   - Why the previous attempt failed
   - What your repair strategy is
   - How the modified skill sequence avoids the same failure

## Output Format (JSON):
{{
    "reasoning_explanation": "Detailed analysis of failure and repair strategy...",
    "subtask_list": [
        {{"robot_name": xxx, "subtask": xxx, "subtask_order": xxx}},
    ]
}}

Your repair plan:
"""
