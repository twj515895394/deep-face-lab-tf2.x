# Handoff - Batch 1 Docker 部署 & xcb/Qt GUI 预览（已完成）

**时间**: 2026-07-27 CST
**状态**: 全部就绪 — 镜像固化、依赖完整、GUI 调通、WSL 配置已设（待 shutdown 生效）

---

## 当前状态总览

| 项目 | 状态 |
|---|---|
| **镜像** | `dfl-tf2:latest` (ID: `8d15fdad9b28`, 10.4 GB) — 通过 `docker commit` 固化，含全部 xcb 依赖 |
| **容器** | `dfl-tf2` — 用户已启动运行中，GPU 识别正常 |
| **训练** | 已验证可正常启动并加载数据 (faceset.pak, aligned jpg)，按 Enter 可正常保存退出 |
| **GUI 预览** | ✅ 已解决 — VcXsrv 固定 `:0`，`train_dfl.bat` 自动检测 display |
| **WSL 内存/swap** | `.wslconfig` 已配置 (48GB/44GB)，待 `wsl --shutdown` 后生效 |

---

## 已完成的修改

### 1. Dockerfile (`T:\deep-face-lab-tf2.x\Dockerfile`)
- `ENTRYPOINT` → `CMD`，支持交互式 bash 和直接执行命令
- 新增完整 xcb/Qt GUI 依赖项（14个包）

### 2. 启动脚本
- `run_dfl.bat` — cmd 版，自动清理旧容器，挂载 S/H/D/E/F/G 盘 (`/mnt/host/` 前缀)
- `run_dfl.sh` — Git Bash 版，支持 `--rebuild` 重建镜像

### 3. 训练脚本
- `train_dfl.bat` — cmd 版，顶部三个变量改路径，启动前自动杀残留进程
- **新增 auto-detect DISPLAY**：自动扫描 VcXsrv 监听端口，计算 display 号，无需手动改
- `train_dfl.sh` — Git Bash 版

### 4. WSL 配置 (`C:\Users\Administrator\.wslconfig`)
```
[wsl2]
memory=48GB
swap=44GB
swapFile=D:\\WSL-Swap\\swap.vhdx
guiApplications=false
```
目录 `D:\WSL-Swap\` 已创建。

### 5. 镜像固化
- 因 Docker Hub 拉取失败无法重建镜像
- 通过 `docker commit dfl-tf2 dfl-tf2:latest` 将全部 xcb 依赖固化到镜像
- **容器删除重建后依赖不丢失** — 已验证重启后 `libqxcb.so` 零 `not found`，Qt OK

---

## GUI 预览 — 关键发现

**VcXsrv 每次重启 display 号可能漂移**（`-displayfd` 动态分配导致）。已通过两个手段解决：

### 方案一（当前生效）：`train_dfl.bat` 自动检测
```bat
REM 自动扫描 VcXsrv 端口并计算 display 号
for /f "tokens=2 delims=:" %%a in ('netstat -ano ^| findstr "LISTENING" ^| findstr "vcxsrv" ^| findstr "0.0.0.0:"') do (
  set /a DISPLAY_NUM=%%a-6000
  set DISPLAY=host.docker.internal:!DISPLAY_NUM!
)
```
**无需手动干预，每次执行自动找到正确的 display 号。**

### 方案二（推荐，下次启动 XLaunch 时配置）：
启动 XLaunch 时选择 **"One window"** 或去掉 `-displayfd`，手动指定 display 为 `0`，这样 VcXsrv 始终监听 6000 端口，`DISPLAY=host.docker.internal:0` 永远正确。

---

## 脚本速查

| 文件 | 用途 | 执行方式 |
|---|---|---|
| `run_dfl.bat` | 启动容器 + 进入 bash | 在 `T:\deep-face-lab-tf2.x\` 执行 `run_dfl.bat` |
| `train_dfl.bat` | 发送训练命令（含 GUI，自动检测 display） | 另开 cmd 窗口执行 `train_dfl.bat` |
| `run_dfl.sh` | 同上，Git Bash 版 | `bash run_dfl.sh` |
| `train_dfl.sh` | 同上，Git Bash 版 | `bash train_dfl.sh` |
| `Dockerfile` | 镜像定义（含 xcb 依赖） | `docker build -t dfl-tf2:latest .` |

训练脚本顶部三个变量：
```bat
set SRC_DIR=/s/src/yangzi-2025/aligned
set DST_DIR=/s/v_source/chenxiang/02/data_dst/aligned
set MODEL_DIR=/h/models2/model-杨紫
```

---

## 未完成事项（优先级排序）

1. **[P1]** 执行 `wsl --shutdown` + 重启 Docker Desktop，使 48GB/44GB swap 生效，检查 `D:\WSL-Swap\swap.vhdx` 是否生成
2. **[P2]** 网络恢复后重建镜像（`bash run_dfl.sh --rebuild`），把 xcb 依赖通过 Dockerfile 层固化（目前用 `docker commit` 临时固化，功能等效但不够规范）
3. **[P3]** XLaunch 启动时固定 display 为 `:0`：选择 "One window" + 去掉 `-displayfd`，使端口始终为 6000

---

## 建议技能

- `handoff` — 下次会话开始时先读此文档
- `custom/diagnose` — 如需深入诊断问题
- `custom/document-helper` — 如需更新 Docker 部署文档
