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
| **GUI 预览** | ✅ 已解决 — VcXsrv 在 display `:2`，`train_dfl.bat` 已修正 |
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
- `train_dfl.bat` — cmd 版，顶部三个变量改路径，启动前自动杀残留进程，DISPLAY=`:2`
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

**VcXsrv 的 display 号不一定是 `:0`**，取决于 XLaunch 启动参数。你的 VcXsrv 用了 `-displayfd 492`（动态分配），实际分配到了 `:2`（监听 6002 端口）。

**检查 VcXsrv 实际 display 号的方法（cmd）：**
```cmd
netstat -ano | findstr LISTENING | findstr vcxsrv
```
端口号减去 6000 就是 display 号（如 `6002` → `:2`）。

**如果 VcXsrv 重启后 display 号变了**，改 `train_dfl.bat` 第 12 行：
```bat
set DISPLAY=host.docker.internal:2   ← 改这里的数字
```

当前已确认可用：
```bash
docker exec -e DISPLAY=host.docker.internal:2 dfl-tf2 python -c \
  "from PyQt5.QtWidgets import QApplication; QApplication([]); print('OK')"
# Output: Qt OK
```

---

## 脚本速查

| 文件 | 用途 | 执行方式 |
|---|---|---|
| `run_dfl.bat` | 启动容器 + 进入 bash | 在 `T:\deep-face-lab-tf2.x\` 执行 `run_dfl.bat` |
| `train_dfl.bat` | 发送训练命令（含 GUI） | 另开 cmd 窗口执行 `train_dfl.bat` |
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
3. **[P3]** VcXsrv 每次重启 display 号可能变，建议固定为 `:0`：重新配置 XLaunch，去掉 `-displayfd`，改用 `-screen 0`

---

## 建议技能

- `handoff` — 下次会话开始时先读此文档
- `custom/diagnose` — 如需深入诊断问题
- `custom/document-helper` — 如需更新 Docker 部署文档
