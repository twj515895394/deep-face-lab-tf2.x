# deep-face-lab-tf2.x Dockerfile
# TF 2.21 / CUDA 12.5 / cuDNN 9.3 / Python 3.11
FROM nvidia/cuda:12.5.0-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# apt 阿里云镜像加速
RUN sed -i 's|http://archive.ubuntu.com|http://mirrors.aliyun.com|g; s|http://security.ubuntu.com|http://mirrors.aliyun.com|g' /etc/apt/sources.list

# 1) 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    git ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# 2) 创建 venv
ENV VIRTUAL_ENV=/opt/venv
RUN python3.11 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 3) 升级 pip
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# 4) 安装 Python 依赖（严格遵循 requirements.txt）
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com

# 5) GUI 依赖（用于 XSeg Editor / preview，配合 Win10 + VcXsrv）
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libxkbcommon0 libdbus-1-3 \
    libxcb-icccm4 libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
    libxcb-render-util0 libxcb-shape0 libxcb-sync1 libxcb-xfixes0 \
    libxcb-xinerama0 libxkbcommon-x11-0 libxcb-xkb1 \
    libsm6 libice6 libxcb-util1 \
    fonts-dejavu-core fontconfig \
    && pip install --no-cache-dir PyQt5 -i https://mirrors.aliyun.com/pypi/simple/ --trusted-host mirrors.aliyun.com \
    && mkdir -p /opt/venv/lib/python3.11/site-packages/cv2/qt/fonts \
    && ln -sf /usr/share/fonts/truetype/dejavu/*.ttf /opt/venv/lib/python3.11/site-packages/cv2/qt/fonts/ \
    && rm -rf /var/lib/apt/lists/*

# 6) 复制项目代码
WORKDIR /app
COPY . /app

# 7) 默认入口（CMD 允许覆盖，ENTRYPOINT 太死）
CMD ["python", "main.py"]
