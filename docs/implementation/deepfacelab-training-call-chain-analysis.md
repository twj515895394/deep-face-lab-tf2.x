# DeepFaceLab TF2.x Training Call Chain Analysis

## 1. Purpose

本文档用于分析 DeepFaceLab TF2.x 的训练执行链路，作为后续训练优化（Identity Geometry、Shape Loss、Sampling、Curriculum Training 等）的代码定位依据。

目标：

- 明确训练入口；
- 明确数据流转；
- 明确 batch 生成位置；
- 明确 forward / loss / backward 调用关系；
- 标记未来增强插入点。

---

# 2. Training Overall Pipeline

```text
Faceset
  |
  v
Sample Generation
  |
  v
Training Data Loader
  |
  v
Model Trainer
  |
  v
SAEHD Forward
  |
  v
Loss Calculation
  |
  v
Optimizer Update
  |
  v
Preview / Save Model
```

---

# 3. Dataset Layer

职责：

- 读取 src/dst faceset；
- 提供训练样本；
- 生成随机 batch；
- 执行增强。

未来增强方向：

```text
Sample Metadata
 |
 +-- quality score
 +-- pose bucket
 +-- occlusion score
 +-- shape anchor
```

---

# 4. Training Loop Responsibilities

训练循环主要负责：

1. 获取 batch；
2. 数据预处理；
3. 输入模型；
4. 获取预测结果；
5. 计算 loss；
6. 更新 optimizer；
7. 保存状态。

---

# 5. SAEHD Modification Points

当前优先不修改网络主体。

推荐扩展：

```text
Existing Loss
    |
    + Identity Loss
    + Landmark Geometry Loss
    + Region Loss
    + Frequency Loss
```

目标：

让模型学习：

```text
Identity
 = Appearance
 + Geometry
```

---

# 6. Loss Injection Design

推荐增加独立 Loss 模块：

```text
losses/

├── identity_geometry_loss.py
├── landmark_loss.py
├── region_loss.py
└── frequency_loss.py
```

保持：

- 可配置；
- 可关闭；
- 可进行 Ablation Experiment。

---

# 7. Sampling Optimization

未来支持：

## Quality Sampling

避免低质量样本主导训练。

## Shape-aware Sampling

增加：

- 正脸；
- 清晰轮廓；
- 高质量 landmark；

作为 identity geometry anchor。

## Curriculum Training

阶段：

```text
Stage 1
Identity

Stage 2
Shape + Expression

Stage 3
Detail + Boundary
```

---

# 8. Recommended Implementation Order

## Phase 1

源码定位与 baseline 固化。

## Phase 2

增加 metadata 与 sampling。

## Phase 3

增加 loss 模块。

## Phase 4

实验验证。

## Phase 5

进入 Shape-aware Merge 联动。

---

# 9. Engineering Principle

核心原则：

不破坏原有 DFL 工作流。

采用：

```text
Extension
+
Config Switch
+
Backward Compatibility
```

让增强能力成为可选高级能力。
