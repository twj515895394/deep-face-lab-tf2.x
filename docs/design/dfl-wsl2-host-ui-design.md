# DeepFaceLab (TF2+BF16) WSL2 后端与宿主机 UI 解耦架构设计方案初稿

## 1. 概述与设计目标

### 1.1 背景
本项目为升级版 DeepFaceLab (基于 Python 3.12 + TensorFlow 2.21.0 + CUDA 12.8 + BF16/FP32 混合精度)，底层计算框架依赖 Linux/WSL2 环境运行。

### 1.2 目标
构建一套**“WSL2 高性能算力引擎 + Windows 宿主机 UI”**的解耦系统：
- **算力引擎（后端）**：运行于 WSL2，负责极致性能的模型训练、人脸提取、预览图生成。
- **用户界面（前端）**：运行于 Windows 宿主机，通过 Web 或桌面 UI 实现交互式的模型/素材选择、参数配置、控制下发、实时 Loss 曲线展示及支持滚轮缩放的预览图监控。

---

## 2. 整体系统架构设计

```mermaid
graph TD
    subgraph Windows 宿主机 (Client & UI)
        UI[Windows 前端界面 (Vue3 / React / Tauri)]
        BrowserPreview[内置图像观察器 (支持滚轮缩放/拖拽)]
        ChartModule[Loss 曲线与日志面板]
    end

    subgraph WSL2 Linux 容器/环境 (Backend & Engine)
        API[FastAPI 服务网关 (HTTP/WebSocket)]
        ProcessMgr[进程与任务管理器 (Process Manager)]
        
        subgraph DFL 核心引擎
            Trainer[Trainer 训练模块 (main.py train)]
            Extractor[Extractor 提取模块 (main.py extract)]
            Merger[Merger 合成模块 (main.py merge)]
        end
        
        DiskStorage[模型与数据集存储 (/mnt/d/workspace or ~/workspace)]
    end

    subgraph 硬件算力 (NVIDIA GPUs)
        GPU0[RTX 3090 (主训卡 - 24GB)]
        GPU1[RTX Pro 5000 (切脸/辅助卡)]
    end

    UI -->|HTTP REST (配置/操控)| API
    UI <-->|WebSocket (日志/指标流)| API
    BrowserPreview -->|HTTP GET 定时轮询 /preview| API
    
    API --> ProcessMgr
    ProcessMgr -->|子进程/线程控制| DFL 核心引擎
    
    Trainer -->|写出 preview.png & autobackup| DiskStorage
    DFL 核心引擎 -->|CUDA 调度| GPU0
    DFL 核心引擎 -->|CUDA 调度| GPU1
```

---

## 3. 核心功能模块设计

### 3.1 后端 API 服务层 (FastAPI - WSL2 侧)

后端在 WSL2 内部运行一个轻量级的 Python FastAPI 服务：
1. **任务控制模块**：
   - 管理 DFL 子进程（启动训练、优雅停止并安全保存权重、切换模型与参数）。
   - 拦截标准输出（stdout/stderr），实时解析当前 Iteration、Loss 变化及训练 FPS。
2. **预览图服务模块**：
   - 提供 `GET /api/train/preview` 静态/缓存图片接口，将模型目录下生成的 `preview.png` 返回给前端。
3. **资源与目录扫描模块**：
   - 扫描 `workspace/data_src`、`workspace/data_dst` 及 `workspace/model` 下的现有素材和已建模型。

### 3.2 宿主机前端 UI (Windows 侧)

建议前端基于 **Web (Vue 3 + Vite + Tailwind3)** 或 **Tauri (桌面客户端包装)** 开发：
1. **仪表盘 (Dashboard)**：
   - **模型与路径选择器**：可视化选择模型类型（SAEHD / Quick96 / AMP 等）、数据集路径。
   - **超参数配置面板**：设置 Batch Size、Learning Rate、GAN 模式、混合精度开关 (BF16)、绑定的 GPU 编号。
2. **实时监控与预览面板 (Training Panel)**：
   - **交互式 Preview 观察器**：支持实时显示生成的预览对比图，支持鼠标滚轮放大/缩小查看细节、鼠标拖拽平移。
   - **Loss 折线图**：通过 ECharts / Chart.js 实时渲染 `src_loss` 与 `dst_loss` 趋势。
   - **终端控制台**：实时滚动显示训练输出与错误日志。
3. **控制按钮**：
   - 【开始训练】、【保存并停止】、【刷新预览】。

---

## 4. API 契约草案 (API Protocol Draft)

### 4.1 RESTful API

| 接口路径 | HTTP 方法 | 功能描述 |
| :--- | :--- | :--- |
| `/api/system/gpus` | `GET` | 查询当前可用 GPU 列表（RTX 3090, Pro 5000 等）及显存状态 |
| `/api/workspace/scan` | `GET` | 扫描工作区目录下的模型文件与素材文件夹列表 |
| `/api/train/start` | `POST` | 启动模型训练任务，提交参数 JSON |
| `/api/train/stop` | `POST` | 发送安全停止与保存指令 |
| `/api/train/status` | `GET` | 获取当前训练状态（IDLE / TRAINING / STOPPING） |
| `/api/train/preview` | `GET` | 获取最新生成的渲染预览图片 (`image/png`) |

### 4.2 WebSocket 接口

* `WS /api/ws/training-metrics`
  - **后端推送数据结构**：
    ```json
    {
      "iteration": 12500,
      "src_loss": 0.0412,
      "dst_loss": 0.0385,
      "fps": 18.5,
      "timestamp": 1720000000
    }
    ```

---

## 5. 多 GPU 调度策略

* **默认分配策略**：
  - **RTX 3090 (24GB)**：绑定 `CUDA_VISIBLE_DEVICES=0`，专用于 SAEHD/AMP 等高负载模型的 BF16 混合精度训练。
  - **RTX Pro 5000**：绑定 `CUDA_VISIBLE_DEVICES=1`，用于后台跑切脸提取 (`extract`) 或预览渲染，实现训练与切脸互不干扰。

---

## 6. 后续开发实施路线图

1. **Phase 1: API 服务骨架封装 (WSL2)**
   - 在 DFL 项目中引入 `api_server.py` (FastAPI)。
   - 实现管理 `main.py train` 子进程的轻量级 Wrapper。
2. **Phase 2: 预览图与 WebSocket 通信调通**
   - 验证 `GET /api/train/preview` 的图片读取与缓存策略。
   - 调通 WebSocket 日志与 Loss 数据流。
3. **Phase 3: 宿主机 UI 界面开发 (Windows/Web)**
   - 搭建 Vue 3 / Vite 基础前端框架与组件布局。
   - 集成鼠标缩放组件（如 `panzoom` 或 `viewerjs`）与 ECharts Loss 曲线。
4. **Phase 4: 联调与测试**
   - 在 3090 + Pro 5000 硬件环境下进行长时训练稳定性验证。

---
*初稿完成，待后续开发推进时细化具体参数规格。*
