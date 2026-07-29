# H-015 — Batch 2 Ticket 13：训练 Loss 窗口统计与可观测性

> 日期：2026-07-29  
> 分支：`codex/batch2-metadata-sampling-design`  
> 状态：已完成 (macOS 轻量验证 PASS, 175/175 测试通过)

## 1. 背景

Batch 1 Windows FP32 + AdaBelief 测试发现保存日志中的 SRC/DST loss 相比旧版 TF1.x 明显跳动。源码核对确认，当前 `mainscripts/Trainer.py` 保存时直接展示：

```python
loss_history[-1]
```

这表示最后一个 batch 的 loss，而不是上一次保存至本次保存之间的平均值。单 batch 会受到样本难度和随机增强影响，天然上下波动。

## 2. 决策

不打断正在进行的 Batch 2 Metadata/Sampling 开发，新增末尾独立 Ticket 13：

```text
.scratch/batch2-training-data-and-sampling/issues/
13-loss-window-logging-and-observability.md
```

对应 GitHub Issue：

```text
#3 Batch 2 Ticket 13: 恢复训练日志区间平均 Loss 并保留单步诊断值
```

## 3. 修复范围

主日志恢复保存窗口 arithmetic mean：

```text
[time][#iter][iter_time][src_mean][dst_mean]
```

同时保留诊断：

```text
count
last
median
可选 min/max
```

窗口必须按 loss history 记录或独立 pending buffer 管理，不允许直接假设：

```text
model iter == loss_history index
```

## 4. 关键生命周期规则

```text
Trainer 新 session 启动
→ 窗口起点为当前已加载 history 末尾
→ 只统计本 session 新增 loss
```

```text
save 成功
→ 输出窗口统计
→ 消费窗口
```

```text
save 失败
→ 错误继续传播
→ 不消费窗口
→ 不输出伪造成功统计
```

空窗口不得输出 `0.0000` 伪 loss。

## 5. 明确不修改

- SAEHD Loss；
- optimizer；
- 学习率；
- finite gate；
- sample generator；
- Batch 2 sampling probability；
- checkpoint / data.dat 格式；
- preview loss history。

## 6. 主要验收

- 保存主值为窗口 mean；
- mean 与离线 NumPy 重算一致；
- last/count 可追溯；
- save/resume 不混入旧 session；
- 保存失败不消费窗口；
- history 裁剪无遗漏、无重复；
- 手动/自动保存同一口径；
- Windows 至少观察 3 个保存窗口；
- 不要求 mean 单调下降，真实发散仍必须可见；
- 统计热路径开销不超过 0.5%。

## 7. 执行顺序

默认：

```text
Ticket 12
↓
Ticket 13
↓
Batch 2 最终收口
```

如 Ticket 11 Windows 验收时日志口径妨碍判断，可以提前实施，但必须独立提交、独立测试和独立 summary，不得混入 Ticket 09/10。

## 8. Summary 输出

```text
.scratch/batch2-training-data-and-sampling/reports/
13-loss-window-logging-and-observability-summary.md
```

## 9. 当前变更

- 新建 GitHub Issue #3；
- 新建 Ticket 13 详细设计；
- 未修改任何运行时代码；
- 未执行训练或测试。