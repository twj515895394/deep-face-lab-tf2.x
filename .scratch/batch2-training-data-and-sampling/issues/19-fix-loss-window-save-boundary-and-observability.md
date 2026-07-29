# Ticket 19 — 修复 Loss Window 保存边界、失败语义与可观测性

> 状态：OPEN / P1 HIGH  
> Blocked by：无  
> Blocks：21  
> 可并行：可与 Ticket 14—18 并行，由独立 Agent 施工  
> 范围：只修保存窗口统计，不修改 Loss 公式、训练步骤或 checkpoint 格式

---

## 1. 问题背景

当前 Trainer 在 `model.save()` 成功后只设置 `after_save=True`，直到下一次 `train_one_iter()` 完成后才计算窗口统计。因此日志窗口多包含一个保存后的 batch，该 batch 并未进入刚刚写入的 checkpoint。

当前行为：

```text
训练窗口 A
→ model.save()
→ after_save=true
→ 再训练 batch B
→ 统计 A+B
```

正确行为：

```text
freeze end_index
→ 保存 checkpoint
→ 保存成功后统计 [start_index:end_index]
→ 输出
→ start_index=end_index
```

保存失败时不得消费窗口。

---

## 2. 开工前必读

1. `AGENTS.md`
2. `.scratch/batch2-training-data-and-sampling/issues/13-loss-window-logging-and-observability.md`
3. Ticket 13 summary/handoff
4. `mainscripts/Trainer.py`
5. `samplelib/sampling/loss_stats.py`
6. `models/ModelBase.py::save`
7. `models/ModelBase.py::train_one_iter`
8. `tests/smoke/test_batch2_loss_window_logging.py`
9. 保存、自动保存、退出、目标迭代相关 tests

---

## 3. 固定窗口定义

窗口定义：

```text
从上一次成功保存之后产生的第一条 loss
到本次保存调用开始前已经存在的最后一条 loss
```

使用半开区间：

```python
history[start_index:end_index]
```

其中：

```text
start_index：上次成功保存消费后的边界
end_index：本次保存前冻结的 len(history)
```

### 会话启动

恢复训练时：

```python
start_index = len(model.get_loss_history())
```

旧 history 不进入新会话首个保存窗口。

### 无新 loss

如果：

```text
start_index == end_index
```

保存仍可成功，但窗口统计为 empty，不得复用旧 last loss 冒充本窗口。

---

## 4. API 设计

扩展纯函数：

```python
def compute_loss_window_stats(history, start_index=0, end_index=None):
    ...
```

要求：

- end_index=None 兼容旧行为；
- start/end 转 int；
- clamp 到合法范围；
- end < start 返回 None 或明确 ValueError，必须冻结并测试；
- 不修改 history；
- finite 校验；
- 维度一致；
- 返回 count、mean、median、last、min、max。

推荐增加状态对象：

```python
class LossWindowTracker:
    start_index
    freeze_end(history)
    stats_for_frozen(history, end_index)
    commit(end_index)
```

但不得为了小功能引入复杂全局状态。纯函数 + Trainer 明确变量也可接受。

---

## 5. 保存流程

建议统一为单一 helper：

```python
def model_save(reason):
    end_index = len(model.get_loss_history())
    model.save()
    stats = compute_loss_window_stats(
        model.get_loss_history(),
        loss_window_start_index,
        end_index,
    )
    log_save_stats(reason, stats, ...)
    loss_window_start_index = end_index
```

注意闭包更新需要 `nonlocal` 或状态 dict，必须清晰。

### 成功定义

只有 `model.save()` 正常返回才算成功。

### 失败定义

如果 `model.save()` 抛异常：

- 原异常继续向外传播；
- start index 不变；
- 不输出成功窗口；
- 不设置 after_save；
- 不发送误导 preview；
- 下次成功保存仍包含此前未消费 loss。

---

## 6. 保存原因

所有入口必须传明确 reason：

```text
initial_iter
manual
scheduled
target_reached
exit
autobackup（若主 save）
```

日志示例：

```text
[Save][scheduled] iter=12000 window=1000
  src mean=0.1234 median=0.1200 last=0.1180 min=0.1100 max=0.1500
  dst mean=0.0987 median=0.0970 last=0.0950 min=0.0900 max=0.1200
```

必须明确：

- window count；
- mean 主显示；
- median；
- last；
- start/end iter 或 history indices；
- reason。

控制台可保持紧凑，但结构化测试应验证字段。

---

## 7. 首次 Iter 保存

当前 `iter==1` 会保存。该窗口可能只包含第一条 loss。

必须测试：

- count=1；
- mean=median=last；
- start index 推进；
- 后续自动保存不重复包含第一条。

