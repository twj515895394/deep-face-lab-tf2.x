# DeepFaceLab TF2.x 升级实现分析

> 文档版本：v1.1（代码实现版）  
> 文档类型：Phase 1 现状分析  
> 更新日期：2026-07-25

---

## 1. 文档目标

本文档用于分析当前 DeepFaceLab TF2.x 版本已经完成的现代化升级，重点回答：

- 升级到底发生在哪些代码层。
- TF2.x 带来的真实优点是什么。
- 哪些功能已经接入主流程。
- 哪些功能只有配置入口或代码骨架。
- 哪些实现存在训练正确性风险。
- 后续应如何验证，而不是仅凭理论收益判断。

本文不是训练算法方案。训练正确性、性能和质量优化将在后续专项文档中展开。

相关文档：

- [当前项目架构与升级分析](dfl-current-project-overview.md)
- [训练架构分析](training-architecture-analysis.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [文档总索引](../README.md)

---

## 2. 升级背景

原版 DeepFaceLab 长期依赖 TensorFlow 1.x 生态：

- 静态计算图
- Session 管理
- placeholder 输入
- 自定义 Leras Layer 和 Optimizer
- 旧版 Python、CUDA、cuDNN 环境

这套架构的优势是成熟、行为稳定、与现有模型一致；主要问题是：

- 新操作系统和新 Python 环境部署困难。
- 新 GPU 与新驱动支持受限。
- 现代混合精度、设备能力和内存管理难以扩展。
- 旧依赖逐步停止维护。
- 继续增加算法和服务化能力的工程成本高。

当前项目选择的是兼容式升级，而不是一次性原生化重写。

---

## 3. 当前升级路线

```text
Python 3.12
    ↓
TensorFlow 2.21 Runtime
    ↓
tensorflow.compat.v1
    ↓
disable_v2_behavior()
    ↓
Static Graph / Session / Placeholder
    ↓
Leras Layer / Model / Optimizer / Ops
    ↓
SAEHD / DF / LIAE
```

该方案的含义：

### 保留的部分

- 静态图构建方式
- Session 执行模式
- Leras 自定义层
- SAEHD 训练结构
- 原有模型保存和恢复思路
- 原训练参数和交互流程

### 升级的部分

- Python 和依赖环境
- TensorFlow Runtime
- CUDA / cuDNN 方向
- 新 GPU 检测
- FP16 / BF16 配置入口
- 新优化器入口
- CPU optimizer state
- IPC 与 Prefetch
- 多 GPU 适配逻辑

### 尚未完成的部分

- 原生 `tf.keras.Model` 重写
- 原生 Keras Optimizer 生命周期
- `tf.function` 训练步
- 完整 `tf.data` 管线
- 标准 Keras mixed precision 自动变量策略
- 原生 `tf.distribute` 多 GPU

因此项目应被描述为：

> **TF2 Runtime 兼容升级，而不是原生 TF2 训练架构重写。**

---

## 4. 代码实现映射

| 升级领域 | 主要代码/配置 | 作用 |
|---|---|---|
| 依赖环境 | `requirements.txt` | 定义 TensorFlow、Keras、NumPy、CUDA pip 依赖等 |
| TensorFlow 初始化 | `core/leras/nn.py` | 导入 `tensorflow.compat.v1`、禁用 v2 behavior、设置 dtype 和设备策略 |
| GPU 检测 | `core/leras/device.py` | GPU 枚举、显存、架构和能力信息 |
| 优化辅助 | `core/leras/optimizations.py` | mixed precision manager、动态 Batch 等辅助类 |
| 模型精度入口 | `models/Model_SAEHD/Model.py` | FP32/FP16/BF16 参数、Loss scale、optimizer、CPU state、多 GPU |
| 网络变量 dtype | `core/leras/archis/DeepFakeArchi.py` | 将精度选择传递到网络结构 |
| 卷积变量 | `core/leras/layers/Conv2D.py` | 创建卷积权重和执行卷积 |
| Dense 变量 | `core/leras/layers/Dense.py` | 创建全连接权重并执行计算 |
| Lion | `core/leras/optimizers/Lion.py` | Lion 优化器实现 |
| AdaBelief | `core/leras/optimizers/AdaBelief.py` | AdaBelief state 和更新逻辑 |
| 梯度操作 | `core/leras/ops/ops.py` | 图梯度计算和多 GPU 梯度平均 |
| SampleGenerator | `samplelib/SampleGeneratorFace.py` | 样本读取、增强、worker、prefetch |
| IPC | `core/joblib/SubprocessGenerator.py` | 子进程 Queue、FP16 IPC 转换 |
| CLI 流程 | `main.py` | Extract、Train、Merge 等命令入口 |

---

## 5. Python、TensorFlow 与 CUDA 环境升级

### 5.1 当前状态

项目依赖已经面向：

- Python 3.12
- TensorFlow 2.21
- Keras 3.x
- NumPy 2.x
- CUDA 12.x 相关 pip 依赖

### 5.2 真实优点

#### 现代 GPU 和驱动支持基础

新版 TensorFlow Runtime 能够面向现代 NVIDIA GPU 和 CUDA 生态，降低旧版二进制与新驱动、新显卡之间的冲突。

#### 依赖更容易维护

相比锁死在旧 Python 和 TensorFlow 1.x，现代依赖更容易进行：

- 安全更新
- 构建和安装
- CI 验证
- 新 GPU 适配
- 后续工具链集成

#### 后续优化空间更大

新版 TensorFlow 提供现代 dtype、算子、编译器和设备支持，为后续实验提供基础。

### 5.3 当前限制

- 项目尚未形成操作系统、驱动、GPU、CUDA pip 依赖的完整兼容矩阵。
- TensorFlow 版本升级不自动保证旧静态图代码完全稳定。
- Keras 3 的 mixed precision policy 不能自动管理 Leras 自建权重。
- NumPy 和图像依赖升级可能带来 API 或数据类型差异。

### 5.4 验证要求

至少需要覆盖：

- Windows 原生环境
- WSL2/Linux 环境
- Ampere、Ada、Blackwell 等 GPU
- 单 GPU 和多 GPU
- 全新训练、保存恢复、旧模型加载、DFM 导出

---

## 6. compat.v1 架构的优点与代价

### 6.1 当前实现

`core/leras/nn.py` 使用：

```text
import tensorflow.compat.v1

并禁用 TensorFlow 2 behavior
```

训练仍使用：

- Graph
- Session
- Placeholder
- `feed_dict`
- 手工计算梯度
- 自定义 Optimizer update op

### 6.2 优点

#### 保留模型和训练行为

相比全面重写，兼容式升级更有利于保持：

- 网络结构
- Loss 组合
- 变量命名
- 模型保存格式
- 训练参数语义

#### 降低重构风险

完整改写原生 TF2 需要同时重构：

- Layer
- Model
- Optimizer
- 数据管线
- 多 GPU
- Checkpoint
- Preview 与推理

当前路线避免把所有风险集中在一次改造中。

### 6.3 代价

- 无法直接享受完整 Keras 自动混合精度。
- 无法直接使用标准 `model.fit`、Callback、Keras Checkpoint。
- `tf.function` 和 eager 调试能力没有充分利用。
- `tf.distribute` 不能直接替代现有 tower 逻辑。
- 自定义 Layer 和 Optimizer 必须自行保证 dtype、slot、Loss Scaling 正确。

### 6.4 结论

compat.v1 当前是合理的过渡方案，但必须避免以下错误认识：

> 使用 TensorFlow 2.21 并不等于训练实现已经自动获得所有 TF2 优化。

---

## 7. GPU 检测与设备能力升级

### 7.1 当前实现

主要由 `core/leras/device.py` 和 `core/leras/nn.py` 提供：

- GPU 列表
- 设备名称
- 显存信息
- Compute Capability
- 架构和能力标签
- 可见设备与配置

### 7.2 优点

- 为新 GPU 建立基本识别能力。
- 为自动推荐精度和 Batch 提供数据来源。
- 为未来按 GPU 角色分配训练、Extract、Merge 提供基础。
- 便于在日志和 UI 中展示设备信息。

### 7.3 已知问题

#### 检测不等于启用

即使检测到 BF16、TF32 或其他能力，也需要确认：

- 对应算子是否真的启用。
- TensorFlow 构建是否支持。
- Leras dtype 是否正确。
- 是否在当前数据格式和卷积路径上获得加速。

#### Compute Capability 判断风险

当前部分代码存在 tuple 和整数比较逻辑不合理的风险，需要修正并加入单元测试。

#### 显存默认回退风险

如果显存读取失败后使用固定默认值，自动 Batch 或策略判断可能错误。

### 7.4 后续设计原则

设备检测结果应拆成：

```text
原始硬件事实
→ TensorFlow 实际可用能力
→ 项目已验证能力
→ 推荐配置
```

只有通过 Benchmark 的能力才能进入“自动推荐”。

---

## 8. FP32、FP16 与 BF16

### 8.1 当前精度入口

SAEHD 模型中已经提供精度参数，并把 dtype 传递到 Leras/DeepFakeArchi。

当前路径大致为：

```text
precision 参数
   ↓
nn.floatx / model dtype
   ↓
DeepFakeArchi
   ↓
Conv2D / Dense 变量创建
   ↓
Forward、Loss、Gradient、Optimizer
```

### 8.2 FP32

状态：已接通。

作用：

- 当前最稳定的训练基线。
- 用于验证低精度是否改变收敛和质量。
- 用于多 GPU、Loss 和 Optimizer 的数值对照。

FP32 不应被过早视为“落后模式”，而应作为所有优化的控制组。

### 8.3 FP16

状态：已接通，待完整正确性验证。

理论优点：

- 降低激活和变量占用。
- 在支持 Tensor Core 的硬件上可能提高吞吐。

需要验证：

- Loss Scaling 是否正确。
- 梯度是否 finite。
- FP32 master weights 是否存在。
- Optimizer state 是否保持 FP32。
- 保存恢复后数值是否一致。

### 8.4 BF16

状态：已接通，但当前实现存在明显设计风险。

#### 当前行为

`DeepFakeArchi.py`、`Conv2D.py` 和 `Dense.py` 会根据选择的 dtype 创建网络变量。这意味着 BF16 模式下，模型权重可能直接成为 BF16。

#### 与标准混合精度的差异

标准的低精度训练通常希望：

```text
FP32 模型主权重
+ FP32 optimizer state
+ BF16/FP16 激活和大部分计算
+ 必要位置使用 FP32 累加
```

当前方式更接近：

```text
BF16 模型变量
+ 可能为 BF16 的 optimizer state
+ BF16 计算
```

#### 风险

- 权重更新精度下降。
- 小梯度和小更新可能丢失。
- optimizer state 精度不足。
- 模型恢复和 dtype 切换更复杂。
- Keras mixed precision policy 不能自动补偿 Leras 自建变量。

#### 结论

BF16 选项目前不能直接标记为“已完成优化”，更准确的状态是：

> **已接通实验路径，存在训练正确性风险，必须在 P0 阶段重构和验证。**

---

## 9. Loss Scaling 实现分析

### 9.1 当前设计

SAEHD 中创建固定 loss scale，并在训练图中进行手动缩放和反缩放。

### 9.2 BF16 的适用性

BF16 的指数范围通常足以避免 FP16 中常见的下溢问题，因此不应默认照搬 FP16 Loss Scaling。是否需要 scale 应由实际梯度观测决定。

### 9.3 当前缩放顺序风险

当前 Generator Loss 可能出现：

```text
基础重建 Loss
    ↓
乘以 loss scale
    ↓
再加入 TrueFace / GAN / TV / Background Loss
    ↓
最终梯度统一除以 loss scale
```

后加入项没有先乘 scale，却在最终被统一除 scale，可能导致这些梯度被极度缩小。

### 9.4 为什么总 Loss 看不出问题

即使训练日志 Loss 正常，也不能证明：

- 每个 Loss 都对变量产生有效梯度。
- GAN 分支真的参与更新。
- TrueFace 分支没有被低精度缩放抹去。
- TV/背景项保持原设计权重。

### 9.5 正确验证方式

- 分项计算 Loss 梯度范数。
- 对关键变量记录每个 Loss 的梯度贡献。
- 比较 FP32 与低精度下相对比例。
- 检查 NaN、Inf、零梯度和异常小梯度。
- 修复后进行固定配置短训练对照。

---

## 10. MixedPrecisionManager 分析

### 10.1 当前作用

`core/leras/optimizations.py` 中存在 mixed precision 管理逻辑，包括：

- 设置 Keras global policy
- 管理 scale 数值
- 动态 Batch 等辅助能力

### 10.2 当前局限

- Leras Layer 自己创建变量，不一定遵循 Keras Layer 的变量策略。
- Leras Optimizer 不是标准 Keras Optimizer 包装。
- policy、变量 dtype、计算 dtype、slot dtype 之间没有形成完整闭环。
- scale 管理与 SAEHD 手动 Loss Scaling 可能重复或割裂。

### 10.3 建议

不要仅凭 global policy 判断混合精度是否正确。应显式定义：

```text
variable_dtype
compute_dtype
gradient_accumulation_dtype
optimizer_state_dtype
loss_dtype
output_dtype
```

---

## 11. Optimizer 升级

### 11.1 Adam

当前可作为稳定对照优化器。

需要补充：

- slot dtype 检查
- 低精度权重兼容性
- 保存恢复回归

### 11.2 AdaBelief

当前实现中 slot 变量可能跟随模型变量 dtype。

BF16 模式下的风险：

- 一阶和二阶统计精度不足。
- 小差异可能被量化。
- 长期训练稳定性下降。

建议：

- slot 强制 FP32。
- 更新计算至少使用 FP32 中间量。
- 最终写回模型变量前再转换。

### 11.3 Lion

当前已经有选择入口，但实现需要重新核对。

重点检查：

- `beta_1` 和 `beta_2` 是否都真正参与。
- sign update 的计算顺序。
- momentum 更新是否符合标准定义。
- decoupled weight decay 是否实现。
- slot 是否为 FP32。
- 恢复旧 checkpoint 时的变量兼容性。

在完成这些检查前，不应宣称 Lion 已带来更快收敛。

### 11.4 CPU Optimizer State

当前优势：

- 可以减少 GPU 上 optimizer slot 的显存占用。
- 高分辨率训练可能获得更大 Batch 空间。

潜在代价：

- CPU/GPU 数据传输。
- 每步同步等待。
- 多 GPU 情况下额外瓶颈。
- NUMA 和内存带宽影响。

需要分别测量：

- 峰值显存
- iteration time
- GPU utilization
- Host-to-device / device-to-host 时间
- 不同分辨率和 Batch 下的收益

---

## 12. 多 GPU 升级

### 12.1 当前方式

SAEHD 当前继续使用传统 tower 思路：

```text
总 Batch
  ↓
平均切分到每张 GPU
  ↓
每个 tower 前向和反向
  ↓
平均梯度
  ↓
统一更新参数
```

### 12.2 优点

- 保留原静态图训练方式。
- 能够在多卡环境下扩展总 Batch。
- 不需要一次性改写为 `tf.distribute`。

### 12.3 风险

- 梯度可能在原低精度 dtype 中直接平均。
- 异构 GPU 会被最慢设备拖累。
- Batch 不能整除时行为需要确认。
- CPU optimizer state 与多 tower 聚合可能形成瓶颈。
- 多卡复制模型会增加显存和构图成本。

### 12.4 建议

- 梯度聚合使用 FP32。
- 同型号 GPU 作为首要支持场景。
- 异构 GPU 默认使用任务分工：训练、Extract、XSeg、Merge。
- Benchmark 同时记录单卡和多卡吞吐、扩展效率、显存和质量。

---

## 13. 数据管线升级

### 13.1 SampleGenerator

当前依然以多进程 SampleGenerator 为核心：

```text
Faceset
  ↓
worker 读取图片
  ↓
解码与增强
  ↓
组成 Batch
  ↓
Queue / IPC
  ↓
主训练进程 feed_dict
```

### 13.2 Prefetch

优点：

- 可以在 GPU 训练时提前准备下一批数据。
- 减少直接等待 worker 的概率。

当前问题：

- 固定 prefetch 深度不适合所有 CPU、磁盘和分辨率。
- 没有直接记录队列等待、队列满和 worker 耗时。
- Prefetch 太大可能增加内存和延迟。

### 13.3 FP16 IPC

当前行为：

- Worker 将浮点数组转换为 FP16。
- 通过 Queue 传输。
- 主进程重新转为 FP32。

可能收益：

- IPC 数据量约减半。
- 队列内存压力下降。

可能代价：

- 两次转换。
- 两次新数组分配或复制。
- Queue 序列化仍然存在。
- 样本输入精度发生变化。

### 13.4 后续方向

- Shared Memory 固定槽位
- Ring Buffer
- 避免 pickle 的元数据协议
- Worker 直接写共享 Batch
- 主进程零复制或少复制读取
- 自适应 worker 和 prefetch
- JPEG 解码与增强分阶段并行
- PackedFaceset/mmap 读取评估

在重构前必须先建立：

```text
data_wait_ms
queue_wait_ms
sample_decode_ms
augmentation_ms
ipc_copy_ms
train_compute_ms
```

---

## 14. Dynamic Batch 与自动优化

`core/leras/optimizations.py` 中存在动态 Batch 相关代码，但当前尚不能认为已经形成稳定能力。

原因：

- 未确认完整接入 SAEHD 主流程。
- 显存估算没有固定 Benchmark 校准。
- 模型架构、分辨率、GAN、optimizer state 都会改变显存。
- OOM 后自动重试会影响模型和 Session 生命周期。

建议顺序：

1. 建立显存观测。
2. 建立固定配置显存表。
3. 实现安全的 Batch 探测模式。
4. 明确 OOM 回滚和重建策略。
5. 最后才提供自动推荐。

---

## 15. 当前升级收益分级

### 15.1 已确认的工程收益

- 可以使用现代 TensorFlow Runtime。
- 可以面向现代 Python 和 CUDA 依赖维护。
- 新 GPU 信息可以被识别和展示。
- 已有精度、优化器、IPC、多 GPU 的扩展入口。
- 后续服务化和 UI 不必建立在旧 TF1 环境之上。

### 15.2 已实现但未证明的收益

- FP16/BF16 吞吐提升。
- BF16 显存收益与收敛稳定性。
- Lion 收敛速度和最终质量。
- CPU optimizer state 的综合收益。
- FP16 IPC 的真实吞吐提升。
- 多 GPU 扩展效率。
- 自动硬件策略。

### 15.3 当前不能成立的结论

在统一 Benchmark 前，不应直接写：

- “BF16 提速多少百分比”。
- “Lion 收敛提高多少百分比”。
- “FP16 IPC 一定更快”。
- “多 GPU 接近线性加速”。
- “新 GPU 检测已经自动发挥全部性能”。

---

## 16. P0、P1、P2 技术债

### P0：训练正确性

- 修正 Compute Capability 判断。
- 明确 variable/compute/gradient/slot dtype。
- BF16 改为 FP32 master weights 方向。
- 修正 Loss Scaling 顺序和适用范围。
- 核对 Lion 标准实现。
- Optimizer state 强制 FP32。
- 多 GPU 梯度在 FP32 聚合。
- 保存恢复和 dtype 切换回归。

### P1：性能与可观测性

- 建立训练 Benchmark。
- 增加数据等待、计算、Preview、保存耗时。
- Shared Memory IPC 原型。
- 自适应 worker/prefetch。
- CPU optimizer state 对照测试。
- 多 GPU 扩展效率测试。

### P2：架构演进

- 配置结构化。
- 训练事件结构化。
- CLI 与核心逻辑解耦。
- 原生 TF2/Keras 支线评估。
- Linux 服务化和 UI。

---

## 17. 验证矩阵

每项升级至少从四个维度验证：

| 维度 | 指标 |
|---|---|
| 正确性 | 梯度 finite、Loss 分项有效、保存恢复一致、旧模型兼容 |
| 性能 | iteration time、images/s、GPU 利用率、data wait、显存 |
| 质量 | 重建、身份、眼嘴、边界、细节、时序稳定性 |
| 稳定性 | 长训练、NaN/Inf、OOM 恢复、中断恢复、多卡一致性 |

固定对照应包含：

```text
FP32 + Adam/AdaBelief + 单 GPU
```

所有低精度、新 optimizer、CPU state 和多 GPU 都与该基线比较。

---

## 18. 后续输出

本文件完成后，下一阶段按顺序输出：

```text
docs/optimization/training-correctness-audit.md
        ↓
docs/validation/training-benchmark-specification.md
        ↓
docs/optimization/training-performance-optimization.md
        ↓
docs/optimization/training-quality-algorithm-roadmap.md
```

---

## 19. 总结

当前 TF2.x 升级版本最大的价值是：

> **让 DeepFaceLab 原有训练体系获得继续在现代硬件和软件环境中演进的基础。**

但当前版本仍需要区分：

- “已经有代码”与“已经正确”。
- “已经接入”与“已经提升性能”。
- “硬件支持”与“实际利用”。
- “理论优势”与“Benchmark 结果”。

因此，下一步重点不是继续添加更多优化选项，而是完成训练正确性审计和统一 Benchmark。
