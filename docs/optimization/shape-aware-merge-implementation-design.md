# Shape-aware Merge Implementation Design

## 1. 文档目标

本文档定义 src-face-shape-training-and-shape-aware-merge-design 的工程实现方案。

目标：在保持 SAEHD / DF / LIAE 模型兼容性的情况下，实现：

```
Source Identity Geometry
+
Source Appearance
+
Destination Pose / Expression
+
Shape-aware Merge
=
更自然的人脸迁移结果
```

本阶段不修改核心网络结构，重点改造 Predictor 与 Merge Pipeline。

---

# 2. 当前 Merge 限制

当前流程：

```
dst frame
 ↓
dst landmark alignment
 ↓
model prediction
 ↓
dst transform inverse warp
 ↓
mask blend
```

主要问题：

- 回贴坐标由 dst landmarks 决定
- dst hull mask 限制输出范围
- affine transform 无法改变局部脸型
- mask 交集会裁剪 src 轮廓

因此需要新增 Shape-aware 模式。

---

# 3. 新 Pipeline

```
Prediction
    |
    v
Predicted Face
Predicted Mask
    |
    v
Predicted Landmark Extraction
    |
    v
Hybrid Landmark Engine
    |
    v
Shape Warp Engine
    |
    v
Shape-aware Mask
    |
    v
Blend
    |
    v
Temporal Stabilization
```

---

# 4. 模块设计

## 4.1 Source Shape Template

新增：

```
shape/
 └── source_shape_template.py
```

职责：

- 保存 src 身份几何信息
- 提供 canonical landmarks
- 提供脸型比例

数据：

```json
{
  "jaw_ratio": 0.82,
  "face_width_ratio": 1.0,
  "chin_ratio": 0.12,
  "eye_distance_ratio": 0.35,
  "landmarks": []
}
```

---

## 4.2 Hybrid Landmark Engine

新增：

```
shape/hybrid_landmark.py
```

目标：融合 src 和 dst 信息。

公式：

```
Hybrid Landmark
=
Source Identity Geometry
+
Destination Pose Transform
+
Destination Expression Offset
```

来源：

Source:

- jaw
- cheek
- face width
- chin
- stable facial ratios

Destination:

- yaw
- pitch
- roll
- eye state
- mouth expression

---

# 5. Shape Warp Engine

新增：

```
shape/shape_warp.py
```

第一阶段采用 Piecewise Affine Warp。

原因：

- OpenCV 支持成熟
- 局部控制能力强
- 比 TPS 稳定
- 不影响模型结构

同步变换：

- predicted RGB
- predicted mask
- XSeg mask

---

# 6. Shape-aware Mask

新增：

```
merge/shape_mask.py
```

新增模式：

## off

保持原逻辑。

## source-contour

迁移 src 外轮廓。

## hybrid

推荐模式：

```
src:
脸型
骨相
固定比例

dst:
表情
姿态
遮挡
```

---

# 7. 配置设计

新增配置：

```yaml
face_shape_mode: off

source_shape_power: 50

shape_mask_mode: hybrid

shape_temporal_smoothing: true
```

兼容策略：

默认关闭，旧模型和旧视频流程不受影响。

---

# 8. 时序稳定

视频模式增加：

```
temporal/
 └── shape_stabilizer.py
```

处理：

- landmarks
- warp field
- mask contour

推荐：

- EMA
- One Euro Filter

避免：

- 脸宽跳动
- 下巴漂移
- 边缘抖动

---

# 9. 开发阶段

## Phase 1

完成 Shape Template。

目标：

验证 src geometry 数据有效。

---

## Phase 2

实现 Hybrid Landmark。

目标：

生成稳定混合几何。

---

## Phase 3

实现 Shape Warp。

目标：

验证脸型迁移。

---

## Phase 4

实现 Shape-aware Mask。

目标：

解决轮廓裁剪。

---

## Phase 5

加入 Temporal Stabilization。

目标：

达到视频可用级别。

---

# 10. 验收指标

新增指标：

## Shape Retention Ratio

```
merged shape similarity /
predicted shape similarity
```

## Identity Score

验证身份保持。

## Expression Preservation

验证 dst 表情保持。

## Temporal Stability

验证视频连续性。

---

# 11. 设计原则

保持：

- 原模型兼容
- 原 DFM 可用
- 原 Merge 可回退

新增：

- Shape-aware 高级模式
- 可配置
- 可实验
- 可逐步优化

最终目标：

```
SAEHD Enhanced Pipeline

=

Existing Model
+
Better Training
+
Identity Geometry
+
Shape-aware Merge
+
Temporal Stability
```
