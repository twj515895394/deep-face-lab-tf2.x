# DeepFaceLab TF2.x 源码审计与改造映射文档

## 1. 文档目标

本文档用于在进入代码改造前，对当前 DeepFaceLab TF2.x 项目的源码结构、核心流程、修改入口和风险区域进行系统审计。

目标：

- 建立源码地图；
- 明确训练、预测、合成三个阶段的修改位置；
- 为后续 Shape-aware Merge、训练增强等功能提供施工依据；
- 避免直接修改核心逻辑导致旧模型和旧流程不可用。

---

# 2. 总体架构映射

当前系统核心流程：

```
Dataset
  |
  v
Training Pipeline
  |
  v
SAEHD / DF / LIAE Model
  |
  v
Predictor
  |
  v
Merger
  |
  v
Final Video
```

后续增强方向：

```
Dataset Intelligence
        |
        v
Enhanced Training
        |
        v
Identity Geometry Learning
        |
        v
Shape-aware Prediction
        |
        v
Shape-aware Merge
        |
        v
Temporal Stabilization
```

---

# 3. Dataset 层审计

## 目标

增加训练数据智能信息。

未来扩展：

- face quality score
- pose bucket
- occlusion score
- shape anchor metadata

建议新增：

```
samplelib/
    sample_metadata.py
```

原则：

不破坏旧 faceset 格式，通过可选 metadata 扩展。

---

# 4. Training 层改造地图

## 当前职责

负责：

- identity learning
- reconstruction
- decoder training
- loss optimization

## 后续修改方向

新增：

```
losses/
    identity_geometry_loss.py
    landmark_loss.py
    region_loss.py
    frequency_loss.py
```

重点：

不修改 SAEHD 主网络结构，优先通过 loss、sampling、training strategy 增强。

---

# 5. Predictor 层改造地图

当前：

```
Input face
   |
Encoder
   |
Decoder
   |
Predicted face
```

未来增加：

- predicted landmark extraction
- source shape metadata loading
- shape confidence

新增模块：

```
shape/
    predictor_adapter.py
```

---

# 6. Merge 层改造地图

## 当前流程

```
DST landmarks
      |
      v
Affine Transform
      |
      v
Predicted Face
      |
      v
Mask
      |
      v
Blend
```

问题：

- dst landmarks 主导几何；
- dst mask 限制脸型范围；
- affine 无法改变局部脸型。

---

## 新增 Shape-aware Merge

目标：

```
Prediction
    |
    v
Hybrid Landmark Engine
    |
    v
Shape Warp
    |
    v
Shape-aware Mask
    |
    v
Blend
```

建议新增：

```
shape/
    source_shape_template.py
    hybrid_landmark.py
    shape_warp.py

merge/
    shape_mask.py
```

---

# 7. 禁止直接修改区域

以下区域第一次开发阶段应保持稳定：

- SAEHD 主网络结构；
- DFM 导出格式；
- 原始 Merge 默认路径；
- 原 faceset 数据结构。

原因：

保证兼容已有模型和用户流程。

---

# 8. 推荐开发顺序

## Phase 1

源码审计 + baseline 固定。

## Phase 2

训练增强：

- loss
- sampling
- metadata

## Phase 3

Source Shape Template。

## Phase 4

Shape-aware Merge。

## Phase 5

Temporal stabilization 和 UI 集成。

---

# 9. 风险等级

| 模块 | 风险 |
|---|---|
| Dataset metadata | 低 |
| Loss 增强 | 中 |
| Sampling 修改 | 中 |
| Predictor 扩展 | 中 |
| Merge 扩展 | 高 |
| 模型结构修改 | 极高 |

---

# 10. 后续工作

下一阶段需要继续结合实际 TF2.x 源码：

1. 标记真实文件路径；
2. 分析函数调用链；
3. 建立修改点清单；
4. 输出代码级改造计划。
