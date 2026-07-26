# DeepFaceLab TF2.x Merger Call Chain Analysis

## 1. Purpose

本文档分析 DeepFaceLab TF2.x 当前合成阶段调用链，为后续 Shape-aware Merge Engine 改造提供源码入口和工程依据。

核心目标：

- 明确当前 Merge 如何决定最终脸型
- 找出 src identity geometry 无法保留的原因
- 定义 Shape-aware Merge 的最佳插入位置

---

# 2. 当前 Merge 总流程

```text
Video Frame
    |
    v
Face Detection
    |
    v
Landmarks Detection
    |
    v
Face Alignment
    |
    v
Model Prediction
    |
    v
Mask Processing
    |
    v
Color Transfer
    |
    v
Blending
    |
    v
Output Frame
```

---

# 3. 当前关键职责

## 3.1 Landmarks

当前 landmarks 主要来自 destination frame。

负责：

- 对齐位置
- 旋转
- 缩放
- 回贴坐标

问题：

dst geometry 从入口阶段已经参与决定最终空间结构。

---

## 3.2 Prediction

模型输出：

- predicted face image
- predicted mask

负责：

- src identity appearance
- 部分身份特征

但是不会直接控制最终回贴轮廓。

---

# 4. 当前限制 src 脸型的关键点

## 4.1 Affine Transform

当前主要依赖整体仿射变换：

```text
translation
rotation
scale
shear
```

无法表达：

- 下颌变化
- 脸宽变化
- 颧骨变化
- 局部几何变化

---

## 4.2 Mask Pipeline

当前 mask 主要用于限制融合区域。

风险：

```text
src prediction
      |
      v
 dst mask constraint
      |
      v
src shape 被裁剪
```

---

# 5. Shape-aware Merge 插入点

推荐增加中间层：

```text
Prediction
    |
    v
Predicted Landmark
    |
    v
Hybrid Landmark Engine
    |
    v
Shape Warp
    |
    v
Shape Mask
    |
    v
Blend
```

---

# 6. 新增模块设计

## shape/

```text
source_shape_template.py
```

保存 src 身份几何。

```text
hybrid_landmark.py
```

融合：

- src identity geometry
- dst pose
- dst expression

```text
shape_warp.py
```

执行局部几何变换。

---

# 7. 推荐第一版实现

采用：

## Piecewise Affine Warp

原因：

- 稳定
- 可控
- 易于回滚
- 与 OpenCV 兼容

暂不采用：

- TPS 大变形
- 新模型预测

---

# 8. Mask 新策略

新增：

```text
shape-aware-soft
```

原则：

- 内部区域支持 src shape
- 边缘区域参考 dst
- 遮挡区域保持 dst

避免简单 mask intersection 导致脸型恢复 dst。

---

# 9. 时序稳定

视频模式必须加入：

- landmark smoothing
- warp smoothing
- mask contour smoothing

避免：

- 脸宽跳动
- 下巴闪动
- 边缘 flicker

---

# 10. 开发阶段

## Phase 1

保持现有 Merge 不变，增加独立 Shape-aware 模式。

## Phase 2

实现 Hybrid Landmark。

## Phase 3

实现 Piecewise Affine Warp。

## Phase 4

加入 Temporal Stabilization。

## Phase 5

UI 集成。

---

# 结论

当前 DFL 的脸型问题不仅是训练问题，也是 Merge 几何约束问题。

未来增强方向应为：

```text
Better Training
+
Identity Geometry
+
Shape-aware Merge
+
Temporal Stabilization
```

而不是单纯增加模型容量。