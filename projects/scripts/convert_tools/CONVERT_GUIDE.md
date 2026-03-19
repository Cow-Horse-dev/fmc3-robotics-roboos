# Dora-Record 转 LeRobot v3.0 数据集转换指南

## 概述

`convert_dora_to_lerobot.py` 将外骨骼遥操采集的 Dora-Record 格式数据转换为 LeRobot v3.0 格式，用于后续的策略模型训练（ACT、Diffusion、PI0、SmolVLA 等）。

## 运行命令

```bash
# 基本用法
python convert_dora_to_lerobot.py \
    --input ./dora-record/<session_id> \
    --output ./pick_and_place \
    --task "grab the bottle on the table" \
    --fps 30 \
    --robot-type fourier_gr2 \
    --video-codec libopenh264

# 或使用 run_convert.sh
bash run_convert.sh
```

## 命令行参数

| 参数 | 缩写 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `--input` | `-i` | 是 | - | Dora-Record session 目录路径，该目录下包含 `episode_000000000/`、`episode_000000001/` 等子目录 |
| `--output` | `-o` | 是 | - | 输出的 LeRobot 数据集目录，转换后所有文件写入此目录 |
| `--task` | `-t` | 否 | `teleoperation` | 任务的自然语言描述，VLA 模型训练时会用到这个文本作为语言指令。例如 `"grab the bottle on the table"` |
| `--fps` | - | 否 | `30` | 输出数据集的帧率。所有传感器数据会被重采样到这个统一帧率 |
| `--video-codec` | - | 否 | `libx264` | ffmpeg 视频编码器。conda 环境下推荐 `libopenh264`，系统 ffmpeg 可用 `libx264` 或 `libsvtav1`(AV1) |
| `--robot-type` | - | 否 | `fourier_gr3` | 机器人类型标识，写入 info.json，训练时用于区分不同机器人 |
| `--no-video` | - | 否 | `false` | 加上此参数跳过图像/视频处理，只转换关节状态和动作数据 |

### video-codec 可选值

| 编码器 | 说明 | 压缩率 | 速度 |
|--------|------|--------|------|
| `libopenh264` | Cisco 开源 H.264，conda ffmpeg 自带 | 中 | 快 |
| `libx264` | 标准 H.264，需系统 ffmpeg | 高 | 快 |
| `libsvtav1` | AV1 编码，压缩最好 | 最高 | 慢 |
| `libx265` | H.265/HEVC | 高 | 中 |

## 输入数据格式（Dora-Record）

### 目录结构

```
dora-record/<session_id>/
├── episode_000000000/
│   ├── metadata.json                           # episode 元信息
│   ├── action.parquet                          # 手臂关节动作（31维）
│   ├── action.base.parquet                     # 底盘动作（6维）
│   ├── observation.state.parquet               # 手臂关节状态（29维）
│   ├── observation.base_state.parquet          # 底盘状态（位姿+IMU，16维）
│   ├── observation.images.camera_top.parquet   # RGB 图像（JPEG 编码）
│   └── observation.images.camera_top_depth.parquet  # 深度图像（PNG 编码）
├── episode_000000001/
│   └── ...
└── episode_000000002/
    └── ...
```

### parquet 文件内部格式

每个 parquet 文件都包含以下公共列：

| 列名 | 类型 | 说明 |
|------|------|------|
| `timestamp_utc` | timestamp[ns] | UTC 时间戳（纳秒精度） |
| `trace_id` | string | 分布式追踪 ID |
| `span_id` | string | 追踪 span ID |
| `parameters` | string | 附加参数 |

加上各自的数据列：

#### action.parquet — 手臂关节动作

数据列 `action` 类型为 `list<struct<name: string, value: double>>`，每行是一个字典列表：

```python
[
    {"name": "left_shoulder_pitch_joint",  "value": 0.123},
    {"name": "left_shoulder_roll_joint",   "value": -0.456},
    {"name": "left_shoulder_yaw_joint",    "value": 0.789},
    ...  # 共 31 个关节
]
```

**31 个关节的完整维度映射：**

