#!/bin/bash
# 使用 conda pack -p 打包所有环境

OUTPUT_DIR="$HOME/conda_envs_backup_$(date +%Y%m%d)"
mkdir -p "$OUTPUT_DIR"

echo "开始打包 conda 环境到: $OUTPUT_DIR"
echo "========================================"

# 环境列表
ENVS=(
    "env_isaaclab"
    "fourier-robot"
    "fourier_speech"
    "lerobot"
    "lerobot-pi0"
    "openteach"
    "openteach_isaac"
    "robobrain"
    "roboos"
    "teleop"
    "unifolm-vla"
)

# 打包每个环境
for env in "${ENVS[@]}"; do
    echo ""
    echo "正在打包: $env"
    echo "----------------------------------------"

    conda pack -p /home/phl/miniconda3/envs/$env -o "$OUTPUT_DIR/${env}.tar.gz" --ignore-missing-files

    if [ $? -eq 0 ]; then
        echo "✓ 已打包 ${env}.tar.gz"
        du -h "$OUTPUT_DIR/${env}.tar.gz"
    else
        echo "✗ 打包 ${env} 失败"
    fi
done

echo ""
echo "========================================"
echo "打包完成！"
echo "输出目录: $OUTPUT_DIR"
echo ""
echo "文件列表："
ls -lh "$OUTPUT_DIR"
echo ""
echo "总大小："
du -sh "$OUTPUT_DIR"
