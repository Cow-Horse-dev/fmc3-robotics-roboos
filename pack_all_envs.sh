#!/bin/bash
# 批量打包所有 conda 环境

# 设置输出目录
OUTPUT_DIR="$HOME/conda_envs_backup_$(date +%Y%m%d)"
mkdir -p "$OUTPUT_DIR"

echo "开始打包 conda 环境到: $OUTPUT_DIR"
echo "========================================"

# 环境列表（不包括 base）
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

    # 导出 yml 配置
    conda env export -n "$env" > "$OUTPUT_DIR/${env}.yml" 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ 已导出 ${env}.yml"
    else
        echo "✗ 导出 ${env}.yml 失败"
    fi

    # 使用 conda-pack 打包完整环境
    conda pack -n "$env" -o "$OUTPUT_DIR/${env}.tar.gz" --ignore-missing-files 2>&1
    if [ $? -eq 0 ]; then
        echo "✓ 已打包 ${env}.tar.gz"
        # 显示文件大小
        du -h "$OUTPUT_DIR/${env}.tar.gz"
    else
        echo "✗ 打包 ${env}.tar.gz 失败"
    fi
done

# 打包 base 环境（只导出 yml）
echo ""
echo "正在导出 base 环境配置"
echo "----------------------------------------"
conda env export -n base > "$OUTPUT_DIR/base.yml" 2>&1
if [ $? -eq 0 ]; then
    echo "✓ 已导出 base.yml"
else
    echo "✗ 导出 base.yml 失败"
fi

echo ""
echo "========================================"
echo "打包完成！"
echo "输出目录: $OUTPUT_DIR"
echo ""
echo "目录内容："
ls -lh "$OUTPUT_DIR"
echo ""
echo "总大小："
du -sh "$OUTPUT_DIR"
