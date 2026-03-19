# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Language

Always answer the user's questions in Chinese.

## Overview

Multi-project robotics workspace centered on Fourier humanoid robots (GR-2, GR-3). The main workflow is: **collect demonstrations via teleoperation** → **convert to LeRobot dataset** → **train policy (ACT/Diffusion/PI0/VLA)** → **deploy on robot via RoboOS**.

## Project Map

| Project | Path | Conda Env | Python | Purpose |
|---------|------|-----------|--------|---------|
| RoboBrain 2.0 | `projects/RoboBrain2.0/` | `robobrain2` | 3.10 | VLM for robotic perception & planning (Qwen2.5-VL based) |
| RoboOS | `projects/RoboOS/` | `robobrain2` | 3.10 | Multi-agent task orchestration (Master→Slaver via Redis) |
| RoboSkill | `projects/RoboSkill/` | `fourier-robot` | - | MCP-based universal skill store |
| GR2Robot Wrapper | `projects/fourier/Robot/` | `fourier-robot` | - | High-level GR-2 control API over Aurora SDK |
| Dataset Tools | `projects/scripts/convert_tools/` | `lerobot` | - | Dora-Record → LeRobot v3.0 conversion |

**External Projects** (in parent workspace):
- `../DexGraspVLA/` - Hierarchical VLA for dexterous grasping (env: `dexgraspvla`, Python 3.9)
- `../teleoperation/` - VR-based teleoperation (env: `teleop` via uv, Python 3.10-3.11)
- `../Open-Teach/` - NYU's VR teleoperation (env: `openteach`, Python 3.10)
- `../lerobot-versions/lerobot/` - HuggingFace LeRobot (env: `lerobot`, Python 3.10+)
- `../lerobot-versions/fourier-lerobot/` - Fork with IDP3/PI0 + Fourier converters
- `../fourier_aurora_sdk/` - Low-level DDS SDK for GR-1P/GR-2/GR-3/N1 (Docker)
- `../chassis-python-sdk/` - MQTT chassis control (192.168.137.68:1085)
- `../dataset/fourier/convert_tools/` - Dora-Record → LeRobot v3.0 conversion

**Models** in `../models/`: RoboBrain2.0-3B, RoboBrain2.0-7B, GR00T-N1.5-3B, pi0, SmolVLM2-500M, Florence-2-large, vosk (speech), CLIP

## Key Commands

### RoboOS — Full Stack Startup

**Quick Start (Multi-Terminal)**:
```bash
# Terminal 1: Fourier Robot Skill Server
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill.py

# Terminal 2: RoboBrain Model Service
conda activate robobrain2
cd projects/RoboBrain2.0
bash startup.sh  # vLLM on port 4567

# Terminal 3: RoboOS Master
conda activate robobrain2
cd projects/RoboOS
python master/run.py  # Flask :5000

# Terminal 4: RoboOS Slaver
conda activate robobrain2
cd projects/RoboOS
python slaver/run.py

# Terminal 5: Web UI
conda activate robobrain2
cd projects/RoboOS
python deploy/run.py  # http://127.0.0.1:8888
```

**Send Task**:
```bash
curl -X POST http://localhost:5000/publish_task \
  -H 'Content-Type: application/json' \
  -d '{"task": "pick up the apple"}'
```

### RoboBrain 2.0 — Model Service

```bash
conda activate robobrain2
cd projects/RoboBrain2.0
bash startup.sh  # starts vLLM on port 4567

# Manual start with custom options:
python inference.py --serve --host 0.0.0.0 --port 4567 \
  --model-id /path/to/RoboBrain2.0-7B --load-in-4bit
```

### MCP Skill Development

**Standard Skill Server**:
```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill.py     # run skill server
mcp dev skill.py    # development mode with inspector
```

**PI0 Inference Skill** (new):
```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill_pi0.py  # PI0 inference MCP server

# Test PI0 service health
python test_pi0_inference.py health

# Test PI0 inference
python test_pi0_inference.py inference --task "pick bottle and place into box"
```

### GR-2 Robot Control

```bash
conda activate fourier-robot
cd projects/fourier/Robot
python example.py
```

### Dataset Conversion (Dora-Record → LeRobot v3.0)

```bash
conda activate lerobot  # or any env with pyarrow, numpy, pandas
cd projects/scripts/convert_tools
python convert_dora_to_lerobot.py \
    --input ./dora-record/<session_id> \
    --output ./pick_and_place \
    --task "grab the bottle" \
    --fps 30 \
    --robot-type fourier_gr2 \
    --video-codec libopenh264  # use libopenh264 in conda (libx264 needs system ffmpeg)
```

### Environment Management

**Backup Conda Environments**:
```bash
# Simple tar.gz backup of all envs
bash pack_envs_simple.sh  # outputs to ~/conda_envs_backup_YYYYMMDD/

# Conda-pack based backup (preserves binary compatibility)
bash pack_envs_conda.sh

# Backup all envs
bash pack_all_envs.sh
```

### Testing

```bash
# RoboOS integration test
python projects/RoboOS/test/test.py

# GR2 connection test
python projects/RoboSkill/fmc3-robotics/fourier/gr2/test_connection.py

# PI0 inference health check
python projects/RoboSkill/fmc3-robotics/fourier/gr2/test_pi0_inference.py health

# PI0 inference test
python projects/RoboSkill/fmc3-robotics/fourier/gr2/test_pi0_inference.py inference
```

