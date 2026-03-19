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

### fourier-robot 环境
```bash
conda pack -p /home/phl/miniconda3/envs/fourier-robot -o fourier-robot.tar.gz
conda pack -p /home/phl/miniconda3/envs/lerobot-pi0 -o lerobot-pi0.tar.gz
```

### robobrain 环境
```bash
conda pack -p /home/phl/miniconda3/envs/robobrain -o robobrain.tar.gz
```

### roboos 环境
```bash
conda pack -p /home/phl/miniconda3/envs/roboos -o roboos.tar.gz
```

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
   - `robobrain.tar.gz` -> `~/miniconda3/envs/robobrain`
   - `roboos.tar.gz` -> `~/miniconda3/envs/roboos`

### 第三步：验证与激活
解压完成后，Conda 应该能自动识别这些环境。

1. **查看环境列表**：
   ```bash
   conda env list
   ```
   你应该能看到刚刚解压的三个环境。

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
