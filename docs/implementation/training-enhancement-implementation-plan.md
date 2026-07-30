# DeepFaceLab TF2.x Training Enhancement Implementation Plan

## 1. 文档目标

本文定义训练侧优化从设计进入代码实现阶段的执行方案。

目标：

- 不修改 SAEHD / DF / LIAE 原有模型架构；
- 保持旧 checkpoint、旧模型配置和训练入口兼容；
- 通过 Metadata、Sampling、Identity Geometry 和后续通用 Loss 提升训练质量；
- 优先为 Source Shape Template 与 Shape-aware Merge 提供可信几何输入；
- 所有能力默认关闭、可独立回退。

核心原则：

> 先改善训练数据，再建立最小 Loss Hook；先验证 Identity Geometry，再叠加通用外观和画质 Loss。

路线调整说明：

- Batch 3 不再一次性实现 Region / Boundary / Frequency / Identity Appearance；
- Batch 3 只实现几何训练必需的 Loss 基础设施、Shape Anchor 和 Geometry MVP；
- 通用身份外观与画质 Loss 后移到脸型闭环稳定后的 Batch 7。

---

## 2. Training Enhancement 总体流程

```text
Dataset
  ↓
Metadata Analysis
  ↓
Smart Sampling
  ↓
Minimal Loss Hook
  ↓
Identity Geometry MVP
  ↓
Source Shape Template / Shape-aware Merge
  ↓
Appearance & Quality Losses
  ↓
Evaluation and Ablation
```

训练侧与 Merge 侧的关系：

```text
训练学习 src geometry
        ↓
输出可验证的几何表示
        ↓
Source Shape Template
        ↓
Merge 真正应用 src geometry
```

只完成训练 Geometry Loss，不代表最终视频一定保留 src 脸型。

---

## 3. Dataset 与 Metadata

Batch 2 已建立的 Metadata / Sampling 是后续几何训练的数据基础。

### 3.1 当前可用信息

```text
quality_score
pose / yaw_bucket
pose_valid
quality_valid
sample identity / signature
faceset fingerprint
```

后续几何阶段可扩展：

```text
landmark_confidence
occlusion_score
shape_anchor_candidate
canonical_shape_features
```

### 3.2 用途

- 选择可信 Shape Anchor 候选；
- 降低错误 Landmark、严重遮挡和低质量样本的几何监督影响；
- 记录 src / dst 姿态和质量分布；
- 支撑 Geometry Curriculum 和 A/B 实验；
- 为 Source Shape Template 提供身份和数据一致性校验。

### 3.3 边界

Metadata 不直接修改图片，不自动删除样本，也不直接改变模型 Loss。训练是否使用某项 Metadata 必须由对应 Feature Flag 决定。

---

## 4. Sampling 与 Geometry 的关系

Batch 2 的智能采样先决定“模型看到哪些样本”，Batch 3 的 Geometry Loss 再决定“模型从样本中学习什么几何目标”。

推荐关系：

```text
SRC：quality_pose_balanced
     → 提高稀缺姿态覆盖
     → 降低低质量 Anchor 候选的重复概率

DST：pose_balanced
     → 保持目标视频稀缺姿态覆盖
     → 不因质量加权过强而忽略真实困难帧
```

Sampling 不能替代 Geometry Loss：

- 多看侧脸，不等于学习 src 下颌比例；
- 多看清晰图，不等于学习 src 脸宽；
- Geometry Loss 仍需明确的 Shape Anchor 和比例目标。

---

## 5. Batch 3：最小 Loss Hook

### 5.1 目标

为 Identity Geometry 提供稳定、可测试、可扩展的 Loss 接入层，而不是在第一批一次性引入所有训练增强。

### 5.2 必须能力

- Loss 注册与调用；
- 每项 Loss 独立开关；
- 每项 Loss 独立权重；
- 单项 Loss 原始值和加权值日志；
- 总 Loss 汇总；
- dtype、shape、mask 和 reduction 契约；
- NaN / Inf 检查；
- 非有限梯度时保持已有 Trainer 失败或跳步语义；
- Feature Flag 关闭后不构建额外计算；
- 保存恢复后配置和 Curriculum 阶段一致；
- 旧 checkpoint 不要求包含新增状态。