### Code Quality

```bash
# Run ruff linter on RoboOS
ruff check projects/RoboOS

# Format with ruff
ruff format projects/RoboOS
```

## Architecture Notes

### RoboOS Master-Slaver Communication

- **Master** (`master/run.py`) decomposes natural language tasks into subtasks via RoboBrain VLM
- **Slaver** (`slaver/run.py`) receives subtasks over Redis pub/sub (localhost:6379) and matches them to MCP skills using semantic similarity
- **Config**:
  - `master/config.yaml` → model endpoint at `cloud_server`
  - `slaver/config.yaml` → robot connection (`call_type: local|remote`)
- **Scene profiles**: `master/scene/profile.yaml` defines available robots and capabilities
- **Communication flow**: User → Deploy UI (:8888) → Master (:5000) → Redis (:6379) → Slaver → MCP Skill → GR2 Robot

### GR2Robot Control Groups

The GR-2 robot is controlled via named joint groups through Aurora SDK (DDS):

| Control Group | Joints | Description |
|---------------|--------|-------------|
| `left_manipulator` / `right_manipulator` | 7 × 2 | shoulder pitch/roll/yaw, elbow pitch, wrist yaw/pitch/roll |
| `left_hand` / `right_hand` | 6 × 2 | pinky/ring/middle/index/thumb proximal |
| `head` | 2 | yaw, pitch |
| `waist` | 1-3 | yaw (always), roll/pitch (action only) |

**FSM States**:
- 0=default, 1=joint_stand, 2=pd_stand, 3=walk
- 9=emergency_stop, 10=user_cmd, 11=upper_body_cmd

### Dataset Dimension Mapping (Dora→LeRobot for GR-2/GR-3)

- **Action (37D)**: left_arm(7) + right_arm(7) + left_hand(6) + right_hand(6) + head(2) + waist(3) + base(6)
- **State (45D)**: left_arm(7) + right_arm(7) + head(2) + waist(1) + left_hand(6) + right_hand(6) + base_pos(3) + base_quat(4) + base_rpy(3) + imu_acc(3) + imu_omega(3)
- **Sensor rates**: action ~100Hz, state ~60Hz, camera ~30Hz → all resampled to target fps (default 30)

### LeRobot Dataset Format (v3.0)

```
dataset_name/
├── meta/info.json          # features, fps, robot_type, splits
├── meta/stats.json         # per-feature min/max/mean/std for normalization
├── meta/tasks.parquet      # task_index → natural language description
├── data/chunk-000/file-000.parquet   # frame-level: action, state, timestamps, indices
└── videos/{camera_key}/chunk-000/file-000.mp4
```

### Communication Protocols

| Project | Protocol | Default Endpoint |
|---------|----------|-----------------|
| RoboOS | Redis pub/sub | localhost:6379 |
| Aurora SDK | DDS | domain_id (e.g. 123) |
| Chassis SDK | MQTT | 192.168.137.68:1085 |
| RoboBrain vLLM | HTTP (OpenAI-compatible) | localhost:4567 |
| MCP Skills | HTTP (stateless) | configurable (default 8000) |

### Configuration Systems

| Project | System | Notes |
|---------|--------|-------|
| RoboOS | YAML | Flat config files in master/ and slaver/ |
| RoboBrain 2.0 | CLI args | startup.sh wraps inference.py with vLLM flags |
| MCP Skills | Environment vars | `FOURIER_GR2_HOST`, `FOURIER_GR2_PORT` |

## Code Style & Conventions

- **Python**: PEP 8, Python 3.10+, 4-space indentation
- **Naming**:
  - `snake_case` for functions/files
  - `PascalCase` for classes
  - `UPPER_SNAKE_CASE` for constants
- **Linting**: Use `ruff` for RoboOS (line-length 120)
- **Paths**: Use absolute paths in configuration files
- **Package manager**: `pip`/`conda` for most projects, `uv` for teleoperation (external)

## Commit & PR Guidelines

- **Commit format**: Use prefix-style subjects (`docs:`, `feat:`, `chore:`, `fix:`, or `name:`)
- **Commit scope**: Keep commits single-purpose, include config changes in same commit when required
- **PR content**: Include affected subprojects, environment used, commands run, key logs/screenshots for deploy UI or robot behavior changes
- **Recent commit examples**:
  - `feat(RoboOS): 添加原子操作任务识别和执行逻辑`
  - `docs: 更新 README，添加完整的项目文档`
  - `chore: 规范化 gitignore 规则，清理自动生成文件`

## Security & Configuration

- **Credentials**: Do not commit real credentials/endpoints in `projects/RoboOS/master/config.yaml` or `projects/RoboOS/slaver/config.yaml`; prefer local overrides/env vars
- **Gitignore**: Avoid committing generated datasets, model weights, logs, or temp files (already broadly covered by `.gitignore`)
- **Model paths**: Use absolute paths for model checkpoints in configs

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Main branch |
| `fmc3-shanghai` | Shanghai team development branch (current) |
| `fmc3-ingolstadt` | Ingolstadt team development branch |

## Additional Resources

- **Startup Guide**: See `projects/fourier/markdown/roboos_startup_guide.md` for detailed multi-terminal startup instructions
- **Voice Control**: See `projects/fourier/markdown/voice_control_guide.md`
- **Conda Packing**: See `projects/fourier/markdown/conda_packing_guide.md`
