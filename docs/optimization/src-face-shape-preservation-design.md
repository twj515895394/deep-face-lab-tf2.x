# src Face Shape Preservation Design

## 1. 文档定位

本文定义 DeepFaceLab TF2.x 增强路线中的 src 脸型保持目标、训练监督边界和实施顺序。

核心目标：

> 在不修改 SAEHD 主模型架构的第一版方案中，让结果尽可能保留 src 的身份几何，同时保持 dst 的姿态、表情、光照和视频运动。

本文不替代：

- 总实施顺序；
- 正式 Batch Ticket；
- Shape-aware Merge 工程施工文档；
- Windows GPU 验收记录。

若顺序冲突，以 `implementation/enhanced-dfl-master-implementation-plan.md` 为准。

---

## 2. 背景问题

DFL 长期存在典型现象：

- 五官像 source；
- 皮肤和纹理可以接近 source；
- 脸宽像 destination；
- 下颌、下巴和外轮廓像 destination。

原因不只在训练：

```text
训练监督不足
+
Merge 使用 dst landmarks / Affine / dst mask
=
最终脸型重新偏向 dst
```

因此：

```text
训练学习 src geometry
        ≠
最终视频保留 src geometry
```

必须分别完成训练侧和 Merge 侧，再进行联调。

---

## 3. Face Shape 定义

Identity Geometry 包含相对稳定的人脸结构：

- 脸宽；
- 下颌宽度与曲线；
- 下巴长度与形状；
- 颧骨比例；
- 额头比例；
- 眼距；
- 鼻宽与脸宽比例；
- 稳定五官相对位置。

这些不是普通纹理信息，也不能由单一 Reconstruction Loss 可靠表达。

Identity 的完整表达应理解为：

```text
Identity
=
Identity Appearance
+
Identity Geometry
```

本轮路线优先完成 Geometry 闭环，Appearance 和通用画质 Loss 后移到 Batch 7。

---

## 4. 优化目标与边界

目标关系：

```text
src Identity Geometry
+
dst Pose
+
dst Expression
+
dst Motion
```

需要保持：

- dst yaw / pitch / roll；
- dst 眼睛开合；
- dst 嘴型和表情；
- dst 光照和遮挡；
- dst 视频运动连续性。

不应追求：

- 把 src 某一张正脸的姿态强制复制到 dst；
- 把 src 静态嘴型覆盖 dst 表情；
- 通过过强 Warp 追求不自然的大形变；
- 仅靠 Mask 扩张假装完成脸型迁移。

---

## 5. 为什么不能把通用 Loss 全部放在前面

Region、Boundary、Frequency 和 Identity Appearance 有助于：

- 五官细节；
- 局部清晰度；
- 外观身份；
- 高频纹理；
- 训练输出边缘。

但它们不能直接回答：

- 模型是否学会 src 脸宽和下颌比例；
- Source Shape Template 是否可信；
- Merge 是否真正应用 src 几何；
- dst Mask 是否重新裁回原轮廓；
- 视频中脸型是否稳定。

因此新路线保留最小 Loss Hook，但把通用 Loss 后移：

```text
Batch 3：Minimal Loss Hook + Identity Geometry
Batch 4：Source Shape Template
Batch 5：Hybrid Landmark + Warp
Batch 6：Shape-aware Mask + Temporal
Batch 7：Appearance / Region / Boundary / Frequency
```

---

## 6. Batch 3：Shape Anchor

### 6.1 作用

Shape Anchor 是 src Identity Geometry 的稳定参考，不是任意单张图片。

### 6.2 候选条件

优先使用：

- Landmark 有效且置信度高；
- 接近正脸或可可靠 canonical normalize；
- 清晰度较高；
- 曝光正常；
- 遮挡少；
- 表情幅度较小；
- 与当前 src identity / faceset fingerprint 一致。

### 6.3 聚合建议

第一版采用可解释流程：

