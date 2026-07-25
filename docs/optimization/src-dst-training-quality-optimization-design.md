# src/dst Training Quality Optimization Design

## Overview

本文定义在**不修改 SAEHD / DF / LIAE 核心模型结构**前提下，对训练质量进行系统优化的路线。

目标不是重新设计模型，而是通过：

- 数据策略
- Loss 设计
- 采样策略
- 训练阶段控制
- 质量评价体系

提升通用模型的换脸质量。

---

# 1. 核心问题

当前 DFL 训练天然存在 src/dst 信息职责混淆：

Source 主要应该提供：

- 身份
- 五官
- 脸型
- 肤质

Destination 主要应该提供：

- 姿态
- 表情
- 光照
- 遮挡
- 视频运动状态

但是传统训练通常使用相近的重建目标，导致：

- 身份保持不足
- dst 身份泄漏
- 表情保持不足
- 几何结构偏向 dst

---

# 2. 优化原则

保持兼容：

- 原模型
- 原训练流程
- 原模型文件
- 原推理流程

优先通过训练系统增强。

---

# 3. P0 修复

## Eyes/Mouth Priority 验证

需要确认局部 mask 是否真实进入 Loss。

增加指标：

- eye loss
- mouth loss
- region pixel ratio
- gradient contribution

避免存在配置开启但实际无梯度的问题。

---

# 4. Source 优化

Source 目标：最大化身份表达。

优化：

- 高质量 identity anchor
- 多角度覆盖
- 颜色增强
- 轻度质量扰动
- 小区域遮挡增强

Source sampler 建议：

- 60% 普通样本
- 20% 稀缺角度
- 15% 困难样本
- 5% 探索样本

---

# 5. Destination 优化

Destination 目标：保持视频属性。

重点：

- pose
- expression
- gaze
- lighting
- occlusion

避免过强几何增强导致表情损失。

---

# 6. Loss 演进

从：

Reconstruction Loss

升级为：

```
Total Loss =
 Reconstruction
 + Identity
 + Attribute
 + Region
 + Boundary
 + Frequency
```

---

# 7. Identity Loss

增加冻结身份编码器：

```
source image
    |
identity encoder
    |
embedding

swap output
    |
identity encoder
    |
embedding
```

约束 swap 输出保持 source identity。

---

# 8. Attribute Preservation

增加：

- Landmark Loss
- Pose Loss
- Expression Loss

确保 swap 保留 dst 的运动属性。

---

# 9. Region Aware Training

从单一 face mask 升级到区域 mask：

- eyes
- mouth
- nose
- skin
- boundary
- occlusion

不同区域使用不同权重。

---

# 10. Curriculum Training

建议：

阶段1：身份稳定

阶段2：属性保持

阶段3：细节增强

阶段4：精修

---

# 11. Evaluation

增加：

- Identity Score
- Attribute Score
- Artifact Score
- Temporal Stability Score

---

# 12. 明确不做

当前阶段不考虑：

- Diffusion Face Swap
- Transformer 重构
- 完全新模型

重点优化现有 DFL 工程路线。
