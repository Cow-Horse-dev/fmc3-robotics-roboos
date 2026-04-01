# Bottle Demo — "抓杯子" 场景

基于 RoboOS + RoboSkill 的杯子操作演示，使用 Fourier GR2 双臂人形机器人完成杯子放入/取出白色纸盒的任务。

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                          用户端                                      │
│  curl / Web UI → POST /publish_task {"task": "将杯子放入盒子"}        │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP :5000
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Master (Brain)                                   │
│                     master/run.py                                    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  Flask API                                                    │    │
│  │  POST /publish_task   — 发布任务                               │    │
│  │  POST /stop_task      — 手动终止 (M-3.2)                      │    │
│  │  POST /reset          — 状态复位                               │    │
│  │  GET  /task_state     — 查询任务状态                           │    │
│  │  GET  /system_status  — 系统状态 + task_state                  │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                         │                                            │
│  ┌──────────────────────▼──────────────────────────────────────┐    │
│  │  GlobalAgent (agent.py)                                      │    │
│  │                                                               │    │
│  │  parse_bottle_demo_task()  ←── 确定性指令解析 (优先)           │    │
│  │       │  识别失败                                              │    │
│  │       ▼                                                       │    │
│  │  planner.classify(task)  ←── LLM 意图分类 (M-1.1/M-1.2)      │    │
│  │       │  INVALID → 拒绝                                       │    │
│  │       ▼  PUT/TAKE/...                                         │    │
│  │  planner.plan(intent)    ←── LLM 子任务规划 (M-2.x)           │    │
│  │       │                                                       │    │
│  │       ▼                                                       │    │
│  │  _dispatch_subtasks_async()  ←── 按 subtask_order 顺序下发    │    │
│  │       │                                                       │    │
│  │       ▼  (每个子任务执行期间)                                   │    │
│  │  VisionMonitor (vision_monitor.py)                             │    │
│  │  ├── 每 5 秒: USB 摄像头抓帧 → Gemini 场景监控                │    │
│  │  │   ├── 瓶子在不在盒子里? (bottle_in_box)                    │    │
│  │  │   └── 瓶子在黄色纸上还是绿色纸上? (bottle_on_paper)        │    │
│  │  └── Slaver 请求视觉判定 → 抓帧 → Gemini 判断 → 回传结果     │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                         │                                            │
│              Redis Pub/Sub: roboos_to_{robot_name}                   │
└────────────────────────┬────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     Slaver (Cerebellum)                               │
│                     slaver/run.py                                     │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  RobotManager                                                 │    │
│  │  ├── handle_task()  — 接收子任务                               │    │
│  │  ├── is_bottle_demo_task()?                                   │    │
│  │  │   ├── YES → SkillSequenceExecutor (确定性, 无 LLM)        │    │
│  │  │   │         SKILL_NAME_MAP: place_in→put_bottle_into_box  │    │
│  │  │   │         调用 skill → 请求 Master 视觉判定 → 决定结果   │    │
│  │  │   │         failed → initialization() → retry (最多 3×)   │    │
│  │  │   │         3× 失败 → stop + 回传 failure_info            │    │
│  │  │   └── NO  → ToolMatcher + ToolCallingAgent (ReAct/LLM)    │    │
│  │  └── _send_result() — 回传结果 + skill_state + failure_info   │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                         │                                            │
│              MCP Client (streamable-http)                             │
└────────────────────────┬────────────────────────────────────────────┘
                         │ HTTP :8000
                         ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     RoboSkill (MCP Skill Server)                     │
