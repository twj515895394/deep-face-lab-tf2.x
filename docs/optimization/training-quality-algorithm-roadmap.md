# DFL TF2.x Training Quality Algorithm Roadmap

## 1. 文档定位

本文档规划 DeepFaceLab TF2.x 后续训练质量算法方向。它负责说明算法优先级，不替代总实施计划、正式 Batch Ticket 或环境验收记录。

当前优先顺序：

```text
训练正确性
    ↓
Metadata / Smart Sampling
    ↓
Minimal Loss Hook
    ↓
Identity Geometry MVP
    ↓
Source Shape Template / Shape-aware Merge 闭环
    ↓
Identity Appearance 与通用画质 Loss
    ↓
网络结构和高级算法实验
```

所有质量优化必须基于固定条件、可复现配置和人工 A/B，不以单一总 Loss 数值作为唯一判断。

---

## 2. 当前质量瓶颈

当前 SAEHD 质量主要受以下因素影响：

- faceset 数据质量；
- 姿态覆盖不足；
- 错误 Landmark 和遮挡样本；
- src Identity Appearance 保持能力；
- src Identity Geometry 保持能力；
- 高频细节恢复能力；
- Mask 和轮廓边界；
- Merge 几何限制；
- 视频时序稳定性。

这些问题分属于不同层：

```text
数据层
  ↓
采样层
  ↓
训练目标层
  ↓
几何桥梁与 Merge 层
  ↓
画质精修层
  ↓
高级网络实验层
```

不能把所有问题都归结为“再增加一个 Loss”。

---

## 3. 已完成优先级：数据与采样

Batch 2 已完成计划内 Metadata / Sampling 实现，包括：

- Faceset Analyzer；
- Quality / Pose Metadata；
- Ordinary / Packed；
- Full / Incremental / Force；
- Quick / Strong Fingerprint；
- Pose Balanced；
- Quality + Pose Balanced；
- SRC / DST 独立策略；
- Fallback、Strict 和 Trainer Control。

这一层解决：

> 模型训练时实际看到哪些素材，以及不同样本出现的概率是否合理。

它不会自动让模型学习 src 脸宽、下颌和下巴比例，因此下一优先级进入 Identity Geometry。

---

## 4. 下一优先级：Minimal Loss Hook

### 4.1 目标

建立可扩展但保持最小的训练目标接入层，为 Geometry Loss 提供：

- 独立开关；
- 独立权重；
- 单项日志；
- dtype / shape / mask 契约；
- NaN / Inf 检查；
- 保存恢复兼容；
- 关闭后基线一致。

### 4.2 非目标

这一阶段不批量实现：

- ArcFace / 大型身份编码器；
- Perceptual Loss；
- Frequency Loss；
- 完整 Region / Boundary Loss；
- 自动 Loss 权重搜索。

原因是这些能力会显著扩大实验矩阵，却不能直接验证 src 脸型能否形成训练到 Merge 的闭环。

---

## 5. 核心优先级：Identity Geometry

### 5.1 问题定义

传统 DFL 容易出现：

```text
五官像 src
脸宽、下颌和下巴仍像 dst
```

Geometry MVP 的目标不是大形变，而是学习稳定的身份比例。

### 5.2 Shape Anchor

从 src faceset 中聚合：

- 高可信 Landmark；
- 较正脸或可稳定 canonical normalize；
- 较高质量；
- 较少遮挡；
- 较弱表情；

形成 Identity Geometry Anchor。

### 5.3 Landmark / Ratio Loss

第一版优先：

```text
face_width / face_height
jaw_width / face_width
chin_length / face_height
cheek_width / face_width
eye_distance / face_width
nose_width / face_width
```

避免第一版直接依赖复杂 3DMM 或大型外部网络。

### 5.4 src / dst 责任分离

```text
src：脸宽、下颌、下巴、颧骨、稳定比例
dst：姿态、眼睛开合、嘴型、表情和运动
```

Geometry Loss 必须避免把 src 某一帧静态表情复制到 dst。

### 5.5 最小 Curriculum

```text
A：Reconstruction
B：Geometry Ramp
C：Geometry Stable
```

阶段状态必须可持久化和恢复。

---

## 6. 几何训练之后：Source Shape Template 与 Merge 闭环

训练 Loss 只能说明模型是否学习几何目标，不能保证最终 Merge 保留这些目标。

因此 Geometry MVP 后必须优先验证：

- Source Shape Template；
- Hybrid Landmark；
- Piecewise Affine Warp；
- Shape-aware Soft Mask；
- 遮挡回退；
- Temporal Stabilization。

只有闭环稳定后，才有可信基线判断通用画质 Loss 的真实收益。

---

## 7. 后移优先级：Identity Appearance Loss

### 7.1 目标

增强源身份的五官、纹理和外观保持。

候选方向：

