# LeRobot v3.0 数据集结构（Fourier GR2）

由 `convert_dora_to_lerobot.py` 从 Dora-Record 转换而来，用于 ACT、Diffusion、PI0、SmolVLA 等策略模型训练。

转换时关节顺序已对齐 GR2 SDK 控制组，部署时可直接按维度切片下发指令。

## 目录结构

```
dataset_name/
├── meta/
│   ├── info.json                                        # 数据集元信息
│   ├── stats.json                                       # 全局统计（归一化用）
│   ├── tasks.parquet                                    # 任务描述映射表
│   └── episodes/
│       └── chunk-000/
│           └── file-000.parquet                         # episode 级元信息 + 统计
├── data/
│   └── chunk-000/
│       └── file-000.parquet                             # 帧级数据（action、state 等）
└── videos/
    ├── observation.images.camera_top/
    │   └── chunk-000/
    │       └── file-000.mp4                             # RGB 视频
    └── observation.images.camera_top_depth/
        └── chunk-000/
            └── file-000.mp4                             # 深度视频
```

## data parquet — 帧级数据

所有 episode 的所有帧按顺序存在一个 parquet 文件中。

| 列名 | 类型 | 说明 |
|------|------|------|
| `action` | list\<float64\> | 动作向量（35维） |
| `observation.state` | list\<float64\> | 状态向量（45维） |
| `timestamp` | float64 | episode 内时间（秒），从 0.0 开始 |
| `frame_index` | int64 | episode 内帧序号，从 0 开始 |
| `episode_index` | int64 | 所属 episode 编号 |
| `index` | int64 | 全局帧序号（跨 episode 唯一） |
| `task_index` | int64 | 任务编号，通过 tasks.parquet 映射到文本 |

## action 维度映射（35维）

关节顺序已对齐 GR2 SDK 控制组。GR2 腰部只有 1 个自由度（waist_yaw），转换时已过滤掉 waist_roll 和 waist_pitch。

### 关节部分（29维，维度 0-28）

| 维度 | 名称 | SDK 控制组 |
|------|------|-----------|
| 0 | left_shoulder_pitch_joint | `left_manipulator` |
| 1 | left_shoulder_roll_joint | `left_manipulator` |
| 2 | left_shoulder_yaw_joint | `left_manipulator` |
| 3 | left_elbow_pitch_joint | `left_manipulator` |
| 4 | left_wrist_yaw_joint | `left_manipulator` |
| 5 | left_wrist_pitch_joint | `left_manipulator` |
| 6 | left_wrist_roll_joint | `left_manipulator` |
| 7 | right_shoulder_pitch_joint | `right_manipulator` |
| 8 | right_shoulder_roll_joint | `right_manipulator` |
| 9 | right_shoulder_yaw_joint | `right_manipulator` |
| 10 | right_elbow_pitch_joint | `right_manipulator` |
| 11 | right_wrist_yaw_joint | `right_manipulator` |
| 12 | right_wrist_pitch_joint | `right_manipulator` |
| 13 | right_wrist_roll_joint | `right_manipulator` |
| 14 | L_index_proximal_joint | `left_hand` |
| 15 | L_middle_proximal_joint | `left_hand` |
| 16 | L_ring_proximal_joint | `left_hand` |
| 17 | L_pinky_proximal_joint | `left_hand` |
| 18 | L_thumb_proximal_pitch_joint | `left_hand` |
| 19 | L_thumb_proximal_yaw_joint | `left_hand` |
| 20 | R_index_proximal_joint | `right_hand` |
| 21 | R_middle_proximal_joint | `right_hand` |
| 22 | R_ring_proximal_joint | `right_hand` |
| 23 | R_pinky_proximal_joint | `right_hand` |
| 24 | R_thumb_proximal_pitch_joint | `right_hand` |
| 25 | R_thumb_proximal_yaw_joint | `right_hand` |
| 26 | head_yaw_joint | `head` |
| 27 | head_pitch_joint | `head` |
| 28 | waist_yaw_joint | `waist` |

### 底盘动作（6维，维度 29-34）

| 维度 | 名称 | 说明 |
|------|------|------|
| 29 | base_vel_x | 前后线速度 |
| 30 | base_vel_y | 左右线速度 |
| 31 | base_vel_yaw | 偏航角速度 |
| 32 | base_vel_height | 升降速度 |
| 33 | base_vel_pitch | 俯仰角速度 |
| 34 | base_base_yaw | 底盘偏航角 |

### 部署时的维度切片

模型输出 35 维 action 后，按以下方式切片下发：

```python
action = model.predict(...)  # shape: (35,)

client.set_joint_positions({
    "left_manipulator":  action[0:7].tolist(),
    "right_manipulator": action[7:14].tolist(),
    "left_hand":         action[14:20].tolist(),
    "right_hand":        action[20:26].tolist(),
    "head":              action[26:28].tolist(),
    "waist":             action[28:29].tolist(),
})

# 底盘速度
client.set_velocity(
    vel_x=action[29], vel_y=action[30], vel_yaw=action[31],
    vel_height=action[32], vel_pitch=action[33]
)
```

