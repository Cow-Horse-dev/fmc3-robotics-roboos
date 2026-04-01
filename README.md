# fmc3-robotics (cup-grasping)

本分支是傅里叶 `GR2` 人形机器人的抓取主线分支，面向 RoboOS 调用的抓取、搬运和原子操作集成。

这里的主叙事不是通用工作空间，也不是 SO101 单臂实验，而是围绕 `Fourier GR2 + MCP Skill + PI0 推理服务` 这条链路整理可运行能力。

## 分支定位

- 机器人主体：Fourier GR2
- 任务方向：杯子抓取、桌面 pick-place、原子操作集成
- 主要调用方式：RoboOS 通过 MCP 调用 GR2 技能服务
- 当前主链路：`RoboOS -> skill_pi0.py / skill.py -> PI0 service -> GR2`

## 当前仓库里可直接对上的实现

### 1. GR2 通用技能服务

- `projects/RoboSkill/fmc3-robotics/fourier/gr2/skill.py`
- `projects/RoboSkill/fmc3-robotics/fourier/gr2/README.md`

这条链路提供 GR2 的基础 MCP 工具，以及 RoboOS 对接 GR2 的基本服务入口。

### 2. GR2 PI0 原子操作技能

- `projects/RoboSkill/fmc3-robotics/fourier/gr2/skill_pi0.py`

这是本分支最贴近“抓取主线”的实现入口。它提供：

- `execute_manipulation_task(...)`
- 自动拉起 PI0 推理服务
- 通过 Unix Socket 与本地推理进程通信
- 面向 RoboOS 的完整原子任务触发方式

代码里已经出现类似下面的任务表达：

```text
grasp the cup and move it to the table
```

但需要注意，当前默认 checkpoint 和默认任务仍然偏向现有本地实验配置，不代表仓库里已经附带了杯子抓取专用模型权重。

### 3. 现有专项实验

- `projects/RoboSkill/fmc3-robotics/fourier/gr2/skill_green_yellow.py`
- `projects/RoboSkill/fmc3-robotics/fourier/gr2/README_skill_green_yellow.md`

这部分是黑盖瓶在绿区/黄区之间搬运的专项实验，属于 GR2 主线上的一个已落地任务，不是本分支唯一目标，但可以作为原子抓取任务的参考样例。

## 快速启动

### 启动 GR2 技能服务

```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
pip install -r requirements.txt
python skill.py
```

### 启动 PI0 抓取技能服务

```bash
conda activate fourier-robot
cd projects/RoboSkill/fmc3-robotics/fourier/gr2
python skill_pi0.py
```

典型调用示例：

```text
execute_manipulation_task("grasp the cup and move it to the table")
```

## RoboOS 对接

在 `projects/RoboOS/slaver/config.yaml` 中把机器人服务指向运行中的 GR2 skill：

```yaml
robot:
  name: fourier_gr2
  call_type: remote
  path: "http://<ROBOT_IP>:8000"
```

## 现阶段边界

- 本分支主线是 GR2，不以 `lerobot/` 下的 SO101 代码为主
- 杯子抓取可以沿用 `skill_pi0.py` 的原子任务入口，但仓库中没有提交杯子专用 checkpoint
- `skill_pi0.py` 里引用了本地绝对路径的推理脚本和模型目录，部署机器需要按实际环境补齐

## 备注

仓库中仍保留了一些其他机器人或历史实验代码，但 `cup-grasping` 分支根 README 以后应以 GR2 抓取主线为准，不再沿用原来的通用工作空间说明。