Warmup 逻辑可能一次外层循环调用多个 `train_one_iter()`，窗口应以实际 history 长度为准，而不是假定每循环一条。

---

## 8. 自动保存

当前按时间累计：

```text
while elapsed >= interval
```

如果跨过多个 interval，只执行一次实际保存时：

- 窗口只消费一次；
- reason=scheduled；
- 不生成多个空窗口日志；
- last_save_time 时间推进逻辑保持。

---

## 9. 手动保存、目标与退出

### 手动 save

- 冻结边界立即保存；
- 日志立即输出，不等下一 batch；
- preview 在成功保存后发送。

### target reached

- 当前迭代 loss 应进入保存；
- 保存成功后标 reached；
- 不额外训练下一 batch；
- window boundary 正确。

### exit

- 用户按 Enter 后保存当前窗口；
- 保存成功才退出；
- 失败不能被 finalize 吞掉；
- 不训练额外 batch。

---

## 10. Loss History 压缩风险

`ModelBase.train_one_iter()` 在 history 很大时会下采样：

```python
self.loss_history = self.loss_history[::keep_ratio]
```

这会使基于 list index 的长期 tracker 失效。

本 Ticket 必须处理：

方案 A（推荐）：Tracker 使用本会话独立 buffer，不依赖可能被压缩的全局 history。每次训练将 loss 同时 append 到 save-window buffer，成功保存后 clear。

方案 B：在 history 压缩时同步 remap start index，但复杂且容易错误。

推荐实现：

```text
Trainer session-local loss_window_items
```

每次成功 `train_one_iter()` 后追加当前 loss；恢复训练时 buffer 为空；保存时复制/freeze buffer；成功后清空；失败保留。

如果采用 buffer：

- 不修改 preview history；
- 不改变 ModelBase 保存的 loss_history；
- 不影响 checkpoint；
- 纯函数仍支持 sequence stats；
- 测试大 history 压缩不影响窗口。

---

## 11. 允许修改文件

```text
mainscripts/Trainer.py
samplelib/sampling/loss_stats.py
相关 tests
Ticket 13 summary/review 状态说明
```

如需 ModelBase 暴露最近 loss，必须最小化接口，不修改训练语义。

---

## 12. 禁止范围

- 不修改 SAEHD Loss；
- 不修改 optimizer；
- 不修改学习率；
- 不修改采样概率；
- 不把新 tracker 写入 checkpoint；
- 不修改 preview loss history；
- 不吞保存错误；
- 不延迟到下一 batch 打日志；
- 不用 `loss_history[-1]` 冒充空窗口 mean；
- 不因日志异常阻止正常训练，除非 loss 非有限本身需按现有核心规则失败。

---

## 13. 必须新增测试

### Pure function

- start/end 半开区间；
- end=None；
- empty；
- one item；
- multi-dim；
- non-finite；
- inconsistent dims；
- invalid indices。

### Tracker/buffer

- session start 不含旧 history；
- first save；
- second save；
- consecutive saves without training；
- failed save retains window；
- next success consumes retained window；
- history compression does not alter buffer。

### Trainer integration with fake model

Fake model 至少提供：

```text
train_one_iter
get_loss_history
save
get_iter
```

测试：

- scheduled save 边界；
- manual save；
- target reached；
- exit save；
- save raises；
- 日志在 save 后、下一 train 前产生；
- preview 只在成功后。

---

## 14. 测试命令

```bash
./.venv/bin/python -m compileall mainscripts/Trainer.py samplelib/sampling/loss_stats.py
./.venv/bin/python -m unittest tests.smoke.test_batch2_loss_window_logging
./.venv/bin/python -m unittest tests.smoke.test_batch2_trainer_save_window
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

---

## 15. 验收标准

- [ ] 保存前冻结 end；
- [ ] 成功后立即统计；
- [ ] 不包含保存后 batch；
- [ ] 失败不消费；
- [ ] 恢复不混旧 history；
- [ ] 空窗口不复用旧 loss；
- [ ] initial/manual/scheduled/target/exit 全覆盖；
- [ ] history 压缩不破坏窗口；
- [ ] mean 与离线重算一致；
- [ ] count/median/last/min/max 正确；
- [ ] 不改变 checkpoint/preview/Loss；
- [ ] 全量回归通过。

---

## 16. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
19-fix-loss-window-save-boundary-and-observability-summary.md
```

必须记录：

- 修复前时序；
- 修复后时序；
- tracker/buffer 设计；
- 各保存 reason 测试；
- failed save 证据；
- history 压缩测试；
- 日志示例；
- 全量回归；
- Reviewer 结论。