#!/usr/bin/env python3
"""Generate full 3-repo architecture diagram — clean version without text overlap."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ─── Canvas ───
fig, ax = plt.subplots(figsize=(26, 18))
ax.set_xlim(0, 26)
ax.set_ylim(0, 18)
ax.axis("off")
fig.patch.set_facecolor("white")

# ─── Colors ───
C_ROBOOS  = "#dce8f5"
C_BRAIN   = "#fef3e2"
C_SKILL   = "#e4f3e6"
C_REDIS   = "#fde0e6"
C_DEPLOY  = "#ede4f5"
C_MASTER  = "#b5cef0"
C_SLAVER  = "#b5cef0"
C_REPAIR  = "#fff8c4"
C_BRAIN_I = "#ffd9a0"
C_SKILL_I = "#b8ddb9"

COL_HTTP  = "#d84315"
COL_REDIS = "#b71c1c"
COL_MCP   = "#1b5e20"
COL_FAIL  = "#c62828"
COL_REPLAN = "#ef6c00"


# ─── Helpers ───
def box(x, y, w, h, fc, ec="#90a4ae", lw=1.5, zorder=1):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.2",
                       fc=fc, ec=ec, lw=lw, zorder=zorder)
    ax.add_patch(p)

def label(x, y, text, fs=9, color="#263238", ha="center", va="center",
          fw="normal", style="normal"):
    ax.text(x, y, text, fontsize=fs, color=color, ha=ha, va=va,
            fontweight=fw, fontstyle=style, zorder=10)

def arrow(x1, y1, x2, y2, color="#546e7a", lw=2, cs="arc3,rad=0", ms=16):
    a = FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", color=color,
                        lw=lw, connectionstyle=cs, mutation_scale=ms, zorder=5)
    ax.add_patch(a)

def arrow_label(x, y, text, color="#546e7a", fs=8):
    ax.text(x, y, text, fontsize=fs, color=color, ha="center", va="center",
            fontweight="bold", zorder=10,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.92))


# ═══════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════
label(13, 17.5, "RoboOS + RoboBrain2.0 + RoboSkill  |  Full System Architecture",
      fs=17, fw="bold", color="#1a237e")
label(13, 17.0, "Fourier GR2 Dual-Arm Humanoid  |  Hikvision Camera Airtightness Inspection",
      fs=11, color="#5c6bc0")


# ═══════════════════════════════════════════════════════════════
# REPO BOUNDARIES
# ═══════════════════════════════════════════════════════════════
box(0.3, 1.5, 16.4, 15.0, C_ROBOOS, ec="#64b5f6", lw=2)
label(1.2, 16.1, "RoboOS", fs=14, fw="bold", color="#1565c0", ha="left")
label(3.7, 16.1, "~/workspace/RoboOS", fs=9, color="#78909c", ha="left", style="italic")

box(17.5, 8.8, 8.0, 7.7, C_BRAIN, ec="#ffb74d", lw=2)
label(18.2, 16.1, "RoboBrain2.0", fs=14, fw="bold", color="#e65100", ha="left")
label(21.7, 16.1, "~/workspace/RoboBrain2.0", fs=9, color="#78909c", ha="left", style="italic")

box(17.5, 1.5, 8.0, 6.5, C_SKILL, ec="#81c784", lw=2)
label(18.2, 7.6, "RoboSkill", fs=14, fw="bold", color="#2e7d32", ha="left")
label(20.5, 7.6, "~/workspace/RoboSkill", fs=9, color="#78909c", ha="left", style="italic")


# ═══════════════════════════════════════════════════════════════
# DEPLOY WEB UI
# ═══════════════════════════════════════════════════════════════
box(0.8, 13.8, 4.5, 2.0, C_DEPLOY)
label(3.05, 15.35, "Deploy Web UI", fs=11, fw="bold", color="#4a148c")
label(3.05, 14.9, "Flask  :8888", fs=9, color="#6a1b9a")
label(3.05, 14.5, "deploy/run.py", fs=8, color="#9e9e9e")
label(3.05, 14.1, "release.html (9 workflow cards)", fs=8, color="#9e9e9e")


# ═══════════════════════════════════════════════════════════════
# MASTER
# ═══════════════════════════════════════════════════════════════
box(6.0, 13.0, 5.5, 3.0, C_MASTER)
label(8.75, 15.55, "Master", fs=12, fw="bold", color="#0d47a1")
label(8.75, 15.15, "Flask  :5000  |  master/run.py", fs=9, color="#1565c0")

label(8.75, 14.6, "GlobalAgent  (agent.py)", fs=9, fw="bold", color="#1565c0")
label(8.75, 14.25, "_handle_result()  +  _do_replan()", fs=8, color="#37474f")

label(8.75, 13.7, "GlobalTaskPlanner  (planner.py)", fs=9, fw="bold", color="#1565c0")
label(8.75, 13.35, "forward()  +  repair_forward()", fs=8, color="#37474f")


# ═══════════════════════════════════════════════════════════════
# PROMPT REPAIR ENGINE
# ═══════════════════════════════════════════════════════════════
box(12.2, 13.0, 4.0, 1.8, C_REPAIR)
label(14.2, 14.4, "PromptRepairEngine", fs=10, fw="bold", color="#f57f17")
label(14.2, 13.95, "prompt_repair.py", fs=8, color="#9e9e9e")
label(14.2, 13.55, "REPAIR_PLANNING_PROMPT", fs=8, color="#9e9e9e")
label(14.2, 13.2, "Failure analysis + new plan", fs=8, color="#ef6c00", style="italic")


# ═══════════════════════════════════════════════════════════════
# REDIS
# ═══════════════════════════════════════════════════════════════
box(6.0, 9.5, 5.5, 2.8, C_REDIS)
label(8.75, 11.9, "Redis", fs=12, fw="bold", color="#b71c1c")
label(8.75, 11.5, "127.0.0.1:6379  |  Pub/Sub", fs=9, color="#c62828")

label(8.75, 10.9, "Channels:", fs=9, fw="bold", color="#c62828")
label(8.75, 10.5, "roboos_to_{robot}   Master -> Slaver", fs=8, color="#37474f")
label(8.75, 10.15, "{robot}_to_RoboOS   Slaver -> Master", fs=8, color="#37474f")
label(8.75, 9.8, "AGENT_REGISTRATION  |  Heartbeat", fs=8, color="#37474f")


# ═══════════════════════════════════════════════════════════════
# SLAVER
# ═══════════════════════════════════════════════════════════════
box(0.8, 2.0, 7.5, 6.8, C_SLAVER)
label(4.55, 8.4, "Slaver  (gr2_robot)", fs=12, fw="bold", color="#0d47a1")
label(4.55, 8.0, "asyncio  |  slaver/run.py", fs=9, color="#1565c0")

label(4.55, 7.4, "RobotManager", fs=10, fw="bold", color="#1565c0")
label(4.55, 7.0, "MCP ClientSession  |  ToolMatcher", fs=8, color="#37474f")

label(4.55, 6.4, "Execution Engine (2 paths):", fs=9, fw="bold", color="#1565c0")

# ReAct box
box(1.2, 4.8, 2.8, 1.3, "#e1f5fe", ec="#90caf9")
label(2.6, 5.8, "ReAct Loop", fs=9, fw="bold", color="#0d47a1")
label(2.6, 5.4, "ToolCallingAgent", fs=8, color="#37474f")
label(2.6, 5.05, "LLM-driven", fs=8, color="#78909c", style="italic")

# StateMachine box
box(4.4, 4.8, 3.5, 1.3, "#e1f5fe", ec="#90caf9")
label(6.15, 5.8, "State Machine", fs=9, fw="bold", color="#0d47a1")
label(6.15, 5.4, "SkillSequenceExecutor", fs=8, color="#37474f")
label(6.15, 5.05, "Retry + Rollback", fs=8, color="#78909c", style="italic")

# Decision routing
label(4.55, 4.4, 'Task has "Execute skills in order" ?', fs=8, color="#0d47a1", style="italic")
arrow(3.4, 4.4, 2.6, 4.8, color="#0d47a1", lw=1, ms=10)
label(2.8, 4.5, "No", fs=7, color="#0d47a1", fw="bold")
arrow(5.6, 4.4, 6.15, 4.8, color="#0d47a1", lw=1, ms=10)
label(6.0, 4.5, "Yes", fs=7, color="#0d47a1", fw="bold")

# Retry/rollback info
label(4.55, 3.6, "Retry 3x per skill  |  Rollback to prev", fs=8, color="#1b5e20")
label(4.55, 3.2, "Max 3 rollbacks  |  Then report failure", fs=8, color="#1b5e20")
label(4.55, 2.5, "failure_info: {skill, reason, completed_steps}", fs=7,
      color="#c62828", style="italic")


# ═══════════════════════════════════════════════════════════════
# ROBOBRAIN2.0 INTERNALS
# ═══════════════════════════════════════════════════════════════
box(18.0, 9.3, 7.0, 6.7, C_BRAIN_I)
label(21.5, 15.55, "RoboBrain Inference", fs=12, fw="bold", color="#e65100")
label(21.5, 15.1, "FastAPI  :4567  |  inference.py", fs=9, color="#bf360c")

label(21.5, 14.3, "UnifiedInference", fs=10, fw="bold", color="#e65100")
label(21.5, 13.85, "/v1/chat/completions", fs=9, color="#37474f")
label(21.5, 13.45, "(OpenAI-compatible API)", fs=8, color="#78909c")

label(21.5, 12.7, "Qwen2.5-VL-3B  model", fs=9, fw="bold", color="#e65100")
label(21.5, 12.3, "Heuristic tool calling", fs=9, color="#37474f")

label(21.5, 11.6, "_extract_tool_args()", fs=9, fw="bold", color="#e65100")
label(21.5, 11.2, "tool_name + arguments from prompt", fs=8, color="#37474f")

label(21.5, 10.5, "ToolMatcher", fs=9, fw="bold", color="#e65100")
label(21.5, 10.1, "sentence-transformer  (all-MiniLM-L6-v2)", fs=8, color="#37474f")
label(21.5, 9.7, "Top-5 tool filtering", fs=8, color="#78909c")


# ═══════════════════════════════════════════════════════════════
# ROBOSKILL INTERNALS
# ═══════════════════════════════════════════════════════════════
box(18.0, 1.8, 7.0, 5.5, C_SKILL_I)
label(21.5, 6.9, "RoboSkill  GR2", fs=12, fw="bold", color="#2e7d32")
label(21.5, 6.5, "FastMCP  :8000  |  skill.py", fs=9, color="#1b5e20")

label(21.5, 5.9, "MCP Tools  (20 skills)", fs=10, fw="bold", color="#2e7d32")

label(19.8, 5.35, "P:", fs=8, fw="bold", color="#2e7d32", ha="left")
label(20.5, 5.35, "visual_localize, visual_inspect", fs=8, color="#37474f", ha="left")
label(20.5, 5.0, "qr_code_recognize, read_screen_result", fs=8, color="#37474f", ha="left")

label(19.8, 4.55, "M:", fs=8, fw="bold", color="#2e7d32", ha="left")
label(20.5, 4.55, "move_to_position, bimanual_sync_move", fs=8, color="#37474f", ha="left")
label(20.5, 4.2, "set_orientation, plan_path", fs=8, color="#37474f", ha="left")

label(19.8, 3.75, "G:", fs=8, fw="bold", color="#2e7d32", ha="left")
label(20.5, 3.75, "open_hand, precision_pinch", fs=8, color="#37474f", ha="left")
label(20.5, 3.4, "force_controlled_grasp, lift_object", fs=8, color="#37474f", ha="left")

label(19.8, 2.95, "O:", fs=8, fw="bold", color="#2e7d32", ha="left")
label(20.5, 2.95, "place_object, press_dual_buttons", fs=8, color="#37474f", ha="left")
label(20.5, 2.6, "lens_cap_operation, fine_align", fs=8, color="#37474f", ha="left")

label(19.8, 2.2, "C/I/S:", fs=8, fw="bold", color="#2e7d32", ha="left")
label(21.0, 2.2, "hand_transfer, wait_for_signal, coordinate_transform", fs=8, color="#37474f", ha="left")


# ═══════════════════════════════════════════════════════════════
# ARROWS
# ═══════════════════════════════════════════════════════════════

# [1] Deploy → Master
arrow(5.3, 14.8, 6.0, 14.8, color=COL_HTTP, lw=2)
arrow_label(5.65, 15.1, "HTTP POST\n/publish_task", color=COL_HTTP, fs=7)

# [2] Master → Redis  (publish task)
arrow(8.2, 13.0, 8.2, 12.3, color=COL_REDIS, lw=2)
arrow_label(9.4, 12.6, "Pub task", color=COL_REDIS, fs=7)

# [3] Redis → Master  (subscribe result)
arrow(9.3, 12.3, 9.3, 13.0, color=COL_REDIS, lw=2)
arrow_label(10.4, 12.6, "Sub result", color=COL_REDIS, fs=7)

# [4] Redis → Slaver  (task dispatch)
arrow(6.0, 10.3, 4.8, 8.8, color=COL_REDIS, lw=2)
arrow_label(4.4, 9.8, "Sub: roboos_to_gr2_robot", color=COL_REDIS, fs=7)

# [5] Slaver → Redis  (result / failure)
arrow(5.5, 8.8, 7.0, 9.5, color=COL_REDIS, lw=2)
arrow_label(7.3, 9.0, "Pub: gr2_robot_to_RoboOS", color=COL_REDIS, fs=7)

# [6] Slaver → RoboSkill  (MCP)
arrow(8.3, 5.3, 18.0, 4.5, color=COL_MCP, lw=2.5)
arrow_label(13.0, 5.3, "MCP  streamable-http\nCallToolRequest / Response", color=COL_MCP, fs=8)

# [7] Slaver → RoboBrain  (ReAct LLM calls)
arrow(4.0, 8.8, 18.0, 12.5, color=COL_HTTP, lw=1.5)
arrow_label(10.5, 11.5, "HTTP  /v1/chat/completions\nReAct: Think -> Act -> Observe", color=COL_HTTP, fs=8)

# [8] Master → RoboBrain  (planning calls)
arrow(11.5, 15.0, 18.0, 14.5, color=COL_HTTP, lw=2)
arrow_label(14.8, 15.1, "HTTP  /v1/chat/completions\nPlanning: forward / repair_forward", color=COL_HTTP, fs=8)

# [9] PromptRepair → Master planner
arrow(12.2, 14.0, 11.5, 14.0, color=COL_REPLAN, lw=2)
arrow_label(11.85, 14.35, "repair\nprompt", color=COL_REPLAN, fs=7)

# [10] Failure path: Slaver → PromptRepair  (via Redis, conceptual)
arrow(8.0, 3.0, 13.5, 13.0, color=COL_FAIL, lw=1.5, cs="arc3,rad=0.25")
arrow_label(11.8, 8.0, "failure_info via Redis\n-> _handle_result()\n-> _do_replan()", color=COL_FAIL, fs=7)

# [11] Replan loop: PromptRepair → RoboBrain → new plan back
arrow(16.2, 14.2, 18.0, 14.0, color=COL_REPLAN, lw=2)
arrow_label(17.1, 14.55, "Replan\n(max 3x)", color=COL_REPLAN, fs=7)


# ═══════════════════════════════════════════════════════════════
# LEGEND
# ═══════════════════════════════════════════════════════════════
ly = 0.7
label(0.8, ly, "Legend:", fs=10, fw="bold", ha="left")
legend_items = [
    (COL_HTTP,   "HTTP REST / OpenAI API"),
    (COL_REDIS,  "Redis Pub/Sub"),
    (COL_MCP,    "MCP (streamable-http)"),
    (COL_FAIL,   "Failure info (via Redis)"),
    (COL_REPLAN, "Replan loop"),
]
for i, (c, t) in enumerate(legend_items):
    lx = 3.5 + i * 4.6
    ax.plot([lx, lx + 0.7], [ly, ly], color=c, lw=3, zorder=10)
    label(lx + 0.9, ly, t, fs=8, fw="bold", color=c, ha="left")

# Port summary
label(13, 0.15,
      "Ports:   Deploy :8888   |   Master :5000   |   RoboBrain :4567   |   RoboSkill :8000   |   Redis :6379",
      fs=10, fw="bold", color="#37474f")

plt.savefig("/home/haoanw/workspace/RoboOS/doc/full_system_architecture.png",
            dpi=200, bbox_inches="tight", facecolor="white")
print("Saved to /home/haoanw/workspace/RoboOS/doc/full_system_architecture.png")
