# DeepFaceLab TF2.x 训练正确性审计规范

> 文档版本：v1.0  
> 文档类型：Phase 2 P0 优化文档  
> 目标：在任何性能优化前，确认当前训练链路的数值正确性、算法一致性和恢复可靠性。

---

## 1. 审计目标

当前项目基于：

```text
TensorFlow 2 Runtime
        +
tensorflow.compat.v1
        +
Leras 自定义静态图体系
        +
SAEHD Training Pipeline
```

因此不能直接套用标准 Keras 混合精度假设。

本阶段核心目标：

```text
发现潜在数值错误
        ↓
确认真实计算行为
        ↓
建立 Benchmark 基线
        ↓
再进行性能优化
```

禁止顺序：

```text
先加 BF16
先换优化器
先改多 GPU
先追求吞吐
```

原因：如果训练结果已经偏离原始算法，性能提升没有意义。

---

# 2. P0 审计列表

| 项目 | 优先级 | 状态 |
|---|---|---|
| BF16/FP16 权重与梯度路径 | P0 | 待审计 |
| Loss Scaling 实现 | P0 | 待审计 |
| Optimizer state dtype | P0 | 待审计 |
| Lion 更新公式 | P0 | 待审计 |
| 多 GPU 梯度聚合精度 | P0 | 待审计 |
| Checkpoint 恢复一致性 | P0 | 待验证 |

---

# 3. 混合精度审计

## 3.1 当前风险

需要确认：

```text
Variable dtype
Compute dtype
Gradient dtype
Optimizer slot dtype
Checkpoint dtype
```

是否符合预期。

不能仅根据：

```python
mixed_precision.set_global_policy()
```

判断已经完成混合精度。

因为当前网络主要使用 Leras 自定义 Layer 和 Variable。

---

## 3.2 BF16 推荐目标

目标结构：

```text
FP32 Master Weight
        |
        ↓
BF16 Forward Compute
        |
        ↓
FP32 Gradient Accumulation
        |
        ↓
FP32 Optimizer Update
```

需要验证：

- Conv 权重
- Dense 权重
- Encoder/Decoder 参数
- Optimizer slot
- EMA 参数（如果存在）

---

# 4. Loss Scaling 审计

## 4.1 风险

当前 Loss 结构包含：

- Pixel Loss
- SSIM
- DSSIM
- Mask Loss
- GAN Loss
- TrueFace Loss
- TV Loss
- Eyes/Mouth Loss

不同 Loss 梯度贡献不同。

错误顺序可能导致：

```text
Loss
 ↓
Scale
 ↓
Gradient
 ↓
Optimizer
```

和：

```text
Gradient
 ↓
Scale
 ↓
Optimizer
```

产生不同结果。

---

## 4.2 验证方法

记录：

- 每个 Loss 数值
- Gradient norm
- NaN/Inf 次数
- 不同 dtype 收敛曲线

---

# 5. Lion 优化器审计

需要确认实现是否符合标准 Lion：

目标形式：

```text
update = sign(beta1 * momentum + (1-beta1)*gradient)
weight = weight - lr * update
```

检查：

- momentum 更新顺序
- weight decay
- dtype
- slot 保存
- checkpoint 恢复

不能只确认存在 `LionOptimizer` 类。

---

# 6. Optimizer State 审计

重点：

Adam/AdaBelief/Lion 都依赖状态变量。

检查：

```text
Parameter
Momentum
Variance
Extra Slot
```

是否：

- 使用 FP32
- 正确保存
- 正确恢复
- 多 GPU 下保持一致

---

# 7. 多 GPU 审计

当前架构：

```text
GPU Tower 0
GPU Tower 1
GPU Tower N
       ↓
Gradient Merge
       ↓
Optimizer Apply
```

重点验证：

- 梯度平均方式
- dtype 转换位置
- loss scaling 后聚合位置
- batch size 改变后的等价性

测试：

```text
1 GPU batch=8

vs

2 GPU batch=4+4
```

比较：

- Loss 曲线
- 权重差异
- Preview 质量

---

# 8. Checkpoint 恢复审计

验证：

```text
训练 N steps
        ↓
保存
        ↓
重新加载
        ↓
继续训练
```

比较：

- Loss 是否连续
- Optimizer state 是否恢复
- Learning rate 是否一致
- Preview 是否跳变

---

# 9. Benchmark 前置要求

所有优化必须建立基线。

固定：

```text
GPU
CUDA
TensorFlow
Python
Faceset
Batch Size
Resolution
Model Config
Seed
```

记录：

## 性能

- steps/sec
- GPU utilization
- VRAM
- CPU usage
- Data wait ratio

## 质量

- Preview 对比
- Identity similarity
- 重建误差
- 视频稳定性

---

# 10. 推荐执行顺序

```text
Phase 1
确认当前行为

        ↓

Phase 2.1
修复 P0 数值问题

        ↓

Phase 2.2
建立 Benchmark

        ↓

Phase 2.3
性能优化

        ↓

Phase 2.4
质量算法实验
```

---

# 11. 后续关联文档

- `validation/training-benchmark-specification.md`
- `optimization/training-performance-optimization.md`
- `validation/model-quality-evaluation.md`
- `validation/compatibility-test-matrix.md`