### 5.3 建议接口

```python
loss_result = loss_hook.compute(
    context=training_context,
    enabled_losses=enabled_losses,
)

# 结果至少包含：
# raw_values
# weighted_values
# total_addition
# warnings
```

Loss Hook 不应直接拥有 Trainer 保存、退出和恢复控制权，只返回结构化结果，由现有训练主链路汇总。

### 5.4 Batch 3 非目标

以下功能保留接口，但不在 Batch 3 批量实现：

```text
Identity Appearance Loss
Region Loss
Boundary Loss
Frequency Loss
大型外部识别模型依赖
自动 Loss 权重搜索
完整多目标 Curriculum
```

---

## 6. Shape Anchor

### 6.1 目标

从 src faceset 中得到稳定的身份几何中心，避免 Geometry Loss 追随任意单帧姿态或表情。

### 6.2 候选样本条件

优先选择：

- Landmark 有效且置信度高；
- 接近正脸或可可靠 canonical normalize；
- 清晰度较高；
- 曝光正常；
- 遮挡较少；
- 表情幅度较小；
- 与当前 src identity / faceset fingerprint 一致。

### 6.3 聚合方式

第一版优先采用可解释方式：

1. Landmark canonical normalize；
2. 过滤低置信度和异常比例样本；
3. 使用 median / trimmed mean 聚合；
4. 输出比例向量和 canonical landmarks；
5. 记录样本数、置信度和生成版本。

不建议第一版使用额外大型网络生成不可解释 Shape Embedding。

---

## 7. Identity Geometry Loss

### 7.1 目标

让模型学习稳定的 src 身份几何，而不是只学习纹理和颜色。

关注：

- 脸宽；
- 下颌宽度与曲线；
- 下巴长度；
- 颧骨比例；
- 眼距；
- 鼻宽与脸宽比例；
- 稳定五官相对位置。

### 7.2 推荐第一版

优先实现 Landmark / Ratio Loss：

```text
face_width / face_height
jaw_width / face_width
chin_length / face_height
cheek_width / face_width
eye_distance / face_width
nose_width / face_width
```

推荐使用归一化比例而不是绝对像素坐标，降低分辨率、缩放和姿态带来的干扰。

### 7.3 src / dst 非对称职责

```text
src 提供：
- 脸宽
- 下颌
- 下巴
- 颧骨
- 稳定五官比例

dst 提供：
- yaw / pitch / roll
- 眼睛开合
- 嘴型
- 眉毛和表情
- 视频运动
```

Geometry Loss 不得要求预测结果复制 src 某一帧的姿态、嘴型或眼睛状态。

### 7.4 权重原则

- `geometry_weight = 0` 必须等价基线；
- 初始权重从低值逐步增加；
- 需要权重上限；
- 单项几何比例要分别记录，不能只记录一个 Geometry Total；
- 低置信度样本应跳过或降权，不得静默作为高可信监督。

---

## 8. 最小 Geometry Curriculum

Batch 3 第一版只实现简单、显式、可恢复的阶段控制。

### Stage A：Reconstruction Baseline

```text
Geometry Loss = 0
```

目标：先建立稳定基础重建。

### Stage B：Geometry Ramp

```text
Geometry Loss 从 0 逐步提升到目标权重
```

目标：避免训练早期突然增加几何目标造成梯度冲突。

### Stage C：Geometry Stable

```text
Geometry Loss 保持稳定权重
```

目标：观察脸型收敛、身份外观和 dst 表情是否保持。

### 状态要求

- 支持按 iteration 或手动切换；
- 当前阶段和进入阶段的 iteration 可持久化；
- 恢复训练不得回到 Stage A；
- 用户可关闭 Curriculum，显式固定 Geometry 权重；
- Batch 7 再扩展 Appearance / Boundary / Frequency 等完整阶段。

---

## 9. Batch 7：通用身份外观与画质 Loss

脸型闭环稳定后，再依次增加：

### 9.1 Identity Appearance Loss

强化五官、身份纹理和外观一致性。第一版不强制依赖大型外部人脸识别模型。