| 维度 | 关节名 | 所属部位 |
|------|--------|---------|
| 0 | left_shoulder_pitch_joint | 左臂 |
| 1 | left_shoulder_roll_joint | 左臂 |
| 2 | left_shoulder_yaw_joint | 左臂 |
| 3 | left_elbow_pitch_joint | 左臂 |
| 4 | left_wrist_yaw_joint | 左臂 |
| 5 | left_wrist_pitch_joint | 左臂 |
| 6 | left_wrist_roll_joint | 左臂 |
| 7 | right_shoulder_pitch_joint | 右臂 |
| 8 | right_shoulder_roll_joint | 右臂 |
| 9 | right_shoulder_yaw_joint | 右臂 |
| 10 | right_elbow_pitch_joint | 右臂 |
| 11 | right_wrist_yaw_joint | 右臂 |
| 12 | right_wrist_pitch_joint | 右臂 |
| 13 | right_wrist_roll_joint | 右臂 |
| 14 | L_pinky_proximal_joint | 左手 |
| 15 | L_ring_proximal_joint | 左手 |
| 16 | L_middle_proximal_joint | 左手 |
| 17 | L_index_proximal_joint | 左手 |
| 18 | L_thumb_proximal_pitch_joint | 左手 |
| 19 | L_thumb_proximal_yaw_joint | 左手 |
| 20 | R_pinky_proximal_joint | 右手 |
| 21 | R_ring_proximal_joint | 右手 |
| 22 | R_middle_proximal_joint | 右手 |
| 23 | R_index_proximal_joint | 右手 |
| 24 | R_thumb_proximal_pitch_joint | 右手 |
| 25 | R_thumb_proximal_yaw_joint | 右手 |
| 26 | head_yaw_joint | 头部 |
| 27 | head_pitch_joint | 头部 |
| 28 | waist_yaw_joint | 腰部 |
| 29 | waist_roll_joint | 腰部 |
| 30 | waist_pitch_joint | 腰部 |

#### action.base.parquet — 底盘动作

数据列 `action.base` 类型同上，6 个自由度：

| 维度 | 名称 | 说明 |
|------|------|------|
| 0 | vel_x | 前后线速度 |
| 1 | vel_y | 左右线速度 |
| 2 | vel_yaw | 偏航角速度 |
| 3 | vel_height | 升降速度 |
| 4 | vel_pitch | 俯仰角速度 |
| 5 | base_yaw | 底盘偏航角 |

#### observation.state.parquet — 手臂关节状态

数据列 `observation.state`，29 个关节（比 action 少腰部 roll 和 pitch）。

#### observation.base_state.parquet — 底盘状态

数据列 `observation.base_state` 为嵌套结构体：

```python
[{
    "base": {
        "position": [x, y, z],           # 位置（米）
        "quat": [qx, qy, qz, qw],       # 四元数
        "rpy": [roll, pitch, yaw]         # 欧拉角（弧度）
    },
    "imu": {
        "acc_B": [ax, ay, az],            # 加速度（m/s²）
        "omega_B": [wx, wy, wz]          # 角速度（rad/s）
    },
    "stand_pose": [4个值],
    "state": 11                           # 状态码
}]
```

展平后为 16 维向量。

#### observation.images.camera_top.parquet — RGB 图像

数据列为 `list<uint8>`，每行是一张 JPEG 编码的图像字节流（约 67KB/帧，480x640x3）。

#### observation.images.camera_top_depth.parquet — 深度图像

数据列为 `list<uint8>`，每行是一张 PNG 编码的深度图字节流（约 106KB/帧，480x640）。

### metadata.json

```json
{
    "episode_index": 0,
    "task_id": null,
    "start_time": "2026-02-12T02:29:11.715Z",
    "end_time": "2026-02-12T02:29:25.814Z",
    "session_id": "019c4fad-86f2-7017-bc8c-35744b1de20d",
    "machine_id": "GR3",
    "equipment": "t5d",
    "notes": "grxtest"
}
```

### 各传感器采样频率不同

| 数据 | 频率 | 说明 |
|------|------|------|
| action | ~100Hz | 动作指令发送最快 |
| observation.state | ~60Hz | 关节状态反馈 |
| observation.base_state | ~60Hz | 底盘状态反馈 |
| camera_top (RGB) | ~30Hz | RGB 摄像头 |
| camera_top_depth | ~30Hz | 深度摄像头 |

