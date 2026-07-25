# DeepFaceLab TF2.x 实现状态与风险矩阵

> 文档版本：v1.0  
> 文档类型：代码实现审计基线  
> 更新日期：2026-07-25

---

## 1. 文档目的

本文档用于把当前项目中的功能分成：

- 已实现并进入主流程
- 已实现但未验证
- 存在正确性风险
- 只有代码骨架
- 仅存在设计文档

本文档不评价某项优化“理论上是否先进”，只关注：

```text
代码在哪里
→ 是否被主流程调用
→ 当前真实行为是什么
→ 存在哪些风险
→ 如何验证
→ 下一步如何处理
```

---

## 2. 状态定义

| 状态 | 定义 |
|---|---|
| 已实现 | 仓库中存在对应代码 |
| 已接通 | 已被训练、提取或合成主流程调用 |
| 已验证 | 有自动测试、Benchmark 或稳定运行证据 |
| 待验证 | 已实现或已接通，但缺少正确性或收益证据 |
| 存在问题 | 代码行为与设计目标、论文算法或数值原则不一致 |
| 代码骨架 | 存在类或函数，但主流程没有使用 |
| 设计阶段 | 仅存在设计文档 |
| 建议重构 | 当前方式不适合继续扩展，应先调整架构 |

---

## 3. 总体结论

当前项目已经完成现代运行环境迁移和多个优化入口接入，但仍属于：

> **TensorFlow 2.21 Runtime 上运行的 compat.v1 + Leras 静态图实验性升级版本。**

当前最主要价值：

- 支持现代 Python、TensorFlow、CUDA 和 GPU 环境。
- 保留原 DeepFaceLab / SAEHD 训练体系。
- 为低精度、优化器、数据管线和服务化增加改造入口。

当前最主要风险：

- BF16 路径不是标准的“FP32 主权重 + BF16 计算”混合精度方案。
- BF16 Loss Scaling 存在缩放顺序不一致问题。
- Lion 实现需要按标准算法重新核对。
- Optimizer state 可能使用低精度变量类型。
- 多 GPU 梯度平均可能在低精度中完成。
- 多项“硬件能力检测”尚未真正转化为自动优化策略。
- 缺少统一 Benchmark 和回归验证体系。

---

## 4. 环境与运行时

| 功能 | 状态 | 代码/配置入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| Python 3.12 环境 | 已实现，待完整验证 | `requirements.txt`、启动环境 | 依赖面向现代 Python 环境 | 第三方依赖兼容性尚未形成矩阵 | 建立安装与冒烟测试 |
| TensorFlow 2.21 | 已实现 | `requirements.txt` | 使用 TF2 Runtime | 不代表训练代码已经原生 TF2 化 | 文档中持续区分 Runtime 升级与架构升级 |
| `tensorflow.compat.v1` | 已接通 | `core/leras/nn.py` | 调用 `disable_v2_behavior()`，继续使用静态图、Session 和 placeholder | 无法直接获得完整 TF2/Keras 训练能力 | 保留兼容路径，同时评估长期原生化分支 |
| CUDA 12.x 依赖 | 已实现，待环境验证 | `requirements.txt` | 使用 NVIDIA CUDA pip 依赖 | 依赖小版本与本地驱动组合尚未形成验证矩阵 | 建立 GPU/驱动/系统兼容表 |
| Keras 3 | 间接依赖，待验证 | `requirements.txt`、mixed precision policy | 主要用于策略配置，不是主训练框架 | Keras policy 与 Leras 自建变量体系可能不一致 | 在混合精度审计中单独验证 |

---

## 5. GPU 检测与硬件能力

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| GPU 枚举 | 已实现并接通 | `core/leras/device.py` | 读取可见 GPU 和设备信息 | 异常情况下显存可能使用默认值 | 增加检测日志与失败降级测试 |
| 显存检测 | 已实现，待验证 | `core/leras/device.py` | 读取显存，失败时存在默认回退 | 默认值可能导致错误 Batch 或策略判断 | 检测失败时禁止自动推断 |
| 架构/能力标签 | 已实现 | `core/leras/device.py` | 提供架构和能力布尔判断 | 标签不等同于真正启用优化 | 每个标签绑定实际配置或删除无效标签 |
| Compute Capability 判断 | 存在问题 | `core/leras/nn.py` | 部分逻辑对 tuple 与整数进行不合理比较 | 可能导致能力判断错误 | P0 修正并加入单元测试 |
| 自动精度推荐 | 代码基础存在，未形成可靠策略 | `device.py`、`nn.py`、模型参数 | 可根据设备信息选择或提示精度 | 当前缺少 Benchmark 与稳定性依据 | 在 Benchmark 后再启用自动推荐 |
| 动态 Batch Size | 代码骨架 | `core/leras/optimizations.py` | 存在 DynamicBatchSizer 类 | 未确认进入 SAEHD 主训练流程 | 先验证显存估算，再接入配置层 |