│                     fmc3-robotics/fourier/gr2/skill.py                │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  GR2Manager                                                   │    │
│  │  ├── connect()          — Aurora SDK (DDS) 连接               │    │
│  │  ├── start_pi0_server() — 启动 Pi0 推理服务                   │    │
│  │  ├── start_pi0_client() — 启动 Pi0 机器人客户端               │    │
│  │  └── move_to_initial_position() — Aurora SDK 直接控制         │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐    │
│  │  MCP Tools (FastMCP, port 8000)                               │    │
│  │                                                               │    │
│  │  @mcp.tool() put_bottle_into_box()     — 杯子放入盒子 (Pi0)  │    │
│  │  @mcp.tool() take_bottle_out_of_box()  — 杯子取出盒子 (Pi0)  │    │
│  │  @mcp.tool() stop_task()               — 停止当前推理任务     │    │
│  │  @mcp.tool() get_task_status()         — 查询推理状态         │    │
│  │  @mcp.tool() check_service_health()    — 健康检查             │    │
│  └──────────────────────────────────────────────────────────────┘    │
│                         │                                            │
│              Aurora SDK / Pi0 Model                                  │
│                         ▼                                            │
│                  Fourier GR2 Robot                                    │
└─────────────────────────────────────────────────────────────────────┘
```

### 共享状态 (Redis)

```
AGENT_REGISTRATION          — 机器人注册通道
roboos_to_{robot_name}      — Master → Slaver 子任务下发
{robot_name}_to_RoboOS      — Slaver → Master 结果回传
{robot_name}:info           — 机器人注册信息 (工具列表、状态)
SHORT_STATUS:{robot_name}   — 已完成动作历史
desk / box                  — 场景物体状态 (contains: [cup])
robot                       — 机器人状态 (position, holding, status)
vision_request:{robot_name} — Slaver → Master 视觉判定请求
vision_result:{robot_name}  — Master → Slaver 视觉判定结果
```

---

## 原子技能定义

### MCP Tool 名称与内部映射

Slaver 使用 `SKILL_NAME_MAP` 将 Master 下发的内部名称映射到实际 MCP tool 名：

| 内部名 (Master/Planner) | MCP Tool 名 (RoboSkill) | 描述 |
|---|---|---|
| `place_in` | `put_bottle_into_box()` | 将瓶子放入盒子 (Pi0 双臂推理) |
| `take_out` | `take_bottle_out_of_box()` | 从盒子取出瓶子 (Pi0 双臂推理) |
| `initialization` | `stop_task()` | 停止当前推理任务 |

### 其他 MCP Tools

| MCP Tool 名 | 描述 |
|---|---|
| `get_task_status()` | 查询当前推理任务状态 |
| `check_service_health()` | 检查 Pi0 推理服务健康状态 |

### Pi0 VLA 模型

- **输入**: 1路头部相机 + 1路腕部相机 + 1路第三人称相机 + 1路机器人状态 + 1路文本指令
- **输出**: 50步动作块 (29维动作向量), 15Hz 推理频率
- `put_bottle_into_box` 和 `take_bottle_out_of_box` 各训练一个独立 Pi0 模型
- Skill 通过 Unix socket 与 Pi0 推理服务通信 (`/tmp/gr2_dual_pi0_rgb_wrist.sock`)

### 成功/失败判定

**技能返回值不作为判定依据。** 成功/失败完全由 Master 端 VisionMonitor (Gemini) 通过摄像头场景判断决定：

| 技能 | 成功条件 (VisionMonitor) |
|------|-------------------------|
| `place_in` | `bottle_in_box == true` |
| `take_out` | `bottle_in_box == false` |

---

## 用户指令映射

| 指令 (中文) | 指令 (英文) | 技能序列 |
|------------|------------|---------|
| 将杯子放入盒子 | put cup in box | `place_in` |
| 将杯子拿出盒子 | take cup out of box | `take_out` |
| 先将杯子放入盒子，再拿出来 | put in then take out | `place_in` → `initialization` → `take_out` |
| 先将杯子拿出盒子，再放进去 | take out then put in | `take_out` → `initialization` → `place_in` |
| 放入-拿出-放入-... (挑战) | multi-step chain | 交替执行, 每步间插入 `initialization` |

Master 使用**确定性正则匹配** (`parse_bottle_demo_task()`) 解析指令, 无需 LLM。不匹配时回退到 LLM Planner。

---

## 任务状态机

### Master 任务状态 (M-0.x ~ M-3.x)

```
  init ──→ waiting ──→ running ──→ waiting (完成)
              ↑            │
              │            ▼
           reset ←──── stop (终止)
