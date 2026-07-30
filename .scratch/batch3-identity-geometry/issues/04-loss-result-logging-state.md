# B3-04 单项 Loss 结果、日志与 requested/effective 状态

## 1. 基本信息

- Ticket ID：`B3-04`
- 状态：`BLOCKED-BY-B3-02-B3-03`
- 优先级：P0
- 前置 Ticket：B3-02、B3-03
- 阻塞 Ticket：B3-05、B3-12、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

当前 SAEHD `_unified_ops` 固定返回：

```text
src_loss, dst_loss, all_gradients_finite, step_applied
```

`onTrainOneIter()` 固定返回 `src_loss`、`dst_loss`，`ModelBase.train_one_iter()` 把返回通道写入 `loss_history`。Batch 2 Loss Window 支持任意固定维度，但同一窗口内维度必须一致。

Batch 3 需要新增 Geometry 可观测性，同时必须避免：

- Geometry 关闭时改变历史通道；
- 同一会话中开关变化导致 loss window 维度不一致；
- 只记录 Geometry total，无法判断 ratio/contour 哪项异常；
- 把 requested 当成 effective；
- 日志读取张量时额外执行第二次 session run。

## 3. Scope

### In Scope

- 定义稳定 runtime state 和 loss metric 名称。
- 定义 `_unified_ops` 可选第五项的结构。
- 定义 `onTrainOneIter` 的附加 loss 通道顺序。
- 定义 startup、每迭代、保存窗口日志的职责分工。
- 为 LossWindowTracker 增加可选 channel labels 接入，不改变 tracker 核心统计。

### Out of Scope

- 不修改具体 Geometry 公式。
- 不实现 GUI 曲线。
- 不保存每样本 loss 历史。
- 不改变 Batch 2 save controller 的成功/失败事务语义。

### Forbidden Changes

- 禁止 Geometry 关闭时增加任何 loss_history 通道。
- 禁止运行中热切换造成通道数变化。
- 禁止为日志执行独立第二次前向。
- 禁止把 warning 字符串写进数值 loss_history。
- 禁止用 dict 的非确定顺序决定通道顺序。

## 4. 代码锚点

- `models/Model_SAEHD/Model.py::_unpack_unified_train_result`
- `models/Model_SAEHD/Model.py::_unified_ops`
- `models/Model_SAEHD/Model.py::unified_train`
- `models/Model_SAEHD/Model.py::SAEHDModel.onTrainOneIter`
- `models/ModelBase.py::ModelBase.train_one_iter`
- `samplelib/sampling/loss_stats.py::LossWindowTracker`
- `samplelib/sampling/loss_stats.py::format_loss_window_log`
- `mainscripts/trainer_save_control.py::TrainerSaveController`

## 5. 状态模型

建议新增：

```python
@dataclass(frozen=True)
class GeometryRuntimeState:
    requested: bool
    effective: bool
    reason: str
    ratio_effective: bool
    contour_effective: bool
    curriculum_effective: bool
    anchor_source: str | None
    warnings: tuple[str, ...]
```

状态来源：

1. B3-02 提供配置 requested。
2. B3-07 提供 anchor/runtime readiness。
3. B3-08 提供 supervision readiness。
4. B3-12 提供 curriculum multiplier。

`effective=true` 不能仅由配置层决定。

## 6. 指标和通道顺序

固定常量：

```python
GEOMETRY_LOSS_CHANNELS = (
    "geometry_ratio_raw",
    "geometry_ratio_weighted",
    "geometry_contour_raw",
    "geometry_contour_weighted",
    "geometry_active_fraction",
    "geometry_weight_multiplier",
)
```

生产 loss history 只保存对训练诊断真正需要的加权通道，建议顺序：

```text
src_loss
dst_loss
geometry_ratio_weighted
geometry_contour_weighted
geometry_active_fraction
```

raw 值和 multiplier 可在结构化迭代日志/保存日志中输出，但不强制进入长期 `loss_history`。最终选择必须在本 Ticket Review 中固定，后续不可由编码 Agent自行删改。

## 7. `_unified_ops` 契约

Geometry disabled：

```python
_unified_ops = [src_loss, dst_loss, all_gradients_finite, step_applied]
```

Geometry enabled：

```python
_unified_ops = [
    src_loss,
    dst_loss,
    all_gradients_finite,
    step_applied,
    ordered_geometry_metrics,
]
```

其中 `ordered_geometry_metrics` 使用 tuple/list，不依赖无序 dict；每项是单个标量或可 batch mean 的固定张量。

`_unpack_unified_train_result` 必须兼容长度 2、4、5，旧测试不可回归。

## 8. 日志职责

### Startup 一次性日志

```text
[Geometry] requested=<bool> effective=<bool> reason=<code>
[Geometry] ratio_weight=<x> contour_weight=<x> curriculum=<state>
[Geometry] anchor_source=<source> confidence=<x> fingerprint_match=<bool>
```

### Iteration 日志

- 不每步打印完整文本。
- 仅通过现有 loss string 显示固定通道。
- warning 采用去重/限频机制，由 Model 层处理，不由 Hook 直接写日志。

### Save Window 日志

- channel labels 与 loss_history 通道数严格对应。
- Window 内出现维度变化必须抛错，不得静默截断。
- save 失败时窗口不 commit，沿用 Batch 2 事务语义。

## 9. 实施步骤

1. 新增 `core/enhancements/geometry/runtime_state.py`。
2. 新增 metric name/order 常量和纯函数 formatter。
3. 扩展 `_unpack_unified_train_result`，但先用 fake results 测试，不接主图。
4. 为 `onTrainOneIter` 设计 helper：`_format_training_loss_items(...)`。
5. 为 save controller 提供 channel labels 的只读入口；不得改变 controller 保存流程。
6. 添加 warning 去重键：`reason + anchor fingerprint + config hash`。
7. 添加 resume 测试，确保 session-local LossWindow 为空且通道定义稳定。

## 10. 测试要求

测试文件：

- `tests/smoke/test_batch3_geometry_runtime_state.py`
- `tests/smoke/test_batch3_geometry_loss_logging.py`

场景：

- requested false/effective false。
- requested true/anchor missing。
- ratio only、contour only、both。
- disabled 返回 2 个 loss channel。
- enabled 返回固定 5 个 history channel。
- session 中通道定义不可变。
- `_unpack_unified_train_result` 兼容旧长度。
- save window labels 正确。
- warning 不重复刷屏。
- 非有限 metric 在进入 history 前抛错。

命令：

```bash
python -m unittest tests.smoke.test_batch3_geometry_runtime_state -v
python -m unittest tests.smoke.test_batch3_geometry_loss_logging -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- requested/effective/reason 来源明确。
- disabled 的 loss history 与基线维度完全相同。
- enabled 通道顺序固定且有 labels。
- 日志不触发第二次前向。
- Loss Window 事务语义不变。
- Summary、Review、SHA 齐全。

## 12. Review 检查表

- 是否把配置 ready 写成 runtime effective？
- 是否依赖 dict 顺序？
- 是否在 disabled 时增加通道？
- 是否会在 resume 后混入旧 session window？
- 是否有第二次 session run？
- 是否把 raw/weighted 混淆？

## 13. 交付物

- runtime state/metric helper
- 两个 smoke test 文件
- 日志格式说明
- Summary、Review、Commit SHA
