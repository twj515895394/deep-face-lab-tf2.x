# B3-05 数值保护、错误传播与 Optional Fallback 边界

## 1. 基本信息

- Ticket ID：`B3-05`
- 状态：`BLOCKED-BY-B3-04`
- 优先级：P0
- 前置 Ticket：B3-04
- 阻塞 Ticket：B3-09、B3-10、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

现有 SAEHD 已在图中检查 unscaled gradients，并在非有限梯度时跳过 optimizer step；`onTrainOneIter()` 会记录上下文后重新抛出异常。Batch 3 必须复用这些语义，不能另建一套“Geometry 异常全部 fallback”的宽松机制。

必须区分：

- 可选数据不可用：可以关闭 Geometry 并继续基线训练；
- 已进入图的张量 shape/dtype/finite 错误：属于实现或数据契约破坏，必须失败；
- OOM、worker、checkpoint、optimizer 错误：必须传播；
- 单个样本监督无效：使用 validity=0 跳过，不抛整批异常；
- 整批无有效样本：Geometry addition=0，但记录 active_fraction=0。

## 3. Scope

### In Scope

- 定义错误分类、异常类型和稳定 reason code。
- 定义 build-time、startup-time、per-batch、optimizer-time 的不同处理。
- 定义 strict_validation 与 fallback_on_optional_error 的交互。
- 定义非有限 anchor、监督输入、loss、metric、gradient 的处理。
- 定义限频 warning 与 failure context。

### Out of Scope

- 不修改核心 SampleLoader 错误语义。
- 不捕获 TensorFlow OOM 转成普通 warning。
- 不自动修复损坏 checkpoint。
- 不实现重试训练。

### Forbidden Changes

- 禁止 `except Exception: return zero_loss`。
- 禁止把 shape/dtype 错误标成“可选 Anchor 缺失”。
- 禁止把非有限 loss 清零后继续 optimizer。
- 禁止在 OOM 时自动降低 batch size并继续。
- 禁止吞 worker/IPC 崩溃。

## 4. 当前代码锚点

- `models/Model_SAEHD/Model.py::_is_oom_exception`
- `models/Model_SAEHD/Model.py::_training_exception_context`
- `models/Model_SAEHD/Model.py::_log_training_exception`
- `_prepare_gv_for_finite_gate`
- `_get_gated_update_op`
- `_update_loss_scale_state`
- `ModelBase.finalize`
- `EnhancementConfig.fallback_on_optional_error`
- `EnhancementConfig.strict_validation`

## 5. 错误分类

### 5.1 可回退 Optional Startup Errors

仅包括：

```text
anchor_not_found
anchor_schema_unsupported
anchor_identity_mismatch
anchor_fingerprint_mismatch
anchor_confidence_below_threshold
optional_geometry_metadata_missing
```

处理：

- `strict_validation=false` 且 `fallback_on_optional_error=true`：Geometry effective=false，基线训练继续，startup warning 一次。
- 其他组合：抛明确异常并阻止训练开始。

### 5.2 可跳过 Per-sample Invalidity

```text
landmark_missing
landmark_count_not_68
sample_confidence_low
pose_outside_safe_range
ratio_denominator_too_small
supervision_map_empty
```

处理：对应 sample/feature validity=0；不得使用 NaN sentinel。

### 5.3 必须失败的契约错误

```text
placeholder shape mismatch
layout mismatch
unexpected dtype
non-finite supervision tensor after validation
non-finite geometry loss
metric order/dimension mismatch
```

这些表示代码或数据管道错误，不允许 fallback。

### 5.4 必须传播的核心错误

- `MemoryError`、TensorFlow ResourceExhausted/OOM。
- generator worker 崩溃、EOF、IPC 错误。
- 核心 SampleLoader 失败。
- checkpoint 损坏、optimizer slot 不兼容。
- 模型权重 load/save 失败。
- 非有限关键梯度。

## 6. 建议异常类型

```python
class GeometryConfigError(ValueError): ...
class GeometryAnchorError(RuntimeError): ...
class GeometrySupervisionError(RuntimeError): ...
class GeometryContractError(RuntimeError): ...
```

- Optional startup error可以用 `GeometryAnchorError` + reason code 交给 resolver 判断。
- `GeometryContractError` 永远不得 fallback。
- 不修改核心异常的原类型；可使用 `raise ... from error` 增加上下文。

## 7. 数值契约

- anchor、ratio、SDF 在进入 TensorFlow feed 前执行 `np.isfinite`。
- validity=0 的样本仍要求承载张量有限，避免 `0 * NaN = NaN`。
- 分母使用显式 epsilon 和 validity gate，不使用无条件 clip 掩盖退化几何。
- geometry raw/weighted loss 在图中分别检查 finite。
- addition 进入 `gpu_src_loss` 前 shape 必须为 `[device_batch]`。
- geometry metrics fetch 后进入 loss_history 前再次执行 Python finite guard。
- 任何 geometry 造成的非有限梯度由现有全梯度 gate 处理，不单独执行 optimizer。

## 8. Fallback 状态转移

```text
requested
  ├─ optional startup failure + allowed fallback
  │      -> effective=false, reason=<code>, baseline training
  ├─ strict or fallback disabled
  │      -> startup exception
  └─ runtime ready
         ├─ per-sample invalid -> validity=0
         ├─ all invalid -> addition=0, active_fraction=0
         └─ contract/nonfinite -> fatal exception
```

Runtime 中 Anchor 文件被删除或修改不在 Batch 3 自动热重载；B3-07 必须在启动时建立不可变快照。避免训练过程中 effective 状态和 loss 维度变化。

## 9. 实施步骤

1. 新增 `core/enhancements/geometry/errors.py`。
2. 新增纯函数 `classify_geometry_startup_error`。
3. 新增 NumPy feed validator。
4. 新增 TensorFlow finite assertion helper，但不得创建独立 optimizer path。
5. 扩展 training exception context：仅在 Geometry requested 时增加 requested/effective/reason、监督 shapes；不得打印完整用户路径或大数组。
6. 新增 warning limiter。
7. 添加 fallback/strict 参数矩阵测试。

## 10. 测试要求

测试文件：`tests/smoke/test_batch3_geometry_error_boundary.py`

必须覆盖：

- anchor missing 四种 strict/fallback 组合。
- fingerprint mismatch。
- 单样本 landmark invalid。
- 整批 validity=0，addition=0。
- validity=0 但数据含 NaN，必须失败。
- ratio 分母退化。
- wrong rank、wrong batch、wrong layout。
- OOM 分类与传播。
- worker error 原样传播。
- non-finite raw/weighted metric。
- non-finite gradient 使用现有 skip/failure 语义。
- warning 限频。

命令：

```bash
python -m unittest tests.smoke.test_batch3_geometry_error_boundary -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- 错误分类表和代码一致。
- Optional fallback 只发生在启动阶段可选资产。
- per-sample invalidity 不污染整批。
- contract/OOM/worker/checkpoint/optimizer 错误不被吞。
- 非有限 loss 不进入 optimizer。
- Summary、Review、SHA 齐全。

## 12. Review 检查表

- 是否存在广泛 `except Exception`？
- 是否使用 `0 * NaN` 假设安全？
- 是否把 runtime 文件变化做成热 fallback？
- 是否修改了核心 OOM 类型？
- 是否打印用户大数组或隐私路径？
- 是否让 Geometry 有独立 optimizer step？

## 13. 交付物

- `core/enhancements/geometry/errors.py`
- feed/finite validators
- `tests/smoke/test_batch3_geometry_error_boundary.py`
- Summary、Review、Commit SHA
