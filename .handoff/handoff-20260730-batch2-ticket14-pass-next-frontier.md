# Handoff — Ticket 14 最终 PASS 与 Batch 2 下一阶段并行任务

> 时间：2026-07-30 09:03 +08:00  
> 分支：`codex/batch2-metadata-sampling-design`  
> Ticket 14：`APPROVED / PASS / CLOSED`  
> Batch 2：`REMEDIATION IN PROGRESS / PENDING WINDOWS SPAWN / PENDING WINDOWS GPU`

---

## 1. 本次状态变化

Ticket 14 最终实现：

```text
37e99255e195d73dbd3720858ec1a93b4c8619cc
```

最终独立 Review：

```text
.scratch/batch2-training-data-and-sampling/reports/
14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md

Review Commit:
94f57f9ec9c488d140eb37fbe0ba03fa26f1b020
```

最终结论：

```text
Canonical bucket：PASS
Analyzer → Loader → Policy E2E：PASS
Ordinary / Packed：PASS
Per-sample validity arrays：PASS
Warning bounded contract：PASS
Ticket 14：CLOSED
```

---

## 2. 当前并行 Frontier

从 Ticket 14 PASS 后，允许四条独立施工线同时启动。**每条线由不同 Agent 负责，不得让同一弱模型同时承担多个 Ticket。**

### Lane A — Ticket 15

```text
Ticket：15-fix-options-json-and-src-dst-sampling-contract.md
等级：P0 BLOCKER
状态：UNBLOCKED / OPEN
```

目标：

```text
--options-json 权威层级
training.enabled + metadata_sampling 双 Gate
扁平 sampling 向后兼容
sampling.src / sampling.dst 独立覆盖与继承
错误层级配置显式 warning
SRC / DST 最终配置分别打印
文档与实现同步
```

施工要求：

- 先画真实调用链：`main.py → ModelBase → SAEHD → EnhancementConfig → SamplingConfig → Runtime`；
- 不得只按旧文档修改；
- 不得重新解释 Ticket 14 的 metadata contract；
- 结束后必须独立 Review，确认错误层级不会静默失效。

建议工作分支：

```text
codex/batch2-ticket15-config-contract
```

### Lane B — Ticket 16

```text
Ticket：16-fix-weighted-index-host-windows-spawn.md
等级：P0 BLOCKER / HIGH RISK
状态：UNBLOCKED / OPEN
强制 Reviewer：是
```

第一优先问题：

```text
全量 test_batch2_*.py unittest 已 OK，
但 Windows 解释器退出阶段 daemon host thread 抢 stderr 锁，
shell exit code = -1073740791。
```

目标：

```text
WeightedIndexHostClient 明确 pickle contract
worker 不持有 Host Python 对象
Windows spawn 真实进程测试
debug=False Generator 链路
close / fatal / timeout / 多 worker / N<batch
host thread 确定性关闭
测试进程 exit code 0
```

施工要求：

- 开工前先提交最小 spawn 复现结果；
- macOS/Linux 只能做 spawn 模拟，最终需要 Windows 实机；
- 施工 Agent 不得自行签 PASS；
- 禁止 broad fallback 掩盖 worker/Host 错误。

建议工作分支：

```text
codex/batch2-ticket16-windows-spawn
```

### Lane C — Ticket 17

```text
Ticket：17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md
等级：P1 HIGH
状态：UNBLOCKED / OPEN
风险：Packed I/O / 多进程 / 缓存一致性
```

建议分两个连续阶段施工，但仍属于同一个 Ticket：

```text
17A：signature / trusted match / stale detection
17B：workers / strong fingerprint / Windows spawn-safe analyzer worker
```

目标：

```text
--workers 真正生效或删除
--strong-fingerprint 真正生效或删除
Quick / Strong signature 契约
逐样本 signature compare
id matched / signature matched / stale / missing 分离
sampling usability 基于 trusted ratio
Ordinary / Packed stale replacement tests
```

施工要求：

- 优先完成 17A，再进入 17B；
- 不得一次性大改 Loader、Analyzer、Incremental 后仅靠 smoke 数量宣称完成；
- 必须验证 Packed raw bytes 获取方式和 worker pickle 安全；
- 完成后解锁 Ticket 18。

建议工作分支：

```text
codex/batch2-ticket17-fingerprint-workers
```

### Lane D — Ticket 19

```text
Ticket：19-fix-loss-window-save-boundary-and-observability.md
等级：P1 HIGH
状态：OPEN / INDEPENDENT
Blocked by：无
```

目标：

```text
保存前冻结 end_index
保存成功后统计 [start_index:end_index]
保存失败不消费窗口
首次 / 自动 / 手动 / target / exit 保存统一
恢复训练不混入旧 history
无新 loss 产生 empty window
日志带 reason / count / mean / median / last / min / max
Trainer 时序测试而非只有纯函数测试
```

施工要求：

- 不修改 Loss 公式、训练步骤或 checkpoint 格式；
- 必须覆盖保存失败异常传播；
- 完成后独立 Review 保存边界和窗口离线重算。

建议工作分支：

```text
codex/batch2-ticket19-loss-window-boundary
```

---

## 3. 后续依赖

```text
Ticket 14：PASS

15 ─┐
16 ─┼──> 20
17 ─┘
 |
 └──> 18

19：独立进行

14—20 全部 PASS
      ↓
21：文档、交接、Windows GPU 最终验收
```

具体状态：

```text
Ticket 15：UNBLOCKED
Ticket 16：UNBLOCKED
Ticket 17：UNBLOCKED
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT
Ticket 20：BLOCKED-BY-15+16+17
Ticket 21：BLOCKED-BY-14—20
```

---

## 4. Agent 分配规则

必须遵守：

1. 一个弱模型一次只领取一个 Ticket；
2. Ticket 15、16、17、19 使用相互独立的工作分支；
3. 每个 Ticket 从当前 Ticket 14 PASS 后的共同基线开始；
4. 施工前先输出源码事实复核和计划，不得直接编码；
5. Summary 自审 PASS 不等于独立 Review PASS；
6. Ticket 16 和 Ticket 20 必须强模型独立 Review；
7. Ticket 17 与 Ticket 18 不得由同一弱模型连续无 Review 地完成；
8. Ticket 21 不得在任何代码 Ticket 未关闭时提前施工；
9. 不修改 SAEHD 网络、Loss 公式、optimizer、checkpoint、DFM、Merge 或 `faceset.pak` 格式；
10. 所有增强继续默认关闭。

---

## 5. 每条施工线的交付物

每个 Ticket 必须提交：

```text
1. 实际源码修改
2. 新增/更新自动测试
3. 完整 Base / Head SHA
4. Python / OS / 关键依赖版本
5. compileall 结果
6. 相关测试 Ran N / OK / failures / skips
7. 全量相关 smoke 结果与 shell exit code
8. Ticket Summary
9. 独立 Review 报告
10. current.md 状态同步
```

不得使用：

```text
只改 Summary
只增加测试数量
删除或放宽旧断言
debug=True 代替真实多进程
macOS fork 代替 Windows spawn
broad except 代替异常分类
```

---

## 6. Batch 2 安全状态

当前允许：

```text
legacy_random
legacy_uniform_yaw
Faceset Analyzer 报告与开发验证
```

当前仍不得用于正式训练结论：

```text
pose_balanced
quality_pose_balanced
```

直到 Ticket 15—20 全部 PASS，并由 Ticket 21 完成 Windows GPU、四种 mode、SRC/DST、Save/Exit/Resume 和文档一致性最终验收。

Batch 3 在 Ticket 21 最终签发前继续保持 BLOCKED。
