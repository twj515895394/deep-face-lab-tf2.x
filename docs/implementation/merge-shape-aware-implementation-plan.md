# DeepFaceLab TF2.x Shape-aware Merge Implementation Plan

## 1. 文档目标

本文将 Shape-aware Merge 拆解为可实施、可验证、可回退的工程计划。

目标：

- 保留原始 DeepFaceLab TF2.x Merge 流程；
- 让 src Identity Geometry 能进入最终回贴；
- 融合 src 脸型与 dst 姿态、表情和遮挡；
- 支持逐模块启用、失败回退和日志定位；
- 为后续 GUI 提供稳定配置接口。

核心原则：

> 不替换原 Merge，而是在原 Pipeline 中增加可控 Geometry Layer。

路线边界：

- Batch 3 负责 Minimal Loss Hook + Identity Geometry；
- Batch 4 负责 Source Shape Template；
- Batch 5 负责 Hybrid Landmark + Piecewise Affine Warp；
- Batch 6 负责 Shape-aware Mask + Temporal；
- Batch 7 的 Appearance / Region / Boundary / Frequency Loss 不是 Shape-aware Merge 的前置依赖。

---

## 2. 当前问题

传统流程：

```text
Frame
  ↓
dst Landmarks
  ↓
Affine Transform
  ↓
Prediction
  ↓
dst / predicted Mask
  ↓
Blend
```

主要限制：

- dst landmarks 决定基础空间结构；
- 单一 Affine 不能表达局部脸型变化；
- dst mask 容易把 Warp 后轮廓重新裁回 dst；
- 逐帧 Landmark 和 Mask 波动会放大为脸型抖动。

因此需要：

```text
Source Shape Template
+
Hybrid Landmark
+
Piecewise Affine Warp
+
Shape-aware Soft Mask
+
Temporal Stabilization
```

---

## 3. 新 Merge Pipeline

```text
Frame / dst Landmarks
        ↓
Prediction
        ↓
Load and Validate Source Shape Template
        ↓
Hybrid Landmark Engine
        ↓
Piecewise Affine Warp
        ↓
Shape-aware Soft Mask
        ↓
Color Adaptation / Blend
        ↓
Temporal State Update
        ↓
Output
```

失败路径：

```text
Template 缺失 / 不匹配
Hybrid Landmark 无效
Warp 拓扑异常
Mask 置信度不足
Temporal 状态异常
        ↓
记录明确原因
        ↓
回退传统 Merge 或降低 Shape 强度
```

核心 Merge 错误不得被错误吞掉；只有明确分类的可选 Shape 增强问题允许回退。

---

## 4. Batch 4：Source Shape Template

### 4.1 模块建议

```text
core/shape/source_shape_template.py
```

### 4.2 职责

- 保存 src Identity Geometry；
- 提供 canonical landmarks；
- 保存稳定比例和 Shape Anchor；
- 校验 identity / faceset；
- 为 Hybrid Landmark 提供只读输入。

### 4.3 建议 Schema

```json
{
  "schema_version": 1,
  "generator_version": "...",
  "source_identity": "...",
  "faceset_fingerprint": "...",
  "canonical_landmarks": [],
  "ratios": {
    "face_width": 0.0,
    "jaw": 0.0,
    "cheek": 0.0,
    "chin": 0.0,
    "eye_distance": 0.0,
    "nose_width": 0.0
  },
  "confidence": 0.0,
  "sample_summary": {}
}
```

字段名和版本以正式 Ticket 为准。

### 4.4 生命周期

必须支持：

- 生成；
- 原子保存；
- 加载；
- Schema 校验；
- 数值有限性校验；
- Landmark 数量和顺序校验；
- Identity / Faceset 校验；
- 重建；
- 明确 Fallback。

### 4.5 回退规则

Template 以下情况不得进入 Shape Merge：

- 文件不存在；
- JSON 损坏；
- Schema 不支持；
- Identity 不匹配；
- Faceset Fingerprint 不匹配；
- Landmark 数量错误；
- 比例或坐标非有限；
- Confidence 低于阈值。

默认行为是回退传统 Merge，而不是阻止所有 Merge。

---

## 5. Batch 5：Hybrid Landmark Engine

### 5.1 模块建议