转换脚本会将所有数据**重采样到统一帧率**（默认 30fps）。

## 输出数据格式（LeRobot v3.0）

### 目录结构

```
pick_and_place/
├── meta/
│   ├── info.json                                    # 数据集元信息
│   ├── stats.json                                   # 全局统计（归一化用）
│   ├── tasks.parquet                                # 任务描述映射表
│   └── episodes/
│       └── chunk-000/
│           └── file-000.parquet                     # episode 级元信息
├── data/
│   └── chunk-000/
│       └── file-000.parquet                         # 帧级数据（action、state等）
└── videos/
    ├── observation.images.camera_top/
    │   └── chunk-000/
    │       └── file-000.mp4                         # RGB 视频（所有 episode 合并）
    └── observation.images.camera_top_depth/
        └── chunk-000/
            └── file-000.mp4                         # 深度视频（所有 episode 合并）
```

### data/chunk-000/file-000.parquet — 帧级数据

所有 episode 的所有帧按顺序存储在一个 parquet 文件中：

| 列名 | 类型 | 说明 |
|------|------|------|
| `action` | list\<float64\> | 动作向量（37维 = 31关节 + 6底盘） |
| `observation.state` | list\<float64\> | 状态向量（45维 = 29关节 + 16底盘状态） |
| `timestamp` | float64 | episode 内的时间（秒），从 0 开始 |
| `frame_index` | int64 | episode 内的帧序号，从 0 开始 |
| `episode_index` | int64 | 所属 episode 的编号 |
| `index` | int64 | 全局帧序号（跨所有 episode 的唯一 ID） |
| `task_index` | int64 | 任务编号，通过 tasks.parquet 映射到文本 |

### 转换后的 action 维度映射（37维）

| 维度 | 名称 | 部位 | 部署时对应 GR2Robot |
|------|------|------|-------------------|
| 0-6 | left_shoulder/elbow/wrist (7个) | 左臂 | `left_manipulator` |
| 7-13 | right_shoulder/elbow/wrist (7个) | 右臂 | `right_manipulator` |
| 14-19 | L_pinky/ring/middle/index/thumb (6个) | 左手 | `left_hand` |
| 20-25 | R_pinky/ring/middle/index/thumb (6个) | 右手 | `right_hand` |
| 26-27 | head_yaw, head_pitch | 头部 | `head` |
| 28-30 | waist_yaw/roll/pitch | 腰部 | `waist` |
| 31-36 | base_vel_x/y/yaw/height/pitch/yaw | 底盘 | `set_velocity()` |

### 转换后的 observation.state 维度映射（45维）

| 维度 | 名称 | 说明 |
|------|------|------|
| 0-6 | 左臂 7 关节 | 与 action 相同 |
| 7-13 | 右臂 7 关节 | 与 action 相同 |
| 14-15 | head_yaw, head_pitch | 头部 |
| 16 | waist_yaw | 腰部（注意：state 比 action 少 roll/pitch） |
| 17-22 | 左手 6 关节 | 顺序与 action 不同：index/middle/ring/pinky/thumb |
| 23-28 | 右手 6 关节 | 同上 |
| 29-31 | base_pos_x/y/z | 底盘位置 |
| 32-35 | base_quat_x/y/z/w | 底盘四元数 |
| 36-38 | base_rpy_roll/pitch/yaw | 底盘欧拉角 |
| 39-41 | imu_acc_x/y/z | IMU 加速度 |
| 42-44 | imu_omega_x/y/z | IMU 角速度 |

### meta/tasks.parquet — 任务映射

| 索引（任务文本） | task_index |
|-----------------|-----------|
| grab the bottle on the table | 0 |

训练时，框架通过 `task_index` 查找任务文本，送入 VLA 模型的语言编码器。

### meta/info.json — 数据集元信息

