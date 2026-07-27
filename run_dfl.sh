#!/bin/bash
# ============================================================
# run_dfl.sh — 启动 deep-face-lab-tf2 容器（交互式）
# 用法: bash run_dfl.sh [--rebuild]
#   --rebuild  重新构建镜像后再启动容器
# ============================================================
set -e

IMAGE="dfl-tf2:latest"
CONTAINER="dfl-tf2"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# ---------- 构建镜像 ----------
if [ "$1" = "--rebuild" ]; then
  echo ">>> 重新构建镜像 $IMAGE ..."
  docker build -t "$IMAGE" .
  echo ">>> 构建完成。"
  shift
fi

if ! docker images --format '{{.Repository}}:{{.Tag}}' | grep -qx "$IMAGE"; then
  echo "!!! 镜像 $IMAGE 不存在，开始构建..."
  docker build -t "$IMAGE" .
fi

# ---------- 如果已有同名容器在运行，先停掉 ----------
if docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo ">>> 容器 $CONTAINER 已在运行，先停止..."
  docker stop "$CONTAINER"
fi
if docker ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  docker rm "$CONTAINER"
fi

# ---------- 启动容器 ----------
echo ">>> 启动容器 $CONTAINER ..."
echo ">>> 挂载盘符: S, H, D, E, F, G"

if [ -t 0 ]; then
  # 交互模式：用户直接在终端里，attach 进去
  echo ">>> 进入容器交互式 shell..."
  echo ""
  MSYS_NO_PATHCONV=1 docker run \
    --name "$CONTAINER" \
    --gpus all \
    -v /mnt/host/d:/d \
    -v /mnt/host/e:/e \
    -v /mnt/host/f:/f \
    -v /mnt/host/g:/g \
    -v /mnt/host/h:/h \
    -v /mnt/host/s:/s \
    -it \
    "$IMAGE" /bin/bash
else
  # 非交互模式：后台启动，用户用 docker exec 进入
  MSYS_NO_PATHCONV=1 docker run \
    --name "$CONTAINER" \
    --gpus all \
    -v /mnt/host/d:/d \
    -v /mnt/host/e:/e \
    -v /mnt/host/f:/f \
    -v /mnt/host/g:/g \
    -v /mnt/host/h:/h \
    -v /mnt/host/s:/s \
    -d \
    "$IMAGE" tail -f /dev/null
  echo ">>> 容器已在后台启动，执行以下命令进入:"
  echo "    docker exec -it $CONTAINER /bin/bash"
fi
