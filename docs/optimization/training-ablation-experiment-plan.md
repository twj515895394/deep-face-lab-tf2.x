# Training Ablation Experiment Plan

## SAEHD Enhanced Training Pipeline 实验验证方案

版本: v1.0

---

# 1. 文档目标

当前训练优化方向已经包含：

- Identity Loss
- Face Shape Preservation
- Region Aware Loss
- Boundary Loss
- Frequency Loss
- src/dst 非对称增强
- Dynamic Sampling
- Curriculum Training

如果同时修改，会无法判断收益来源。

因此建立标准化实验体系，通过单变量和组合实验验证每个优化项。

目标：

> 在保持模型结构兼容的情况下，找到收益最高、风险最低的训练增强组合。

---

# 2. 基础 Baseline 定义

所有实验必须基于固定 Baseline。

Baseline:

```
Original SAEHD TF2.x
+
原始 Dataset
+
原始 Loss
+
原始 Training Schedule
```

固定：

- 模型结构
- 分辨率
- batch size
- GPU 环境
- faceset
- 训练步数
- preview 测试集

避免环境变化影响结果。

---

# 3. 评价指标体系

## 3.1 Identity Score

评价：

- src 身份保持
- 五官相似度
- 脸型相似度

指标：

```
Source embedding similarity
Landmark shape similarity
```

---

## 3.2 Attribute Preservation

评价 dst 信息保持：

- 表情
- 嘴型
- 眼神
- 姿态
- 光照

---

## 3.3 Visual Quality

评价：

- 清晰度
- 纹理
- 边界
- 颜色一致性

---

## 3.4 Video Consistency

针对视频：

- 帧间稳定
- 闪烁
- mask 抖动
- 颜色跳变

---

# 4. P0 实验：基础问题修复

## Experiment-001

### Eyes/Mouth Loss 修复

目标：

确认 eyes/mouth priority 真正产生梯度。

验证：

记录：

```
eye loss
mouth loss
mask ratio
gradient contribution
```

成功标准：

- loss 非零
- 局部区域质量提升

---

# 5. P1 实验：Identity Enhancement

## Experiment-010

加入 Identity Loss。

实验：

```
Baseline
vs
Baseline + Identity Loss
```

观察：

提升：

- 五官一致性
- 身份相似度

风险：

- 表情下降
- 过度 src 化

---

# 6. P1 实验：Face Shape Preservation

## Experiment-020

加入：

- Landmark Shape Loss
- Face Geometry Loss

目标：

解决：

```
src 五官像
但是 dst 脸型存在
```

评价重点：

- 下颌
- 脸宽
- 颧骨
- 眼距

---

# 7. P1 实验：Region Aware Loss

## Experiment-030

加入 face parsing region weight。

区域：

```
Eyes
Mouth
Nose
Skin
Jaw
Boundary
```

验证：

是否提升：

- 眼睛质量
- 嘴部质量
- 边缘自然度

---

# 8. P2 实验：Detail Enhancement

## Experiment-040

加入：

- Laplacian Pyramid Loss
- Frequency Loss
- Gradient Loss

目标：

改善：

- 蜡像感
- 纹理不足
- 皮肤细节

风险：

过早加入导致噪声。

---

# 9. P2 实验：src/dst Sampling

## Experiment-050

比较：

```
Random Sampling

vs

Quality Weighted Sampling
```

重点：

src：

- identity coverage

 dst：

- motion coverage

---

# 10. P2 实验：Curriculum Training

## Experiment-060

阶段：

Stage 1:

身份学习

Stage 2:

属性保持

Stage 3:

细节增强

比较：

固定训练
vs
Curriculum

---

# 11. 组合实验

在单项验证完成后：

## Combo-A

```
Identity Loss
+
Shape Loss
```

目标：

身份 + 脸型。

---

## Combo-B

```
Identity
+
Shape
+
Region
```

目标：

综合质量提升。

---

## Combo-C

```
Identity
+
Shape
+
Region
+
Frequency
+
Curriculum
```

目标：

最终增强版本。

---

# 12. 实验记录规范

每次实验记录：

```
Experiment ID

Code Commit

Config

Dataset Version

Training Steps

GPU

Loss Curve

Preview Result

Metric Result

Conclusion
```

---

# 13. 合入规则

任何优化进入主分支必须满足：

1. 有明确指标提升
2. 无明显副作用
3. 可重复实验
4. 参数可配置
5. 可以关闭回退

---

# 14. 当前推荐开发顺序

```
P0
修复训练正确性

↓

P1
Identity
Shape
Region

↓

P2
Sampling
Curriculum
Frequency

↓

P3
高级实验
GAN
Architecture Adapter
```

---

# 15. 最终目标

形成：

```
Enhanced SAEHD Training Pipeline

=

Original Model
+
Better Data Strategy
+
Better Supervision
+
Better Evaluation
```

保持兼容，同时获得更高质量换脸能力。
