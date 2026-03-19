MASTER_PLANNING_PLANNING = """

Please only use {robot_name_list} with skills {robot_tools_info}.
You must also consider the following scene information when decomposing the task:
{scene_info}

CRITICAL RULES:
1. The subtask field MUST contain ONLY the exact tool name from the robot's available tools list above.
2. DO NOT invent new tool names. DO NOT use descriptions.
3. For example, if the available tools include "take_bottle_out_of_box", then the subtask must be exactly "take_bottle_out_of_box", NOT "open_container" or "select_bottle_from_container".

Example of CORRECT output:
{{
    "reasoning_explanation": "The task requires taking a bottle out of the box. The robot has a tool called 'take_bottle_out_of_box' which directly accomplishes this task.",
    "subtask_list": [
        {{"robot_name": "fourier_gr2", "subtask": "take_bottle_out_of_box", "subtask_order": 1}}
    ]
}}

Example of WRONG output (DO NOT DO THIS):
{{
    "subtask_list": [
        {{"robot_name": "robot1", "subtask": "open_container", "subtask_order": 1}},
        {{"robot_name": "robot1", "subtask": "select_bottle", "subtask_order": 2}}
    ]
}}

Break down the given task into sub-tasks using ONLY the exact tool names from the robot's available tools.
Each sub-task must use an exact tool name that exists in the robot's tools list.
Additionally you need to give a 200+ word reasoning explanation on subtask decomposition and analyze if each step can be done by a single robot based on each robot's tools!

## The output format is as follows, in the form of a JSON structure:
{{
    "reasoning_explanation": xxx,
    "subtask_list": [
        {{"robot_name": xxx, "subtask": "exact_tool_name_here", "subtask_order": xxx}},
        {{"robot_name": xxx, "subtask": "exact_tool_name_here", "subtask_order": xxx}},
    ]
}}

## Note: 'subtask_order' means the order of the sub-task.
If the tasks are not sequential, please set the same 'task_order' for the same task.
If the tasks are sequential, the 'task_order' should be set in the order of execution.

# The task to be completed is: {task}. Your output answer:
"""