```text
候选筛选
  ↓
Canonical Normalize
  ↓
异常比例过滤
  ↓
Median / Trimmed Mean
  ↓
Canonical Landmarks + Ratio Vector
```

需要记录：

- 输入样本数；
- 有效样本数；
- 被过滤原因；
- 各比例分布；
- Anchor confidence；
- 生成版本和 fingerprint。

### 6.4 风险

- SRC 正脸数量过少；
- Anchor 被单一表情主导；
- Landmark 系统性偏差；
- Packed / Ordinary 身份映射不一致；
- 素材更新后仍使用旧 Anchor。

这些风险必须通过 confidence、fingerprint 和重建机制控制。

---

## 7. Batch 3：Landmark / Ratio Loss

### 7.1 基本思路

不直接比较未归一化的绝对像素 Landmark，而是比较 canonical 坐标和稳定比例。

推荐第一版：

```text
face_width / face_height
jaw_width / face_width
chin_length / face_height
cheek_width / face_width
eye_distance / face_width
nose_width / face_width
```

### 7.2 Geometry Loss 结构

示意：

```text
L_geometry
=
w_face × L_face_width
+
w_jaw × L_jaw
+
w_chin × L_chin
+
w_cheek × L_cheek
+
w_feature_ratio × L_feature_ratio
```

具体公式、权重和归一化方式必须在正式 Ticket 中冻结，并通过数值测试验证。

### 7.3 置信度处理

低置信度监督应：

- 跳过；或
- 按 confidence 降权；

不得静默按满权重进入 Loss。

### 7.4 非目标

第一版不要求：

- 复杂 3DMM；
- 大型几何编码器；
- 新 Backbone；
- Diffusion；
- Transformer；
- 训练内实时重建完整 3D Head。

当前主要问题是监督目标不足和 Merge 几何约束，不是模型容量不足。

---

## 8. Shape 与 Expression 分离

不能约束全部 Landmark 都接近 src。

### src 提供

- 脸宽；
- 下颌；
- 下巴；
- 颧骨；
- 眼距；
- 稳定五官比例。

### dst 提供

- yaw / pitch / roll；
- 眼睛开合；
- 嘴张开和嘴型；
- 眉毛变化；
- 表情偏移；
- 视频运动。

目标：

```text
src stable shape
+
dst dynamic expression
```

需要按 Landmark 区域和几何属性拆分职责，不能简单在两套完整 Landmark 之间线性插值后就认为完成。

---

## 9. Batch 3：最小 Geometry Curriculum

第一版只实现三个显式阶段。

### Stage A：Reconstruction

- Geometry 权重为 0；
- 建立稳定基础重建；
- 验证旧流程和保存恢复。

### Stage B：Geometry Ramp

- Geometry 权重逐步上升；
- 观察 Geometry 单项 Loss；
- 检查身份外观、表情和姿态是否明显受损。

### Stage C：Geometry Stable

- Geometry 权重保持稳定；
- 输出固定 Preview 和比例指标；
- 为 Shape Template 提供稳定数据。

状态必须写入可恢复配置或 checkpoint sidecar，恢复训练不得错误回到 Stage A。

完整 Appearance / Region / Boundary / Frequency Curriculum 属于 Batch 7。

---

## 10. Batch 4：Source Shape Template

训练几何需要转化为 Merge 可读取的标准资产。

建议产物：

```text
model.srcshape
```

包含：

- canonical landmarks；
- face width / jaw / cheek / chin ratios；
- Shape Anchor；
- quality / confidence；
- src identity 标识；
- faceset fingerprint；
- schema version；
- generator version。

原则：

- 不修改旧模型权重格式；
- 缺失时回退传统 Merge；
- 版本和身份不匹配时拒绝静默使用；
- 支持重新生成；
- 需要定义训练结果、离线聚合和用户指定 Template 的优先级。

---

## 11. Batch 5：Hybrid Landmark 与 Shape Warp

### 11.1 Hybrid Landmark

