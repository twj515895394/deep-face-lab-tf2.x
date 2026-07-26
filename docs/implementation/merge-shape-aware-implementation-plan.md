# DeepFaceLab TF2.x Shape-aware Merge Implementation Plan

## 1. 文档目标

本文将 `Shape-aware Merge` 从算法设计进一步拆解为工程实施计划，作为后续 Merge 改造阶段的施工文档。

目标：

- 保留原始 DeepFaceLab TF2.x Merge 流程兼容性
- 增加 src identity geometry 保留能力
- 支持 src 脸型、dst 表情、姿态的融合
- 为未来 UI/Linux 服务化提供稳定接口

核心原则：

> 不替换原 Merge，而是在中间增加可控增强层。

---

## 2. 当前问题

当前流程：

```
Frame
 ↓
Landmarks
 ↓
Affine Transform
 ↓
Prediction
 ↓
Mask
 ↓
Blend
```

主要问题：

- dst landmarks 决定空间结构
- Affine 无法表达脸型变化
- mask 容易重新约束回 dst 外轮廓

因此需要新增 Geometry Layer。

---

## 3. 新 Merge Pipeline

```
Prediction
    ↓
Predicted Landmark
    ↓
Hybrid Landmark Engine
    ↓
Shape Warp
    ↓
Shape-aware Mask
    ↓
Color Adaptation
    ↓
Blend
    ↓
Temporal Stabilization
```

---

## 4. 新增模块设计

### shape/source_shape_template.py

职责：

- 保存 src 身份几何信息
- 提供 canonical shape
- 保存 landmark anchor

数据：

```
face_width
jaw_ratio
cheek_ratio
landmarks
quality_score
```

---

### shape/hybrid_landmark.py

负责融合：

```
src identity geometry
+
dst pose
+
dst expression
```

策略：

- 脸宽、下颌、骨相更多参考 src
- 眼睛、嘴巴动态参考 dst
- 表情变化保留 dst

---

### shape/shape_warp.py

第一版本采用：

```
Piecewise Affine Warp
```

原因：

- 稳定
- 可控
- 易调试
- OpenCV 支持成熟

暂不采用：

- TPS 大变形
- 新模型预测

---

## 5. Mask 改造

新增：

```
Shape-aware Soft Mask
```

规则：

- 中心区域优先 src geometry
- 边界区域平滑参考 dst
- 遮挡区域保持 dst

避免：

```
src shape
 ↓
dst mask
 ↓
shape loss
```

---

## 6. Temporal Stabilization

视频模式增加：

- landmark smoothing
- warp smoothing
- mask contour smoothing

目标：

避免：

- 脸宽跳动
- 下巴闪烁
- 边缘 flicker

---

## 7. 配置设计

示例：

```yaml
shape_merge:
  enabled: false
  mode: hybrid
  source_shape_power: 50
  warp_mode: piecewise_affine
  temporal_smoothing: true
```

默认关闭，保证兼容。

---

## 8. 开发阶段

### Phase 1

实现 Shape Template。

### Phase 2

实现 Hybrid Landmark Engine。

### Phase 3

实现 Shape Warp。

### Phase 4

实现 Shape Mask。

### Phase 5

加入 Temporal Stabilization。

### Phase 6

UI 参数接入。

---

## 9. 验证指标

需要增加：

- Shape Retention Ratio
- Identity Similarity
- Boundary Quality
- Temporal Stability Score

不能只依靠主观视觉判断。

---

## 10. 后续方向

完成该模块后，可以进一步研究：

- 更强的 identity geometry representation
- 自动 shape strength 调节
- 基于视频的人脸几何跟踪
- 服务化 Pipeline
