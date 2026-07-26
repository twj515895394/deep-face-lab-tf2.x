# Source Face Shape Training and Shape-aware Merge Design

## 1. 文档定位

本文档定义 DeepFaceLab TF2.x 增强路线中的一个核心方向：在不修改 SAEHD / DF / LIAE 主模型架构的情况下，实现：

> Source Identity + Source Face Geometry + Destination Pose/Expression 的高质量融合。

当前 DFL 最大的问题之一：

- 五官可以较好迁移到 src；
- 皮肤纹理可以接近 src；
- 但是脸宽、下颌、脸型比例经常仍接近 dst。

该问题不是单纯训练问题，而是 Training 与 Merge 共同造成的结果。

---

# 2. 核心问题分析

## 2.1 Identity 不应该只包含纹理

传统换脸通常认为 Identity 包含：

- 眼睛
- 鼻子
- 嘴巴
- 皮肤纹理

但是人脸识别中，几何结构同样属于身份信息。

因此重新定义：

## Identity Appearance

包括：

- 五官细节
- 肤质
- 颜色
- 纹理

## Identity Geometry

包括：

- 脸宽
- 下颌
- 下巴长度
- 颧骨比例
- 眼距
- 鼻脸比例

最终身份表示：

```
Identity = Appearance + Geometry
```

---

# 3. 当前 DFL 为什么保留 dst 脸型

当前流程：

```
dst frame
   |
landmarks
   |
Affine alignment
   |
SAEHD prediction
   |
Merge
   |
original frame
```

主要问题：

## 3.1 对齐坐标由 dst 决定

当前 face transform 基于 dst landmarks。

结果：

- 脸的位置由 dst 决定；
- 尺寸由 dst 决定；
- 基础几何由 dst 决定。

---

## 3.2 Mask 限制 src 外轮廓

当前 mask 通常包含：

- hull mask
- XSeg mask
- predicted mask

大量情况下等价于：

```
src prediction ∩ dst face region
```

因此 src 脸型超出 dst 轮廓的部分会被裁掉。

---

# 4. 总体设计方案

最终 Pipeline：

```
Dataset
 |
Training
 |
Predict
 |
Source Shape Extraction
 |
Hybrid Geometry
 |
Shape-aware Warp
 |
Shape-aware Mask
 |
Blend
 |
Temporal Stabilization
```

---

# 5. Source Shape Template

为每个 src identity 建立几何模板。

生成流程：

1. 收集 src faceset；
2. 提取 landmarks；
3. 筛选高质量正脸；
4. Canonical Normalize；
5. 计算稳定几何中心。

保存：

```
model_name.srcshape
```

内容：

- canonical landmarks
- jaw contour
- face width ratio
- cheek ratio
- chin ratio
- confidence

---

# 6. Training 优化方向

训练阶段增加 Identity Geometry 监督。

## Shape Loss

目标：

```
predicted face shape ≈ source shape
```

可使用：

- landmark geometry loss
- jaw loss
- contour loss
- parsing region loss

---

# 7. Hybrid Landmark Engine

不能简单替换 dst landmarks。

需要拆分职责：

## Source 提供

- 脸宽
- 下颌
- 下巴
- 固定五官比例

## Destination 提供

- yaw
- pitch
- roll
- 眼睛开合
- 嘴部运动
- 表情变化

最终：

```
Hybrid Landmark = Source Identity Geometry
                + Destination Pose
                + Destination Expression Offset
```

---

# 8. Shape-aware Merge

## 8.1 不推荐只使用 Affine

Affine 只能：

- 平移
- 缩放
- 旋转

不能改变：

- 下颌形状
- 脸宽比例
- 局部轮廓

---

## 8.2 推荐 Piecewise Affine Warp

流程：

```
predicted face
      |
landmarks
      |
triangle mesh
      |
local affine warp
      |
shape adapted face
```

优点：

- 与 OpenCV 兼容；
- 不需要修改模型；
- 可局部控制；
- 兼容旧模型。

---

# 9. Shape-aware Mask

新的 Mask 模式：

```
off
source-contour
hybrid
```

推荐：

```
hybrid
```

原则：

src 控制：

- 身份区域
- 脸型轮廓

dst 控制：

- 遮挡
- 表情边界

避免简单：

```
src_mask * dst_mask
```

因为会重新恢复 dst 脸型。

---

# 10. Temporal Stabilization

视频必须处理时序稳定。

需要平滑：

- hybrid landmarks
- warp field
- mask contour
- shape power

推荐：

- EMA
- One Euro Filter

避免：

- 脸宽跳动
- 下巴抖动
- 边缘闪烁

---

# 11. 参数设计

新增：

```
face_shape_mode

source_shape_power

shape_mask_mode
```

示例：

```
source_shape_power=0
```

完全保持当前 DFL。

```
source_shape_power=50
```

中等 src 脸型迁移。

```
source_shape_power=100
```

最大实验模式。

---

# 12. 工程实施路线

## Phase 1

训练侧：

- Shape Loss
- Landmark Metrics
- Shape Evaluation

## Phase 2

数据侧：

- Source Shape Template
- Identity Geometry Cache

## Phase 3

Merge：

- Hybrid Landmark
- Piecewise Warp
- Shape Mask

## Phase 4

视频：

- Temporal Stabilization

## Phase 5

UI：

提供高级模式开关。

---

# 13. 验收指标

新增评价：

## Shape Retention Ratio

```
Merged Shape Score
------------------
Predicted Shape Score
```

衡量预测结果经过 Merge 后保留多少 src 几何。

同时观察：

- Identity Score
- Expression Score
- Video Stability Score

---

# 14. 最终目标

最终增强版 DFL：

```
Source
 |
Identity Appearance
Identity Geometry
 |

Destination
 |
Pose
Expression
Motion
 |

Enhanced Merge
 |

Natural Face Replacement
```

目标不是简单换五官，而是实现：

> src 的身份和脸型 + dst 的运动表现。

同时保持：

- 原模型兼容；
- 原训练流程可用；
- 原 Merge 可回退。