---

## 6. 精度与混合精度

### 6.1 当前 dtype 链路

当前主要链路大致为：

```text
SAEHD precision 参数
        ↓
nn.floatx / model_data_format
        ↓
DeepFakeArchi
        ↓
Conv2D / Dense 创建变量
        ↓
Forward / Loss / Gradient
        ↓
Optimizer state 与权重更新
```

### 6.2 状态矩阵

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| FP32 | 已接通 | `models/Model_SAEHD/Model.py`、`core/leras/nn.py` | 作为稳定基线精度 | 仍缺统一 Benchmark | 作为所有优化的对照组 |
| FP16 | 已接通，待验证 | `Model_SAEHD`、Leras layers | 低精度变量与计算路径 | 需要确认溢出、Loss Scaling 和保存恢复 | 纳入训练正确性审计 |
| BF16 | 已接通，存在问题 | `Model_SAEHD`、`DeepFakeArchi.py`、`Conv2D.py`、`Dense.py` | 卷积和 Dense 权重可能直接以 BF16 创建 | 缺少 FP32 master weights，优化器状态也可能继承低精度 | P0 重构为 FP32 变量、BF16 计算 |
| Keras mixed precision policy | 已配置但作用有限 | `core/leras/optimizations.py`、`core/leras/nn.py` | 设置 Keras policy | Leras 自定义变量创建并不完全服从标准 Keras mixed precision 生命周期 | 不依赖 policy 宣称正确性，需显式控制 dtype |
| Loss Scaling | 已接通，存在问题 | `models/Model_SAEHD/Model.py` | 创建固定 scale 并手动缩放/反缩放 | BF16 通常不需要 Loss Scaling；不同 Loss 项加入时机不一致 | P0 修正并为各 Loss 检查梯度贡献 |
| 动态 Loss Scaling | 部分代码，未形成闭环 | `core/leras/optimizations.py`、训练循环 | 存在 scale 管理逻辑 | 与实际 Leras optimizer 没有形成标准包装关系 | 统一实现或删除重复机制 |

---

## 7. Loss Scaling 已知高风险点

当前 Generator Loss 的构建顺序中，存在以下风险模式：

```text
基础 Generator Loss
        ↓
乘以 loss_scale
        ↓
继续加入 TrueFace / GAN / TV / Background 等 Loss
        ↓
对最终梯度统一除以 loss_scale
```

结果可能是：

- 先缩放的基础 Loss 梯度恢复正常。
- 后加入、未缩放的 Loss 梯度在最后被额外除以 scale。
- 当 scale 很大时，后加入 Loss 的实际梯度贡献可能接近消失。

该问题属于训练正确性 P0，不能只通过“Loss 数值正常”判断，需要：

1. 分别计算每个 Loss 对关键变量的梯度范数。
2. 比较 FP32、FP16、BF16 下的相对梯度比例。
3. 确认 TrueFace、GAN、TV、背景 Loss 在低精度模式下仍然有效。
4. 修正后进行短训练和固定数据集对照。

---

## 8. Optimizer

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| Adam | 已接通 | `core/leras/optimizers/`、`Model_SAEHD` | 作为常规优化器入口 | 低精度 slot dtype 仍需确认 | 作为收敛基准 |
| AdaBelief | 已接通，待验证 | `core/leras/optimizers/AdaBelief.py` | slot 变量与模型变量 dtype 关联 | BF16 权重时，optimizer state 可能也是 BF16 | 将 slot 强制为 FP32 并验证恢复 |
| Lion | 已接通，存在问题 | `core/leras/optimizers/Lion.py` | 提供 Lion 选择入口 | 当前更新逻辑未完整体现标准 Lion 的双 beta 动量与权重衰减语义 | 按论文/官方参考重新实现并写单元测试 |
| CPU optimizer state | 已接通，待 Benchmark | `Model_SAEHD`、optimizer 初始化 | 可将 optimizer state 放到 CPU | 节省显存但可能增加 PCIe 传输和同步开销 | 分辨率/显存/吞吐对照测试 |
| Optimizer checkpoint | 已实现，待完整回归 | 模型保存与 optimizer 变量 | 可随模型保存恢复 | dtype 变化、优化器切换和旧模型恢复风险未形成矩阵 | 建立保存恢复回归测试 |

---