```text
core/shape/hybrid_landmark.py
```

### 5.2 输入

- Source Shape Template；
- 当前帧 dst landmarks；
- 当前帧 pose / expression 信息；
- Template confidence；
- 当前帧 landmark / occlusion confidence；
- `source_shape_power`；
- 安全阈值。

### 5.3 输出

建议返回结构化结果：

```text
hybrid_landmarks
requested_shape_power
effective_shape_power
confidence
fallback_reason
warnings
```

不得只返回坐标，导致调用方无法判断是否发生降级。

### 5.4 职责分离

```text
src：face width / jaw / cheek / chin / stable ratios
dst：pose / eyes / mouth / brows / expression / motion
```

### 5.5 `source_shape_power`

约束：

- `0` 等价传统 dst 几何；
- 有明确上限；
- 低置信度时动态降低；
- 不允许因为参数过高生成明显越界几何；
- requested 与 effective 必须分别记录。

### 5.6 极端情况

以下情况应降低强度或回退：

- 大 yaw / pitch；
- 遮挡；
- Landmark 跟踪失败；
- Template 与当前脸型差异过大；
- 表情 Offset 超出安全范围；
- 坐标和拓扑异常。

---

## 6. Batch 5：Piecewise Affine Warp

### 6.1 模块建议

```text
core/shape/shape_warp.py
```

### 6.2 第一版算法

```text
Piecewise Affine Warp
```

第一版不优先：

- TPS 大形变；
- 神经网络 Warp；
- 光流网络；
- 额外 3D 渲染链路。

### 6.3 原因

- 稳定；
- 可解释；
- 易测试；
- OpenCV 支持成熟；
- 可局部控制；
- 失败容易回退。

### 6.4 安全检查

必须检查：

- Landmark 数量和顺序；
- 坐标有限；
- 固定三角拓扑；
- 三角面积下限；
- Triangle Flip；
- 目标坐标越界；
- 输出空洞；
- 插值和边界模式；
- Warp 强度；
- 处理耗时。

### 6.5 输出

```text
warped_face
warped_mask
warp_valid
triangle_stats
fallback_reason
```

Warp 失败时不得输出半有效结果继续 Blend。

---

## 7. Batch 6：Shape-aware Soft Mask

### 7.1 模块建议

```text
core/merge/shape_mask.py
```

### 7.2 目标

防止经过 Shape Warp 的结果再次被 dst mask 裁回原轮廓。

### 7.3 原则

- 中心身份区域优先 src；
- Jaw / Cheek / Chin 使用软过渡；
- 遮挡区域优先 dst；
- Mask 跟随 Warp 后轮廓；
- 不把 `predicted_mask * dst_mask` 作为唯一规则；
- 传统 Mask 可随时切换。

### 7.4 模式建议

```text
off
source_contour
hybrid
```

默认：

```text
off
```

### 7.5 遮挡处理

需要融合：

- dst / predicted mask；
- XSeg（若存在）；
- occlusion confidence；
- Warp 后 contour；
- 当前帧 Landmark confidence。

需重点验证：

- 头发；
- 手；
- 眼镜；
- 麦克风；
- 面部配饰；
- 极端侧脸；
- 下巴和脸颊边缘。

---

## 8. Batch 6：Temporal Stabilization

### 8.1 模块建议

```text
core/temporal/stabilizer.py
```

### 8.2 平滑对象

- Hybrid landmarks；
- Effective shape power；
- Warp 参数；
- Mask contour；
- Confidence gate。

### 8.3 第一版算法

优先：

- EMA；
- One Euro Filter；
- 参数突变限制。

不优先复杂 Optical Flow Network。

### 8.4 Reset

必须支持：

- Scene Cut Reset；
- Tracking Lost Reset；
- Identity Change Reset；
- Frame Index 跳变 Reset；
- 分辨率变化 Reset；
- 用户手动 Reset。

### 8.5 单帧行为

单帧 Merge：

- 不强制启用 Temporal；
- 不依赖前一帧；
- 输出应可重复；
- Temporal 关闭时不保留隐式状态。

---

## 9. 与 Batch 7 Loss 的关系

Batch 7 将增加：

- Identity Appearance Loss；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- 完整 Curriculum。

