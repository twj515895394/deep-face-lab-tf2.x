# DeepFaceLab TF2.x Source Tree Analysis

## 1. 文档目标

本文档用于建立 deep-face-lab-tf2.x 当前源码结构地图，为后续训练优化、Shape-aware Merge、性能优化以及 UI 集成提供代码定位依据。

目标：

- 明确核心模块职责
- 建立 Training / Prediction / Merge 调用链
- 标记未来改造入口
- 降低 AI Agent 修改代码时的理解成本

---

# 2. 总体 Pipeline

```text
Dataset
  |
  v
Sample Processing
  |
  v
Trainer
  |
  v
Model (SAEHD / DF / LIAE)
  |
  v
Predictor
  |
  v
Merger
  |
  v
Video Output
```

---

# 3. 核心模块职责

## 3.1 samplelib

职责：

- faceset 管理
- sample 加载
- landmarks 数据
- mask 数据
- augmentation 数据

未来扩展：

增加：

- quality score
- pose metadata
- shape anchor metadata

用于：

- Smart Sampling
- Curriculum Training
- Source Shape Template

---

## 3.2 models

职责：

- 网络定义
- Encoder
- Decoder
- Training Graph
- Loss 计算

主要改造方向：

不修改主体网络结构，优先增加：

- identity geometry loss
- landmark loss
- region loss

---

## 3.3 SAEHD / DF / LIAE

当前职责：

- 学习 src identity
- 学习 dst attribute
- 输出预测脸

未来增强：

Identity 拆分：

```text
Identity
 |
 +-- Appearance
 |
 +-- Geometry
```

---

## 3.4 Predictor

职责：

- 加载模型
- 输入 aligned face
- 输出预测结果

未来扩展：

增加：

- predicted landmark
- shape metadata
- confidence

---

## 3.5 Merger

当前最关键模块。

当前流程：

```text
DST Landmarks
    |
    v
Affine Transform
    |
    v
Prediction
    |
    v
Mask
    |
    v
Blend
```

问题：

dst geometry 主导最终脸型。

---

# 4. 未来 Shape-aware Merge 改造入口

新增模块：

```text
shape/
 |
 +-- source_shape_template.py
 +-- hybrid_landmark.py
 +-- shape_warp.py

merge/
 |
 +-- shape_mask.py

```

流程：

```text
Prediction
 |
 v
Pred Landmark
 |
 v
Hybrid Landmark
 |
 v
Piecewise Affine Warp
 |
 v
Shape-aware Mask
 |
 v
Blend
```

---

# 5. 修改风险等级

| 模块 | 风险 |
|---|---|
| metadata | 低 |
| dataset | 中 |
| loss | 中 |
| predictor | 中 |
| merger | 高 |
| model architecture | 极高 |

---

# 6. 开发原则

## 保持兼容

旧模型：

```text
DFL Original Pipeline
```

继续工作。

增强模式：

```text
Enhanced Pipeline
```

通过配置开启。

---

# 7. 下一阶段

下一步需要进行真实源码审计：

- trainer 入口定位
- SAEHD 调用链分析
- merger.py 详细分析
- mask pipeline 分析
- 性能瓶颈定位

最终形成可执行修改计划。
