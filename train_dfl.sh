#!/bin/bash
# ============================================================
# train_dfl.sh — DFL 训练脚本（交互式 + GUI 预览）
# 用法: bash train_dfl.sh
#
# 修改下面三个路径即可开始训练:
#   SRC_DIR   - src 素材目录（faceset.pak 所在目录）
#   DST_DIR   - dst 素材目录（aligned 图片所在目录）
#   MODEL_DIR - 模型输出/加载目录
# ============================================================
set -e

CONTAINER="dfl-tf2"

# ==========================================
# ★ 修改这三行，改成你要训练的素材
# ==========================================
SRC_DIR="/s/src/yangzi-2025/aligned"
DST_DIR="/s/v_source/chenxiang/02/data_dst/aligned"
MODEL_DIR="/h/models2/model-杨紫"

# 模型类型和额外参数（一般不用改）
MODEL="SAEHD"
EXTRA_ARGS=""

# ==========================================
# ★ DISPLAY 设置（GUI 预览，需要 VcXsrv）
# ==========================================
# 如果 PowerShell 中设了 $env:DISPLAY 则自动继承，
# 否则用默认值（根据你的 VcXsrv 配置修改）
if [ -z "$DISPLAY" ]; then
  DISPLAY="host.docker.internal:0"
fi

# ==========================================
# 检查 + 启动
# ==========================================
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "!!! 容器 $CONTAINER 未运行，请先执行: bash run_dfl.sh"
  exit 1
fi

echo "=========================================="
echo "  DFL 训练"
echo "  SRC  : $SRC_DIR"
echo "  DST  : $DST_DIR"
echo "  MODEL: $MODEL_DIR"
echo "  GPU  : $(MSYS_NO_PATHCONV=1 docker exec $CONTAINER python -c "import tensorflow as tf; g=tf.config.list_physical_devices('GPU'); print(g[0].name if g else 'N/A')" 2>/dev/null)"
echo "=========================================="
echo ""

# 容器内执行训练（交互模式，GUI 预览）
MSYS_NO_PATHCONV=1 docker exec \
  -e DISPLAY="$DISPLAY" \
  -it "$CONTAINER" \
  python main.py train \
    --model "$MODEL" \
    --training-data-src-dir "$SRC_DIR" \
    --training-data-dst-dir "$DST_DIR" \
    --model-dir "$MODEL_DIR" \
    $EXTRA_ARGS "$@"