```

| 状态 | 含义 | 触发条件 |
|------|------|---------|
| `init` | 系统初始化中 | 启动时 |
| `waiting` | 等待用户指令 | 初始化完成 / 任务完成 / 手动 reset |
| `running` | 任务执行中 | 用户提交有效指令 |
| `stop` | 任务终止 | 3次连续失败 (M-3.1) / 手动终止 (M-3.2) |

### Slaver 技能状态 (S-2.x)

```
  ready ──→ running ──→ 请求 Master 视觉判定 ──→ finished (下一个技能)
                │                │
                │                ▼ (视觉判定失败)
                │             failed ──→ initialization() ──→ ready (重试, 最多3次)
                │                │
                │                ▼ (连续3次失败)
                │              stop ──→ initialization() ──→ 任务终止
                ▼
            外部终止 → stop
```

| 状态 | 含义 |
|------|------|
| `ready` | 前置条件满足, 可以开始 |
| `running` | 技能执行中 (Pi0 推理活跃) |
| `finished` | 技能完成 (Master VisionMonitor 场景确认通过) |
| `failed` | 技能失败 (Master VisionMonitor 判定场景不符合预期) |
| `stop` | 连续 3 次失败 / 外部终止信号 |

### 成功/失败判定流程 (VisionMonitor)

技能执行完成后，Slaver 不检查返回值，而是请求 Master 端 VisionMonitor 做场景判定：

```
Slaver                                   Master
  │                                        │
  ├── 调用 MCP skill (忽略返回值)            │
  │   (put_bottle_into_box / ...)          │
  │                                        │
  ├── 写 Redis: vision_request:{robot}  ──→ 发现请求
  │                                        ├── VisionMonitor 抓帧 → Gemini 判断
  │                                        ├── place_in: bottle_in_box==true → 成功
  │                                        ├── take_out: bottle_in_box==false → 成功
  │   轮询 ←── 写 Redis: vision_result:{robot}
  │                                        │
  ├── 成功 → finished                      │
  └── 失败 → initialization → retry        │
```

---

## Gemini 视觉判定 (VisionMonitor)

VisionMonitor 是任务成功/失败的**唯一判定依据**。Slaver 执行完技能后，请求 Master 通过 top-view USB 摄像头 + Gemini 视觉能力判断场景状态，决定技能是否成功。

### 判断场景

VisionMonitor 判断两种场景状态：

| 场景 | 字段 | 取值 | 含义 |
|------|------|------|------|
| 瓶子在不在盒子里 | `bottle_in_box` | `true` / `false` | 瓶子在盒内 / 不在盒内 |
| 瓶子在哪种颜色纸上 | `bottle_on_paper` | `"yellow"` / `"green"` / `null` | 在黄色纸上 / 绿色纸上 / 不在纸上或无法判断 |

### 双重角色

VisionMonitor 在任务执行中有两个角色：

1. **周期性场景监控** — 子任务执行期间，每 5 秒抓帧 + Gemini 判断，记录到事件日志
2. **技能结果判定** — Slaver 技能执行完毕后，请求 Master 做一次场景判定，决定 finished/failed

### 视觉判定协议

```
Slaver                                        Master
  │                                             │
  ├── 写 Redis: vision_request:{robot}     ──→  轮询发现请求
  │   {"skill_name": "place_in", ...}           │
  │                                             ├── VisionMonitor 抓帧
  │                                             ├── Gemini 判断场景状态
  │                                             ├── SKILL_SUCCESS_CRITERIA:
  │                                             │   place_in → bottle_in_box==true
  │                                             │   take_out → bottle_in_box==false
  │                                             │
  │   轮询 ←── 写 Redis: vision_result:{robot}
  │            {"success": true/false, "reason": "..."}
  │
  ├── success → finished
  └── failed  → retry (最多 3×)
```

### Gemini 判断格式

每次调用返回 (强制 JSON 输出 `response_mime_type: application/json`)：

```json
{
    "bottle_in_box": true,
    "bottle_on_paper": "yellow",
    "reason": "瓶子在盒子内，盒子放在黄色纸上",
    "confidence": 0.92
}
```

### 配置 (`master/config.yaml`)

```yaml
vision_monitor:
  enable: true                  # 是否启用视觉监控
  camera_id: /dev/video6        # USB 摄像头设备 ID
  api_key: "AIzaSy..."          # Google Gemini API key
  model: "gemini-3-flash-preview"  # Gemini 视觉模型
  interval_sec: 5.0             # 抓帧间隔 (秒)
  confidence_threshold: 0.7     # 置信度阈值 (低于此值假定成功)