- 轻量冻结身份特征；
- Face Recognition Feature Loss；
- ArcFace Embedding Loss；
- 不依赖外部模型的局部身份特征约束。

### 7.2 风险

- 外部模型域偏差；
- 额外显存和推理成本；
- 与 Reconstruction / Geometry 梯度冲突；
- 可能提高 Identity Score，但损伤表情或自然度。

第一版 Batch 7 不应默认强依赖大型识别模型。

---

## 8. 后移优先级：Region / Boundary / Frequency

### 8.1 Region Loss

关注：

- Eyes；
- Mouth；
- Nose；
- Cheek；
- Skin；
- Face Contour。

需要与已修复的 Eyes / Mouth Priority 做职责和权重统一，避免重复监督。

### 8.2 Boundary Loss

目标：

- 改善下巴和外轮廓预测；
- 减少边缘模糊和断裂；
- 为 Shape-aware Mask 提供更稳定输入。

Boundary Loss 不能替代 Merge Mask；训练边界和最终回贴边界属于不同阶段。

### 8.3 Frequency Loss

候选：

- FFT Loss；
- Laplacian Pyramid Loss；
- Focal Frequency Loss。

目标：改善毛发、眉毛、嘴唇、皮肤纹理和高频细节。

风险：

- 过度锐化；
- 噪声和压缩纹理被放大；
- GAN 同时启用时稳定性下降。

---

## 9. Perceptual Loss

候选：

- LPIPS；
- VGG Feature Loss；
- DINO Feature Loss。

该方向属于 Batch 7 之后的可选实验，不是第一版脸型闭环的必要条件。

风险：

- 降低像素级重建精度；
- 引入额外模型和依赖；
- 对人脸域、分辨率和颜色空间敏感。

---

## 10. 网络结构增强

网络结构实验必须晚于训练与 Merge 闭环。

### 10.1 Attention

候选：

- CBAM；
- SE Block；
- ECA。

风险：增加计算量并破坏旧 checkpoint 兼容。

### 10.2 Decoder

候选：

- 多尺度 Decoder；
- 高频细节分支；
- Mask / RGB Decoder 解耦。

第一版不进入该范围，因为当前优先问题是监督目标和 Merge 几何，不是模型容量。

---

## 11. GAN 优化

当前 GAN 风险较高，建议保持独立实验：

- Discriminator 稳定性；
- Gradient Penalty；
- Feature Matching；
- 与 Geometry / Frequency Loss 的梯度冲突。

不能只以锐度作为收益，需要同时观察身份、脸型、表情和时序稳定。

---

## 12. 时序一致性

视频质量满足：

```text
单帧优秀 != 视频优秀
```

脸型闭环阶段优先使用轻量时序方案：

- Landmark smoothing；
- Warp parameter smoothing；
- Mask contour smoothing；
- Source shape power smoothing；
- Scene Cut Reset。

复杂方向如 Optical Flow Consistency、Latent Temporal Constraint 属于后续研究，不是第一版默认方案。

---

## 13. 更新后的实验优先级

### P0：当前硬门

- Batch 2 Windows GPU Final Matrix；
- 旧流程、保存恢复和资源清理。

### P1：下一开发批次

- Minimal Loss Hook；
- Shape Anchor；
- Landmark / Ratio Loss；
- Identity Geometry；
- Geometry Curriculum；
- Geometry 固定条件 A/B。

### P2：脸型闭环

- Source Shape Template；
- Hybrid Landmark；
- Piecewise Affine Warp；
- Shape-aware Soft Mask；
- Temporal Stabilization。

### P3：通用训练增强

- Identity Appearance Loss；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- Full Multi-objective Curriculum；
- Perceptual Loss 实验。

### P4：高级结构实验

- Attention；
- Multi-scale Decoder；
- GAN 改造；
- Temporal Model；
- 大模型 Encoder。

---

## 14. 验证标准

所有实验必须记录：

- 代码 Commit；
- 训练配置；
- 数据集和 Metadata / Shape Template 身份；
- 随机种子；
- iteration 和训练时长；
- 单项 Loss 曲线；
- Preview；
- Identity Similarity；
- Shape Retention；
- Expression / Pose 保持；
- Boundary Quality；
- Video Stability；
- 性能、显存和资源变化；
- 保存、退出和恢复结果。

禁止仅根据总 Loss 判断效果。

---

## 15. 后续开发顺序

```text
Batch 2 Final Sign-off
        ↓
Minimal Loss Hook
        ↓
Identity Geometry MVP
        ↓
Source Shape Template
        ↓
Shape-aware Merge MVP
        ↓
Mask / Temporal
        ↓
Identity Appearance / Region / Boundary / Frequency
        ↓
Network and Advanced Experiments
```

若专项文档与该顺序冲突，以 `implementation/enhanced-dfl-master-implementation-plan.md` 为准。