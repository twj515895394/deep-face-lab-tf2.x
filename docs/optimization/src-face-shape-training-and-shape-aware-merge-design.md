# Source Face Shape Training and Shape-aware Merge Design

## 1. 文档定位

本文定义 DeepFaceLab TF2.x 增强路线中的核心闭环：

> Source Identity Appearance + Source Identity Geometry + Destination Pose / Expression / Motion。

目标是在不修改 SAEHD / DF / LIAE 主模型架构的第一版方案中，使训练学习到的 src 几何能够通过标准 Geometry Bridge 进入 Merge，并在视频中稳定保留。

本文负责训练与 Merge 的联合算法边界，不替代：

- 总实施计划；
- 正式 Batch Ticket；
- 具体文件和函数施工文档；
- Windows GPU 环境验收记录。

路线调整：

```text
先完成 Minimal Loss Hook + Identity Geometry
再完成 Shape Template / Hybrid Landmark / Warp / Mask / Temporal
最后叠加 Identity Appearance / Region / Boundary / Frequency
```

---

## 2. 核心问题

当前 DFL 常见现象：

- 五官可以较好迁移到 src；
- 皮肤和纹理可以接近 src；
- 脸宽、下颌、下巴和外轮廓仍明显接近 dst。

该问题由 Training 和 Merge 共同造成：

```text
训练侧：缺少明确的 Identity Geometry 监督
Merge 侧：dst landmarks + 单一 Affine + dst mask 主导最终几何
```

因此：

```text
训练 Loss 改善
    ≠
最终视频自动保留 src 脸型
```

必须建立端到端几何链路。

---

## 3. Identity 定义

### 3.1 Identity Appearance

包括：

- 五官细节；
- 肤质；
- 颜色；
- 局部纹理；
- 眉毛、眼睛、鼻子和嘴的外观特征。

### 3.2 Identity Geometry

包括：

- 脸宽；
- 下颌；
- 下巴长度；
- 颧骨比例；
- 眼距；
- 鼻宽与脸宽比例；
- 稳定五官相对位置。

完整身份：

```text
Identity = Appearance + Geometry
```

本轮路线优先 Geometry 闭环。Appearance 和通用画质 Loss 在闭环完成后进入 Batch 7。

---

## 4. src / dst 职责

### Source 提供

- Identity Appearance；
- 脸宽；
- 下颌和下巴；
- 颧骨；
- 稳定五官比例；
- Source Shape Template。

### Destination 提供

- yaw / pitch / roll；
- 眼睛开合；
- 嘴部运动；
- 眉毛和表情；
- 光照；
- 遮挡；
- 视频运动状态。

目标：

```text
src stable identity geometry
+
dst dynamic pose and expression
```

禁止简单使用 src 完整 Landmark 替换 dst 完整 Landmark。

---

## 5. 总体 Pipeline

```text
SRC / DST Dataset
        ↓
Metadata / Smart Sampling
        ↓
Minimal Loss Hook
        ↓
Identity Geometry Training
        ↓
Source Shape Template
        ↓
Prediction
        ↓
Hybrid Landmark Engine
        ↓
Piecewise Affine Warp
        ↓
Shape-aware Soft Mask
        ↓
Color / Blend
        ↓
Temporal Stabilization
        ↓
Final Video
```

Batch 7 的 Appearance / Region / Boundary / Frequency Loss 可以改善训练输出，但不是上面 Geometry Pipeline 的前置依赖。

---

## 6. Batch 3：训练侧 Geometry MVP

### 6.1 Minimal Loss Hook

必须提供：

- 独立开关和权重；
- 单项 Loss 日志；
- shape / dtype / mask 契约；
- NaN / Inf 检查；
- 保存恢复兼容；
- 关闭后保持基线。

本阶段只为 Geometry 提供必要基础，不批量引入通用 Loss。

### 6.2 Shape Anchor

生成流程：

```text
SRC faceset
  ↓
可信 Landmark / 质量 / 遮挡筛选
  ↓
Canonical Normalize
  ↓
异常比例过滤
  ↓
Median / Trimmed Mean 聚合
  ↓
Shape Anchor
```

需要输出：

- canonical landmarks；
- ratio vector；
- confidence；
- sample count；
- identity / faceset fingerprint；
- generator version。

### 6.3 Landmark / Ratio Loss

第一版优先约束：

```text
face_width / face_height
jaw_width / face_width
chin_length / face_height
cheek_width / face_width
eye_distance / face_width
nose_width / face_width
```