```

### 依赖

```bash
pip install google-genai pillow opencv-python
```

### 事件类型

视觉监控产生的事件通过 `/task_state` API 返回：

| 事件类型 | 含义 |
|---------|------|
| `vision_start` | 开始监控某个子任务 |
| `vision_check` | 周期性场景状态检查 (每 5 秒) |
| `vision_judge_request` | 收到 Slaver 视觉判定请求 |
| `vision_judge_result` | 视觉判定结果 (成功/失败 + 原因) |

### 容错

- VisionMonitor 未启用 → 所有技能假定成功
- Gemini API 调用失败 → 假定成功 (不因视觉服务故障阻断任务)
- 置信度 < 0.7 → 假定成功 (不因低信心判断导致误判)
- Slaver 等待视觉结果超时 (默认 30s) → 假定成功

---

## 文件改动清单

### RoboOS (branch: `stand-alone-fmc3-bottle-demo`)

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `master/agents/prompts.py` | 重写 | 替换 Hikvision 9步工作流 → 杯子操作 3 技能 + 4 指令映射 |
| `master/agents/agent.py` | 重写 | 新增 `parse_bottle_demo_task()` 确定性解析; 任务状态管理; 失败终止逻辑; 执行事件日志; VisionMonitor 集成; `_handle_vision_judgment_request()` 处理 Slaver 视觉判定请求; `SKILL_SUCCESS_CRITERIA` 定义各技能成功条件 |
| `master/scene/profile.yaml` | 重写 | `desk` (contains: cup) + `box` (empty) |
| `master/run.py` | 修改 | 新增 `/stop_task`, `/reset`, `/task_state` 端点; 任务状态校验; `/task_state` 返回执行事件日志 |
| `master/agents/vision_monitor.py` | 新增 | Gemini 视觉监控: USB 摄像头抓帧 + 场景状态判断 (VisionMonitor, MonitorState, SceneState); 使用 `google-genai` SDK; `response_mime_type=application/json` 强制 JSON 输出 |
| `master/config.yaml` | 修改 | 新增 `vision_monitor` 配置段 (camera_id=/dev/video6, api_key, model=gemini-3-flash-preview, interval_sec=5.0, confidence_threshold=0.7) |

### RoboSkill (fmc3-robotics-roboos)

**Repo 路径**: `/home/haoanw/workspace/fmc3-robotics-roboos/projects/RoboSkill/fmc3-robotics/fourier/gr2`

| 文件 | 说明 |
|------|------|
| `skill_mock.py` | MCP Skill Server (FastMCP, port 8000): `put_bottle_into_box()`, `take_bottle_out_of_box()`, `stop_task()`, `get_task_status()`, `check_service_health()`; 通过 Unix socket 转发到 Pi0 推理服务 |

### Slaver (branch: `stand-alone-fmc3-bottle-demo`)

| 文件 | 改动类型 | 说明 |
|------|---------|------|
| `slaver/agents/skill_executor.py` | 新增 | `SkillSequenceExecutor` — 确定性技能调度器: 状态机 (ready/running/finished/failed/stop), 3次重试 + initialization() 恢复; `SKILL_NAME_MAP` 映射内部名→MCP tool名; 技能返回值不判定成功, 通过 `vision_judge` 回调请求 Master 视觉判定 |
| `slaver/run.py` | 修改 | `_execute_task()` 新增 bottle demo 分支; `_request_vision_judgment()` 通过 Redis key-value 请求 Master 视觉判定并轮询结果; `_send_result()` 新增 `skill_state` + `failure_info` 字段 |
| `slaver/config.yaml` | 修改 | 新增 `bottle_demo.max_retries` 配置 |

### Claude Code Commands

| 文件 | 说明 |
|------|------|
| `.claude/commands/demo_bottle/check-skills.md` | 审计技能覆盖率 |
| `.claude/commands/demo_bottle/check-state-machine.md` | 验证状态机实现 |
| `.claude/commands/demo_bottle/plan-task.md` | 生成任务执行计划 |
| `.claude/commands/demo_bottle/adapt-master.md` | 适配 Master 指南 |
| `.claude/commands/demo_bottle/adapt-slaver.md` | 适配 Slaver 指南 |
| `.claude/commands/demo_bottle/new-skill.md` | 新建技能脚手架 |

---

## 快速启动

### 1. 启动 Redis

```bash
redis-server
```

### 2. 启动 RoboSkill (MCP Skill Server)

```bash
cd /home/haoanw/workspace/fmc3-robotics-roboos/projects/RoboSkill/fmc3-robotics/fourier/gr2

