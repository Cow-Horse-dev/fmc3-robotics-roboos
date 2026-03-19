# fmc3-robotics

> "The best way to predict the future is to invent it." — Alan Kay

**FMC3 Robotics** 是一个多项目机器人工作空间，围绕 **Fourier 人形机器人（GR-2 / GR-3）** 构建。核心工作流程为：

**遥操作采集示教数据 → 转换为 LeRobot 数据集 → 训练策略模型（ACT / Diffusion / PI0 / VLA） → 通过 RoboOS 部署到机器人**

---

## 项目结构

```
fmc3-robotics/
├── projects/
│   ├── RoboBrain2.0/        # 机器人视觉语言模型（基于 Qwen2.5-VL）
│   ├── RoboOS/              # 多智能体任务编排系统（Master-Slaver 架构）
│   ├── RoboSkill/           # 基于 MCP 的通用技能库
│   ├── fourier/
│   │   ├── Robot/           # GR-2 高层控制 API（基于 Aurora SDK）
│   │   ├── demo/            # 演示代码
│   │   └── Tools/           # 工具脚本
│   ├── lerobot/             # LeRobot 相关示例脚本
│   └── scripts/
│       └── convert_tools/   # Dora-Record → LeRobot v3.0 数据集转换工具
```

## 项目说明

| 项目 | 路径 | 说明 |
|------|------|------|
| **RoboBrain 2.0** | `projects/RoboBrain2.0/` | 基于 Qwen2.5-VL 的机器人视觉语言模型，用于感知与规划 |
| **RoboOS** | `projects/RoboOS/` | 多智能体任务编排系统，Master 分解任务 → Slaver 通过 Redis 执行 |
| **RoboSkill** | `projects/RoboSkill/` | 基于 MCP 协议的通用机器人技能库 |
| **GR2Robot Wrapper** | `projects/fourier/Robot/` | GR-2 机器人高层控制 API，封装 Aurora SDK（DDS） |
| **数据集转换工具** | `projects/scripts/convert_tools/` | Dora-Record 格式到 LeRobot v3.0 格式的转换工具 |

## 快速开始

### RoboBrain 2.0 — 模型服务

```bash
conda activate robobrain2
cd projects/RoboBrain2.0
bash startup.sh  # 启动 vLLM 服务，端口 4567
```

### RoboOS — 全栈启动

```bash
# 前置条件：redis-server 已运行，vLLM 模型服务已在 4567 端口启动
cd projects/RoboOS
python master/run.py    # Master 智能体（Flask :5000）
python slaver/run.py    # Slaver 智能体（连接机器人）
python deploy/run.py    # Web UI: http://127.0.0.1:8888

# 发送任务
curl -X POST http://localhost:5000/publish_task \
  -H 'Content-Type: application/json' \
  -d '{"task": "pick up the apple"}'
```

### GR-2 机器人控制

```bash
conda activate fourier-robot
cd projects/fourier/Robot
python example.py
```

### 数据集转换（Dora-Record → LeRobot v3.0）

```bash
conda activate lerobot
cd projects/scripts/convert_tools
python convert_dora_to_lerobot.py \
    --input ./dora-record/<session_id> \
    --output ./pick_and_place \
    --task "grab the bottle" \
    --fps 30 \
    --robot-type fourier_gr2 \
    --video-codec libopenh264
```

### MCP 技能开发

```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill.py     # 运行技能服务
mcp dev skill.py    # 开发模式（Inspector）
```

## 系统架构

### RoboOS Master-Slaver 通信

- **Master**（`master/run.py`）通过 RoboBrain VLM 将自然语言任务分解为子任务
- **Slaver**（`slaver/run.py`）通过 Redis pub/sub（localhost:6379）接收子任务，并通过语义相似度匹配 MCP 技能执行
- 场景配置：`master/scene/profile.yaml` 定义可用的机器人和能力

### GR-2 机器人控制组

通过 Aurora SDK（DDS）按关节组控制：

| 控制组 | 关节数 | 说明 |
|--------|--------|------|
| `left_manipulator` / `right_manipulator` | 7 × 2 | 肩部俯仰/横滚/偏航、肘部俯仰、腕部偏航/俯仰/横滚 |
| `left_hand` / `right_hand` | 6 × 2 | 小指/无名指/中指/食指/拇指近端 |
| `head` | 2 | 偏航、俯仰 |
| `waist` | 1-3 | 偏航（始终）、横滚/俯仰（仅 action） |

### 数据集维度映射（GR-2/GR-3）

- **Action（37D）**：left_arm(7) + right_arm(7) + left_hand(6) + right_hand(6) + head(2) + waist(3) + base(6)
- **State（45D）**：left_arm(7) + right_arm(7) + head(2) + waist(1) + left_hand(6) + right_hand(6) + base_pos(3) + base_quat(4) + base_rpy(3) + imu_acc(3) + imu_omega(3)

### 通信协议

| 组件 | 协议 | 默认端点 |
|------|------|----------|
| RoboOS | Redis pub/sub | localhost:6379 |
| Aurora SDK | DDS | domain_id |
| RoboBrain vLLM | HTTP (OpenAI-compatible) | localhost:4567 |

## 环境要求

| 项目 | Conda 环境 | Python 版本 |
|------|-----------|-------------|
| RoboBrain 2.0 / RoboOS | `robobrain2` | 3.10 |
| RoboSkill / GR2Robot | `fourier-robot` | - |
| 数据集转换工具 | `lerobot` | 3.10+ |

## 分支说明

| 分支 | 说明 |
|------|------|
| `main` | 主分支 |
| `fmc3-shanghai` | 上海团队开发分支 |
| `fmc3-ingolstadt` | 英戈尔施塔特团队开发分支 |

## License

详见各子项目目录下的 LICENSE 文件。