```text
Hybrid Landmark
=
src Identity Geometry
+ dst Pose
+ dst Expression Offset
```

需要：

- Landmark 分区；
- canonical → dst pose 映射；
- `source_shape_power`；
- 表情保持；
- 极端姿态和遮挡回退；
- 低置信度动态降权。

### 11.2 Piecewise Affine Warp

第一版优先 Piecewise Affine：

- 稳定；
- 可解释；
- OpenCV 支持成熟；
- 易于单元测试和可视化；
- 可以局部调整脸宽、下颌和下巴。

必须验证：

- 三角拓扑；
- 三角翻转；
- 空洞和越界；
- `source_shape_power = 0` 与传统几何等价；
- 失败时回退传统 Merge。

---

## 12. Batch 6：Shape-aware Mask

Shape Warp 后，传统 dst Mask 可能再次把结果裁回 dst 轮廓。

新的 Mask 原则：

- 中心身份区域优先 src；
- 脸颊、下巴和外轮廓采用软过渡；
- 遮挡区域保持 dst；
- 低置信度时降低 Shape 强度；
- 传统 Mask 始终可切换。

不建议只使用：

```text
predicted_mask * dst_mask
```

作为唯一规则。

需要处理：

- 头发；
- 手；
- 麦克风；
- 眼镜；
- 极端侧脸；
- Landmark 异常；
- Warp 质量异常。

---

## 13. Batch 6：Temporal Stabilization

逐帧 Shape 增强会放大 Landmark 和 Mask 的微小波动。

需要平滑：

- Hybrid Landmark；
- Warp 参数；
- Mask contour；
- `source_shape_power`；
- confidence gate。

第一版建议：

- EMA；
- One Euro Filter；
- Scene Cut Reset；
- Tracking Lost Reset。

避免：

- 脸宽跳动；
- 下巴抖动；
- 外轮廓呼吸感；
- Mask 边缘闪烁；
- 场景切换后沿用旧状态。

单帧 Merge 不强制启用 Temporal。

---

## 14. Batch 7：后续通用 Loss

脸型闭环稳定后，再增加：

- Identity Appearance Loss；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- 完整 Multi-objective Curriculum。

这些 Loss 必须以稳定 Geometry / Shape Merge 作为固定基线，逐项消融。

特别注意：

- Boundary Loss 改善训练输出边缘；
- Shape-aware Mask 决定 Merge 时轮廓如何保留和过渡；
- 两者有关联，但不能互相替代。

---

## 15. 推荐消融实验

### A：Baseline

传统训练 + 传统 Merge。

### B：Sampling

Batch 2 Metadata Sampling。

### C：Geometry Training

Minimal Loss Hook + Shape Anchor + Ratio Loss。

### D：Geometry Bridge

C + Source Shape Template。

### E：Shape Merge

D + Hybrid Landmark + Piecewise Warp。

### F：Mask / Temporal

E + Shape-aware Mask + Temporal。

### G：Appearance / Quality Loss

F 基线上逐项增加 Identity Appearance、Region、Boundary、Frequency。

比较：

- Identity Similarity；
- Shape Retention；
- Expression / Pose 保持；
- Boundary；
- Occlusion；
- Video Stability；
- 性能和显存。

---

## 16. 完成标准

脸型保持不能只凭单帧主观感受完成签发。

必须至少具备：

```text
训练 Geometry 可独立启停
+
Shape Anchor 和 Ratio 可验证
+
Source Shape Template 可校验
+
Hybrid Landmark / Warp 可回退
+
Mask / Temporal 可切换
+
固定条件人工 A/B
+
旧模型和旧 Merge 兼容
```

---

## 结论

Face Shape Preservation 是增强版 DFL 从普通五官替换走向高保真身份迁移的核心方向。

调整后的优先级是：

```text
先完成 Geometry 训练和 Merge 闭环
再叠加通用外观与画质 Loss
```

这样既保留 Loss Hook 的必要技术依赖，又能更早验证项目最关键的差异化价值。