# Ticket 19 — Loss Window 保存边界与可观测性 实施总结

> 当前状态：**IMPLEMENTATION COMPLETE / AWAITING WAVE-1 CENTRAL REVIEW**  
> 实现者自审：`PASS`（不得自行签发 APPROVED/PASS/CLOSED）  
> Base：`c342cc5`（含 Ticket 16+17）  
> 分支：`codex/batch2-ticket19-loss-window`  
> `--options-json`：**NA**

---

## 1. 修复前 vs 修复后时序

### 修复前

```text
训练窗口 A → model.save() → after_save=true
→ 再训练 batch B → 统计 A+B（B 未进入刚写入的 checkpoint）
```

### 修复后

```text
每次 train_one_iter 成功 → append session buffer
model_save(reason):
  freeze buffer
  model.save()          # 失败则 re-raise，buffer 保留
  立即 log 窗口 stats
  commit/clear buffer
```

不包含保存后的 batch；失败不消费窗口。

---

## 2. Tracker / buffer 设计

```text
LossWindowTracker（session-local）
  - 不依赖可能被压缩的 model.loss_history 索引
  - resume 时 buffer 为空（旧 history 不进首窗）
  - freeze / stats_for_frozen / commit
```

`compute_loss_window_stats(history, start_index=0, end_index=None)`：
- 半开区间；end=None 兼容旧行为；end<start → ValueError

---

## 3. 保存 reason

| reason | 入口 |
|---|---|
| initial_iter | iter==1 |
| scheduled | 自动保存 interval（多 interval 合并一次） |
| manual | s 键 |
| target_reached | 达目标迭代 |
| exit | Enter 退出 |

Preview 仅在 **save 成功后** 发送（scheduled/manual）。

---

## 4. 修改文件

| 文件 | 变更 |
|---|---|
| `samplelib/sampling/loss_stats.py` | end_index、Tracker、format log |
| `mainscripts/Trainer.py` | 立即窗口统计；session buffer；reason |
| `tests/smoke/test_batch2_loss_window_logging.py` | 纯函数 + tracker |
| `tests/smoke/test_batch2_trainer_save_window.py` | fake model 集成 |

未改 Loss 公式 / checkpoint / preview history 写入。

---

## 5. 测试证据

```text
python -m unittest tests.smoke.test_batch2_loss_window_logging tests.smoke.test_batch2_trainer_save_window
Ran 20 / OK / EXIT=0
```

覆盖：半开区间、empty、failed retain、compression immune、first/manual/scheduled/target/exit、log-before-next-train。

### 日志示例

```text
[Save][scheduled] iter=12000 window=1000
  src mean=0.1234 median=0.1200 last=0.1180 min=0.1100 max=0.1500
  dst mean=0.0987 median=0.0970 last=0.0950 min=0.0900 max=0.1200
```

空窗：`[Save][manual] iter=5 window=0 (empty)`（不复用旧 last）。

---

## 6. 状态

```text
IMPLEMENTATION COMPLETE
AWAITING-WAVE1-CENTRAL-REVIEW
```
