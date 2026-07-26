# DeepFaceLab TF2.x Code Modification Map

## 1. 文档目标

本文档用于指导后续 DeepFaceLab TF2.x 增强开发，将前期算法设计映射到具体工程模块。

目标：

- 保持原有 SAEHD/DF/LIAE 模型兼容
- 增量式增加优化能力
- 避免直接重构核心流程
- 支持随时关闭新能力回退旧流程

---

# 2. 总体改造原则

## 不直接修改

- 原模型结构
- DFM 导出格式
- 原始训练流程
- 默认 Merge 行为

## 新增 Hook

通过扩展方式加入：

```
Training Hook
Prediction Hook
Merge Hook
Evaluation Hook
```

---

# 3. 模块改造地图

## 3.1 Training 部分

目标：增强 Identity Geometry 学习。

建议位置：

```
models/
    Model_SAEHD/
```

新增能力：

```
identity_geometry_loss
landmark_loss
region_loss
frequency_loss
```

职责：

- Identity Appearance 优化
- Identity Geometry 优化
- Face Shape Loss
- Region Aware Loss

---

# 4. Dataset 改造

目标：增加 src/dst 智能采样能力。

位置：

```
samplelib/
```

新增 metadata：

```json
{
 "pose_bucket": "front",
 "quality_score": 0.95,
 "shape_anchor": true,
 "occlusion_score":0.1
}
```

用于：

- Hard Sample Mining
- Shape Anchor
- Curriculum Training

---

# 5. Source Shape Template

新增模块：

```
shape/
    source_shape_template.py
```

负责：

- src faceset 分析
- landmark 聚合
- canonical shape 生成
- identity geometry 保存

输出：

```
model.srcshape
```

---

# 6. Predictor 改造

位置：

```
models/ModelBase.py
predictor/
```

新增 Hook：

```
predicted_face
predicted_mask
predicted_landmark
```

注意：

不改变模型输出结构，通过后处理获取 geometry 信息。

---

# 7. Merge 改造重点

当前：

```
Prediction
 ↓
Affine Transform
 ↓
Mask Blend
 ↓
Output
```

增强后：

```
Prediction
 ↓
Shape Analysis
 ↓
Hybrid Landmark
 ↓
Shape Warp
 ↓
Shape Mask
 ↓
Blend
```

---

# 8. Shape-aware Merge 新模块

建议：

```
merger/

shape_merge.py
shape_mask.py
shape_warp.py
```

职责：

## shape_merge.py

负责整体流程。

## shape_warp.py

负责：

- Piecewise Affine
- Landmark deformation

## shape_mask.py

负责：

- Soft mask
- Boundary mask
- Occlusion mask

---

# 9. Temporal Stabilization

新增：

```
temporal/
    shape_stabilizer.py
```

处理：

- landmark jitter
- warp jitter
- mask flicker

算法：

第一阶段：EMA

后续：One Euro Filter

---

# 10. 配置系统

新增配置：

```yaml
face_shape_mode: off
source_shape_power: 50
shape_mask_mode: hybrid
shape_temporal_filter: true
```

默认：

```
off
```

确保旧用户无感升级。

---

# 11. 开发阶段

## Phase 1

代码审计与测试基线。

## Phase 2

训练增强：

- Loss
- Sampling
- Metadata

## Phase 3

Shape Template。

## Phase 4

Shape-aware Merge。

## Phase 5

UI 集成。

---

# 12. 验收标准

必须满足：

- 原模型可正常使用
- 默认模式效果不变化
- Shape 模式可单独开启
- 视频无明显抖动
- src 脸型保持指标提升
- 无明显边界伪影

---

End.
