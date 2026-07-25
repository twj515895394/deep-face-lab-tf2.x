# DeepFaceLab TF2.x 当前项目架构与升级分析

> 文档版本：v1.2（项目总览）  
> 文档类型：Phase 1 项目现状分析  
> 更新日期：2026-07-25

---

## 1. 文档定位

本文档是项目总览，用于统一说明：

- 当前项目的真实技术定位
- Extract、Training、Merge 三条主链路
- TF2.x 升级覆盖范围
- 已实现、待验证和仅设计的能力
- 当前最高优先级风险
- Phase 1、Phase 2、Phase 3 的执行边界

专项细节请继续阅读：

- [文档总索引](../README.md)
- [TF2.x 升级实现分析](dfl-tf2-upgrade-analysis.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [Extract / 切脸架构分析](extraction-architecture-analysis.md)
- [训练架构分析](training-architecture-analysis.md)
- [Merge / 合成架构分析](merging-architecture-analysis.md)

---

## 2. 项目定位

当前项目不是完全重写的原生 TensorFlow 2 / Keras 项目，而是 DeepFaceLab 的现代化兼容升级版本。

```text
原版 DeepFaceLab
        ↓
Python 3.12
        ↓
TensorFlow 2.21 Runtime
        ↓
tensorflow.compat.v1 + disable_v2_behavior
        ↓
Leras 静态图、Session、placeholder
        ↓
SAEHD / DF / LIAE
        ↓
新增现代 GPU、低精度、优化器、IPC 等改造
```

当前最准确的架构定义：

> **TensorFlow 2 Runtime + compat.v1 静态图 + Leras 自定义网络层的混合架构。**

这意味着项目已经升级运行环境，但尚未完成：

- 原生 `tf.keras.Model` 重写
- 原生 Keras Optimizer 生命周期
- `tf.function` 训练步
- 全量 `tf.data` 管线
- `tf.distribute` 多 GPU
- 标准 Keras mixed precision 全链路

因此必须区分：

```text
TensorFlow Runtime 升级 ≠ 训练架构已经原生 TF2 化
```

---

## 3. 当前技术栈

| 层级 | 当前技术 | 说明 |
|---|---|---|
| Python | Python 3.12 | 面向现代依赖环境 |
| TensorFlow | TensorFlow 2.21 | 提供现代 Runtime 和 CUDA 支持 |
| 图执行 | `tensorflow.compat.v1` | 静态图、Session、placeholder、feed_dict |
| 网络框架 | Leras | 自定义 Layer、Model、Optimizer、Ops |
| 主训练模型 | SAEHD | DF、LIAE 等架构路径 |
| GPU 运行时 | CUDA 12.x、cuDNN 9 方向 | 具体组合仍需兼容性测试 |
| 图像处理 | OpenCV / NumPy | Extract 与 Merge 大量 CPU 处理 |
| 并行 | multiprocessing / Queue | SampleGenerator、Extract、Merge 任务 |
| 主要入口 | CLI | 未来再逐步结构化为服务接口 |

核心初始化和依赖入口：

```text
requirements.txt
core/leras/nn.py
core/leras/device.py
core/leras/optimizations.py
main.py
```

---

## 4. 项目模块分层

```text
main.py / mainscripts/
        ↓
业务流程和 CLI 调度

core/
├── leras/       TensorFlow、Layer、Optimizer、Ops
├── joblib/      多进程和 IPC
├── imagelib/    图像处理
└── ...

facelib/
        ↓
Detector、Landmark、XSeg、几何变换

samplelib/
        ↓
Faceset 读取、增强、Batch 和采样

models/Model_SAEHD/
        ↓
构图、Loss、Gradient、Optimizer、保存和推理

merger/
        ↓
Predictor、Mask、颜色、融合和输出帧
```

---

## 5. 完整业务流程

```text
输入视频
   ↓
视频拆帧
   ↓
人脸检测
   ↓
Landmark 与对齐
   ↓
Faceset 输出和整理
   ↓
SampleGenerator 读取与增强
   ↓
SAEHD 训练
   ↓
模型保存、恢复和 Preview
   ↓
Predictor 推理
   ↓
Mask、Warp、颜色和融合
   ↓
输出帧
   ↓
视频编码
```

工程上分成三条主链路：

1. **Extract / 数据链路**：图片或视频帧 → Detector → Landmark → Align → Faceset。
2. **Training 链路**：Faceset → SampleGenerator → SAEHD → Loss → Gradient → Optimizer → Checkpoint。
3. **Merge 链路**：帧和 Landmark → Predictor → Mask/颜色/融合 → 输出帧 → 编码。

当前最高优先级是 Training 链路。

---

## 6. Extract 当前架构

主要代码：

```text
mainscripts/Extractor.py
facelib/
DFLIMG/
core/joblib/Subprocessor.py
```

当前能力：

- S3FD 人脸检测
- FAN Landmark
- 旋转图检测
- GPU/CPU worker
- 手动 Landmark 修正
- Face type 对齐
- JPEG Faceset 输出
- DFLJPG 元数据写入

主要技术债：

- Detector 和 Landmark 缺少 Batch inference。
- 每个 worker 同时承担模型、OpenCV 和文件 I/O。
- 视频相邻帧没有 tracking 和时序平滑。
- Final 阶段包含逐脸 Warp、JPEG 编码和二次元数据写入。
- Faceset 输出后缺少清晰度、遮挡、身份、重复和姿态分析。

详细内容参见：[Extract / 切脸架构分析](extraction-architecture-analysis.md)。

---

## 7. Training 当前架构

主要代码：

```text
models/Model_SAEHD/Model.py
models/ModelBase.py
core/leras/
samplelib/SampleGeneratorFace.py
core/joblib/SubprocessGenerator.py
```

当前能力：

- SAEHD、DF、LIAE
- FP32、FP16、BF16 入口
- Adam、AdaBelief、Lion
- CPU optimizer state
- 多 GPU tower
- Prefetch 和 FP16 IPC
- GAN、TrueFace、eyes/mouth、mask 等训练分支
- 模型保存、恢复和 Preview

当前最重要风险：

1. BF16 可能直接创建低精度模型权重。
2. Optimizer state 可能跟随 BF16 变量类型。
3. Generator Loss Scaling 顺序可能使后加入 Loss 梯度失效。
4. BF16 默认使用大 Loss Scale 的必要性存疑。
5. Lion 实现需要按标准算法重新核对。
6. 多 GPU 梯度可能在低精度中直接平均。
7. 缺少固定 Benchmark 和保存恢复回归矩阵。

详细内容参见：

- [训练架构分析](training-architecture-analysis.md)
- [TF2.x 升级实现分析](dfl-tf2-upgrade-analysis.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)

---

## 8. Merge 当前架构

主要代码：

```text
merger/MergeMasked.py
merger/MergerConfig.py
mainscripts/Merger.py
```

当前能力：

- SAEHD predictor
- learned、destination、XSeg 等多种 mask
- Erode、Dilate、Blur
- 多种颜色迁移和 histogram match
- seamlessClone
- Face Enhancer / Super Resolution
- Motion Blur、Sharpen、Denoise、Degrade
- 多脸组合

主要技术债：

- Predictor、XSeg、Enhancer 逐脸调用，缺少 Batch。
- 大量 `warpAffine`、`resize` 和 OpenCV CPU 操作。
- 多脸时可能重复执行帧级全局处理。
- 图像和 mask 临时副本较多。
- 缺少颜色、mask、Landmark 和输出的时序平滑。
- Decode、Predict、Merge、Encode 尚未形成统一流水线。

详细内容参见：[Merge / 合成架构分析](merging-architecture-analysis.md)。

---

## 9. TF2.x 升级内容

### 9.1 已完成的工程升级

- Python 3.12 方向
- TensorFlow 2.21 Runtime
- CUDA 12.x / cuDNN 9 方向
- 现代 NVIDIA GPU 枚举和信息检测
- FP32 / FP16 / BF16 配置入口
- Lion 优化器入口
- CPU optimizer state
- Prefetch
- FP16 IPC
- 多 GPU tower

### 9.2 已确认的主要价值

- 旧 DFL 训练体系可以继续运行在现代软件环境。
- 新 GPU 和新驱动具备适配基础。
- 后续精度、优化器和数据管线有明确扩展入口。
- UI 和 Linux 服务化不必继续绑定旧 TensorFlow 1.x 环境。

### 9.3 尚未证明的收益

以下结论必须通过 Benchmark 才能成立：

- BF16 是否真正提高吞吐。
- FP16 是否保持质量和稳定性。
- Lion 是否更快收敛。
- CPU optimizer state 是否综合收益为正。
- FP16 IPC 是否减少总迭代时间。
- 多 GPU 是否获得合理扩展效率。
- 硬件检测是否真正转化为自动优化。

---

## 10. 功能状态摘要

| 模块 | 状态 | 当前判断 |
|---|---|---|
| Python 3.12 | 已实现，待矩阵验证 | 现代环境基础 |
| TensorFlow 2.21 | 已实现 | Runtime 升级 |
| compat.v1 | 已接通 | 保留兼容性，也限制原生 TF2 能力 |
| CUDA 12.x | 已配置，待验证 | 需要驱动和 GPU 组合测试 |
| FP32 | 已接通 | 当前基线 |
| FP16 | 已接通，待验证 | 需审计 dtype、scale 和恢复 |
| BF16 | 已接通，存在问题 | 需要 FP32 master weight 方向重构 |
| Adam | 已接通 | 基准优化器 |
| AdaBelief | 已接通，待验证 | 需检查 slot dtype |
| Lion | 已接通，存在问题 | 需按标准算法修正 |
| CPU optimizer state | 已接通，待 Benchmark | 显存与吞吐权衡 |
| FP16 IPC | 已接通，待 Benchmark | 数据减半但有转换和复制 |
| 多 GPU | 已实现，待验证 | 同型号优先，异构卡不宜默认同步 |
| Dynamic Batch | 代码骨架 | 尚未形成可靠策略 |
| Gradient Checkpoint | 设计阶段 | P0 修复后再开发 |
| Gradient Accumulation | 设计阶段 | Benchmark 后评估 |
| Faceset Analyzer | 设计阶段 | 后续高价值方向 |
| CBAM / FFL / LPIPS | 设计阶段 | 必须做消融实验 |
| Linux 后端 / UI | 设计阶段 | 当前冻结实施 |

完整状态参见：[实现状态与风险矩阵](implementation-status-and-risk-matrix.md)。

---

## 11. 当前执行路线

### Phase 1：项目现状与 TF2.x 升级分析

当前状态：主体完成，进入收尾。

已完成：

- [x] 文档总索引
- [x] 项目总体架构分析
- [x] TF2.x 升级实现分析
- [x] 实现状态与风险矩阵
- [x] Extract 架构分析
- [x] Training 架构分析
- [x] Merge 架构分析

尚未完成：

- [ ] 环境、GPU、模型恢复和导出兼容矩阵
- [ ] 将 P0 问题转为正式审计和开发任务

建议完成度：**约 75%**。

Phase 1 不应继续无限扩写；后续应进入专项审计。

### Phase 2：核心引擎优化

固定顺序：

```text
训练正确性审计
        ↓
统一 Benchmark
        ↓
训练性能和显存优化
        ↓
数据和采样优化
        ↓
Loss 与网络结构实验
        ↓
Extract / Faceset 优化
        ↓
Merge 与时序稳定性优化
```

下一份正式文档：

```text
docs/optimization/training-correctness-audit.md
```

### Phase 3：Linux 服务化与 UI

启动条件：

- 训练核心链路通过正确性验证。
- Benchmark 和兼容性测试稳定。
- Extract、Training、Merge 参数可以结构化传入。
- 运行过程可以输出结构化事件。
- 核心流程不再强依赖终端交互和窗口。

当前只保留设计，实施冻结。

---

## 12. 为未来服务化保留的原则

Phase 2 新增代码应逐步支持：

```text
TrainingConfig
ExtractionConfig
MergeConfig
DeviceConfig
```

并输出结构化事件，例如：

```json
{
  "event": "training_iteration",
  "iteration": 12000,
  "src_loss": 0.042,
  "dst_loss": 0.039,
  "iteration_time_ms": 580,
  "data_wait_ms": 72,
  "gpu_memory_mb": 21120
}
```

这不代表提前开发完整 API，而是避免继续扩大核心逻辑与终端 UI 的耦合。

---

## 13. 当前结论

当前项目已经完成 DeepFaceLab 向现代 Python、TensorFlow Runtime、CUDA 和 GPU 环境演进的重要基础工作，并且 Extract、Training、Merge 三条主链路已经形成代码级文档基线。

下一阶段不应继续堆叠功能数量，而应完成四件事：

1. 证明训练数值正确。
2. 修正 BF16、Loss Scaling、Lion、Optimizer state 和低精度梯度等 P0 问题。
3. 建立固定数据、固定配置和固定指标的 Benchmark。
4. 证明优化不破坏模型恢复、输出质量和视频稳定性。

完成这些工作后，再进入更深的训练性能、质量算法、Extract、Merge，以及最终 Linux 服务化和 UI 建设。