## 9. 梯度与多 GPU

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| 图梯度计算 | 已接通 | `core/leras/ops/ops.py` | 使用静态图梯度接口 | 需检查 None gradient、稀疏梯度和 dtype | 增加梯度健康检查工具 |
| 多 GPU Batch 切分 | 已接通 | `models/Model_SAEHD/Model.py` | 按 GPU 数量平均切分 Batch | 异构 GPU 会被最慢设备拖累 | 默认只推荐同型号同步训练 |
| 多 GPU 梯度平均 | 已接通，待验证 | `core/leras/ops/ops.py` | 对各 tower 梯度求平均 | 可能在 BF16/FP16 dtype 中直接平均 | 聚合前转 FP32，更新前再按需要转换 |
| 异构 GPU 调度 | 尚未实现 | 当前只有同步多 GPU 路径 | 无任务级角色分工 | 3090 + Pro 5000 等组合不适合直接同步 | 后期设计训练卡/预处理卡/合成卡分工 |

---

## 10. 数据输入与 IPC

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| SampleGenerator 多进程 | 已接通 | `samplelib/SampleGeneratorFace.py` | 多 worker 生成样本 | 每个 worker 内仍有串行读取和增强 | 建立数据等待占比指标 |
| Prefetch | 已接通，待验证 | `SampleGeneratorFace.py` | 使用固定预取深度 | 固定值不一定适合不同 CPU/磁盘/分辨率 | 改为可观测、可配置、自适应 |
| FP16 IPC | 已接通，待 Benchmark | `core/joblib/SubprocessGenerator.py` | 子进程 FP32 转 FP16，主进程收到后再转 FP32 | 减少队列数据量，但增加两次转换与内存复制 | 与原始 FP32、共享内存方案对照 |
| multiprocessing Queue | 已接通 | `SubprocessGenerator.py` | 通过 Queue 序列化传输 Batch | pickle、复制和队列阻塞可能成为瓶颈 | 设计 Shared Memory Ring Buffer |
| Shared Memory | 设计阶段 | 尚无主流程实现 | 无 | 需要处理生命周期、异常退出和跨平台 | 先做最小可验证原型 |
| mmap / PackedFaceset 加速 | 设计阶段 | Faceset 相关模块 | 尚未形成完整读取优化 | 数据格式与兼容性需要评估 | 结合 Faceset Analyzer 统一设计 |

---

## 11. 训练循环与稳定性

| 功能 | 状态 | 代码入口 | 当前行为 | 风险 | 下一步 |
|---|---|---|---|---|---|
| SAEHD 主训练循环 | 已接通 | `models/Model_SAEHD/Model.py` | 长期静态图训练 | 缺少每阶段耗时和梯度观测 | 增加结构化训练指标 |
| Loss scale 调整 | 已接通，存在问题 | `Model_SAEHD` 训练循环 | 基于返回 Loss 调整 scale | 只看总 Loss 不能识别单个梯度溢出或失效 | 检查梯度 finite 状态 |
| NaN/Inf 处理 | 部分存在，待完善 | 训练循环 | 异常时处理流程有限 | 可能晚于问题发生时才发现 | 增加梯度、权重和 Loss 分项检测 |
| 保存与恢复 | 已实现，待回归 | ModelBase / SAEHD | 支持模型持久化 | 新 dtype、新 optimizer、旧模型兼容尚未系统验证 | 建立兼容矩阵 |
| Preview | 已实现 | 训练预览流程 | 周期性生成预览 | 可能阻塞训练并干扰吞吐测量 | Benchmark 时独立记录 Preview 成本 |

---

## 12. 训练算法候选功能

| 功能 | 当前状态 | 当前判断 | 启动条件 |
|---|---|---|---|
| Gradient Checkpoint | 设计阶段 | 有显存价值，但需使用正确 TensorFlow API 并验证静态图兼容 | P0 正确性修复后 |
| Gradient Accumulation | 设计阶段 | 可扩大有效 Batch，但会改变优化器步进和统计 | Benchmark 建立后 |
| LossWeightedSampler | 设计阶段 | 可提升难样本利用率，但可能过拟合异常样本 | 先完成 Faceset 分析与采样基线 |
| Deduplication | 设计阶段 | 高价值、低风险，但感知哈希和身份校验需可靠 | Faceset Analyzer 设计后 |
| CBAM | 设计阶段 | 可能提升局部注意力，也会增加计算和兼容成本 | 建立质量评估后做消融 |
| FFL | 设计阶段 | 可能改善高频细节，权重不当会增加伪影 | 先完成 Loss 梯度审计 |
| LPIPS | 设计阶段 | 感知质量方向有价值，但额外模型和显存成本较高 | 先做离线评价再决定训练接入 |
| CutMix | 设计阶段 | 不一定适合像素级人脸重建目标 | 需要明确应用区域和实验假设 |
| 3D Mesh / Geometry Loss | 设计阶段 | 对姿态和结构一致性有潜力 | 需要稳定 Landmark/3D 几何输入 |

