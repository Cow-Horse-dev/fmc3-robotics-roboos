# fmc3-robotics (hikvision branch)

本分支用于推进「海康摄像头气密检测」任务在 GR2 + RoboOS 体系下的落地。

和 `main` 不同，这里重点不是通用演示，而是围绕海康流程做方案沉淀、运行链路对齐和后续实现准备。

## 分支定位

- 任务目标: 海康摄像头气密检测流程自动化
- 机器人形态: Fourier GR2
- 系统主链路: RoboBrain2.0 (理解/分解) -> RoboOS (编排/调度) -> RoboSkill (执行)

## 当前内容状态 (按仓库现状)

### 1) 已有方案文档 (核心)

- `projects/doc/海康摄像头气密检测任务实现方案.md`
- `projects/doc/海康摄像头气密检测任务实现方案.pdf`
- `projects/fourier_demo/markdown/海康摄像头气密检测任务实现方案.md`

建议以 `projects/doc/` 下版本为主。

### 2) 已有可运行通用组件

- RoboBrain2.0 模型服务: `projects/RoboBrain2.0/startup.sh`
- RoboOS 编排与界面:
  - `projects/RoboOS/master/run.py`
  - `projects/RoboOS/slaver/run.py`
  - `projects/RoboOS/deploy/run.py`
- GR2 技能服务:
  - `projects/RoboSkill/fmc3-robotics/fourier/gr2/skill.py`
  - `projects/RoboSkill/fmc3-robotics/fourier/gr2/skill_pi0.py`

### 3) 当前未在本分支提供的海康专用实现

方案文档中出现的示例文件（例如 `hikvision_skills.py`、`hikvision_endtoend_skills.py`、`test_hikvision_flow.py`）目前不在仓库中，现阶段仍属于设计/示例内容，不应视为可直接运行代码。

## 快速启动 (基于当前可运行链路)

下面命令用于启动现有通用链路，便于对接海康方案中的任务编排逻辑。

### 1. 启动 GR2 技能服务

```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill.py
```

### 2. 启动 RoboBrain2.0 服务

```bash
conda activate robobrain
cd projects/RoboBrain2.0
bash startup.sh
```

### 3. 启动 RoboOS

```bash
conda activate roboos
cd projects/RoboOS/master && python run.py
cd projects/RoboOS/slaver && python run.py
cd projects/RoboOS/deploy && python run.py
```

## 推荐阅读顺序

1. `projects/doc/海康摄像头气密检测任务实现方案.md`
2. `projects/doc/roboos_startup_guide.md`
3. `projects/RoboSkill/fmc3-robotics/fourier/gr2/README.md`

## 说明

本 README 只描述当前仓库中可验证的内容；后续若补充海康专用技能代码，应同步更新本文件中的「当前内容状态」。
