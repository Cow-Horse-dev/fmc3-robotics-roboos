MASTER_PLANNING_PLANNING = """

Please only use {robot_name_list} with skills {robot_tools_info}.
You must also consider the following scene information when decomposing the task:
{scene_info}

SPECIAL RULE (HIGHEST PRIORITY):
If any robot exposes a tool named "execute_manipulation_task", treat it as an atomic end-to-end manipulation executor.
Only trigger this rule for a clear single-object pick-and-place intent:
- the task must include a pick/grasp/take action and a place/put action with a destination.
- examples: "pick bottle and place into box", "grab apple and put it in bowl", "抓起杯子放到桌上".
Do NOT trigger this rule for navigation, inspection, reporting, diagnostics, service control, or multi-stage tasks, even if they contain words like "move", "to", or "and".
When this rule is triggered, DO NOT decompose the task.
Return exactly ONE subtask assigned to that robot.
Set the subtask text to: "execute_manipulation_task: {task}".
Set subtask_order to 1.

For all other tasks that do not match the rule above, break down the given task into sub-tasks, each of which cannot be too complex, make sure that a single robot can do it.
Each sub-task in the output needs a concise name of the sub-task, which includes the robots that need to complete the sub-task. 
Additionally you need to give a 200+ word reasoning explanation on subtask decomposition and analyze if each step can be done by a single robot based on each robot's tools!

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
When the SPECIAL RULE is triggered, subtask_list must contain only one item.

# The task to be completed is: {task}. Your output answer:
"""
