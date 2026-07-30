# Batch 3：Identity Geometry 训练基础详细施工设计

> 状态：TICKET-DESIGN-DRAFT
> 路线：GEOMETRY-FIRST
> 基线分支：`codex/batch2-ticket19-loss-window`
> 前置事实：Batch 2 代码与自动验收完成；Windows GPU Final Matrix 为 `DEFERRED-BY-MAINTAINER`，不得写成 PASS。

## 1. 目标

在不改变默认 SAEHD 行为、不修改 Merge 和 checkpoint 核心格式的前提下，建立 Identity Geometry MVP 所需的最小训练基础：配置、Loss Hook、Shape Anchor、几何特征、Geometry Loss、最小 Curriculum、保存恢复、日志与验收。

## 2. 非目标

不实现 Identity Appearance、Region、Boundary、Frequency、LPIPS/VGG/DINO/ArcFace、新 Backbone、Source Shape Template 正式 sidecar、Hybrid Landmark、Piecewise Affine Warp、Shape-aware Mask、Temporal、完整 GUI 或自动权重搜索。

## 3. 已审计代码锚点

- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize_options`：SAEHD 选项入口。
- `models/Model_SAEHD/Model.py`：训练张量、Loss、`onTrainOneIter`、异常上下文及 loss-window 接入点。
- `models/ModelBase.py`：options、迭代数、保存恢复、训练控制流。
- `core/enhancements/config.py::DEFAULT_ENHANCEMENT_CONFIG`：增强默认值唯一来源；已有 `training.loss_hooks`、`training.identity_geometry`、`training.curriculum` 预留门。
- `core/enhancements/config.py::EnhancementConfig`：配置归一化、unknown-field 忽略、requested/effective 状态基础。
- `samplelib/metadata/`：Batch 2 metadata、样本身份与 fingerprint 基础，Anchor 身份绑定应复用，不另建平行 ID。
- `tests/smoke/`：Batch 1/2 的纯函数、spawn、兼容和控制流测试风格。

## 4. 固定契约

### 4.1 默认关闭与零影响

只有 `training.enabled && training.loss_hooks && training.identity_geometry` 同时为真时 Geometry 路径才可 effective。全部关闭时：总 Loss、梯度、采样、保存恢复、Merge 与旧基线等价。

### 4.2 SRC/DST 职责

- SRC：身份稳定几何，包括脸宽、下颌、下巴、颧骨和稳定比例。
- DST：姿态、表情、眼睛开合、嘴型和运动属性。
- 禁止要求 SRC/DST 样本逐帧 landmark 配对；禁止用 Geometry Loss 静态化 DST 表情。

### 4.3 Tensor/Mask/DType

- 训练图像继续沿用 SAEHD 当前 NHWC float 张量约定。
- 几何特征计算必须显式说明 batch 维、feature 维和有效性 mask。
- 新模块内部统计采用 `float32`；不得因输入精度隐式切到 float64。
- 非有限 anchor、feature、loss 或梯度不得静默进入 optimizer。

### 4.4 错误与 Fallback

仅可对可选 Anchor/Geometry 增强数据失败进行回退，且必须记录 requested/effective/reason。OOM、worker 崩溃、核心 tensor shape/dtype 错误、checkpoint 损坏、optimizer state 不兼容和非有限关键梯度必须传播。

### 4.5 保存恢复

不修改权重文件和 optimizer slot 格式。Curriculum 状态优先由确定性函数根据已保存 iter 与配置重建；确需持久状态时只使用 ModelBase 已支持的 options/state 入口。旧 checkpoint 缂字段按默认关闭恢复。

## 5. Ticket DAG

```text
B3-01 baseline/contracts/fixtures
  ├─> B3-02 config schema
  ├─> B3-03 minimal loss hook
  └─> B3-06 anchor identity model
B3-02 + B3-03 -> B3-04 result/log state -> B3-05 numeric/error boundary
B3-06 -> B3-07 anchor loader/cache -> B3-08 geometry features
B3-05 + B3-08 -> B3-09 ratio geometry loss -> B3-10 landmark geometry loss
B3-09 + B3-10 -> B3-11 src/dst isolation
B3-04 + B3-11 -> B3-12 curriculum
B3-02..B3-12 -> B3-13 SAEHD integration/checkpoint
B3-13 -> B3-14 control-flow/master matrix/GPU A-B
B3-14 -> B3-15 docs/review/handoff closeout
```

可并行：B3-02、B3-03、B3-06；B3-09 与 B3-10 在共享特征契约稳定后可并行。主链路接入 B3-13 不得提前。

## 6. Ticket 列表

| ID | 标题 | 前置 |
|---|---|---|
| B3-01 | 基线冻结、术语、Tensor/Mask/DType 契约与 Fixtures | 无 |
| B3-02 | 配置 Schema、默认值、Feature Flag 与 options-json | B3-01 |
| B3-03 | Minimal Loss Hook API、注册与零影响 | B3-01 |
| B3-04 | 单项 Loss 结果、日志与 requested/effective 状态 | B3-02,B3-03 |
| B3-05 | 数值保护、错误传播与 Optional Fallback | B3-04 |
| B3-06 | Shape Anchor 数据模型与样本身份绑定 | B3-01 |
| B3-07 | Shape Anchor 加载、缓存、失效与安全回退 | B3-02,B3-06 |
| B3-08 | Landmark/Ratio 特征、归一化与有效性 | B3-07 |
| B3-09 | Ratio Geometry Loss MVP | B3-05,B3-08 |
| B3-10 | Landmark Geometry Loss MVP | B3-05,B3-08 |
| B3-11 | SRC/DST 非对称职责与 Geometry/Expression 隔离 | B3-09,B3-10 |
| B3-12 | Reconstruction→Ramp→Stable 最小 Curriculum | B3-04,B3-11 |
| B3-13 | SAEHD 主链路、旧 checkpoint 与 optimizer 兼容 | B3-02..B3-12 |
| B3-14 | Loss Window/保存退出恢复回归、Master Matrix 与 GPU A/B | B3-13 |
| B3-15 | 用户/GUI Schema、Summary、Review 与 Handoff 收口 | B3-14 |

## 7. 统一完成定义

每个 Ticket 必须具备：独立 Issue 文档；限定文件/类/函数；自动测试；关闭时零影响证据；异常和未执行项记录；Summary；独立 Review；Commit SHA。不得以“效果更好”作为完成标准。

## 8. 施工入口

动态执行区：`.scratch/batch3-identity-geometry/`。编码前必须完成全部 Issue 文档、Master Test Matrix、Windows GPU A/B 规约及一次文档一致性 Review。