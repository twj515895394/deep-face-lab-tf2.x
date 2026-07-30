# DeepFaceLab TF2.x Code Modification Map

## 1. 文档目标

本文将增强路线映射到具体工程模块，指导后续 Batch 3—8 的文件、Hook 和主链路接入。

目标：

- 保持 SAEHD / DF / LIAE 模型和旧 checkpoint 兼容；
- 增量增加训练几何与 Shape-aware Merge；
- 避免在核心文件中堆积算法代码；
- 所有新能力可关闭、可回退、可观测；
- 先完成脸型闭环，再加入通用画质 Loss。

本文不定义最终字段名和公式；正式实现以对应 Batch Ticket 为准。

---

## 2. 总体改造原则

### 不直接替换

- 原模型结构；
- 原 checkpoint 权重布局；
- DFM 导出格式；
- 原训练入口；
- 原 SampleGenerator 张量接口；
- 原默认 Merge 行为。

### 使用稳定 Hook

```text
Training Loss Hook
Sampling Hook
Shape Template Provider
Hybrid Geometry Hook
Warp Hook
Mask Hook
Temporal Hook
Evaluation / Logging Hook
```

核心主文件只负责：

- 构建上下文；
- 调用 Hook；
- 汇总结果；
- 保持现有保存、退出、恢复和错误传播语义。

---

## 3. 当前已完成基础

Batch 1 / Batch 2 已提供：

- Enhancement Config / Feature Flag；
- options-json 配置入口；
- Faceset Analyzer；
- Metadata Loader；
- SRC / DST SamplingConfig；
- Sampling Runtime；
- WeightedIndexHost；
- Trainer Control / Loss Window；
- Fallback 和核心错误传播。

Batch 3 之后应复用这些基础，不建立第二套配置或采样框架。

---

## 4. Batch 3：Minimal Loss Hook

### 4.1 建议模块

```text
core/training/losses/
├── base.py
├── registry.py
├── result.py
├── geometry.py
└── validation.py
```

实际目录可根据现有项目结构调整，但职责必须分离。

### 4.2 SAEHD 接入点

主要位置：

```text
models/Model_SAEHD/Model.py
```

主文件只应：

1. 准备 predicted / target / mask / landmark context；
2. 调用 Loss Hook；
3. 将 `total_addition` 合并到现有总 Loss；
4. 保存单项日志；
5. 保持现有梯度和 Trainer Control 语义。

不建议把 Geometry 公式、Anchor 聚合和 Ratio 计算全部直接写进 `Model.py`。

### 4.3 Loss Result

建议统一返回：

```text
raw_values
weighted_values
total_addition
metrics
warnings
valid
```

### 4.4 数值保护

需要集中处理：

- dtype 对齐；
- shape 检查；
- mask 非空和范围；
- 有限值；
- reduction 维度；
- Geometry confidence；
- 非有限 Loss 的失败或跳过策略。

不得在 Hook 内吞掉 MemoryError、TensorFlow、Optimizer 或未分类编程错误。

---

## 5. Batch 3：Shape Anchor 与 Identity Geometry

### 5.1 建议模块

```text
core/shape/
├── shape_anchor.py
├── geometry_features.py
└── geometry_metrics.py
```

### 5.2 职责

`shape_anchor.py`：

- 选择可信 src 样本；
- canonical normalize；
- 异常比例过滤；
- median / trimmed mean 聚合；
- confidence 和 fingerprint。

`geometry_features.py`：

- face width；
- jaw；
- cheek；
- chin；
- eye distance；
- nose width；
- 归一化比例向量。

`geometry_metrics.py`：

- 训练和验收共用的 Ratio Error；
- Shape Retention 中间指标；
- 数值和维度校验。

### 5.3 数据来源

可复用 Batch 2 Metadata：

- quality；
- pose；
- sample identity / signature；
- faceset fingerprint。

后续新增 Landmark confidence / occlusion 时，应扩展 Schema 或建立 Geometry Sidecar，不能偷偷改变 Batch 2 v1 字段语义。

---

## 6. Batch 3：Curriculum

### 建议模块

```text
core/training/curriculum/
├── state.py
└── geometry_schedule.py
```

职责：

- Reconstruction / Geometry Ramp / Geometry Stable；
- 按 iteration 或手动切换；
- 状态持久化；
- 恢复训练；
- 日志和阶段变更原因。

Batch 3 不实现完整 Appearance / Region / Boundary / Frequency Curriculum，只预留扩展接口。

---

## 7. Batch 4：Source Shape Template

### 建议模块

```text
core/shape/source_shape_template.py
```

职责：

- Template Schema；
- src faceset 分析和 Anchor 聚合；
- canonical shape；
- ratios；
- identity / faceset fingerprint；
- 原子保存；
- 加载、校验和重建；
- Fallback reason。

输出建议：

```text
model.srcshape
```

或等价独立 Sidecar。

不得修改原模型权重文件格式来强制保存 Template。

---

## 8. Predictor 与 Geometry 数据

第一版不改变模型输出签名。

现有 Predictor 继续输出：

```text
predicted_face
predicted_mask
```

Geometry 数据优先来自：

- Source Shape Template；
- 当前帧 dst landmarks；
- 当前帧 pose / expression；
- Warp / Mask Runtime。