### 9.2 Region Loss

对 Eyes、Mouth、Nose、Cheek、Skin、Boundary 等区域提供可配置权重。

### 9.3 Boundary Loss

关注下巴、外轮廓和 Mask 边缘，但不得与 Shape-aware Mask 的职责混淆：

- Boundary Loss 改善训练输出边界；
- Shape-aware Mask 决定 Merge 时如何保留和过渡轮廓。

### 9.4 Frequency Loss

改善眉毛、嘴唇、皮肤纹理和高频细节。

### 9.5 完整 Curriculum

建议扩展为：

```text
A：Reconstruction
B：Geometry
C：Identity Appearance
D：Region / Boundary
E：Frequency / Detail Refinement
```

必须逐项消融，不一次性启用全部 Loss。

---

## 10. 配置设计

示例仅表示结构，字段名以对应 Batch 最终 Ticket 为准：

```yaml
training:
  loss_hook_enabled: false

  identity_geometry:
    enabled: false
    weight: 0.0
    anchor_path: null

  curriculum:
    enabled: false
    stage: reconstruction

  appearance_losses:
    identity_enabled: false
    region_enabled: false
    boundary_enabled: false
    frequency_enabled: false
```

约束：

- 未提供字段时使用 DFL 内部默认值；
- GUI 不重复维护底层固定默认值；
- Batch 3 配置不能提前宣称支持 Batch 7 尚未实现的 Loss；
- 未知字段必须忽略或明确报错，不得意外启用功能；
- 配置 Schema 版本必须有兼容策略。

---

## 11. 实施阶段

### Phase 1：Metadata / Sampling

对应 Batch 2。计划内代码已完成，生产签发等待 Windows GPU Matrix。

### Phase 2：Minimal Loss Hook

对应 Batch 3 第一部分：接口、开关、权重、日志、数值保护和兼容。

### Phase 3：Identity Geometry MVP

对应 Batch 3 第二部分：Shape Anchor、Landmark / Ratio Loss 和最小 Curriculum。

### Phase 4：Geometry Bridge and Merge Integration

对应 Batch 4—6：Source Shape Template、Hybrid Landmark、Warp、Mask 和 Temporal。

### Phase 5：Appearance and Quality Losses

对应 Batch 7：Identity Appearance、Region、Boundary、Frequency 和完整 Curriculum。

### Phase 6：Ablation and Productization

对应 Batch 8：固定条件 A/B、默认参数、性能、兼容、GUI 和文档。

---

## 12. 验证指标

训练工程指标：

- 启动和稳定迭代；
- 单项 Loss 数值有限；
- 梯度有限；
- 关闭功能后基线一致；
- 保存、退出和恢复；
- 旧 checkpoint 兼容；
- 性能和显存变化；
- 日志可定位。

Geometry 指标：

- face width ratio；
- jaw ratio；
- chin ratio；
- cheek ratio；
- Shape Anchor confidence；
- src Identity Geometry 保留趋势；
- dst pose / expression 保持。

效果层指标：

- Identity Similarity；
- Shape Retention；
- Detail Quality；
- Boundary Quality；
- Video Stability。

禁止仅根据总 Loss 下降判断效果。

---

## 13. 完成定义

Batch 3 只有同时满足以下条件才可完成：

```text
Minimal Loss Hook 已接入
+
Geometry Loss 可独立启停
+
Shape Anchor 可验证
+
保存恢复正确
+
关闭后保持基线
+
Windows GPU 固定条件 A/B 已执行
+
文档和 Handoff 已更新
```

Batch 7 的通用 Loss 不能用于替代 Batch 3 的完成条件。

---

## 总结

调整后的训练路线不是放弃身份外观和画质增强，而是先完成最关键、最容易被传统 Merge 抵消的身份几何闭环：

```text
Metadata / Sampling
+
Minimal Loss Hook
+
Identity Geometry
+
Source Shape Template
+
Shape-aware Merge
```

在这一闭环稳定后，再增加：

```text
Identity Appearance
+
Region
+
Boundary
+
Frequency
+
Full Curriculum
```

这样更容易建立可信的消融基线，也能更早验证增强版 DFL 的核心差异化价值。