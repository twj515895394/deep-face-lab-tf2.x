# DeepFaceLab TF2.x 训练 Benchmark 规范

> 文档版本：v1.0  
> 阶段：Phase 2 - 核心训练优化  
> 目标：为训练正确性审计、性能优化和质量优化提供统一可重复的测试基线。

---

## 1. 文档目的

在进入 BF16、FP16、多 GPU、数据管线、Loss、网络结构等优化之前，必须建立统一 Benchmark。

所有优化必须回答三个问题：

1. 是否更快？
2. 是否更省资源？
3. 是否保持或提升生成质量？

禁止只根据单一指标判断优化成功。

---

## 2. Benchmark 分层

### 2.1 Correctness Benchmark

目标：验证训练行为没有被破坏。

关注：

- Loss 是否正常下降
- 是否出现 NaN/Inf
- checkpoint 是否可恢复
- optimizer state 是否一致
- 多 GPU 与单 GPU 是否等价
- 不同 precision 是否产生异常漂移

---

### 2.2 Performance Benchmark

目标：衡量吞吐、显存和资源利用率。

核心指标：

| 指标 | 说明 |
|---|---|
| steps/sec | 每秒训练 step 数 |
| iteration time | 单 step 时间 |
| GPU utilization | GPU 利用率 |
| VRAM peak | 峰值显存 |
| CPU usage | CPU 占用 |
| data wait ratio | 数据等待比例 |
| checkpoint overhead | 保存开销 |

---

### 2.3 Quality Benchmark

目标：确认视觉质量是否提升。

指标包括：

- 身份一致性
- 人脸结构保持
- 五官细节
- mask 边缘质量
- 颜色一致性
- 视频时序稳定性

不能只使用训练 Loss 判断质量。

---

## 3. 固定测试环境

每次 Benchmark 必须记录：

```text
Hardware
- GPU model
- GPU count
- VRAM
- CPU
- RAM

Software
- OS
- Python version
- TensorFlow version
- CUDA version
- cuDNN version

Training
- Model type
- Resolution
- Batch size
- Precision
- Optimizer
- Dataset
```

---

## 4. 标准测试配置

### Baseline A：快速正确性测试

```text
Resolution: 128
Batch: 8
Precision: FP32
GAN: Off
Steps: 1000
```

用于：

- 新代码冒烟测试
- 数值稳定性检查

---

### Baseline B：常规训练测试

```text
Resolution: 256
Batch: 最大稳定 batch
Precision: FP32 / FP16 / BF16
GAN: Off
Steps: 10000
```

用于：

- 精度比较
- 性能比较

---

### Baseline C：高质量测试

```text
Resolution: 384+
Batch: 最大稳定 batch
GAN: On/Off
Long training
```

用于：

- 最终质量验证

---

## 5. 优化实验规范

每个优化必须记录：

```text
实验名称
修改内容
修改文件
目标
Baseline结果
优化后结果
质量变化
结论
```

示例：

```text
Experiment:
BF16 mixed precision

Expected:
降低显存，提高吞吐

Compare:
FP32 vs BF16

Check:
Loss curve
Preview
VRAM
Speed
```

---

## 6. 必须建立的对照实验

### Precision

```text
FP32
FP16
BF16
```

比较：

- 收敛速度
- 最终质量
- 显存
- 稳定性

---

### Optimizer

```text
Adam
AdaBelief
Lion
```

比较：

- 收敛速度
- 震荡情况
- 最终视觉质量

---

### GPU Scale

```text
1 GPU
2 GPU
```

比较：

- throughput
- gradient consistency
- quality drift

---

## 7. Benchmark 输出格式

建议统一保存：

```text
benchmarks/
├── configs/
├── logs/
├── metrics/
├── previews/
└── reports/
```

每次实验生成：

```json
{
  "experiment": "bf16_test",
  "gpu": "RTX xxx",
  "precision": "bf16",
  "steps": 10000,
  "step_time_ms": 0,
  "peak_vram": 0,
  "quality": {}
}
```

---

## 8. Phase 2 后续关系

执行顺序：

```text
training-correctness-audit
          ↓
training-benchmark-specification
          ↓
training-performance-optimization
          ↓
training-quality-algorithm-roadmap
```

Benchmark 是所有后续优化的验收基础。
