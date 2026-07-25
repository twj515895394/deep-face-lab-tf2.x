# DeepFaceLab TF2.x 训练架构分析

> 文档版本：v1.0
> 类型：第一阶段架构分析

## 1. 文档目标

本文档用于分析当前 DeepFaceLab TF2.x 项目的训练核心架构，为后续训练正确性审计、性能优化和算法升级提供基础。

重点覆盖：

- SAEHD 训练流程
- Leras 训练框架
- 数据输入链路
- Forward / Loss / Backward
- Optimizer
- Checkpoint 与恢复
- 当前可优化方向

---

# 2. 当前训练架构定位

当前项目仍保持 DeepFaceLab 原有训练思想：

```
SampleGenerator
      ↓
Batch Input
      ↓
SAEHD Model
      ↓
Encoder
      ↓
Decoder
      ↓
Prediction
      ↓
Loss
      ↓
Optimizer
      ↓
Update Weights
```

底层运行方式：

```
TensorFlow 2.x Runtime
        ↓
compat.v1
        ↓
Static Graph
        ↓
Leras Layer System
        ↓
SAEHD
```

因此当前并非纯 Keras TF2 训练体系，而是现代 Runtime 下运行的经典 DFL 图训练架构。

---

# 3. SAEHD 训练流程

## 3.1 初始化阶段

主要工作：

- 创建网络结构
- 创建 TensorFlow Graph
- 初始化变量
- 创建 Optimizer
- 创建训练 Session

初始化完成后进入长期训练循环。

---

## 3.2 数据输入阶段

数据来源：

```
Faceset
 ↓
SampleGenerator
 ↓
Augmentation
 ↓
Batch
 ↓
feed_dict
```

当前重点关注：

- 数据读取速度
- CPU/GPU等待
- batch生成效率
- augmentation成本

后续需要 Benchmark 数据等待占比。

---

# 4. Forward 流程

典型 SAEHD：

```
Source Face
    ↓
Encoder
    ↓
Latent
    ↓
Decoder
    ↓
Predicted Face
```

同时包含：

- mask 分支
- eyes/mouth 优化
- GAN 分支
- TrueFace 等辅助 Loss

需要重点验证不同分支是否共享计算。

---

# 5. Loss 架构分析

当前训练可能包含：

- Reconstruction Loss
- Mask Loss
- GAN Loss
- TrueFace Loss
- Color/Detail相关Loss

后续需要进行：

1. 每个 Loss 梯度贡献分析
2. 不同精度下 Loss 数值稳定性分析
3. 权重比例影响分析

---

# 6. Backward 与 Optimizer

当前优化器体系支持：

- Adam
- AdaBelief
- Lion

需要进一步验证：

- 是否符合论文实现
- optimizer state 精度
- FP16/BF16兼容性
- 学习率策略

特别关注：

```
Weights
Optimizer State
Gradient
```

三者的数据类型是否合理。

---

# 7. 当前训练架构优势

## 7.1 稳定性

保留原有 DFL 训练逻辑，兼容已有模型。

## 7.2 可扩展性

已经增加：

- 新GPU适配
- 多精度支持
- 新优化器入口
- 数据管线优化入口

## 7.3 迁移成本低

相比完全重写 TF2/Keras，当前方案风险更低。

---

# 8. 当前主要技术债

## P0

- 混合精度训练正确性验证
- Optimizer 实现审计
- Loss scaling验证
- Benchmark体系缺失

## P1

- 数据输入流水线优化
- 多GPU策略优化
- Checkpoint机制优化
- 显存生命周期分析

## P2

- 原生TF2训练迁移可能性
- XLA优化
- 网络结构升级

---

# 9. 后续优化方向

推荐顺序：

```
训练正确性审计
        ↓
Benchmark体系
        ↓
性能优化
        ↓
Loss与采样优化
        ↓
网络结构实验
```

不建议直接增加大量算法模块，应先保证基础训练链路可信。

---

# 10. 下一阶段输入

基于本文继续输出：

```
docs/optimization/training-correctness-audit.md
```

重点分析：

- BF16/FP16实现
- Loss scaling
- Optimizer
- 梯度流程
- 权重保存恢复
- 数值稳定性
