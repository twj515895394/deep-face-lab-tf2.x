# DeepFaceLab TF2.x 配置与扩展架构设计

## 1. 文档目标

本文定义 DeepFaceLab TF2.x 后续增强能力的工程接入和配置边界，目标是在不破坏原训练、模型和 Merge 流程的情况下，引入：

- Metadata / Smart Sampling；
- Minimal Loss Hook；
- Identity Geometry；
- Source Shape Template；
- Shape-aware Merge；
- Shape-aware Mask 与 Temporal；
- 后续 Identity Appearance 和通用画质 Loss；
- GUI / Linux 服务化预留。

核心原则：

> 保持兼容，采用扩展，而不是重写；DFL 是默认值和配置语义的唯一权威来源。

路线顺序：

```text
Batch 3：Minimal Loss Hook + Identity Geometry
Batch 4：Source Shape Template
Batch 5：Hybrid Landmark + Warp
Batch 6：Mask + Temporal
Batch 7：Appearance / Region / Boundary / Frequency
```

---

## 2. 配置权威与职责

### 2.1 DFL 负责

- 字段默认值；
- 类型和范围；
- Schema 版本；
- 未知字段策略；
- Feature Gate；
- Fallback / Strict 语义；
- SRC / DST 继承规则；
- 运行时 requested / effective 状态。

### 2.2 GUI 负责

- 展示已实现、已发布的字段；
- 保存用户实际选择；
- 只传启用项和用户改动项；
- 不复制维护 DFL 内部固定默认值；
- 不提前暴露尚未实现的未来字段；
- 展示 DFL 返回的状态、警告和错误。

### 2.3 禁止双重默认值

不应出现：

```text
GUI 默认值一套
DFL 默认值另一套
```

GUI 省略字段时，DFL 必须使用内部权威默认值。

---

## 3. Feature Flag 设计

所有增强功能默认关闭。

概念示例：

```yaml
features:
  metadata_sampling: false
  loss_hook: false
  identity_geometry: false
  source_shape_template: false
  shape_aware_merge: false
  shape_aware_mask: false
  temporal_stabilization: false
  appearance_losses: false
```

实际项目继续使用现有 `options-json.enhancements` 权威入口，字段名以各 Batch 正式 Schema 为准。

要求：

- 总 Gate 和子 Gate 语义明确；
- 只开子 Gate 不能绕过总 Gate；
- 关闭总 Gate 时不构建额外计算和状态；
- 未知布尔字段不得意外启用；
- 不支持的未来 Schema 必须安全关闭增强。

---

## 4. 配置分层

建议逻辑分层：

```text
enhancements
├── schema_version
├── training
│   ├── enabled
│   ├── metadata_sampling
│   ├── losses
│   ├── identity_geometry
│   └── curriculum
├── sampling
│   ├── base
│   ├── src
│   └── dst
├── merge
│   ├── enabled
│   ├── source_shape_template
│   ├── hybrid_landmark
│   ├── shape_warp
│   ├── shape_mask
│   └── temporal_stabilization
└── runtime
    ├── fallback_on_optional_error
    ├── strict_validation
    └── logging
```

这是一种职责结构，不代表所有字段应一次性实现。

---

## 5. Batch 3 配置边界

Batch 3 只公开几何训练所需字段。

概念示例：

```yaml
training:
  loss_hook:
    enabled: false

  identity_geometry:
    enabled: false
    weight: 0.0
    anchor_path: null

  curriculum:
    enabled: false
    mode: geometry_minimal
    stage: reconstruction
```

必须支持：

- Loss Hook 总开关；
- Geometry 独立开关和权重；
- Anchor 自动发现或显式路径；
- Reconstruction / Geometry Ramp / Geometry Stable；
- 单项日志；
- 保存恢复。

Batch 3 不得宣称已经支持：

```text
Identity Appearance
Region
Boundary
Frequency
Full Multi-objective Curriculum
```

可以预留解析边界，但不能让未实现字段产生有效行为。

---

## 6. Batch 4 配置边界

Source Shape Template 概念结构：

```yaml
merge:
  source_shape_template:
    enabled: false
    path: null
    rebuild: false
```

需要定义：

- 默认发现路径；
- 显式路径；
- 生成 / 重建入口；
- Schema；
- Identity / Faceset Fingerprint；
- Strict / Fallback；
- 用户指定与自动发现的优先级。

Template 缺失不能破坏传统 Merge。

---

## 7. Batch 5 配置边界

概念结构：

```yaml
merge:
  enabled: false

  hybrid_landmark:
    enabled: false
    source_shape_power: 0

  shape_warp:
    enabled: false
    mode: piecewise_affine
```

约束：

- `source_shape_power = 0` 等价传统几何；
- requested / effective power 分开记录；
- Warp 必须独立开关；
- 低置信度自动降级；
- Warp 模式未知时不能自动选择实验算法；
- 第一版默认只允许 Piecewise Affine。

---

## 8. Batch 6 配置边界

概念结构：

```yaml
merge:
  shape_mask:
    enabled: false
    mode: off

  temporal_stabilization:
    enabled: false
    mode: ema

runtime:
  shape_fallback_on_optional_error: true
  shape_strict_validation: false
```