Geometry Loss 不应直接约束 dst 的动态眼睛和嘴部状态接近 src Anchor。

### 6.4 Minimal Curriculum

```text
A：Reconstruction
B：Geometry Ramp
C：Geometry Stable
```

阶段必须可追踪、可保存和可恢复。

---

## 7. Batch 4：Source Shape Template

### 7.1 作用

Source Shape Template 是训练侧和 Merge 侧之间的权威几何契约。

建议产物：

```text
model_name.srcshape
```

或等价独立 sidecar。

### 7.2 建议内容

```text
schema_version
generator_version
source_identity
faceset_fingerprint
canonical_landmarks
face_width_ratio
jaw_ratio
cheek_ratio
chin_ratio
eye_distance_ratio
nose_width_ratio
quality
confidence
sample_summary
```

### 7.3 生命周期

必须支持：

- 生成；
- 保存；
- 原子写入；
- 加载；
- Schema 校验；
- Identity / Faceset 校验；
- 重建；
- 缺失和异常回退。

### 7.4 优先级规则

需要在正式 Ticket 中冻结：

```text
用户显式指定 Template
训练生成 Template
离线 faceset 生成 Template
自动发现 Template
```

不得在多个来源冲突时静默选择。

### 7.5 兼容原则

- 不修改旧模型权重格式；
- 旧模型没有 Template 时继续传统 Merge；
- Template 不匹配时拒绝 Shape Merge，但不阻止传统 Merge；
- 第一版允许完全离线生成。

---

## 8. Batch 5：Hybrid Landmark Engine

### 8.1 核心表达

```text
Hybrid Landmark
=
src Identity Geometry
+ dst Pose Transform
+ dst Expression Offset
```

### 8.2 Landmark 分区

建议至少区分：

- 外轮廓 / Jaw；
- Cheek / Chin；
- Eyes；
- Brows；
- Nose；
- Mouth；
- Stable feature ratios；
- Dynamic expression regions。

### 8.3 `source_shape_power`

语义：

```text
0：传统 dst 几何
中间值：src Identity Geometry 与 dst 动态几何融合
高值：更强 src 脸型迁移实验
```

硬契约：

```text
source_shape_power = 0
≈
传统 Merge 几何路径
```

### 8.4 Confidence Gate

以下情况应自动降低 Geometry 强度或回退：

- Template confidence 低；
- 当前帧 Landmark confidence 低；
- 极端 yaw / pitch；
- 严重遮挡；
- Landmark 拓扑异常；
- 当前帧与 Template 的比例差异超出安全阈值。

---

## 9. Batch 5：Piecewise Affine Warp

### 9.1 为什么不只使用 Affine

单一 Affine 只能表达：

- 平移；
- 缩放；
- 旋转。

不能可靠表达：

- 下颌变化；
- 脸宽比例；
- 下巴长度；
- 局部轮廓变化。

### 9.2 第一版方案

```text
predicted face
  ↓
source / hybrid landmark mesh
  ↓
triangle topology
  ↓
local affine warp
  ↓
shape-adapted prediction
```

采用 Piecewise Affine 的原因：

- OpenCV 支持成熟；
- 不修改模型结构；
- 局部可控；
- 容易可视化和测试；
- 失败时容易回退。

### 9.3 安全检查

- Landmark 数量和顺序；
- 坐标有限；
- 三角拓扑固定；
- 三角面积下限；
- 翻转检测；
- 越界裁剪；
- 空洞检测；
- Warp 强度上限；
- 回退原因日志。

第一版不优先 TPS 或网络化 Warp。

---

## 10. Batch 6：Shape-aware Soft Mask

### 10.1 当前问题

传统 Mask 大量情况下接近：

```text
src prediction ∩ dst face region
```

这会把已经 Warp 的 src 轮廓重新裁回 dst。

### 10.2 新 Mask 原则

- 中心身份区域优先 src；
- Jaw / Cheek / Chin 使用软过渡；
- 遮挡区域保持 dst；
- 不把 `predicted_mask * dst_mask` 作为唯一规则；
- Mask 需要理解 Warp 后的轮廓；
- 传统 Mask 始终可选。

建议模式：

```text
off
source_contour
hybrid
```

第一版推荐 `hybrid`，但默认仍保持 `off`。

### 10.3 遮挡处理

需要处理：

- 头发；
- 手；
- 眼镜；
- 麦克风；
- 面部配饰；
- 大角度侧脸；
- Landmark 失败；
- XSeg / predicted mask 冲突。

遮挡置信度不足时应降低 Shape 强度或回退传统路径。

---