---

## 13. Extract 与 Faceset

| 功能 | 状态 | 代码入口 | 当前情况 | 后续重点 |
|---|---|---|---|---|
| S3FD 检测 | 已接通 | `main.py`、extractor | 作为主要自动检测器 | 批推理、现代检测器对照 |
| 手动检测 | 已接通 | `main.py` | 人工修正路径 | 保留兜底能力 |
| Landmark / 对齐 | 已接通 | extractor / facelib | 维持原 DFL 处理链路 | 大角度、遮挡、时序平滑 |
| 多 GPU Extract worker | 已接通，待测试 | CLI 参数与 extractor | 支持每 GPU worker 配置 | 检测、Landmark、保存的流水线拆分 |
| Faceset 自动分析 | 尚未实现 | 无统一模块 | 缺少清晰度、遮挡、身份、重复、姿态分析 | 设计 Faceset Analyzer |
| 采样平衡 | 基础能力存在，智能策略未实现 | SampleGenerator | 传统随机与现有采样逻辑 | 姿态/表情/遮挡/难度混合采样 |

---

## 14. Merge 与输出

| 功能 | 状态 | 代码入口 | 当前情况 | 风险 | 下一步 |
|---|---|---|---|---|---|
| Predictor 推理 | 已接通 | `merger/MergeMasked.py` | 逐脸调用 predictor | 多脸和多帧未批处理 | 设计 Batch predictor |
| Mask 处理 | 已接通 | `MergeMasked.py` | 支持多种 mask 与 XSeg | 大量 CPU OpenCV 操作 | 评估 GPU 化和缓存 |
| Warp / Resize | 已接通 | `MergeMasked.py` | CPU 图像操作较多 | 高分辨率下成本明显 | 记录阶段耗时并尝试批处理 |
| Color Transfer | 已接通 | merger | 多种颜色匹配 | 参数逐帧波动可能造成闪烁 | 增加时序平滑和缓存 |
| seamlessClone / blur / sharpen | 已接通 | merger | CPU 后处理 | 串行、多次内存复制 | 合并处理阶段、减少往返 |
| 多脸合成 | 已实现 | `MergeMasked.py` | 按脸循环组合 | 串行 predictor 与后处理 | 多脸批量推理、冲突处理 |
| 视频编码 | 已实现 | 主流程相关模块 | 输出视频 | 编解码可能与推理串行 | 解码、推理、合成、编码流水线化 |

---

## 15. P0 风险清单

以下项目未解决前，不建议继续叠加训练算法：

1. **BF16 模型变量和 optimizer state 精度设计不合理。**
2. **Generator Loss Scaling 顺序可能使部分 Loss 梯度接近失效。**
3. **Lion 优化器实现需要重新按标准算法核对。**
4. **低精度多 GPU 梯度聚合需要验证并优先使用 FP32 累加。**
5. **Compute Capability 判断逻辑存在明显风险。**
6. **保存恢复、旧模型和 dtype 切换缺少回归验证。**
7. **缺少固定数据、固定配置、固定指标的训练 Benchmark。**

---

## 16. 建议处理顺序

```text
P0-1 修正硬件能力判断
        ↓
P0-2 建立 dtype/变量/slot/gradient 可观测工具
        ↓
P0-3 修正 BF16 与 Loss Scaling
        ↓
P0-4 修正 Lion 与 optimizer state
        ↓
P0-5 修正多 GPU FP32 梯度聚合
        ↓
P0-6 建立保存恢复回归测试
        ↓
P0-7 建立统一 Benchmark
        ↓
P1 数据管线、显存和吞吐优化
        ↓
P1/P2 Loss、采样和网络结构实验
```

---

## 17. 验证要求

每项功能从“待验证”改为“已验证”至少需要：

1. 单元测试或静态检查。
2. 最小模型短训练冒烟测试。
3. 固定配置的 FP32 对照。
4. 保存、停止、恢复训练测试。
5. 记录吞吐、显存、Loss 和梯度健康度。
6. 涉及质量的功能必须有固定样例和视频时序对照。
7. 涉及旧模型的功能必须做兼容性回归。

---

## 18. 与后续文档的关系

本文档是以下文档的状态来源：

- `docs/optimization/training-correctness-audit.md`
- `docs/validation/training-benchmark-specification.md`
- `docs/optimization/training-performance-optimization.md`
- `docs/optimization/training-quality-algorithm-roadmap.md`
- `docs/optimization/extraction-optimization.md`
- `docs/optimization/merging-optimization.md`

后续每完成一项开发和验证，应同步更新本矩阵中的：

```text
状态、证据、风险、验证结果、默认配置建议
```
