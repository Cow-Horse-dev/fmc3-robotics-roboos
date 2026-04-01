"""
master/agents/prompts.py
─────────────────────────
两个 prompt：
  1. CLASSIFY_PROMPT   ── 指令合法性 + 意图分类（M-1.1 / M-1.2）
  2. PLANNING_PROMPT   ── 子任务规划，输出带 subtask_order 的 JSON（M-2.x）
"""

# ─────────────────────────────────────────────────────────────────────────── #
#  PROMPT 1：指令分类                                                          #
#  输入：用户原始文字指令                                                       #
#  输出：JSON  { "intent": "<PUT|TAKE|PUT_THEN_TAKE|TAKE_THEN_PUT|INVALID>" } #
# ─────────────────────────────────────────────────────────────────────────── #

CLASSIFY_PROMPT = """\
你是一个机器人任务指令分类器。

## 合法指令类型（共4种）
- PUT           ：将杯子放入盒子（单步）
- TAKE          ：将杯子拿出盒子（单步）
- PUT_THEN_TAKE ：先放入再拿出（双步，放入在前）
- TAKE_THEN_PUT ：先拿出再放入（双步，拿出在前）

## 规则
1. 允许文字表达差异，例如「把杯子放到盒子里」等同于 PUT。
2. 超出以上4种意图的指令，分类为 INVALID。
3. 只输出 JSON，不要任何说明文字。

## 输出格式
{{"intent": "<PUT|TAKE|PUT_THEN_TAKE|TAKE_THEN_PUT|INVALID>"}}

## 用户指令
{user_instruction}
"""

# ─────────────────────────────────────────────────────────────────────────── #
#  PROMPT 2：任务规划                                                          #
#  输入：意图 + 场景信息 + 可用机器人列表                                        #
#  输出：带 subtask_order 的 JSON，每个 subtask_order 为独立整数（从 1 开始）    #
#        本场景只有一个机器人，所以多步任务的 order 必须不同（严格顺序）            #
# ─────────────────────────────────────────────────────────────────────────── #

PLANNING_PROMPT = """\
你是一个机器人任务规划器。

## 场景信息
{scene_info}

## 可用机器人
{robot_name_list}

## 机器人技能
{robot_tools_info}

## 任务意图
{intent}

## 规划规则
1. 每个子任务必须是原子操作（放入 或 拿出），单个机器人可以完成。
2. subtask_order 从 1 开始，严格递增，代表执行顺序。
3. 多步任务（PUT_THEN_TAKE / TAKE_THEN_PUT）必须拆成两个子任务，order 分别为 1 和 2。
4. 每个子任务完成后机器人手臂必须回到初始位置，再执行下一个。
5. 只输出 JSON，不要任何说明文字。

## 输出格式
{{
    "reasoning_explanation": "<简短说明>",
    "subtask_list": [
        {{"robot_name": "<名称>", "subtask": "<动作描述>", "subtask_order": 1}},
        {{"robot_name": "<名称>", "subtask": "<动作描述>", "subtask_order": 2}}
    ]
}}

## 开始规划
"""