# Mock 版本 (转发到 Pi0 推理服务 Unix socket)
python skill_mock.py
# MCP server 运行在 :8000
```

### 3. 启动 vLLM 推理服务 (可选, 仅 LLM fallback 需要)

```bash
vllm serve RoboBrain2.0-7B \
    --gpu-memory-utilization=0.9 \
    --max-model-len=10000 \
    --port=4567 \
    --trust-remote-code \
    --enable-auto-tool-choice \
    --tool-call-parser hermes \
    --chat-template deploy/templates/tool_chat_template_hermes.jinja
```

### 4. 启动 Master

```bash
cd master
python run.py
# Flask API 运行在 :5000
```

### 5. 启动 Slaver

```bash
cd slaver
python run.py
# 连接到 MCP skill server (:8000) 和 Redis
```

### 6. 发送任务

```bash
# 单步: 放入
curl -X POST http://localhost:5000/publish_task \
  -H "Content-Type: application/json" \
  -d '{"task": "将杯子放入盒子", "refresh": true}'

# 单步: 取出
curl -X POST http://localhost:5000/publish_task \
  -H "Content-Type: application/json" \
  -d '{"task": "将杯子拿出盒子", "refresh": true}'

# 多步: 放入再取出
curl -X POST http://localhost:5000/publish_task \
  -H "Content-Type: application/json" \
  -d '{"task": "先将杯子放入盒子，再拿出来", "refresh": true}'

# 挑战: 多步链式任务
curl -X POST http://localhost:5000/publish_task \
  -H "Content-Type: application/json" \
  -d '{"task": "放入-拿出-放入-拿出", "refresh": true}'

# 手动终止
curl -X POST http://localhost:5000/stop_task

# 状态复位
curl -X POST http://localhost:5000/reset

