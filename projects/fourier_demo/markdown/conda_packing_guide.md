# Conda 环境打包指南

本文档记录了如何使用 `conda-pack` 打包环境，并将其恢复到新电脑的 Conda 目录中，以便继续使用 `conda` 命令进行管理（如 `conda activate`）。

## 1. 安装打包工具 (旧电脑)

确保已安装 `conda-pack`：

```bash
conda install -c conda-forge conda-pack
# 或
pip install conda-pack
```

## 2. 打包环境 (旧电脑)

运行以下命令生成 `.tar.gz` 压缩包：

### 常规环境
```bash
conda pack -p /home/phl/miniconda3/envs/env_isaaclab -o env_isaaclab.tar.gz --ignore-editable-packages
conda pack -p /home/phl/miniconda3/envs/fourier-robot -o fourier-robot.tar.gz
conda pack -p /home/phl/miniconda3/envs/fourier_speech -o fourier_speech.tar.gz
conda pack -p /home/phl/miniconda3/envs/lerobot -o lerobot.tar.gz --ignore-editable-packages
conda pack -p /home/phl/miniconda3/envs/lerobot-pi0 -o lerobot-pi0.tar.gz --ignore-editable-packages
conda pack -p /home/phl/miniconda3/envs/model_sdk -o model_sdk.tar.gz
conda pack -p /home/phl/miniconda3/envs/roboos -o roboos.tar.gz
conda pack -p /home/phl/miniconda3/envs/teleop -o teleop.tar.gz
conda pack -p /home/phl/miniconda3/envs/unifolm-vla -o unifolm-vla.tar.gz
```

### 有 conda/pip 文件冲突的环境
```bash
conda pack -p /home/phl/miniconda3/envs/openteach -o openteach.tar.gz --ignore-missing-files
conda pack -p /home/phl/miniconda3/envs/openteach_isaac -o openteach_isaac.tar.gz --ignore-missing-files
conda pack -p /home/phl/miniconda3/envs/robobrain -o robobrain.tar.gz --ignore-missing-files
```

说明：
- `--ignore-editable-packages` 用于跳过 `pip install -e` 形式安装的可编辑包检查。
- `--ignore-missing-files` 用于跳过 conda 管理文件被 `pip` 覆盖或删改后的检查。
- 如果要覆盖已有压缩包，可以在命令后追加 `--force`。

## 3. 在新电脑上恢复并集成到 Conda

为了让新电脑上的 Conda 能够识别并管理这些环境（即可以使用 `conda activate xxx`），你需要将它们解压到新电脑 Conda 的 `envs` 目录下。

### 第一步：找到新电脑的 Conda 环境目录
在新电脑终端运行以下命令查看安装位置：
```bash
conda info --base
```
假设输出是 `/home/username/miniconda3`，那么你的环境目录通常是 `/home/username/miniconda3/envs`。

### 第二步：解压环境
将 `.tar.gz` 文件复制到新电脑，然后解压到 `envs` 目录中相应的文件夹。

以 `fourier-robot` 为例（假设 Conda 安装在 `~/miniconda3`）：

1. **创建目标目录**：
   ```bash
   mkdir -p ~/miniconda3/envs/fourier-robot
   ```

2. **解压文件**：
   ```bash
   tar -xzf fourier-robot.tar.gz -C ~/miniconda3/envs/fourier-robot
   ```

3. **对其他环境重复此步骤**：
   - `env_isaaclab.tar.gz` -> `~/miniconda3/envs/env_isaaclab`
   - `fourier_speech.tar.gz` -> `~/miniconda3/envs/fourier_speech`
   - `lerobot.tar.gz` -> `~/miniconda3/envs/lerobot`
   - `lerobot-pi0.tar.gz` -> `~/miniconda3/envs/lerobot-pi0`
   - `model_sdk.tar.gz` -> `~/miniconda3/envs/model_sdk`
   - `openteach.tar.gz` -> `~/miniconda3/envs/openteach`
   - `openteach_isaac.tar.gz` -> `~/miniconda3/envs/openteach_isaac`
   - `robobrain.tar.gz` -> `~/miniconda3/envs/robobrain`
   - `roboos.tar.gz` -> `~/miniconda3/envs/roboos`
   - `teleop.tar.gz` -> `~/miniconda3/envs/teleop`
   - `unifolm-vla.tar.gz` -> `~/miniconda3/envs/unifolm-vla`

### 第三步：验证与激活
解压完成后，Conda 应该能自动识别这些环境。

1. **查看环境列表**：
   ```bash
   conda env list
   ```
   你应该能看到刚刚解压的环境。

2. **激活环境**：
   ```bash
   conda activate fourier-robot
   ```

3. **清理路径（可选）**：
   如果是跨路径迁移（例如用户名不同），`conda-pack` 通常会自动处理脚本路径。如果遇到问题，可以在激活后运行：
   ```bash
   conda-unpack
   ```

## 4. 常见问题
- **操作系统必须一致**：只能从 Linux 迁移到 Linux。
- **文件大小**：压缩包可能很大，传输时请确保完整。
- **Editable 包限制**：如果环境里有 `pip install -e` 安装的包，`conda-pack` 默认会报错，可改用 `--ignore-editable-packages`，但目标机器仍需要对应源码或重新安装该包。
- **Conda/Pip 冲突**：如果报 `Files managed by conda were found to have been deleted/overwritten`，可尝试使用 `--ignore-missing-files`，但这类环境最好额外做一次功能验证。