若未来需要 predicted landmarks，应通过独立后处理模块或可选输出接入，不能直接破坏 DFM 或旧 Predictor 接口。

---

## 9. Batch 5：Hybrid Landmark

### 建议模块

```text
core/shape/hybrid_landmark.py
```

输入：

```text
source_shape_template
dst_landmarks
pose / expression
requested_shape_power
confidence / occlusion
```

输出：

```text
hybrid_landmarks
requested_shape_power
effective_shape_power
confidence
fallback_reason
warnings
```

必须保证：

```text
source_shape_power = 0
≈
传统 dst 几何
```

---

## 10. Batch 5：Shape Warp

### 建议模块

```text
core/shape/shape_warp.py
```

第一版：

```text
Piecewise Affine Warp
```

职责：

- 固定 Landmark 三角拓扑；
- Triangle Area / Flip 检查；
- 局部 Affine；
- 越界和空洞检测；
- 输出 Warp Stats；
- 失败回退。

输出：

```text
warped_face
warped_mask
warp_valid
triangle_stats
fallback_reason
```

---

## 11. Batch 6：Shape-aware Mask

### 建议模块

```text
core/merge/
├── shape_merge.py
└── shape_mask.py
```

`shape_merge.py`：

- 编排 Template、Hybrid Landmark、Warp、Mask、Temporal；
- 不重复实现各算法；
- 汇总 requested / effective / fallback 状态。

`shape_mask.py`：

- Source contour；
- Hybrid soft mask；
- Boundary transition；
- Occlusion preservation；
- 传统 Mask 回退。

Shape-aware Mask 不得依赖 Batch 7 Boundary Loss 才能工作。

---

## 12. Batch 6：Temporal

### 建议模块

```text
core/temporal/stabilizer.py
```

处理：

- Hybrid Landmark jitter；
- Effective shape power jitter；
- Warp parameter jitter；
- Mask contour flicker；
- Scene Cut / Tracking Lost Reset。

第一版：EMA / One Euro Filter。

单帧模式不建立隐式跨帧状态。

---

## 13. Batch 7：通用训练 Loss

### 建议模块

```text
core/training/losses/
├── identity_appearance.py
├── region.py
├── boundary.py
└── frequency.py
```

职责：

- Identity Appearance；
- Region Aware；
- Boundary；
- Frequency / Detail；
- 完整 Multi-objective Curriculum。

这些模块复用 Batch 3 Registry / Result / Validation，不建立第二套 Loss Hook。

职责边界：

```text
Geometry Loss：训练 src 几何
Boundary Loss：改善预测边缘
Shape Mask：Merge 保留和过渡轮廓
```

不得互相替代。

---

## 14. 配置映射

现有权威入口继续使用：

```text
options-json.enhancements
```

后续建议在现有层级扩展：

```text
enhancements.training.losses
enhancements.training.identity_geometry
enhancements.training.curriculum
enhancements.merge.source_shape_template
enhancements.merge.shape_warp
enhancements.merge.shape_mask
enhancements.merge.temporal_stabilization
enhancements.runtime
```

最终字段名以对应 Batch Schema Ticket 为准。

要求：

- DFL 是默认值唯一来源；
- GUI 只传用户改动字段；
- 未实现字段不能提前进入公开 GUI；
- 未知字段不得意外启用；
- 新 Schema 必须有版本和兼容策略。

---

## 15. 日志与状态

建议统一结构：

```text
requested
effective
status
confidence
fallback_reason
warnings
metrics
```

训练日志：

- 单项 Loss；
- Geometry ratios；
- Curriculum stage；
- Anchor / Template status。

Merge 日志：

- requested / effective shape power；
- Warp valid；
- Mask mode；
- Temporal reset；
- Fallback distribution。

---

## 16. 更新后的开发阶段

### Phase 1：Batch 3

- Minimal Loss Hook；
- Shape Anchor；
- Landmark / Ratio Loss；
- Geometry Curriculum。

### Phase 2：Batch 4

- Source Shape Template。

### Phase 3：Batch 5

- Hybrid Landmark；
- Piecewise Affine Warp。

### Phase 4：Batch 6

- Shape-aware Soft Mask；
- Temporal Stabilization。

### Phase 5：Batch 7

- Identity Appearance；
- Region；
- Boundary；
- Frequency；
- Full Curriculum。

### Phase 6：Batch 8

- GUI；
- A/B；
- 性能和兼容；
- 默认值和文档。

---

## 17. 验收标准

必须满足：

- 原模型可使用；
- 默认模式不变化；
- Geometry / Shape 模块可独立开启；
- `source_shape_power = 0` 基线等价；
- 旧 checkpoint 和旧 Merge 可回退；
- 保存恢复正确；
- 视频无明显脸型和边缘抖动；
- src 脸型保持趋势提升；
- dst 表情和姿态可接受；
- 无明显 Warp 空洞和边界伪影；
- 日志能够定位 Fallback 原因；
- Windows GPU / 视频固定条件验收完成。

---

## 18. 非目标

第一版不做：

- 替换 SAEHD；
- 破坏旧 DFM；
- 默认启用增强；
- TPS 作为默认 Warp；
- 新大型几何网络；
- 自动参数搜索；
- 完整 Web 服务化；
- 在 Batch 3 一次性实现全部通用 Loss。

---

End.