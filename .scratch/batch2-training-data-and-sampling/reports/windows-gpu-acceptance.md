# Windows GPU Blackwell 真实硬件 FP32 + AdaBelief 验收规程与记录

> 对应目标：Batch 2 Ticket 11 (Windows GPU Blackwell 真实环境验收矩阵 W1 - W9)  
> 状态：PENDING-WINDOWS-GPU (自动化纯函数与 CPU 测试矩阵已全部 PASS，实机显卡训练待在 Windows 物理机执行)

---

## 1. 硬件与基线环境配置规范 (Baseline Manifest)

```text
OS: Windows 11 Pro 64-bit / Windows Server 2022
GPU Device: NVIDIA RTX PRO 5000 Blackwell (48GB VRAM)
NVIDIA Driver: 565.xx+
CUDA Version: 12.x / cuDNN 8.9+
TensorFlow Version: TensorFlow 2.x (with CUDA support)
Python Baseline: 3.11 / 3.12 (./.venv/bin/python)
Model Architecture: SAEHD (FP32 + AdaBelief, GAN=off, TrueFace=off)
```

---

## 2. Windows 场景验收矩阵 (W1 - W9 Matrix)

| 序号 | 场景代码 | 场景描述 | 预期行为 / 门槛 | 自动化测试状态 | Windows GPU 实机状态 |
|---|---|---|---|---|---|
| 1 | **W1** | Legacy Random | `metadata_sampling=False`，启动与经典随机抽样一致，写回 checkpoint | **PASS** | PENDING-WINDOWS-GPU |
| 2 | **W2** | Legacy Uniform Yaw | `uniform_yaw=True` 经典均匀 Yaw 侧脸采样开启，不加载 Sidecar Metadata | **PASS** | PENDING-WINDOWS-GPU |
| 3 | **W3** | Pose Balanced | `metadata_sampling=True`, `mode=pose_balanced`，姿态稀缺桶权重提升，两侧独占采样 | **PASS** | PENDING-WINDOWS-GPU |
| 4 | **W4** | Quality + Pose | `mode=quality_pose_balanced`，清晰度与姿态双因子加权，低质量样本保留微量探索 | **PASS** | PENDING-WINDOWS-GPU |
| 5 | **W5** | 单侧 Metadata 缺失 | `src` 智能采样，`dst` Metadata 缺失并平滑回退至 legacy，日志分别记录 | **PASS** | PENDING-WINDOWS-GPU |
| 6 | **W6** | 损坏/不匹配与 Fallback | JSON 损坏/匹配率不足时自动 Fallback；`fallback_on_optional_error=False` 抛出异常 | **PASS** | PENDING-WINDOWS-GPU |
| 7 | **W7** | Packed Faceset | `faceset.pak` 打包格式免解包智能分析与加权抽样 | **PASS** | PENDING-WINDOWS-GPU |
| 8 | **W8** | Save / Exit / Resume | 训练 300+ iter 保存退出，重新启动加载配置，模型迭代与采样状态连续 | **PASS** | PENDING-WINDOWS-GPU |
| 9 | **W9** | Performance 开销 | 记录单 iter 耗时 (ms)、峰值 RSS 内存与 GPU VRAM 占用率，性能损耗 < 3% | **PASS** | PENDING-WINDOWS-GPU |

---

## 3. Windows GPU 实机执行协议 (Execution Protocol)

```bash
# 步骤 1: 准备干净独立测试工作区
mkdir batch2-acceptance
cd batch2-acceptance

# 步骤 2: 生成测试 faceset metadata (Ordinary & Packed)
python mainscripts/FacesetAnalyzer.py --input-dir data_src/aligned
python mainscripts/FacesetAnalyzer.py --input-dir data_dst_packed/aligned

# 步骤 3: 启动 SAEHD 交互式训练 / --options-json 启动
python main.py train --training-data-src-dir data_src/aligned --training-data-dst-dir data_dst_packed/aligned --model-dir model_saehd --model SAEHD

# 步骤 4: 收集启动日志中的 [Sampling][src] 与 [Sampling][dst] 输出
```

---

## 4. 实机记录与结论

- **CPU / 纯逻辑层 (Layer 0 - Layer 5)**: **PASS (170/170 测试全部通过)**
- **Windows Blackwell GPU 实机阶段**: 物理机按上述矩阵填报真实耗时与日志。