## 11. Batch 6：Temporal Stabilization

视频需要平滑：

- Hybrid Landmarks；
- Warp 参数；
- Mask contour；
- `source_shape_power`；
- Confidence Gate。

第一版：

- EMA；
- One Euro Filter；
- Scene Cut Reset；
- Tracking Lost Reset；
- 参数突变保护。

避免：

- 脸宽跳动；
- 下巴闪烁；
- 外轮廓呼吸；
- Mask Flicker；
- 场景切换状态污染。

单帧模式不强制启用 Temporal。

---

## 12. Batch 7：身份外观与画质增强

在 Geometry Pipeline 稳定后，再加入：

- Identity Appearance Loss；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- 完整 Multi-objective Curriculum。

这些模块的目的：

- 提高五官和纹理身份；
- 改善局部区域；
- 改善训练输出边缘；
- 增强高频细节。

它们不能替代：

- Source Shape Template；
- Hybrid Landmark；
- Warp；
- Shape-aware Mask；
- Temporal。

Batch 7 必须在 Batch 6 的稳定基线上逐项消融，避免同时启用造成归因失败。

---

## 13. 参数边界

示例结构仅用于表达职责，字段名以正式 Ticket 为准：

```yaml
training:
  identity_geometry:
    enabled: false
    weight: 0.0
    anchor_path: null

shape_template:
  enabled: false
  path: null
  rebuild: false

shape_merge:
  enabled: false
  source_shape_power: 0
  warp_mode: piecewise_affine
  mask_mode: off
  temporal_smoothing: false
```

默认行为：

```text
identity_geometry.enabled = false
shape_template.enabled = false
shape_merge.enabled = false
source_shape_power = 0
mask_mode = off
temporal_smoothing = false
```

GUI 只应传用户实际启用或修改的参数，底层默认值由 DFL 统一管理。

---

## 14. 工程实施路线

### Phase 1 / Batch 3

- Minimal Loss Hook；
- Shape Anchor；
- Landmark / Ratio Loss；
- Geometry Curriculum；
- Geometry GPU A/B。

### Phase 2 / Batch 4

- Source Shape Template；
- Schema / Fingerprint；
- Lifecycle 和 Fallback。

### Phase 3 / Batch 5

- Hybrid Landmark；
- `source_shape_power`；
- Piecewise Affine Warp；
- Confidence Gate。

### Phase 4 / Batch 6

- Shape-aware Soft Mask；
- Occlusion Fallback；
- Temporal Stabilization。

### Phase 5 / Batch 7

- Identity Appearance；
- Region；
- Boundary；
- Frequency；
- Full Curriculum。

### Phase 6 / Batch 8

- A/B；
- 参数默认值；
- 性能、兼容和文档；
- GUI 接入。

---

## 15. 验收指标

### 训练侧

- Geometry 单项 Loss；
- Shape Ratio Error；
- Anchor confidence；
- Identity Similarity；
- dst Pose / Expression 保持；
- 保存恢复；
- 性能和显存。

### Geometry Bridge

- Template Schema / Identity / Fingerprint；
- Template 重建等价性；
- 缺失和损坏回退。

### Merge 侧

- Shape Retention Ratio；
- Landmark topology；
- Warp invalid rate；
- Boundary Quality；
- Occlusion handling；
- Temporal Stability；
- `source_shape_power = 0` 基线等价性。

### 人工验收

- src 身份；
- src 脸型；
- dst 表情和姿态；
- 拉伸、错位、空洞；
- 边缘；
- 遮挡；
- 视频闪烁。

---

## 16. 消融矩阵

```text
A：Baseline
B：A + Batch 2 Sampling
C：B + Geometry Training
D：C + Shape Template
E：D + Hybrid Landmark / Warp
F：E + Shape Mask
G：F + Temporal
H：G + Appearance Loss
I：H + Region / Boundary / Frequency（逐项）
```

禁止直接从 A 跳到 I 后只比较最终效果，否则无法判断各模块收益和副作用。

---

## 17. 最终目标

```text
Source
  ├── Identity Appearance
  └── Identity Geometry

Destination
  ├── Pose
  ├── Expression
  ├── Lighting
  ├── Occlusion
  └── Motion

Geometry-aware Training and Merge
  ↓
Natural Face Replacement
```

目标不是简单换五官，而是：

> src 的身份和稳定脸型 + dst 的姿态、表情和运动表现。

同时保持：

- 原模型兼容；
- 原训练流程可用；
- 原 Merge 可回退；
- 新模块可独立启停；
- 失败原因可定位。