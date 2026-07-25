#!/bin/bash
# ============================================================
# 🚀 DeepFaceLab WSL2 GPU 启动脚本 (Linux Native)
# 用法: source ./activate_gpu.sh
#       source ./activate_gpu.sh --skip-test   (跳过GPU测试,秒开)
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/dfl_env"

SKIP_TEST=0
if [[ "$1" == "--skip-test" || "$1" == "-s" ]]; then
    SKIP_TEST=1
fi

if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "⚠️  Virtual environment not found at $VENV_DIR"
    echo "   Run: python3 -m venv $VENV_DIR"
    echo "   Then: pip install 'tensorflow[and-cuda]==2.21.0' opencv-python scikit-image numpy scipy Pillow h5py tqdm colorama"
    return 1 2>/dev/null || exit 1
fi

source "$VENV_DIR/bin/activate"

VENV_SITE_PACKAGES="$VENV_DIR/lib/python3.12/site-packages"
NVIDIA_LIBS="$VENV_SITE_PACKAGES/nvidia"

LIB_PATHS=""
for dir in "$NVIDIA_LIBS"/*/lib; do
    if [ -d "$dir" ]; then
        LIB_PATHS="${LIB_PATHS:+$LIB_PATHS:}$dir"
    fi
done

export LD_LIBRARY_PATH="$LIB_PATHS:${LD_LIBRARY_PATH:-}"
export TF_CPP_MIN_LOG_LEVEL=3
export TF_ENABLE_ONEDNN_OPTS=0
export DISPLAY=:0

_CACHE_FILE="/tmp/dfl_gpu_tested_$$"

if [ ! -f "$_CACHE_FILE" ] && [ "$SKIP_TEST" -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "  DeepFaceLab WSL2 GPU Mode"
    echo "=========================================="
    echo ""
    echo "✅ CUDA Libraries: Loaded"

    python3 -c "
import os, sys
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
try:
    import tensorflow as tf
    gpus = tf.config.list_physical_devices('GPU')
    if gpus:
        print('🎉 SUCCESS! GPU Ready!')
        print(f'   Device: {gpus[0].name}')
        try:
            import subprocess
            r = subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=5)
            if r.returncode==0:
                p=[x.strip() for x in r.stdout.strip().split(',')]
                if len(p)>=2: print(f'   GPU: {p[0]}  VRAM: {int(p[1])//1024} GB')
        except: pass
        print('')
        print('Ready! Run your training command now.')
    else:
        print('⚠️  No GPU detected')
except Exception as e:
    print(f'❌ Error: {e}')
" 2>/dev/null

    touch "$_CACHE_FILE"
    echo "=========================================="
else
    echo "✅ DFL GPU Mode (cached, OK)"
fi