# 查询状态
curl http://localhost:5000/task_state
```

---

## API 参考

### Master API (port 5000)

| 端点 | 方法 | 说明 | 请求体 |
|------|------|------|--------|
| `/publish_task` | POST | 发布任务 | `{"task": "...", "refresh": true}` |
| `/publish_task` | GET | 健康检查 | — |
| `/stop_task` | POST | 手动终止当前任务 | — |
| `/reset` | POST | 从 stop 状态恢复到 waiting | — |
| `/task_state` | GET | 查询任务状态 + 执行事件日志 (含视觉监控事件) | — |
| `/system_status` | GET | CPU/内存 + task_state | — |
| `/robot_status` | GET | 所有已注册机器人状态 | — |

### `/task_state` 响应格式

```json
{
    "task_state": "running",
    "events": [
        {"time": "22:49:22", "type": "task_start",            "message": "收到指令: 将杯子放入盒子"},
        {"time": "22:49:22", "type": "plan_done",              "message": "指令 '将杯子放入盒子' → 1 个子任务: place_in"},
        {"time": "22:49:22", "type": "state",                  "message": "waiting → running"},
        {"time": "22:49:22", "type": "dispatch",               "message": "子任务 1/1: place_in → fourier_gr2"},
        {"time": "22:49:32", "type": "vision_judge_request",   "message": "fourier_gr2 请求视觉判定: place_in"},
        {"time": "22:49:36", "type": "vision_judge_result",    "message": "place_in → 成功: bottle in box, not on colored paper (confidence: 98%)"},
        {"time": "22:49:36", "type": "skill_done",             "message": "fourier_gr2: place_in → success"},
        {"time": "22:49:36", "type": "task_done",              "message": "任务 '将杯子放入盒子' 调度结束"}
    ]
}
```

| 事件类型 | 含义 |
|---------|------|
| `task_start` | 收到用户指令 |
| `plan_done` / `plan_fail` | 规划结果 |
| `state` | Master 状态变化 |
| `dispatch` | 子任务派发到机器人 |
| `vision_judge_request` | 收到 Slaver 视觉判定请求 |
| `vision_judge_result` | 视觉判定结果 (成功/失败) |
| `skill_done` / `skill_fail` | Slaver 技能最终结果 |
| `vision_check` | 周期性场景监控 (每 5 秒) |
| `task_stop` | 连续失败终止 |
| `task_done` | 任务完成 |

### 任务结果 Payload (Slaver → Master via Redis)

```json
{
    "robot_name": "fourier_gr2",
    "subtask_handle": "place_in",
    "subtask_result": "place_in: success — bottle in box, not on colored paper (confidence: 98%): 瓶子在盒子内",
    "skill_state": "finished",
    "tools": [{"tool_name": "place_in", "tool_arguments": "{}"}],
    "task_id": "abc123",
    "failure_info": null
}
```

失败终止时 (连续 3 次视觉判定失败):

```json
{
    "robot_name": "fourier_gr2",
    "subtask_handle": "place_in",
    "subtask_result": "Task terminated: place_in failed 3 consecutive times",
    "skill_state": "stop",
    "tools": [{"tool_name": "place_in", "tool_arguments": "{}"}],
    "task_id": "abc123",
    "failure_info": {
        "failed_skill": "place_in",
        "attempts": 3,
        "last_error": "bottle not in box, not on colored paper (confidence: 95%): The bottle is on the table"
    }
}
```

---

## 配置参考

### Slaver config.yaml (关键字段)

```yaml
robot:
  name: fourier_gr2
  call_type: remote
  path: "http://127.0.0.1:8000"

tool:
  support_tool_calls: true
  matching:
    max_tools: 5
    min_similarity: 0.1

bottle_demo:
  max_retries: 3              # 连续失败最大重试次数
  vision_judge_timeout: 30    # 等待 Master 视觉判定超时 (秒)
```

### Master scene/profile.yaml

```yaml
scene:
  - name: desk
    type: surface
    contains:
      - cup

  - name: box
    type: container
    contains: []
```

### RoboSkill 环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GR2_DOMAIN_ID` | `123` | Aurora SDK DDS domain ID |
| `GR2_ROBOT_NAME` | `gr2` | 机器人名称 |
| `PI0_SERVER_HOST` | `127.0.0.1` | Pi0 推理服务地址 |
| `PI0_SERVER_PORT` | `8080` | Pi0 推理服务端口 |
| `PI0_DEVICE` | `cuda` | Pi0 推理设备 |
| `PI0_FPS` | `15` | Pi0 推理频率 |
| `PI0_PLACE_IN_MODEL` | `/home/haoanw/DataCenter/pi0_place_in` | place_in 模型路径 |
| `PI0_TAKE_OUT_MODEL` | `/home/haoanw/DataCenter/pi0_take_out` | take_out 模型路径 |

---

## 待实现 (TODO)

- [x] **Slaver 状态机集成** — `SkillSequenceExecutor` 实现确定性技能调度 + 3次重试 + initialization() 恢复 + 任务终止
- [x] **VisionMonitor 视觉判定** — Gemini (gemini-3-flash-preview) + USB 摄像头, 作为技能成功/失败的唯一判定依据
- [x] **Slaver ↔ Master 视觉判定协议** — 通过 Redis key-value (`vision_request` / `vision_result`) 实现 Slaver 请求判定 → Master 回传结果
- [x] **SKILL_NAME_MAP** — Slaver 内部名 (place_in/take_out) 映射到新 RoboSkill MCP tool 名 (put_bottle_into_box/take_bottle_out_of_box)
- [x] **新 RoboSkill Repo 对接** — 已对接 `fmc3-robotics-roboos` 项目的 MCP Skill Server
- [ ] **前端 UI** — 任务状态实时展示 (SocketIO 推送)
- [ ] **Slaver 状态反馈** — 每秒向 Master 反馈 1 次技能状态 (S-2.5)
