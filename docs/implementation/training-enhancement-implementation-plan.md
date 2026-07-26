# DeepFaceLab TF2.x Training Enhancement Implementation Plan

## 1. 文档目标

本文定义训练侧优化从设计进入代码实现阶段的执行方案。

目标：

- 不修改原有模型架构
- 保持旧模型兼容
- 通过扩展训练能力提升 identity、geometry、quality
- 为后续 Shape-aware Merge 提供更高质量模型输出

核心原则：

> 先增强训练数据和优化目标，再考虑模型结构升级。

---

# 2. Training Enhancement 总体流程

```text
Dataset
  |
  v
Metadata Analysis
  |
  v
Smart Sampling
  |
  v
Training Loop
  |
  v
Multi Objective Loss
  |
  v
Model Update
  |
  v
Evaluation
```

---

# 3. Dataset 增强

## 3.1 Sample Metadata

新增样本级信息：

```text
quality_score
pose_bucket
occlusion_score
landmark_confidence
shape_anchor
```

用途：

- 高质量样本优先训练
- 降低异常样本影响
- 支撑 curriculum training

---

# 4. Sampling 优化

## 4.1 Quality Sampling

降低：

- 模糊脸
- 严重遮挡
- 错误 landmarks

## 4.2 Shape-aware Sampling

增加：

- 正脸比例
- 清晰轮廓
- 稳定身份几何样本

---

# 5. Loss 扩展设计

保持原 reconstruction loss。

新增：

```text
Identity Geometry Loss
Landmark Loss
Region Loss
Frequency Loss
Boundary Loss
```

目标：

```text
Identity
 =
 Appearance
 +
 Geometry
```

---

# 6. Identity Geometry Loss

关注：

- 脸宽
- 下颌
- 下巴
- 颧骨
- 五官比例

避免：

训练只优化纹理，忽略骨相结构。

---

# 7. Curriculum Training

建议阶段：

## Stage 1

Identity reconstruction

## Stage 2

Geometry + Expression

## Stage 3

Detail + Boundary refinement

---

# 8. 配置设计

示例：

```yaml
training:
  enable_identity_geometry_loss: false
  enable_landmark_loss: false
  enable_curriculum: false
```

默认关闭，保证兼容。

---

# 9. 实施阶段

## Phase 1

增加 metadata 和 sampling 框架。

## Phase 2

增加 Loss Hook。

## Phase 3

加入 Identity Geometry 实验。

## Phase 4

建立 ablation 测试体系。

## Phase 5

与 Shape-aware Merge 联调。

---

# 10. 验证指标

包括：

- Identity Similarity
- Shape Retention
- Detail Quality
- Boundary Quality
- Video Stability

---

# 总结

训练优化方向不是简单增加模型容量，而是让模型学习更完整的身份表示：

```text
Appearance
+
Geometry
+
Detail
```

并为后续 Shape-aware Merge 提供可靠输入。
