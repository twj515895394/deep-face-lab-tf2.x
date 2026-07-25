#!/bin/bash
# ============================================================
# 🚀 DeepFaceLab WSL2 全自动环境搭建脚本
# 在 Linux 原生文件系统中创建纯净的 GPU 环境
#
# 用法: bash setup_linux_native.sh
# ============================================================

set -e

PROJECT_DIR="$HOME/DeepFaceLab-master"
VENV_DIR="$PROJECT_DIR/dfl_env"
WORKSPACE_DIR="$HOME/workspace"

echo ""
echo "============================================"
echo "  DeepFaceLab Linux Native Setup"
echo "============================================"
echo ""

# ---- 第1步：检查项目位置 ----
if [ ! -f "$PROJECT_DIR/main.py" ]; then
    echo "❌ Error: Project not found at $PROJECT_DIR"
    echo "   First copy the project:"
    echo "   cp -r /mnt/d/BaiduNetdiskDownload/DeepFaceLab-master ~/DeepFaceLab-master"
    exit 1
fi
echo "✅ [1/7] Project found at $PROJECT_DIR"

# ---- 第2步：检查 Python ----
PYTHON_VERSION=$(python3 --version 2>&1 | grep -oP '\d+\.\d+')
echo "✅ [2/7] Python $PYTHON_VERSION"

# ---- 第3步：创建虚拟环境 ----
if [ -d "$VENV_DIR" ]; then
    echo "⚠️  [3/7] Virtual environment already exists, removing..."
    rm -rf "$VENV_DIR"
fi

echo "📦 [3/7] Creating virtual environment at $VENV_DIR ..."
python3 -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
echo "✅ [3/7] Virtual environment created and activated"

# ---- 第4步：升级 pip ----
echo "📦 [4/7] Upgrading pip ..."
pip install --upgrade pip setuptools wheel -q
echo "✅ [4/7] pip upgraded"

# ---- 第5步：安装 TensorFlow GPU 版本 ----
echo "📦 [5/7] Installing TensorFlow 2.21.0 with CUDA support (~2-3GB) ..."
pip install "tensorflow[and-cuda]==2.21.0" -q
echo "✅ [5/7] TensorFlow 2.21.0 installed"

# ---- 第6步：安装其他依赖 ----
echo "📦 [6/7] Installing OpenCV (with GUI) and other dependencies ..."
pip install opencv-python scikit-image numpy scipy Pillow h5py tqdm colorama numexpr -q
echo "✅ [6/7] All dependencies installed"

# ---- 第7步：安装 GUI 支持（如果还没有） ----
echo "📦 [7/7] Checking GUI libraries..."
if ! dpkg -l | grep -q libgtk-3-0; then
    echo "   Installing GTK+ for OpenCV GUI..."
    sudo apt update -qq && sudo apt install -y -qq libgtk-3-0t64 libgtk-3-dev libgl1 libglib2.0-0t64 \
        libsm6 libxext6 libxrender1 libgtk2.0-0t64 libgdk-pixbuf2.0-0 \
        libnotify4 libdbus-glib-1-2 libxcb1 libx11-6 libxxf86vm1 fonts-dejavu-core > /dev/null 2>&1 || true
fi
echo "✅ [7/7] GUI libraries ready"

# ---- 验证 CUDA 库 ----
echo ""
echo "============================================"
echo "  Verifying NVIDIA CUDA Libraries"
echo "============================================"

NVIDIA_LIBS="$VENV_DIR/lib/python3.12/site-packages/nvidia"
if [ -d "$NVIDIA_LIBS" ]; then
    LIB_COUNT=$(find "$NVIDIA_LIBS" -name "*.so*" 2>/dev/null | wc -l)
    echo "✅ Found $LIB_COUNT CUDA shared libraries in $NVIDIA_LIBS/"
else
    echo "⚠️  No nvidia directory found. TF may use system CUDA."
fi

# ---- 最终测试 ----
echo ""
echo "============================================"
echo "  Testing GPU Detection"
echo "============================================"

export LD_LIBRARY_PATH=""
for dir in "$NVIDIA_LIBS"/*/lib; do
    if [ -d "$dir" ]; then
        export LD_LIBRARY_PATH="${LD_LIBRARY_PATH:+$LD_LIBRARY_PATH:}$dir"
    fi
done
export TF_CPP_MIN_LOG_LEVEL=3
export DISPLAY=:0

python3 -c "
import os
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
try:
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print('🎉🎉🎉 SUCCESS! 🎉🎉🎉')
        print(f'   Device: {gpus[0].name}')
        try:
            import subprocess
            r = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if r.returncode==0:
                p=[x.strip() for x in r.stdout.strip().split(',')]
                if len(p)>=2:
                    print(f'   GPU: {p[0]}')
                    print(f'   VRAM: {int(p[1])//1024} GB')
        except: pass
    else:
        print('❌ No GPU detected')
except Exception as e:
    print(f'❌ Error: {e}')
" 2>/dev/null

echo ""
echo "============================================"
echo "  ✅ SETUP COMPLETE!"
echo "============================================"
echo ""
echo "Environment info:"
echo "  Project : $PROJECT_DIR"
echo "  VEnv    : $VENV_DIR"
echo "  Workspace: $WORKSPACE_DIR"
echo ""
echo "To start training:"
echo "  cd ~/DeepFaceLab-master"
echo "  source ./activate_gpu.sh"
echo "  python3 main.py train --training-data-src-dir \$HOME/workspace/data_src \\"
echo "      --training-data-dst-dir \$HOME/workspace/data_dst \\"
echo "      --model-dir \$HOME/workspace/model --model SAEHD"
echo ""
echo "Quick start options:"
echo "  source ./activate_gpu.sh -s     # skip test, instant start"
echo "  source ./activate_gpu.sh         # full test + start"
echo ""
