# DeepFaceLab TF2.x 当前项目架构与升级分析

> 文档版本：v1.1（代码基线）  
> 文档类型：Phase 1 项目现状分析  
> 更新日期：2026-07-25

---

## 1. 文档目标

本文档用于建立当前项目的真实技术基线，明确：

- 项目当前定位与演进方式
- 完整业务流程和代码模块
- TF2.x 升级覆盖范围
- 已实现、已接通、待验证和仅设计能力
- 当前主要技术收益与技术债
- 第二阶段训练、Extract、Faceset、Merge 优化顺序
- 第三阶段 Linux 服务化与 UI 的启动条件

本文档是项目总览，不替代专项审计。详细状态和风险参见：

- [TF2.x 升级实现分析](dfl-tf2-upgrade-analysis.md)
- [训练架构分析](training-architecture-analysis.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [文档总索引](../README.md)

---

## 2. 项目定位

当前项目并非完全重写的原生 TensorFlow 2 / Keras 项目，而是在 DeepFaceLab 原有代码体系上进行的现代化升级。

整体演进：

```text
原版 DeepFaceLab
        ↓
Python 3.12 运行环境
        ↓
TensorFlow 2.21 Runtime
        ↓
tensorflow.compat.v1 + disable_v2_behavior
        ↓
Leras 静态图、Session、placeholder
        ↓
SAEHD / DF / LIAE 训练体系
        ↓
新增现代 GPU、低精度、优化器、IPC 等改造
```

因此，当前最准确的架构定义是：

> **TensorFlow 2 Runtime + compat.v1 静态图 + Leras 自定义网络层的混合架构。**

这条路线的重点是：

- 保留 DeepFaceLab 原训练逻辑和模型体系。
- 降低一次性重写为原生 TF2 的风险。
- 先解决现代 Python、CUDA 和新 GPU 的可运行性。
- 在现有 Leras 架构中逐步验证和引入性能优化。

它并不意味着：

- 已经使用 `tf.function` 重写训练循环。
- 已经全面采用 `tf.data`。
- 已经使用标准 Keras Layer、Model 和 Optimizer 生命周期。
- 设置 Keras mixed precision policy 后，Leras 自定义变量就自动成为标准混合精度实现。

---

## 3. 当前技术栈

| 层级 | 当前技术 | 说明 |
|---|---|---|
| Python | Python 3.12 | 面向现代 Python 环境 |
| TensorFlow | TensorFlow 2.21 | 提供现代运行时和 CUDA 支持 |
| 图执行模式 | `tensorflow.compat.v1` | 继续使用静态图、Session、placeholder |
| 网络框架 | Leras | DeepFaceLab 自定义 Layer、Model、Optimizer、Ops |
| 主训练模型 | SAEHD | 支持 DF、LIAE 等架构路径 |
| GPU 运行时 | CUDA 12.x、cuDNN 9 方向 | 具体驱动/小版本兼容仍需形成测试矩阵 |
| 图像处理 | OpenCV 等 | Extract、Faceset、Merge 大量依赖 CPU 图像操作 |
| 并行机制 | multiprocessing + Queue | 用于样本生成、IPC 和部分任务并行 |
| 主要平台 | 当前以现代 NVIDIA GPU 环境为主 | WSL2/Linux 服务化仍属于后续阶段 |

依赖定义主要位于：

```text
requirements.txt
```

TensorFlow/Leras 初始化主要位于：

```text
core/leras/nn.py
core/leras/device.py
core/leras/optimizations.py
```

---

## 4. 项目分层架构

### 4.1 命令与流程入口

```text
main.py
```

负责提供主要命令入口，包括：

- 视频/图片处理
- 人脸提取
- 模型训练
- 模型合成
- 数据和模型辅助操作

当前 CLI 仍然是主要操作方式，配置大量依赖交互式输入和命令参数。

### 4.2 核心运行层

```text
core/
├── leras/       TensorFlow、Layer、Model、Optimizer、Ops
├── joblib/      多进程、队列、子进程生成器
├── imagelib/    图像处理
└── ...
```

### 4.3 人脸能力层

```text
facelib/
```

主要负责：

- 人脸检测
- Landmark
- 对齐与变换
- XSeg 等人脸相关能力

### 4.4 数据与采样层

```text
samplelib/
```

主要负责：

- Faceset 样本读取
- 样本增强
- Batch 生成
- 训练数据供给

### 4.5 模型层

```text
models/
└── Model_SAEHD/
```

主要负责：

- 训练参数
- 模型构建
- 多 GPU tower
- Loss 构建
- 梯度计算
- Optimizer 更新
- 保存、恢复、Preview 和推理入口

### 4.6 合成层

```text
merger/
```

主要负责：

- 模型 predictor 调用
- Mask 生成与调整
- Warp、resize、颜色匹配
- seamless clone、锐化、模糊、降噪
- 多脸组合
- 输出帧生成

---

## 5. 当前完整业务流程

```text
输入视频
   ↓
视频拆帧
   ↓
人脸检测
   ↓
Landmark 与对齐
   ↓
Faceset 输出
   ↓
人工/脚本整理 Faceset
   ↓
SampleGenerator 读取与增强
   ↓
SAEHD 模型训练
   ↓
模型保存与 Preview
   ↓
模型 predictor 推理
   ↓
Mask、Warp、颜色和融合处理
   ↓
输出帧
   ↓
视频编码
```

从工程优化角度，可以拆成三条主链路：

1. **训练链路**：Faceset → SampleGenerator → SAEHD → Loss → Optimizer → Checkpoint。
2. **切脸与数据链路**：视频/图片 → Detector → Landmark → Align → Faceset → 分析与整理。
3. **合成链路**：帧与对齐信息 → Predictor → Mask/颜色/融合 → 输出帧 → 编码。

项目当前最重要的是第一条链路。

---

## 6. TF2.x 升级范围

### 6.1 环境升级

已完成的主要方向：

- Python 3.12 环境适配
- TensorFlow 2.21 Runtime
- CUDA 12.x 依赖方向
- cuDNN 9 方向
- 现代 NVIDIA GPU 基础支持

实际价值：

- 降低旧版 DFL 环境部署难度。
- 允许在新驱动和新 GPU 上继续运行现有训练体系。
- 为后续 BF16、现代 Tensor Core 和新算子探索提供运行基础。

### 6.2 GPU 检测与能力判断

主要代码：

```text
core/leras/device.py
core/leras/nn.py
```

当前包含：

- GPU 枚举
- GPU 名称和显存信息
- 架构/能力判断
- 不同设备配置入口

需要注意：

> 检测到某项硬件能力，不等于训练主流程已经真正使用该能力。

例如架构标签、Flash Attention 能力、自动精度判断等，必须继续检查是否实际影响网络、算子或参数选择。

### 6.3 精度支持

当前配置方向包括：

- FP32
- FP16
- BF16

相关代码主要分布于：

```text
models/Model_SAEHD/Model.py
core/leras/nn.py
core/leras/optimizations.py
core/leras/archis/DeepFakeArchi.py
core/leras/layers/Conv2D.py
core/leras/layers/Dense.py
```

当前最大问题不是“有没有 BF16 选项”，而是：

- 权重是否保留 FP32 master copy。
- 激活和计算是否使用 BF16。
- 梯度在哪里转换和聚合。
- Optimizer state 是否保持 FP32。
- Loss Scaling 是否适用于当前精度。
- 所有 Loss 是否经过一致的缩放。

这些问题已被列入 Phase 2 的 P0 正确性审计。

### 6.4 Optimizer 扩展

当前提供或扩展：

- Adam
- AdaBelief
- Lion
- CPU optimizer state/offload 方向

主要入口：

```text
core/leras/optimizers/
models/Model_SAEHD/Model.py
```

当前状态：

- 优化器选择入口已接通。
- CPU state 路径需要显存和吞吐对照。
- AdaBelief slot dtype 需要核对。
- Lion 更新逻辑需要按标准算法重新审计。

### 6.5 数据管线优化

当前增加或强化方向：

- 多进程样本生成
- Prefetch
- FP16 IPC
- 子进程队列传输

主要代码：

```text
samplelib/SampleGeneratorFace.py
core/joblib/SubprocessGenerator.py
```

当前 FP16 IPC 大致行为：

```text
Worker 产生 FP32 Batch
        ↓
转成 FP16
        ↓
multiprocessing.Queue 序列化传输
        ↓
主进程接收
        ↓
重新转为 FP32
        ↓
feed_dict 输入训练图
```

它可能降低 IPC 数据体积，但仍存在：

- 两次 dtype 转换
- 内存复制
- pickle/Queue 开销
- 主进程阻塞

是否有效必须通过数据等待比例和吞吐 Benchmark 证明。

### 6.6 多 GPU

当前 SAEHD 支持：

- 按 GPU 数量拆分 Batch
- 每张 GPU 建立 tower
- 聚合多卡梯度
- 统一更新参数

需要继续验证：

- 梯度是否在 FP32 中聚合。
- 不同 GPU 是否产生额外同步和复制。
- 异构 GPU 是否被最慢设备拖累。
- CPU optimizer state 是否放大多 GPU 同步开销。

默认建议：

- 同型号 GPU 可以进入同步训练 Benchmark。
- 异构 GPU 优先考虑训练、Extract、XSeg、Merge 任务分工，而不是直接同步训练。

---

## 7. 当前能力状态总表

| 模块 | 当前状态 | 结论 |
|---|---|---|
| Python 3.12 | 已实现，待完整兼容测试 | 现代环境基础 |
| TensorFlow 2.21 Runtime | 已实现 | 运行时升级，不是原生 TF2 重写 |
| compat.v1 静态图 | 已接通 | 保留 DFL 核心兼容性，也限制 TF2 原生能力 |
| CUDA 12.x | 已配置，待环境矩阵验证 | 需明确驱动和小版本组合 |
| 新 GPU 检测 | 已实现 | 部分能力标签未转化为实际优化 |
| FP32 | 已接通 | 当前正确性和质量基线 |
| FP16 | 已接通，待验证 | 需审计 Loss Scaling、slot 和恢复 |
| BF16 | 已接通，存在问题 | 当前可能直接创建 BF16 权重，不是标准混合精度 |
| Lion | 已接通，存在问题 | 需要按标准算法重新实现或修正 |
| AdaBelief | 已接通，待验证 | 重点检查 optimizer state dtype |
| Optimizer CPU state | 已接通，待 Benchmark | 可能节省显存，也可能降低吞吐 |
| FP16 IPC | 已接通，待 Benchmark | 降低传输体积但增加转换和复制 |
| Prefetch | 已接通，待调优 | 固定深度未必适合所有机器 |
| 多 GPU | 已实现，待正确性和收益验证 | 异构卡不一定适合同步训练 |
| Dynamic Batch | 代码骨架 | 尚未形成可靠主流程策略 |
| Gradient Checkpoint | 设计阶段 | 需先解决 P0 正确性问题 |
| Gradient Accumulation | 设计阶段 | 需明确优化器步进语义 |
| LossWeightedSampler | 设计阶段 | 需防止异常样本被过度采样 |
| Dedup / Faceset Analyzer | 设计阶段 | 高价值的后续数据优化方向 |
| CBAM | 设计阶段 | 需要质量与性能消融实验 |
| FFL | 设计阶段 | 需要先完成 Loss 梯度审计 |
| LPIPS | 设计阶段 | 计算和显存成本需评估 |
| WSL2/Linux 后端 | 设计阶段 | Phase 3，当前冻结实施 |
| Windows/Tauri/Web UI | 设计阶段 | 核心引擎稳定后启动 |

完整矩阵参见：[实现状态与风险矩阵](implementation-status-and-risk-matrix.md)。

---

## 8. 当前升级的主要优点

### 8.1 保留原 DFL 能力

没有立即重写整个训练栈，降低了以下风险：

- 模型架构行为变化
- 旧模型不兼容
- 训练参数语义变化
- 一次性重构范围过大

### 8.2 现代环境可运行性

项目已经具备面向新 Python、TensorFlow、CUDA 和 GPU 演进的基础，不再完全受旧版 TensorFlow 1.x 环境限制。

### 8.3 优化入口增多

已经有明确入口用于继续优化：

- 精度策略
- Optimizer
- CPU optimizer state
- IPC 和 Prefetch
- 多 GPU
- 设备能力判断

### 8.4 为服务化准备基础

虽然尚未进入 UI 开发，但当前代码分析已经明确未来需要：

- 结构化配置
- 结构化训练事件
- 可查询任务状态
- 模型和数据资产管理
- 可恢复任务流程

---

## 9. 当前主要问题

### 9.1 TF2 Runtime 与原生 TF2 概念混淆

当前使用 TF2.21，但训练仍运行在 compat.v1 静态图模式。后续文档和宣传必须区分：

```text
运行时升级 ≠ 训练架构已经原生 TF2 化
```

### 9.2 BF16 混合精度实现需要重构

当前 Leras Layer 可能直接以 BF16 创建权重，导致：

- 缺少 FP32 master weights。
- 更新精度不足。
- Optimizer state 可能继承 BF16。
- 保存恢复和旧模型兼容复杂化。

### 9.3 Loss Scaling 顺序风险

部分基础 Loss 先缩放，后续 GAN、TrueFace、TV 等 Loss 再加入，最终统一反缩放，可能导致后加入项的梯度被额外缩小。

这是训练正确性 P0。

### 9.4 Lion 实现风险

当前 Lion 更新需要重新核对：

- 双 beta 更新语义
- sign update
- momentum 更新顺序
- weight decay
- slot dtype

### 9.5 Benchmark 缺失

当前无法可靠回答：

- BF16 是否更快。
- FP16 IPC 是否真的提升吞吐。
- CPU optimizer state 是否值得开启。
- 多 GPU 加速比例是多少。
- 同样训练步数下质量是否提高。

### 9.6 Extract 与 Merge 仍偏串行

Extract 和 Merge 保留大量：

- 逐帧
- 逐脸
- CPU OpenCV
- 多次内存复制
- 缺少批处理和阶段流水线

但这些应在训练主链路稳定后再进入专项优化。

---

## 10. 三阶段路线

### Phase 1：当前项目与 TF2.x 升级分析

目标：

- 建立项目架构基线。
- 明确每项升级的代码入口。
- 建立实现状态和风险矩阵。
- 梳理训练、Extract、Merge 当前调用链。

当前状态：

```text
总索引：已完成
项目总览：v1.1
TF2.x 实现分析：v1.1
训练架构分析：v1.1
状态风险矩阵：已完成
Extract 独立分析：待创建
Merge 独立分析：待创建
建议完成度：约 55%
```

### Phase 2：核心引擎优化

固定顺序：

```text
训练正确性审计
        ↓
统一 Benchmark
        ↓
训练性能与显存优化
        ↓
数据与采样优化
        ↓
Loss 与网络结构实验
        ↓
Extract / Faceset 优化
        ↓
Merge 与时序稳定性优化
```

当前最重要的下一份文档：

```text
docs/optimization/training-correctness-audit.md
```

### Phase 3：Linux 服务化与 UI

启动条件：

- 训练核心链路通过正确性验证。
- Benchmark 和兼容测试稳定。
- Extract 和 Merge 参数能够结构化传入。
- 训练、提取、合成过程能够输出结构化事件。
- 核心流程不再强依赖终端交互式输入。

当前只保留设计，不进入主要开发。

---

## 11. 为 Phase 3 提前保留的工程原则

Phase 2 修改核心代码时，应避免继续扩大终端耦合。

### 11.1 结构化配置

未来至少需要：

```text
TrainingConfig
ExtractionConfig
MergeConfig
DeviceConfig
```

CLI、API 和 UI 应共用同一配置模型。

### 11.2 结构化事件

训练过程未来应输出类似：

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

### 11.3 核心逻辑与展示分离

训练、提取和合成核心逻辑不应直接依赖：

- 终端清屏
- 键盘监听
- 交互式问答
- Preview 窗口生命周期

这些应逐步改造成可插拔适配层，但不需要在 Phase 2 初期一次性重写。

---

## 12. Phase 1 完成标准

只有满足以下条件，Phase 1 才能正式结束：

- [x] 建立文档总索引。
- [x] 建立项目总体架构分析。
- [x] 建立 TF2.x 升级实现分析。
- [x] 建立训练架构分析。
- [x] 建立实现状态与风险矩阵。
- [ ] 建立 Extract 架构分析。
- [ ] 建立 Merge 架构分析。
- [ ] 建立环境、GPU、模型和导出兼容矩阵。
- [ ] 将第一轮代码审计问题转入正式 P0 任务清单。

Phase 1 不要求所有问题已经修复，但必须明确：

```text
问题在哪里、为什么是问题、如何验证、后续由哪份文档和任务处理。
```

---

## 13. 当前结论

当前项目已经完成 DeepFaceLab 向现代运行环境演进的重要基础工作，但仍属于需要系统审计和验证的实验性升级版本。

下一阶段不应继续以“增加功能数量”为目标，而应以以下四个结果为目标：

1. 证明训练数值正确。
2. 证明优化确实提升吞吐或显存效率。
3. 证明优化不破坏模型恢复和输出质量。
4. 建立可重复的 Benchmark 和回归验证体系。

完成这些工作后，再进入 Extract、Merge，以及最终 Linux 服务化与 UI 建设。
