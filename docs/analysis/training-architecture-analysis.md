# DeepFaceLab TF2.x 训练架构分析

> 文档版本：v1.1（代码链路版）  
> 文档类型：Phase 1 训练架构基线  
> 更新日期：2026-07-25

---

## 1. 文档目标

本文档用于完整梳理当前 DeepFaceLab TF2.x 项目的训练核心架构，为后续工作提供统一输入：

- 训练正确性审计
- Benchmark 体系建设
- 训练吞吐与显存优化
- 数据和采样优化
- Loss 与网络结构实验
- 保存恢复和兼容性验证
- 未来 Linux 服务化与 UI 训练监控

重点覆盖：

- SAEHD 初始化与参数
- Leras 静态图
- SampleGenerator 与 IPC
- Forward 分支
- Loss 构建
- Loss Scaling
- 多 GPU tower
- Gradient 计算与聚合
- Optimizer 和 slot state
- 训练循环
- Checkpoint、恢复和 Preview
- 当前性能瓶颈和 P0 风险

相关文档：

- [当前项目架构与升级分析](dfl-current-project-overview.md)
- [TF2.x 升级实现分析](dfl-tf2-upgrade-analysis.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [文档总索引](../README.md)

---

## 2. 当前训练架构定位

当前训练体系保留 DeepFaceLab 原有思想：

```text
Faceset
   ↓
SampleGenerator
   ↓
Batch Input
   ↓
SAEHD Model
   ↓
Encoder
   ↓
Inter / Latent
   ↓
Decoder / Mask Decoder
   ↓
Prediction
   ↓
Loss
   ↓
Gradient
   ↓
Optimizer
   ↓
Update Weights
   ↓
Checkpoint / Preview
```

底层运行方式：

```text
TensorFlow 2.21 Runtime
        ↓
tensorflow.compat.v1
        ↓
disable_v2_behavior
        ↓
Static Graph
        ↓
Session + placeholder + feed_dict
        ↓
Leras Layer / Model / Optimizer
        ↓
SAEHD
```

因此当前不是纯 Keras TF2 训练体系，而是现代 Runtime 下运行的经典 DFL 图训练架构。

---

## 3. 训练相关代码地图

| 领域 | 主要代码 | 作用 |
|---|---|---|
| 训练 CLI | `main.py` | 接收模型、workspace、设备等训练参数 |
| SAEHD 主模型 | `models/Model_SAEHD/Model.py` | 参数、构图、多 GPU、Loss、Optimizer、训练步、Preview |
| 模型基础设施 | `models/ModelBase.py` | 模型生命周期、保存恢复、训练循环公共能力 |
| TensorFlow/Leras 初始化 | `core/leras/nn.py` | Session、device、dtype、基础 ops 和模型注册 |
| 网络结构 | `core/leras/archis/DeepFakeArchi.py` | Encoder、Inter、Decoder 等结构 |
| Layer | `core/leras/layers/` | Conv2D、Dense、Norm、Upscale 等 |
| Gradient ops | `core/leras/ops/ops.py` | 图梯度、多 GPU 梯度平均、张量操作 |
| Optimizer | `core/leras/optimizers/` | Adam、AdaBelief、Lion 等 |
| 精度辅助 | `core/leras/optimizations.py` | mixed precision manager、动态 Batch 等 |
| 样本生成 | `samplelib/SampleGeneratorFace.py` | 读取、增强、Batch、worker、prefetch |
| IPC | `core/joblib/SubprocessGenerator.py` | 子进程 Queue、数组转换与传输 |
| Faceset | `samplelib/`、DFLJPG/packed faceset 相关模块 | 训练数据和元数据 |

---

## 4. 训练生命周期

完整生命周期可分为九个阶段：

```text
1. 读取命令与 workspace
2. 读取或创建模型配置
3. 初始化 TensorFlow / Device / Session
4. 构建 SAEHD 网络与变量
5. 构建多 GPU Forward 和 Loss
6. 构建 Gradient 与 Optimizer update
7. 创建 SampleGenerator
8. 进入长期训练循环
9. 周期保存、Preview、备份和退出
```

每个阶段都可能影响：

- 数值正确性
- 显存
- 构图时间
- 迭代吞吐
- 中断恢复
- 未来服务化接口

---

## 5. 初始化和训练参数

### 5.1 配置来源

当前 SAEHD 的训练参数主要来自：

- 已保存模型配置
- CLI 参数
- 交互式 `io.input_*`
- GPU/设备信息
- 默认值和历史配置

参数通常包括：

- 分辨率
- Face type
- DF/LIAE 架构和维度
- Batch size
- Precision
- Optimizer
- CPU optimizer state
- learning rate
- eyes/mouth priority
- mask 训练
- GAN/TrueFace 等分支
- 数据增强
- Preview 和保存周期

### 5.2 当前问题

- 配置读取与交互逻辑和模型构建耦合较深。
- 参数合法性依赖运行时分支检查。
- 不利于自动测试和无交互执行。
- 未来 UI/API 难以直接复用。

### 5.3 Phase 2 的保留原则

训练优化时不需要立即重写全部配置，但新增参数应优先进入结构化对象，例如：

```text
TrainingConfig
PrecisionConfig
OptimizerConfig
DataPipelineConfig
BenchmarkConfig
```

CLI 只负责把输入转换为这些配置。

---

## 6. TensorFlow 和 Leras 初始化

### 6.1 当前执行模式

`core/leras/nn.py` 使用 `tensorflow.compat.v1` 并禁用 v2 behavior。

训练依赖：

- Graph
- Session
- placeholder
- `feed_dict`
- 手工变量初始化
- 手工梯度构建
- update op

### 6.2 优势

- 保留原 DFL 网络行为。
- 变量名和 checkpoint 兼容性更容易维持。
- 不需要一次性重写全部 Layer 和 Optimizer。

### 6.3 限制

- Keras mixed precision policy 不能自动管理 Leras 变量。
- 数据输入不能自动获得 `tf.data` 的全部优化。
- 调试需要图级工具，不能完全依赖 eager。
- 动态控制和异常恢复更复杂。
- 多 GPU 仍使用手工 tower。

---

## 7. 网络结构构建

### 7.1 SAEHD 典型结构

```text
Source / Destination Face
          ↓
        Encoder
          ↓
     Inter / Latent
          ↓
Face Decoder + Mask Decoder
          ↓
Predicted Source / Destination / Swap
```

根据 DF、LIAE 和具体架构选项，Encoder、Inter 和 Decoder 的共享方式不同。

### 7.2 DeepFakeArchi

`core/leras/archis/DeepFakeArchi.py` 负责生成：

- Encoder
- Inter
- Decoder
- 上采样和卷积结构
- 数据格式和 dtype 传递

### 7.3 Layer 变量

`Conv2D.py`、`Dense.py` 等会根据 `nn.floatx` 或传入 dtype 创建权重。

这意味着 precision 选择不仅影响激活，也可能直接改变模型变量类型。

### 7.4 当前 P0 关注点

- BF16/FP16 下权重是否低精度存储。
- 是否存在 FP32 master weights。
- Normalization、Loss 和关键累加是否回到 FP32。
- 变量命名和 dtype 改造是否破坏旧 checkpoint。
- 模型输出在何处转换为 Preview 和 Merge 所需格式。

---

## 8. SampleGenerator 数据链路

### 8.1 当前流程

```text
src/dst Faceset
       ↓
SampleGeneratorFace
       ↓
多 worker 读取样本
       ↓
解码、warp、颜色和几何增强
       ↓
生成 warped / target / mask / eyes-mouth 等张量
       ↓
组成 Batch
       ↓
SubprocessGenerator Queue
       ↓
训练主进程
       ↓
feed_dict
```

### 8.2 当前生成内容

根据 SAEHD 配置，Batch 通常可能包含：

- warped source
- target source
- source mask
- source eyes/mouth mask
- warped destination
- target destination
- destination mask
- destination eyes/mouth mask

### 8.3 当前并行方式

- 多个子进程负责生成样本。
- 每个 worker 内部仍然逐样本读取和处理。
- 通过 multiprocessing Queue 返回 Batch。
- 可以启用 Prefetch。
- 高分辨率条件下可以启用 FP16 IPC。

### 8.4 已知瓶颈

- JPEG/图片解码。
- 随机增强和 warp。
- Python 逐样本循环。
- Queue 序列化。
- FP32→FP16→FP32 两次转换。
- 内存分配和复制。
- 主进程等待 Batch。
- 固定 worker 和 prefetch 不能适配所有机器。

### 8.5 需要新增的指标

```text
sample_read_ms
image_decode_ms
augmentation_ms
batch_pack_ms
queue_put_wait_ms
queue_get_wait_ms
ipc_convert_ms
data_wait_ms
```

没有这些指标前，不能准确判断 GPU 利用率低的根因。

---

## 9. 输入 placeholder 与 feed_dict

### 9.1 当前方式

训练图使用 placeholder 接收每个 Batch 的 src/dst 图片、mask 和辅助数据。

训练循环通过 `feed_dict` 把 NumPy 数组传入 Session。

### 9.2 优点

- 与原 DFL 架构兼容。
- 数据增强保留在 Python/NumPy/OpenCV 侧。
- 图结构相对稳定。

### 9.3 性能代价

- Host 到 Device 复制需要每步发生。
- 数据预处理和 TensorFlow 执行之间边界明显。
- 很难获得 `tf.data` 的图内流水线和自动 prefetch。
- 多 GPU 时输入拆分和复制需要手工管理。

### 9.4 后续方向

短期：

- 优化 IPC 和内存复用。
- 固定 Batch buffer。
- 减少 dtype 转换。
- 记录 feed 和 H2D 时间。

长期：

- 评估 `tf.data` 或自定义高性能输入适配层。
- 不强制在第一轮优化中全面迁移。

---

## 10. 多 GPU Tower 构建

### 10.1 当前流程

```text
总 Batch
   ↓
按 GPU 数量平均切片
   ↓
GPU 0 Tower：Forward / Loss / Gradient
GPU 1 Tower：Forward / Loss / Gradient
...
   ↓
平均各 Tower Gradient
   ↓
统一 Optimizer Update
```

### 10.2 优点

- 与静态图和 Leras Optimizer 兼容。
- 可以扩大总 Batch。
- 不需要全面迁移 `tf.distribute`。

### 10.3 风险

- 低精度梯度直接平均。
- 异构 GPU 同步等待。
- 每卡 Batch 太小时收敛和利用率下降。
- 变量放置和 optimizer state 可能引入额外传输。
- Batch 不能整除时处理需要测试。

### 10.4 优化原则

- Gradient aggregation 使用 FP32。
- 同型号卡优先作为同步训练支持范围。
- 异构卡优先任务级分工。
- 记录每卡 tower 时间和同步等待时间。
- 对比单卡 images/s 和多卡 scaling efficiency。

---

## 11. Forward 计算分支

### 11.1 主重建分支

典型流程：

```text
warped_src / warped_dst
          ↓
        Encoder
          ↓
     Inter / Latent
          ↓
        Decoder
          ↓
predicted_src / predicted_dst / predicted_swap
```

### 11.2 Mask 分支

同时生成：

- source mask
- destination mask
- swap mask

Mask 分支影响训练和 Merge 质量。

### 11.3 Eyes/Mouth 分支

通过局部 mask 或优先权重加强眼睛和嘴部区域。

需要验证：

- 局部 Loss 的实际梯度比例。
- 分辨率变化时权重是否合理。
- 低精度缩放后是否仍有效。

### 11.4 GAN 分支

当 GAN 相关参数开启时，构建 discriminator 和额外 Loss。

需要分析：

- Generator Forward 是否被重复计算。
- Discriminator 输入是否复用已有预测。
- GAN 分支何时加入总 Loss。
- 低精度和 Loss Scaling 是否一致。
- GAN 开启后的显存、吞吐和稳定性。

### 11.5 TrueFace 分支

用于进一步约束身份或真实感的辅助分支。

当前最重要的是确认其 Loss 在缩放流程中是否产生有效梯度。

---

## 12. Loss 架构

当前训练可能包含以下类别：

### 12.1 Reconstruction Loss

用于 source 和 destination 的像素或结构重建。

可能涉及：

- DSSIM / SSIM 类结构项
- pixel difference
- mask 范围内重建
- 不同尺度 blur

### 12.2 Mask Loss

用于训练 face mask、destination mask 和 swap mask。

### 12.3 Eyes/Mouth Loss

提高眼睛和嘴部局部质量。

### 12.4 GAN Loss

用于提高纹理和局部真实感。

### 12.5 TrueFace Loss

用于增强身份或真实感约束。

### 12.6 TV、背景与其他正则

用于平滑、背景一致性或局部约束。

### 12.7 当前最大缺口

当前日志通常返回总 src/dst Loss，但这不足以判断每个 Loss 是否有效。

后续必须增加：

```text
loss_value
loss_weight
unscaled_gradient_norm
scaled_gradient_norm
relative_gradient_ratio
finite_status
```

并按 Loss 分项记录。

---

## 13. Loss Scaling 调用链

### 13.1 当前风险模式

当前 Generator Loss 构建中存在如下顺序风险：

```text
基础 G Loss
   ↓
乘 loss_scale
   ↓
加入 TrueFace / GAN / TV / Background 等项
   ↓
对最终 G Gradient 统一除 loss_scale
```

如果后加入项未同步乘 scale，则最终反缩放会额外压低这些项的梯度。

### 13.2 可能影响

- GAN Generator Loss 几乎不参与更新。
- TrueFace Loss 权重与配置值不符。
- TV/背景正则接近失效。
- 日志 Loss 看似正常，但梯度路径错误。

### 13.3 验证方式

1. 对每个 Loss 独立调用梯度。
2. 记录关键层的梯度范数。
3. 关闭其他 Loss，做单项短训练。
4. 对比 FP32、FP16、BF16。
5. 修复为“先构建完整 Loss，再统一 scale”。
6. BF16 默认不启用 Loss Scaling，除非观测证明需要。

---

## 14. Gradient 计算

### 14.1 当前实现

`core/leras/ops/ops.py` 负责图梯度计算和多 GPU 梯度处理。

### 14.2 需要审计的内容

- 是否存在 `None` gradient。
- 是否存在长期为零的 gradient。
- gradient dtype。
- 聚合 dtype。
- clipping 的位置和方式。
- Loss Scaling 的反缩放位置。
- 稀疏梯度是否被正确处理。
- GAN 和主模型变量集合是否分离正确。

### 14.3 建议的数据流

```text
完整 Loss
   ↓
必要时统一 scale
   ↓
计算各变量 Gradient
   ↓
检查 finite
   ↓
反缩放
   ↓
转 FP32 聚合/裁剪
   ↓
Optimizer Update
```

### 14.4 梯度可观测工具

建议新增调试模式，周期输出：

- 全局 gradient norm
- 各网络模块 norm
- 各 Loss 分项 norm
- 最大/最小绝对值
- NaN/Inf 数量
- 零梯度变量列表

该工具应只在审计和 Benchmark 模式开启，避免长期训练性能损失。

---

## 15. Optimizer 架构

### 15.1 当前选择

SAEHD 当前可选择：

- Adam
- AdaBelief
- Lion

并支持 CPU optimizer state 方向。

### 15.2 Optimizer 初始化

典型流程：

```text
选择 Optimizer 类型
      ↓
确定 learning rate 和参数
      ↓
确定 state 放置设备
      ↓
根据模型变量创建 slot
      ↓
接收 Gradient
      ↓
生成 update op
```

### 15.3 slot dtype 风险

当前 Leras Optimizer 的 slot 变量可能跟随模型变量 dtype。

当模型权重为 BF16 时，可能出现：

```text
BF16 weight
BF16 momentum/state
BF16 update intermediate
```

这会明显降低长期统计精度。

建议：

- 模型 master weight 使用 FP32。
- optimizer state 使用 FP32。
- update intermediate 使用 FP32。
- 计算和激活按策略使用 BF16/FP16。

### 15.4 Lion 风险

当前 Lion 需要重新核对：

- `beta_1`、`beta_2`
- sign update
- momentum update 顺序
- weight decay
- checkpoint slot 命名

在修复和验证前，Lion 只能标记为实验选项。

### 15.5 CPU Optimizer State

作用：

- 节省 GPU slot 显存。

风险：

- 增加每步 CPU/GPU 同步。
- 多 GPU 下可能成为集中瓶颈。
- 不同 CPU、内存和 PCIe 平台差异大。

必须通过固定配置对照决定是否默认开启。

---

## 16. 训练执行循环

典型训练循环：

```text
获取 src/dst Batch
       ↓
构建 feed_dict
       ↓
Session.run(train_op, losses, ...)
       ↓
返回 src/dst Loss 和耗时
       ↓
更新 iteration
       ↓
周期生成 Preview
       ↓
周期保存模型
       ↓
处理用户命令或退出
```

### 16.1 当前可观测信息不足

训练通常可以看到：

- iteration
- src loss
- dst loss
- iteration time

但缺少：

- data wait
- H2D copy
- GPU compute
- gradient aggregation
- optimizer update
- Preview cost
- save cost
- GPU memory
- GPU utilization
- Loss 分项梯度

### 16.2 结构化事件建议

未来训练循环应输出：

```json
{
  "event": "training_iteration",
  "iteration": 12000,
  "src_loss": 0.042,
  "dst_loss": 0.039,
  "iteration_time_ms": 580,
  "data_wait_ms": 72,
  "compute_ms": 480,
  "gpu_memory_mb": 21120,
  "loss_scale": 1.0,
  "gradient_finite": true
}
```

当前阶段可以先写 JSONL 或日志事件，不需要提前开发完整 API。

---

## 17. Loss Scale 动态调整

当前训练循环存在根据返回 Loss 调整 scale 的逻辑。

问题是：

- 总 Loss 有限不代表所有 gradient 有限。
- 总 Loss 正常不代表部分 Loss 梯度被缩小到失效。
- BF16 不应默认依赖 FP16 式的固定大 scale。
- scale 更新与实际 optimizer 包装没有形成统一机制。

正确判断应基于：

- gradient finite
- overflow/underflow 统计
- 连续稳定步数
- 分项 Loss 梯度

---

## 18. Checkpoint 与恢复

### 18.1 当前能力

训练支持：

- 模型变量保存
- optimizer state 保存
- 迭代信息和配置保存
- 中断后恢复训练
- 周期备份

### 18.2 TF2.x 升级后的风险

- 变量 dtype 改变。
- optimizer slot 数量和命名改变。
- Lion 等新 optimizer 与旧模型不兼容。
- FP32、FP16、BF16 之间切换。
- CPU/GPU slot 放置改变。
- Keras 3/TF2 Runtime 对 checkpoint 行为的间接影响。

### 18.3 必须建立的回归矩阵

| 场景 | 验证内容 |
|---|---|
| FP32 保存→FP32 恢复 | Loss、输出和 iteration 连续性 |
| FP16 保存→FP16 恢复 | scale、slot、权重连续性 |
| BF16 保存→BF16 恢复 | dtype 与数值稳定性 |
| 旧模型→新代码 | 变量匹配和输出一致性 |
| Adam/AdaBelief/Lion | slot 保存和恢复 |
| GPU state→CPU state | 变量放置和数值一致性 |
| 单 GPU→多 GPU | 变量和 optimizer 恢复 |
| 训练模型→DFM 导出 | 推理输出一致性 |

---

## 19. Preview

Preview 是 DFL 训练判断质量的重要能力，但也会影响性能测量。

需要区分：

- 纯训练 iteration time
- Preview 生成耗时
- Preview 图像处理耗时
- UI 显示耗时

Benchmark 时应：

- 关闭 Preview 或独立计时。
- 固定 Preview 频率。
- 保存固定样本，以便质量对照。

未来 UI 不应直接接管训练图，而应订阅 Preview 产物和结构化事件。

---

## 20. 当前训练架构的优点

### 20.1 保留成熟模型体系

SAEHD、DF、LIAE、mask、eyes/mouth、GAN 等核心思路得以延续。

### 20.2 兼容迁移风险较低

相比完全重写 Keras，当前架构更容易保持变量、参数和输出行为。

### 20.3 可逐步优化

当前已经有明确改造点：

- dtype
- optimizer
- gradient
- IPC
- prefetch
- 多 GPU
- 配置和事件

### 20.4 适合建立双轨演进

短期继续修正 Leras 静态图；长期可以建立原生 TF2/Keras 实验分支，而不是阻塞现有项目。

---

## 21. 当前训练架构的主要技术债

### P0：正确性

- BF16 模型权重和 optimizer state。
- Loss Scaling 顺序。
- BF16 是否应使用 Loss Scaling。
- Lion 标准实现。
- 多 GPU 低精度梯度聚合。
- Compute Capability 判断。
- 保存恢复和 dtype 切换。

### P1：性能与观测

- 数据等待指标。
- 训练阶段耗时拆分。
- Shared Memory IPC。
- worker 和 prefetch 自适应。
- CPU optimizer state 对照。
- 多 GPU scaling efficiency。
- Preview 和保存成本隔离。

### P2：质量和算法

- Faceset 去重与质量分析。
- 姿态/表情/遮挡采样。
- hard sample 上限机制。
- Identity / Geometry / Boundary Loss。
- FFL / LPIPS 实验。
- CBAM 或其他结构实验。
- 时序一致性。

### P3：架构演进

- 结构化配置。
- 结构化事件。
- 核心训练与终端交互解耦。
- 原生 TF2/Keras 支线。
- Linux 服务和 UI。

---

## 22. 训练 Benchmark 输入

后续 Benchmark 至少应固定三组配置。

### 基准 A：正确性冒烟

```text
Resolution: 128
Architecture: df
Batch: 4 或 8
Precision: FP32
Optimizer: 稳定基线
GAN: Off
用途: 单元集成、保存恢复、短训练
```

### 基准 B：常规训练

```text
Resolution: 256
Architecture: liae-ud 或项目常用架构
Batch: 8/16
Precision: FP32、FP16、BF16
GAN: Off
用途: 吞吐、显存、收敛对照
```

### 基准 C：压力测试

```text
Resolution: 384/512
Architecture: df-ud 或高容量配置
Batch: 最大稳定值
GAN: Off / On
用途: 显存、CPU state、多 GPU、数据瓶颈
```

统一记录：

- images/s
- iteration time
- data wait
- peak VRAM
- Host RAM
- GPU utilization
- Loss 和 gradient health
- 保存恢复结果
- 固定步数后的 Preview/质量指标

---

## 23. 训练优化的固定顺序

```text
1. 修正 P0 正确性
      ↓
2. 建立 Benchmark 和可观测性
      ↓
3. 数据管线、显存和计算图优化
      ↓
4. 采样与 Faceset 优化
      ↓
5. Loss 实验
      ↓
6. 网络结构实验
      ↓
7. 长训练和兼容性验证
```

不建议当前直接加入大量算法模块，因为如果基础梯度和 dtype 不正确，算法实验结论将不可信。

---

## 24. 下一份专项文档

基于本文，下一步应创建：

```text
docs/optimization/training-correctness-audit.md
```

重点章节：

1. Compute Capability 修正。
2. Variable、Compute、Gradient、Slot dtype 审计。
3. BF16 主权重设计。
4. Loss Scaling 完整调用链。
5. 每个 Loss 的梯度贡献。
6. Lion 标准实现对照。
7. AdaBelief/Adam slot 精度。
8. 多 GPU FP32 gradient aggregation。
9. Checkpoint 和恢复矩阵。
10. 最小测试与验收条件。

完成正确性审计后，再创建：

```text
docs/validation/training-benchmark-specification.md
```

---

## 25. 总结

当前训练架构的优势是保留了成熟的 DeepFaceLab/SAEHD 体系，并在现代 TensorFlow Runtime 上获得继续演进的可能。

当前训练架构的核心问题不是缺少更多算法，而是：

- dtype 生命周期尚未严格定义。
- Loss Scaling 可能改变部分 Loss 的真实梯度权重。
- 新 optimizer 尚未完成标准实现和回归。
- 数据、计算、同步和保存成本缺少拆分指标。
- 缺少统一 Benchmark 和兼容验证。

因此下一步必须先完成训练正确性审计，之后才进入性能和质量优化。