## observation.state 维度映射（45维）

关节部分（维度 0-28）的顺序与 action 完全一致，均对齐 SDK 控制组。

### 关节部分（29维，维度 0-28）

与 action 的维度 0-28 相同（left_manipulator → right_manipulator → left_hand → right_hand → head → waist）。

### 底盘状态（16维，维度 29-44）

| 维度 | 名称 | 说明 |
|------|------|------|
| 29 | base_pos_x | 底盘位置 X（米） |
| 30 | base_pos_y | 底盘位置 Y（米） |
| 31 | base_pos_z | 底盘位置 Z（米） |
| 32 | base_quat_x | 底盘四元数 X |
| 33 | base_quat_y | 底盘四元数 Y |
| 34 | base_quat_z | 底盘四元数 Z |
| 35 | base_quat_w | 底盘四元数 W |
| 36 | base_rpy_roll | 底盘欧拉角 Roll（弧度） |
| 37 | base_rpy_pitch | 底盘欧拉角 Pitch（弧度） |
| 38 | base_rpy_yaw | 底盘欧拉角 Yaw（弧度） |
| 39 | imu_acc_x | IMU 加速度 X（m/s²） |
| 40 | imu_acc_y | IMU 加速度 Y（m/s²） |
| 41 | imu_acc_z | IMU 加速度 Z（m/s²） |
| 42 | imu_omega_x | IMU 角速度 X（rad/s） |
| 43 | imu_omega_y | IMU 角速度 Y（rad/s） |
| 44 | imu_omega_z | IMU 角速度 Z（rad/s） |

## 视频

所有 episode 的帧合并到同一个 mp4 文件中，每个 episode 在视频中的位置由 episodes parquet 的 `from_timestamp` / `to_timestamp` 指定。

| 视频 | 分辨率 | 格式 | 说明 |
|------|--------|------|------|
| observation.images.camera_top | 480 x 640 x 3 | H.264, yuv420p | RGB 摄像头 |
| observation.images.camera_top_depth | 480 x 640 x 3 | H.264, yuv420p | 深度图（归一化为 8bit 灰度伪 RGB） |

## meta/info.json

```json
{
    "codebase_version": "v3.0",
    "robot_type": "fourier_gr2",
    "total_episodes": 27,
    "total_frames": 5922,
    "total_tasks": 1,
    "chunks_size": 1000,
    "fps": 30,
    "splits": {"train": "0:27"},
    "data_path": "data/chunk-{chunk_index:03d}/file-{file_index:03d}.parquet",
    "video_path": "videos/{video_key}/chunk-{chunk_index:03d}/file-{file_index:03d}.mp4",
    "features": {
        "action": {"dtype": "float32", "shape": [35], "names": [...]},
        "observation.state": {"dtype": "float32", "shape": [45], "names": [...]},
        "observation.images.camera_top": {"dtype": "video", "shape": [480, 640, 3], ...},
        "observation.images.camera_top_depth": {"dtype": "video", "shape": [480, 640, 3], ...},
        "timestamp": {"dtype": "float32", "shape": [1]},
        "frame_index": {"dtype": "int64", "shape": [1]},
        "episode_index": {"dtype": "int64", "shape": [1]},
        "index": {"dtype": "int64", "shape": [1]},
        "task_index": {"dtype": "int64", "shape": [1]}
    }
}
```

## meta/tasks.parquet

| 索引（任务文本） | task_index |
|-----------------|-----------|
| grab the bottle on the table | 0 |

训练时框架通过 `task_index` 查找任务文本，送入 VLA 模型的语言编码器。

## meta/stats.json

全局统计信息，用于训练时数据归一化。包含每个特征的 min / max / mean / std / count。

## meta/episodes parquet

每个 episode 一行，包含：

| 列类别 | 列名示例 | 说明 |
|--------|----------|------|
| 基本信息 | `episode_index`, `tasks`, `length` | episode 编号、任务列表、帧数 |
| 数据位置 | `data/chunk_index`, `data/file_index` | 数据 parquet 位置 |
| 数据范围 | `dataset_from_index`, `dataset_to_index` | 在全局帧序号中的范围 |
| 视频位置 | `videos/.../chunk_index`, `videos/.../file_index` | 视频文件位置 |
| 视频时间 | `videos/.../from_timestamp`, `videos/.../to_timestamp` | episode 在视频中的起止时间 |
| 统计信息 | `stats/action/min`, `stats/action/max`, ... | 每个 episode 的特征统计 |

## 验证转换结果

```python
import pyarrow.parquet as pq
import json

# 检查数据
t = pq.read_table("dataset_name/data/chunk-000/file-000.parquet")
print(t.schema)
print(f"总帧数: {t.num_rows}")

# 检查 action 维度
action = t.column("action")[0].as_py()
print(f"action 维度: {len(action)}")  # 应为 35

# 检查 state 维度
state = t.column("observation.state")[0].as_py()
print(f"state 维度: {len(state)}")  # 应为 45

# 检查 info
with open("dataset_name/meta/info.json") as f:
    info = json.load(f)
print(json.dumps(info, indent=2))
```
