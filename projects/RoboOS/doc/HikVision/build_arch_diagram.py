"""
RoboOS System Architecture — Remote Communication Diagram
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch
import matplotlib.patheffects as pe

fig, ax = plt.subplots(figsize=(20, 13))
ax.set_xlim(0, 20)
ax.set_ylim(0, 13)
ax.axis("off")
fig.patch.set_facecolor("#0D1B2A")
ax.set_facecolor("#0D1B2A")

# ── Colour palette ────────────────────────────────────────────────────────────
C_BG      = "#0D1B2A"
C_PANEL   = "#162338"
C_BLUE    = "#0078D4"
C_CYAN    = "#00D4FF"
C_GREEN   = "#06D6A0"
C_ORANGE  = "#FF9500"
C_PURPLE  = "#A06CFF"
C_RED     = "#FF4466"
C_YELLOW  = "#FFD166"
C_WHITE   = "#FFFFFF"
C_LGRAY   = "#AABBCC"
C_DGRAY   = "#445566"

def box(ax, x, y, w, h, facecolor, edgecolor, radius=0.25, lw=2, alpha=1.0):
    b = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0,rounding_size={radius}",
                       facecolor=facecolor, edgecolor=edgecolor,
                       linewidth=lw, alpha=alpha, zorder=3)
    ax.add_patch(b)

def label(ax, x, y, text, size=10, color=C_WHITE, bold=False, ha="center", va="center", zorder=5):
    weight = "bold" if bold else "normal"
    ax.text(x, y, text, fontsize=size, color=color, ha=ha, va=va,
            fontweight=weight, zorder=zorder,
            fontfamily="monospace")

def tag(ax, x, y, text, color):
    """Small pill tag for port numbers."""
    ax.text(x, y, text, fontsize=8.5, color=C_BG, ha="center", va="center",
            fontweight="bold", zorder=6,
            bbox=dict(boxstyle="round,pad=0.25", facecolor=color,
                      edgecolor="none"))

def arrow(ax, x1, y1, x2, y2, color, label_text="", lw=2, style="->", ls="-"):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                linestyle=ls,
                                connectionstyle="arc3,rad=0.0"),
                zorder=4)
    if label_text:
        mx, my = (x1+x2)/2, (y1+y2)/2
        ax.text(mx, my, label_text, fontsize=7.5, color=color,
                ha="center", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=C_BG,
                          edgecolor=color, linewidth=0.8))

def curved_arrow(ax, x1, y1, x2, y2, color, label_text="", rad=0.25, lw=2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                                connectionstyle=f"arc3,rad={rad}"),
                zorder=4)
    if label_text:
        mx = (x1+x2)/2 + rad*(y2-y1)*0.4
        my = (y1+y2)/2 - rad*(x2-x1)*0.4
        ax.text(mx, my, label_text, fontsize=7.5, color=color,
                ha="center", va="center", zorder=6,
                bbox=dict(boxstyle="round,pad=0.2", facecolor=C_BG,
                          edgecolor=color, linewidth=0.8))

# ══════════════════════════════════════════════════════════════════════════════
# TITLE
# ══════════════════════════════════════════════════════════════════════════════
ax.text(10, 12.5, "RoboOS  ×  RoboBrain2.0  ×  RoboSkill   —   System Communication Architecture",
        fontsize=15, color=C_CYAN, ha="center", va="center",
        fontweight="bold", fontfamily="monospace", zorder=5)
ax.axhline(12.15, color=C_CYAN, lw=1.2, alpha=0.5, zorder=3)

# ══════════════════════════════════════════════════════════════════════════════
# REPO BANNERS (background lanes)
# ══════════════════════════════════════════════════════════════════════════════
# RoboBrain2.0 lane (top)
box(ax, 0.3, 9.6, 19.4, 2.2, "#0A1E32", C_BLUE, radius=0.3, lw=1.5, alpha=0.5)
ax.text(0.7, 11.6, "REPO 1 · RoboBrain2.0", fontsize=8, color=C_BLUE,
        fontweight="bold", fontfamily="monospace", zorder=5, alpha=0.9)

# RoboOS lane (middle)
box(ax, 0.3, 3.5, 19.4, 5.8, "#0A2018", C_GREEN, radius=0.3, lw=1.5, alpha=0.4)
ax.text(0.7, 9.1, "REPO 2 · RoboOS", fontsize=8, color=C_GREEN,
        fontweight="bold", fontfamily="monospace", zorder=5, alpha=0.9)

# RoboSkill lane (bottom)
box(ax, 0.3, 0.3, 19.4, 2.9, "#1A1030", C_PURPLE, radius=0.3, lw=1.5, alpha=0.4)
ax.text(0.7, 3.0, "REPO 3 · RoboSkill", fontsize=8, color=C_PURPLE,
        fontweight="bold", fontfamily="monospace", zorder=5, alpha=0.9)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: RoboBrain2.0 inference.py   (top centre)
# ══════════════════════════════════════════════════════════════════════════════
BX, BY, BW, BH = 6.8, 9.85, 6.4, 1.8
box(ax, BX, BY, BW, BH, "#0A2840", C_BLUE, lw=2)
box(ax, BX, BY+BH-0.38, BW, 0.38, C_BLUE, C_BLUE, lw=0)   # header strip
label(ax, BX+BW/2, BY+BH-0.19, "RoboBrain2.0  /  inference.py", size=10, bold=True, color=C_BG)
label(ax, BX+BW/2, BY+1.1, "FastAPI + vLLM  ·  OpenAI-compatible", size=9, color=C_LGRAY)
label(ax, BX+BW/2, BY+0.65, "/v1/chat/completions  (tool-calling enabled)", size=8.5, color=C_CYAN)
tag(ax, BX+BW/2, BY+0.22, "0.0.0.0 : 4567", C_BLUE)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: Redis   (top right)
# ══════════════════════════════════════════════════════════════════════════════
RX, RY, RW, RH = 14.5, 9.85, 4.8, 1.8
box(ax, RX, RY, RW, RH, "#2A1008", C_RED, lw=2)
box(ax, RX, RY+RH-0.38, RW, 0.38, C_RED, C_RED, lw=0)
label(ax, RX+RW/2, RY+RH-0.19, "Redis  /  redis-server", size=10, bold=True, color=C_BG)
label(ax, RX+RW/2, RY+1.1, "Pub/Sub message bus", size=9, color=C_LGRAY)
label(ax, RX+RW/2, RY+0.65, "Shared scene & agent state", size=8.5, color=C_RED)
tag(ax, RX+RW/2, RY+0.22, "127.0.0.1 : 6379", C_RED)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: Master   (middle left)
# ══════════════════════════════════════════════════════════════════════════════
MX, MY, MW, MH = 0.6, 5.6, 5.2, 3.1
box(ax, MX, MY, MW, MH, "#082818", C_GREEN, lw=2)
box(ax, MX, MY+MH-0.38, MW, 0.38, C_GREEN, C_GREEN, lw=0)
label(ax, MX+MW/2, MY+MH-0.19, "master/run.py  (Brain)", size=10, bold=True, color=C_BG)
label(ax, MX+MW/2, MY+2.35, "Flask + SocketIO", size=9, color=C_LGRAY)
label(ax, MX+MW/2, MY+1.85, "GlobalAgent + GlobalTaskPlanner", size=8.5, color=C_GREEN)
ax.plot([MX+0.2, MX+MW-0.2], [MY+1.6, MY+1.6], color=C_DGRAY, lw=0.8, zorder=4)
label(ax, MX+MW/2, MY+1.25, "POST  /publish_task", size=8, color=C_LGRAY)
label(ax, MX+MW/2, MY+0.88, "GET   /robot_status", size=8, color=C_LGRAY)
label(ax, MX+MW/2, MY+0.55, "GET   /system_status", size=8, color=C_LGRAY)
tag(ax, MX+MW/2, MY+0.18, "0.0.0.0 : 5000", C_GREEN)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: Slaver   (middle centre)
# ══════════════════════════════════════════════════════════════════════════════
SX, SY, SW, SH = 7.2, 5.6, 5.6, 3.1
box(ax, SX, SY, SW, SH, "#082818", C_GREEN, lw=2)
box(ax, SX, SY+SH-0.38, SW, 0.38, C_GREEN, C_GREEN, lw=0)
label(ax, SX+SW/2, SY+SH-0.19, "slaver/run.py  (Cerebellum)", size=10, bold=True, color=C_BG)
label(ax, SX+SW/2, SY+2.35, "ToolCallingAgent  (ReAct loop)", size=9, color=C_LGRAY)
label(ax, SX+SW/2, SY+1.9, "ToolMatcher  (semantic embedding)", size=8.5, color=C_GREEN)
label(ax, SX+SW/2, SY+1.5, "SceneMemory + AgentMemory", size=8.5, color=C_GREEN)
ax.plot([SX+0.2, SX+SW-0.2], [MY+1.3, MY+1.3], color=C_DGRAY, lw=0.8, zorder=4)
label(ax, SX+SW/2, SY+0.95, "Listens: roboos_to_{robot}", size=8, color=C_LGRAY)
label(ax, SX+SW/2, SY+0.58, "Replies: {robot}_to_RoboOS", size=8, color=C_LGRAY)
label(ax, SX+SW/2, SY+0.18, "no inbound port  (outbound only)", size=7.5,
      color=C_DGRAY)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: Deploy UI   (middle right)
# ══════════════════════════════════════════════════════════════════════════════
DX, DY, DW, DH = 14.0, 5.6, 5.6, 3.1
box(ax, DX, DY, DW, DH, "#1A1A08", C_YELLOW, lw=2)
box(ax, DX, DY+DH-0.38, DW, 0.38, C_YELLOW, C_YELLOW, lw=0)
label(ax, DX+DW/2, DY+DH-0.19, "deploy/run.py  (Dashboard)", size=10, bold=True, color=C_BG)
label(ax, DX+DW/2, DY+2.35, "Flask Web UI", size=9, color=C_LGRAY)
label(ax, DX+DW/2, DY+1.9, "Validates & starts all services", size=8.5, color=C_YELLOW)
ax.plot([DX+0.2, DX+DW-0.2], [DY+1.65, DY+1.65], color=C_DGRAY, lw=0.8, zorder=4)
label(ax, DX+DW/2, DY+1.25, "/api/validate-config", size=8, color=C_LGRAY)
label(ax, DX+DW/2, DY+0.88, "/api/start-master  /api/start-slaver", size=8, color=C_LGRAY)
label(ax, DX+DW/2, DY+0.55, "/api/start-inference", size=8, color=C_LGRAY)
tag(ax, DX+DW/2, DY+0.18, "0.0.0.0 : 8888", C_YELLOW)

# ══════════════════════════════════════════════════════════════════════════════
# NODE: RoboSkill GR2   (bottom centre)
# ══════════════════════════════════════════════════════════════════════════════
KX, KY, KW, KH = 5.5, 0.55, 9.0, 2.2
box(ax, KX, KY, KW, KH, "#150C28", C_PURPLE, lw=2)
box(ax, KX, KY+KH-0.38, KW, 0.38, C_PURPLE, C_PURPLE, lw=0)
label(ax, KX+KW/2, KY+KH-0.19,
      "RoboSkill / fmc3-robotics / fourier / gr2 / skill.py", size=10, bold=True, color=C_BG)
label(ax, KX+KW/2, KY+1.35, "FastMCP  ·  stateless HTTP  ·  19 atomic skills (P/M/G/O/C/I/S)", size=9, color=C_LGRAY)
label(ax, KX+KW/2, KY+0.88, "Connects to:  GR2 robot hardware via Fourier SDK", size=8.5, color=C_PURPLE)
tag(ax, KX+KW/2, KY+0.25, "0.0.0.0 : 8000   /mcp", C_PURPLE)

# ══════════════════════════════════════════════════════════════════════════════
# ARROWS
# ══════════════════════════════════════════════════════════════════════════════

# Master → RoboBrain (HTTP)
arrow(ax, MX+MW/2, MY+MH,
          BX+0.8,  BY,
      C_BLUE, "HTTP  /v1/chat/completions\n(task planning)", lw=1.8)

# Slaver → RoboBrain (HTTP)
arrow(ax, SX+SW/2, SY+SH,
          BX+BW/2, BY,
      C_BLUE, "HTTP  /v1/chat/completions\n(tool calling)", lw=1.8)

# Master ↔ Redis (both directions, offset slightly)
curved_arrow(ax, MX+MW, MY+MH-0.6,
                 RX,     RY+RH/2+0.3,
             C_RED, "PUB task → roboos_to_{robot}", rad=-0.25, lw=1.8)
curved_arrow(ax, RX,     RY+RH/2-0.3,
                 MX+MW,  MY+MH-1.1,
             C_RED, "SUB status ← {robot}_to_RoboOS", rad=-0.25, lw=1.8)

# Slaver ↔ Redis
curved_arrow(ax, SX+SW, SY+0.9,
                 RX,     RY+0.55,
             C_RED, "SUB  roboos_to_{robot}", rad=0.15, lw=1.8)
curved_arrow(ax, RX,     RY+0.25,
                 SX+SW,  SY+0.35,
             C_RED, "PUB  {robot}_to_RoboOS", rad=0.15, lw=1.8)

# Slaver → RoboSkill MCP (HTTP)
arrow(ax, SX+SW/2, SY,
          KX+KW*0.4, KY+KH,
      C_PURPLE, "HTTP  127.0.0.1:8000/mcp\n(MCP tool calls)", lw=2.2)

# Deploy → services (dashed, management)
arrow(ax, DX+DW/2, DY,
          DX+DW/2-2.5, MY+MH,
      C_YELLOW, "spawns process", lw=1.4, ls="dashed")
arrow(ax, DX+0.5, DY+MH/2,
          SX+SW,  SY+MH/2,
      C_YELLOW, "spawns process", lw=1.4, ls="dashed")

# Deploy validates Redis
arrow(ax, DX+DW/2, DY+DH,
          RX+RW/2, RY,
      C_RED, "validates\nRedis", lw=1.2, ls="dashed")

# Deploy validates MCP
arrow(ax, DX+0.8, DY,
          KX+KW*0.85, KY+KH,
      C_PURPLE, "validates /mcp", lw=1.2, ls="dashed")

# ══════════════════════════════════════════════════════════════════════════════
# LEGEND
# ══════════════════════════════════════════════════════════════════════════════
lx, ly = 0.55, 4.6
box(ax, lx, ly-0.55, 5.5, 0.75, C_PANEL, C_DGRAY, radius=0.15, lw=1)
legend_items = [
    (C_BLUE,   "HTTP  /v1/chat/completions"),
    (C_RED,    "Redis Pub/Sub"),
    (C_PURPLE, "HTTP MCP  :8000/mcp"),
    (C_YELLOW, "Process management (dashed)"),
]
for i, (col, txt) in enumerate(legend_items):
    lxx = lx + 0.15 + i * 1.35
    ax.plot([lxx, lxx+0.22], [ly-0.17, ly-0.17], color=col, lw=2.5)
    ax.text(lxx+0.28, ly-0.17, txt, fontsize=6.8, color=C_LGRAY,
            va="center", fontfamily="monospace")

# ══════════════════════════════════════════════════════════════════════════════
# PORT SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
tx, ty = 0.55, 3.3
box(ax, tx, ty-1.2, 6.2, 1.35, C_PANEL, C_DGRAY, radius=0.15, lw=1)
rows = [
    ("Port",  "Host",        "Repo",           "Process",              "Protocol"),
    ("4567",  "0.0.0.0",     "RoboBrain2.0",   "inference.py",         "HTTP OpenAI /v1"),
    ("5000",  "0.0.0.0",     "RoboOS",         "master/run.py",        "HTTP + WebSocket"),
    ("6379",  "127.0.0.1",   "Redis",          "redis-server",         "Redis Pub/Sub"),
    ("8000",  "0.0.0.0",     "RoboSkill",      "gr2/skill.py",         "HTTP MCP /mcp"),
    ("8888",  "0.0.0.0",     "RoboOS",         "deploy/run.py",        "HTTP Web UI"),
]
col_x = [tx+0.12, tx+0.72, tx+1.4, tx+2.7, tx+4.15]
row_colors = [C_CYAN, C_BLUE, C_GREEN, C_RED, C_PURPLE, C_YELLOW]
for ri, row in enumerate(rows):
    ry = ty - 0.05 - ri * 0.2
    bold = ri == 0
    color = C_WHITE if ri == 0 else C_LGRAY
    col_color = row_colors[ri] if ri > 0 else C_WHITE
    for ci, cell in enumerate(row):
        c = col_color if ci == 0 and ri > 0 else color
        sz = 7.0 if ri == 0 else 6.8
        ax.text(col_x[ci], ry, cell, fontsize=sz, color=c,
                va="center", fontweight="bold" if bold else "normal",
                fontfamily="monospace", zorder=5)

# ══════════════════════════════════════════════════════════════════════════════
# STARTUP ORDER
# ══════════════════════════════════════════════════════════════════════════════
ox, oy = 7.5, 3.3
box(ax, ox, oy-1.2, 12.1, 1.35, C_PANEL, C_DGRAY, radius=0.15, lw=1)
label(ax, ox+0.1, oy+0.02, "Startup Order:", size=8, bold=True, color=C_CYAN, ha="left")
steps = [
    ("[1]", C_RED,    "redis-server"),
    ("[2]", C_BLUE,   "RoboBrain2.0/inference.py  --port 4567"),
    ("[3]", C_PURPLE, "RoboSkill/.../gr2/skill.py   (port 8000)"),
    ("[4]", C_GREEN,  "RoboOS/master/run.py          (port 5000)"),
    ("[5]", C_GREEN,  "RoboOS/slaver/run.py"),
    ("[6]", C_YELLOW, "RoboOS/deploy/run.py          (port 8888)  [optional]"),
]
for i, (num, col, txt) in enumerate(steps):
    sx2 = ox + 0.15 + i * 2.0
    ax.text(sx2, oy-0.28, num, fontsize=8, color=col, va="center",
            fontweight="bold", fontfamily="monospace", zorder=5)
    ax.text(sx2, oy-0.62, txt, fontsize=6.5, color=C_LGRAY, va="center",
            fontfamily="monospace", zorder=5)
    if i < len(steps)-1:
        ax.annotate("", xy=(sx2+1.88, oy-0.42), xytext=(sx2+0.22, oy-0.42),
                    arrowprops=dict(arrowstyle="->", color=C_DGRAY, lw=1.0),
                    zorder=4)

# ══════════════════════════════════════════════════════════════════════════════
# SAVE
# ══════════════════════════════════════════════════════════════════════════════
OUT = "/home/haoanw/workspace/RoboOS/doc/system_architecture.png"
plt.tight_layout(pad=0)
plt.savefig(OUT, dpi=180, bbox_inches="tight",
            facecolor=C_BG, edgecolor="none")
plt.close()
print(f"Saved → {OUT}")
