# DFL TF2.x Training Performance Optimization Design

## 1. 文档目的

本文进入 Phase 2 的性能优化阶段。在完成训练正确性审计和 Benchmark 规范后，针对 SAEHD 训练链路进行系统性能优化设计。

优化原则：

- 正确性优先于性能
- 所有优化必须通过 Benchmark 验证
- 不为了单纯吞吐牺牲模型质量
- 保持旧模型兼容能力

---

# 2. 当前训练性能模型

当前训练链路：

```
Faceset
  ↓
SampleGenerator
  ↓
SubprocessGenerator
  ↓
Queue / IPC
  ↓
feed_dict
  ↓
Leras Static Graph
  ↓
Forward
  ↓
Loss
  ↓
Backward
  ↓
Optimizer Update
```

性能瓶颈主要来自：

1. GPU 计算效率
2. 数据准备等待
3. CPU/GPU 数据传输
4. 显存压力
5. Python 调度开销
6. Preview 和 checkpoint 开销

---

# 3. 优化优先级

## P0：必须优化

- 数据等待分析
- GPU 利用率分析
- dtype 路径优化
- checkpoint 开销控制
- preview 与训练解耦

## P1：高收益优化

- 数据流水线重构
- Shared Memory IPC
- Batch 调优
- 激活检查点
- 梯度累积
- 多 GPU 优化

## P2：实验优化

- XLA
- Flash Attention 类技术探索
- 网络结构优化
- CUDA Kernel 优化

---

# 4. 计算图优化方向

## 4.1 Cast 操作优化

需要检查：

- Conv 输入输出 dtype 转换
- Loss 前 dtype 转换
- Gradient dtype 转换

目标：

减少：

```
FP32 → BF16 → FP32 → BF16
```

这种重复转换。

---

## 4.2 Forward 计算复用

检查：

- Encoder 是否重复计算
- GAN discriminator 是否重复 forward
- Preview 是否重新构建计算图

目标：

减少无效计算。

---

# 5. 显存优化设计

## 目标架构

推荐：

```
FP32 Master Weight
        ↓
BF16/FP16 Compute
        ↓
FP32 Gradient
        ↓
FP32 Optimizer Update
```

避免：

```
BF16 Weight
 ↓
BF16 Gradient
 ↓
BF16 Optimizer State
```

---

## 5.1 激活检查点

适用于：

- 高分辨率训练
- 大 Batch
- 大 Encoder

交换：

计算时间 ↑
显存 ↓

需要 Benchmark 权衡。

---

## 5.2 梯度累积

目标：

允许：

```
small batch
+
multiple accumulation
=
large effective batch
```

需要验证对 SAEHD 收敛影响。

---

# 6. 数据管线优化

当前路径：

```
Worker
 ↓
Pickle Queue
 ↓
Main Process
 ↓
feed_dict
```

潜在瓶颈：

- Python pickle
- 内存复制
- dtype 转换

---

## 优化方向

### Shared Memory Buffer

设计：

```
Worker
 ↓
Shared Memory Ring Buffer
 ↓
Trainer
```

减少：

- copy
- serialization

---

### Prefetch 自适应

根据：

- GPU idle 时间
- Queue 深度
- CPU 使用率

动态调整 worker。

---

# 7. Batch Size 自动优化

目标：

自动寻找：

```
最大稳定 Batch
```

考虑：

- GPU VRAM
- resolution
- precision
- model size

输出：

```
recommended_batch_size
```

---

# 8. 多 GPU 优化

不默认采用同步多 GPU。

需要评估：

## 数据并行

```
GPU0 batch
GPU1 batch
 ↓
gradient average
```

风险：

- 通信成本
- 梯度精度
- 异构 GPU

## 异构 GPU 分工

推荐探索：

```
GPU A
训练

GPU B
Extract / XSeg / 预处理
```

---

# 9. Preview 与 Checkpoint 优化

当前风险：

训练过程中非必要 IO 影响吞吐。

优化：

- Preview 独立线程
- 降低 preview 频率
- checkpoint 异步保存
- 增量保存

---

# 10. 优化验证流程

每个优化必须记录：

```
Baseline
 ↓
代码修改
 ↓
Benchmark
 ↓
质量检查
 ↓
是否合并
```

禁止：

只看 steps/sec。

---

# 11. 下一步开发顺序

1. 建立训练 profiler
2. 测量 GPU idle
3. 优化数据管线
4. 优化 dtype 路径
5. 优化显存
6. 验证多 GPU
7. 实验高级优化
