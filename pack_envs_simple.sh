#!/bin/bash
# 直接打包 conda 环境目录为压缩包

OUTPUT_DIR="$HOME/conda_envs_backup_$(date +%Y%m%d)"
mkdir -p "$OUTPUT_DIR"

echo "开始打包 conda 环境到: $OUTPUT_DIR"
echo "========================================"

cd /home/phl/miniconda3/envs

for env_dir in */; do
    env_name="${env_dir%/}"
    echo ""
    echo "正在压缩: $env_name"
    tar -czf "$OUTPUT_DIR/${env_name}.tar.gz" "$env_name" 2>&1 | grep -v "socket ignored"
    if [ $? -eq 0 ]; then
        echo "✓ 已打包 ${env_name}.tar.gz"
        du -h "$OUTPUT_DIR/${env_name}.tar.gz"
    else
        echo "✗ 打包失败"
    fi
done

echo ""
echo "========================================"
echo "打包完成！"
echo "输出目录: $OUTPUT_DIR"
echo ""
du -sh "$OUTPUT_DIR"
ls -lh "$OUTPUT_DIR"