```json
{
    "codebase_version": "v3.0",
    "robot_type": "fourier_gr2",
    "total_episodes": 86,
    "total_frames": 25000,
    "total_tasks": 1,
    "chunks_size": 1000,
    "fps": 30,
    "splits": {"train": "0:86"},
    "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
    "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
    "features": {
        "action": {"dtype": "float32", "shape": [37], "names": [...]},
        "observation.state": {"dtype": "float32", "shape": [45], "names": [...]},
        "observation.images.camera_top": {"dtype": "video", "shape": [480, 640, 3], ...},
        "observation.images.camera_top_depth": {"dtype": "video", ...},
        "timestamp": {"dtype": "float32", "shape": [1]},
        "frame_index": {"dtype": "int64", "shape": [1]},
        "episode_index": {"dtype": "int64", "shape": [1]},
        "index": {"dtype": "int64", "shape": [1]},
        "task_index": {"dtype": "int64", "shape": [1]}
    }
}
```

### meta/stats.json — 全局统计

用于训练时数据归一化，包含每个特征的 min/max/mean/std/count。

### 视频存储方式

所有 episode 的帧**合并到同一个 mp4 文件**中（与 LeRobot 标准一致）。每个 episode 在视频中的位置由 episodes parquet 中的 `from_timestamp` 和 `to_timestamp` 指定。训练时框架根据时间戳自动从视频中提取对应帧。

## 转换流程详解

### 第一步：读取 Dora-Record 数据

```
对每个 episode 目录:
  1. 读取 metadata.json（空文件或损坏会自动跳过）
  2. 读取 action.parquet → 31维关节动作 + 时间戳
  3. 读取 action.base.parquet → 6维底盘动作 + 时间戳
  4. 读取 observation.state.parquet → 29维关节状态 + 时间戳
  5. 读取 observation.base_state.parquet → 16维底盘状态 + 时间戳
  6. 读取 observation.images.camera_top.parquet → JPEG 图像 + 时间戳
  7. 读取 observation.images.camera_top_depth.parquet → PNG 深度图 + 时间戳
```

### 第二步：时间对齐与重采样

由于各传感器采样频率不同（action ~100Hz，state ~60Hz，camera ~30Hz），需要统一到目标帧率：

```
1. 以 action 的时间范围为基准：start_ns = action_ts[0], end_ns = action_ts[-1]
2. 按目标 fps 生成均匀时间戳序列
3. 对每个数据源用最近邻插值重采样到统一时间轴
```

### 第三步：合并维度

```
action = [31维手臂关节] + [6维底盘动作] = 37维
state  = [29维手臂关节] + [16维底盘状态] = 45维
```

### 第四步：编码视频

```
所有 episode 的 RGB 帧拼接 → 一个 mp4 文件
所有 episode 的深度帧拼接 → 一个 mp4 文件（深度图归一化为 8bit 灰度伪 RGB）
记录每个 episode 在视频中的起止时间戳
```

### 第五步：生成 LeRobot 元数据

```
1. data parquet: 所有帧的 action、state、timestamp、frame_index 等
2. tasks.parquet: 任务文本到 task_index 的映射
3. episodes parquet: 每个 episode 的统计信息和视频位置信息
4. stats.json: 全局统计（归一化用）
5. info.json: 数据集描述（特征定义、视频参数等）
```

## 常见问题

### Q: ffmpeg 报 "Unknown encoder 'libx264'"
**A:** conda 环境的 ffmpeg 通常不带 libx264，改用 `--video-codec libopenh264`。

### Q: 某个 episode 的 metadata.json 为空
**A:** 脚本会自动跳过损坏的 episode 并打印警告。

### Q: 只想转换状态/动作数据，不需要图像
**A:** 加 `--no-video` 参数。

### Q: 转换后数据量太大
**A:** 视频是主要的空间占用。可以用 `--video-codec libsvtav1`（AV1）获得更好的压缩率，但编码更慢。

### Q: 如何验证转换结果
**A:** 用 Python 检查输出：
```python
import pyarrow.parquet as pq
import json

# 检查数据
t = pq.read_table("pick_and_place/data/chunk-000/file-000.parquet")
print(t.schema)
print(t.num_rows)

# 检查 info
with open("pick_and_place/meta/info.json") as f:
    info = json.load(f)
print(json.dumps(info, indent=2))
```