需要定义：

- Mask 模式：`off / source_contour / hybrid`；
- 遮挡回退；
- Temporal 模式和强度；
- Scene Cut / Tracking Lost Reset；
- 单帧模式；
- Shape 可选错误与核心 Merge 错误边界。

`shape_mask.mode=off` 和 Temporal 关闭时必须保持传统行为。

---

## 9. Batch 7 配置边界

Batch 7 复用 Batch 3 Loss Hook：

```yaml
training:
  losses:
    identity_appearance:
      enabled: false
      weight: 0.0

    region:
      enabled: false
      weight: 0.0

    boundary:
      enabled: false
      weight: 0.0

    frequency:
      enabled: false
      weight: 0.0

  curriculum:
    mode: full_multi_objective
```

约束：

- 每项独立开关和权重；
- 未实现项不能提前出现在 GUI；
- 不强制依赖大型外部模型；
- 与 Geometry Loss 分项记录；
- 完整关闭后保持 Batch 6 稳定基线。

---

## 10. 配置解析与继承

推荐优先级：

```text
DFL 内部默认值
→ base 配置
→ role / module override
→ runtime effective adjustment
```

必须区分：

```text
requested：用户请求值
effective：置信度、环境或回退后实际值
```

例如：

```text
requested source_shape_power = 70
effective source_shape_power = 25
reason = LOW_LANDMARK_CONFIDENCE
```

不得把 effective 值覆盖回用户持久配置。

---

## 11. Fallback 与 Strict

### Optional Enhancement Error

可选增强错误示例：

- Shape Template 缺失；
- 可选 Sidecar 损坏；
- Template Fingerprint 不匹配；
- Hybrid Landmark 低置信度；
- Warp 拓扑退化；
- Temporal 状态可重建。

允许按配置回退传统路径。

### Core Error

不得被 Fallback 吞掉：

- 模型加载失败；
- Frame / SampleLoader 核心失败；
- PermissionError；
- MemoryError / OOM；
- TensorFlow / CUDA 错误；
- 保存失败；
- 未分类编程错误；
- 传统 Merge 自身失败。

Strict 开启时，任何声明为必需的 Geometry / Shape 资产异常都应阻止增强路径启动。

---

## 12. 扩展模块架构

建议：

```text
core/
├── training/
│   ├── losses/
│   └── curriculum/
├── shape/
│   ├── shape_anchor.py
│   ├── geometry_features.py
│   ├── source_shape_template.py
│   ├── hybrid_landmark.py
│   └── shape_warp.py
├── merge/
│   ├── shape_merge.py
│   └── shape_mask.py
└── temporal/
    └── stabilizer.py
```

保持原 Trainer 和 Merger 不被直接替换，只增加稳定 Hook 和编排入口。

---

## 13. CLI / options-json

当前训练 GUI 继续通过：

```text
--options-json
```

传递结构化配置。

未来独立工具可提供：

```text
source-shape-build
source-shape-inspect
shape-merge-validate
```

不建议为每个内部字段增加散乱的顶层 CLI 参数；复杂配置优先归入版本化 JSON。

进程调用必须使用参数数组，不拼接 Shell 字符串。

---

## 14. UI 接入预留

```text
GUI
  ↓
Typed Config Model
  ↓
JSON Serializer
  ↓
DFL options-json / CLI
  ↓
Runtime Status Parser
```

GUI 接入原则：

- 每个 Batch 完成并冻结 Schema 后再接入；
- 不一次性添加 Batch 3—7 全部未来字段；
- 显示 requested / effective / fallback reason；
- DFL 默认值不由 GUI 重复写死；
- 未知版本提示升级，不猜测字段含义。

---

## 15. Linux 服务化方向

未来架构：

```text
Web UI
  ↓
API Server
  ↓
Job Queue
  ↓
DFL Worker
  ↓
GPU Runtime
```

训练、Faceset Analyzer、Shape Template Build 和 Merge 均可作为任务执行。

但核心链路未稳定前，不进入完整服务化；服务化不能成为 Batch 3—7 算法实现的前置依赖。

---

## 16. 开发原则

1. 所有新功能可关闭；
2. 所有字段由 DFL 提供默认值；
3. 新模块不破坏旧模型；
4. 未实现字段不得产生行为；
5. 每个模块有 Feature Gate；
6. Optional Fallback 和 Core Error 边界明确；
7. 配置、日志和状态使用同一术语；
8. 每个算法必须有固定条件实验；
9. GUI 不先于后端 Schema；
10. 历史 Batch 记录不因未来路线调整而重写。

---

## 17. 后续开发顺序

```text
Phase 1：Batch 3 Minimal Loss Hook + Identity Geometry
Phase 2：Batch 4 Source Shape Template
Phase 3：Batch 5 Hybrid Landmark + Piecewise Affine Warp
Phase 4：Batch 6 Shape-aware Mask + Temporal
Phase 5：Batch 7 Appearance / Region / Boundary / Frequency
Phase 6：Batch 8 A/B、默认值、GUI、兼容和文档
```

当前 Batch 3 仍受 Batch 2 Windows GPU Final Sign-off 阻塞。路线调整不改变该环境门。