这些能力可以改善预测脸，但不是 Shape-aware Merge 的依赖。

职责边界：

```text
Geometry Loss：训练模型学习 src 稳定几何
Boundary Loss：改善训练输出轮廓
Source Shape Template：保存权威 src 几何
Hybrid Landmark / Warp：在 Merge 中应用几何
Shape-aware Mask：保留并软化最终轮廓
Temporal：保持视频连续性
```

不得使用 Boundary Loss 替代 Shape-aware Mask，也不得使用 Identity Appearance Loss 替代 Source Shape Template。

---

## 10. 配置设计

示例结构：

```yaml
shape_template:
  enabled: false
  path: null
  rebuild: false

shape_merge:
  enabled: false
  source_shape_power: 0
  warp_mode: piecewise_affine
  mask_mode: off

runtime:
  shape_fallback_on_optional_error: true
  shape_strict_validation: false
  temporal_smoothing: false
```

原则：

- DFL 是默认值唯一来源；
- GUI 只传用户实际启用或修改的字段；
- Feature Flag 默认关闭；
- 未知字段不得意外启用；
- Strict 与 Fallback 的语义必须在正式 Ticket 中冻结；
- `source_shape_power = 0` 必须保持传统路径。

---

## 11. 日志与可观测性

每帧不应输出大量普通日志，但必须提供周期统计和异常明细。

建议记录：

```text
shape template status
requested / effective shape power
hybrid landmark confidence
warp valid / invalid count
triangle flip / degenerate count
mask mode
occlusion fallback count
temporal reset count
fallback reason distribution
processing latency
```

最终验收需要可以定位：

- 是 Template 问题；
- 是当前帧 Landmark 问题；
- 是 Warp 问题；
- 是 Mask 问题；
- 还是 Temporal 状态问题。

---

## 12. 实施阶段

### Phase 1 / Batch 4

- Source Shape Template Schema；
- 生成、保存、加载、校验；
- Identity / Faceset Fingerprint；
- Fallback。

### Phase 2 / Batch 5A

- Hybrid Landmark；
- Source Shape Power；
- Confidence Gate；
- 传统几何等价测试。

### Phase 3 / Batch 5B

- Piecewise Affine Warp；
- 拓扑安全检查；
- Warp Fallback；
- 性能测试。

### Phase 4 / Batch 6A

- Shape-aware Soft Mask；
- Occlusion Fallback；
- Mask A/B。

### Phase 5 / Batch 6B

- Temporal Stabilization；
- Scene Cut / Tracking Reset；
- 视频 A/B。

### Phase 6 / Batch 8

- GUI 参数；
- 推荐预设；
- 兼容说明；
- 文档和验收收口。

---

## 13. 验证矩阵

### Template

- Ordinary / Packed SRC；
- Unicode 路径；
- Schema 不支持；
- Identity / Fingerprint 不匹配；
- 原子写入；
- 重建。

### Hybrid Landmark

- `source_shape_power = 0`；
- 正脸；
- 轻侧脸；
- 大侧脸；
- 眼睛和嘴部表情；
- 低置信度；
- 遮挡。

### Warp

- 三角拓扑；
- Flip / Degenerate；
- 越界；
- 空洞；
- 不同分辨率；
- 性能和内存。

### Mask

- 下巴；
- 脸颊；
- 头发；
- 手；
- 眼镜；
- XSeg；
- 传统 Mask 回退。

### Temporal

- 静态；
- 连续转头；
- 快速运动；
- Scene Cut；
- Tracking Lost；
- 单帧模式。

---

## 14. 完成定义

任一 Shape-aware Merge Ticket 只有满足以下条件才可完成：

```text
代码接入主链路
+
默认关闭
+
传统路径可回退
+
自动测试
+
真实视频或环境 A/B
+
日志可定位
+
文档更新
```

视觉效果由人工验收。Agent 不得仅凭代码存在或单帧截图宣称脸型效果已经完成。

---

## 15. 后续方向

完成 Batch 4—6 后，可以研究：

- 更强 Identity Geometry Representation；
- 自动 Shape Strength 调节；
- 视频人脸几何跟踪；
- Optical Flow Consistency；
- TPS 或 3D Warp 实验；
- 服务化 Pipeline。

这些方向不得提前进入第一版默认方案。