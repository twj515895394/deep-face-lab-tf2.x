# B3-12 Reconstruction → Geometry Ramp → Stable 最小 Curriculum

## 1. 基本信息

- Ticket ID：`B3-12`
- 状态：`BLOCKED-BY-B3-04-B3-11`
- 优先级：P1
- 前置 Ticket：B3-04、B3-11
- 阻塞 Ticket：B3-13、B3-14
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

`ModelBase` 已可靠保存 `iter` 和 `options`。Batch 3 不需要新增 checkpoint state 就能恢复 Curriculum：只要阶段和 multiplier 是 `iter + frozen config` 的确定性函数，恢复后即可得到完全相同状态。

第一版禁止手动热切阶段和自适应权重，避免会话内图/日志契约变化。

## 3. Scope

### In Scope

- 三阶段确定性 scheduler。
- 输出 stage、stage_iter、multiplier、requested/effective。
- 从已保存 `iter` 恢复。
- 支持 curriculum gate 关闭时 multiplier=1（Geometry 本身有效时）。
- startup/保存日志中记录状态。

### Out of Scope

- 不实现自动 loss balance。
- 不根据 loss 曲线动态切换。
- 不持久化新的 optimizer slot、变量或 sidecar。
- 不实现 Batch 7 多目标 Curriculum。
- 不支持训练运行中修改 warmup/ramp 参数。

### Forbidden Changes

- 禁止新增 TF Variable 表示 stage。
- 禁止恢复时回到 Stage A。
- 禁止将 stage 写入模型权重文件。
- 禁止 wall-clock 驱动。
- 禁止在 Geometry 未 effective 时声称 Stage B/C 正在训练。

## 4. 代码锚点

- `models/ModelBase.py::iter/get_iter/save`
- `core/enhancements/config.py`：`training.curriculum`、geometry warmup/ramp
- `models/Model_SAEHD/Model.py::on_initialize/onTrainOneIter`
- B3-04 runtime state/metrics

## 5. 冻结函数

```python
@dataclass(frozen=True)
class GeometryCurriculumState:
    requested: bool
    effective: bool
    stage: str
    stage_iter: int
    multiplier: float
    reason: str
```

```python
def resolve_geometry_curriculum(
    *, current_iter: int, curriculum_enabled: bool,
    geometry_effective: bool, warmup_iters: int, ramp_iters: int
) -> GeometryCurriculumState:
    ...
```

阶段：

```text
Stage A reconstruction: current_iter < warmup_iters, multiplier=0
Stage B geometry_ramp: warmup <= iter < warmup+ramp
  multiplier=(iter-warmup)/max(ramp,1)
Stage C geometry_stable: iter >= warmup+ramp, multiplier=1
```

边界：

- `ramp_iters=0`：到达 warmup 后直接 Stable。
- curriculum disabled 且 Geometry effective：stage=`fixed`、multiplier=1。
- Geometry ineffective：stage=`inactive`、multiplier=0。
- current_iter/warmup/ramp 非负整数。
- multiplier 强制有限且 `[0,1]`。

## 6. 保存恢复语义

- 唯一持久输入是已有 `iter` 与规范化 options。
- 保存前后相同 iter 得到相同 state。
- `ModelBase.train_one_iter()` 在成功 step 后递增 iter；当前迭代构图/权重使用调用前的 `get_iter()`，日志必须注明该语义。
- skipped optimizer step 不应由 scheduler 自行递增任何状态；是否 `ModelBase` 仍递增 iter 属于现有控制流事实，B3-14 必须回归并记录。
- 改配置后恢复属于新实验，不承诺继续原 ramp；启动日志必须显示配置 hash 变化。

## 7. 实施步骤

1. 新建 `core/enhancements/geometry/curriculum.py`。
2. 实现 dataclass 和纯函数。
3. 增加 config hash helper，仅记录 geometry 相关稳定字段。
4. 在 Hook context 中只传 scalar multiplier，不传 scheduler 对象。
5. 在 B3-04 日志 formatter 中加入 stage/multiplier。
6. 在假 ModelBase resume fixtures 上验证保存恢复。
7. 不接主图；B3-13 接入。

## 8. 测试要求

测试文件：`tests/smoke/test_batch3_geometry_curriculum.py`

必须覆盖：

- iter 0、warmup 前一位、warmup 边界、ramp 中点、ramp 末位、stable。
- warmup=0、ramp=0。
- curriculum disabled。
- Geometry ineffective。
- 负数、bool、NaN 类型拒绝。
- multiplier 单调且范围合法。
- 保存/恢复同 iter 状态完全相同。
- 多次调用无 mutable state。
- config hash 稳定且参数改变会变化。
- 不创建 TF variable/checkpoint 文件。

命令：

```bash
python -m unittest tests.smoke.test_batch3_geometry_curriculum -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 9. 完成定义

- Curriculum 是纯确定性函数。
- 无新增 checkpoint/optimizer 格式。
- 恢复不回退阶段。
- inactive/fixed/ramp/stable 语义有测试。
- Summary、Review、SHA 齐全。

## 10. Review 检查表

- 是否引入 mutable stage？
- 是否按 wall clock？
- 是否 off-by-one？
- 是否在 Geometry inactive 时输出非零 multiplier？
- 是否把 skipped step 自行计数？
- 是否混入 Batch 7 自适应策略？

## 11. 交付物

- `core/enhancements/geometry/curriculum.py`
- `tests/smoke/test_batch3_geometry_curriculum.py`
- 状态/边界说明
- Summary、Review、Commit SHA
