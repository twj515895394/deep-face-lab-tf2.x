# Batch 2 Wave 1 — 统一返修与 Review 工作分支约定

> 生效日期：2026-07-30 14:47 +08:00  
> 当前统一分支：`codex/batch2-ticket19-loss-window`  
> 适用范围：Ticket 16、17、19 的待修复问题整理、修复建议、实施 Summary、Review 报告、测试证据与 Handoff。

---

## 1. 决策

`codex/batch2-ticket19-loss-window` 已经包含 Ticket 15、16、17、19 的完整提交链，并且各 Ticket 的 implementation commit 边界仍可独立识别。

因此，Wave 1 返修期间不再强制创建：

```text
codex/batch2-wave1-r1-ticket16-remediation
codex/batch2-wave1-r1-ticket17-remediation
codex/batch2-wave1-r1-ticket19-remediation
```

统一在当前分支存储：

```text
待修复问题清单
修复建议与设计说明
每票 implementation/remediation Summary
独立 Review Round N
Wave 集成 Review
测试输出与验收记录
.handoff/current.md
```

---

## 2. 单分支不等于混合提交

虽然使用同一个远端分支，Ticket 16、17、19 仍必须保持可独立审查：

```text
一个 Ticket 一组独立 remediation commit
commit message 必须带 Ticket 号或明确主题
不得把 16/17/19 的代码修复压成一个不可拆分 commit
每票单独更新自己的 Summary
每票单独记录 focused tests、环境和 exit code
跨票适配必须使用独立 integration commit
```

推荐提交顺序：

```text
fix(ticket16): ...
docs(ticket16): update remediation summary

fix(ticket17): ...
docs(ticket17): update remediation summary

fix(ticket19): ...
docs(ticket19): update remediation summary

test(wave1): run integrated regression
review(wave1): record final independent review
```

允许顺序调整，但必须保留独立 commit 边界。

---

## 3. 文档存储规则

所有 Review 与返修文档统一放在：

```text
.scratch/batch2-training-data-and-sampling/reports/
```

命名建议：

```text
16-...-remediation-summary.md
16-...-review-round2.md
17-...-remediation-summary.md
17-...-review-round2.md
19-...-remediation-summary.md
19-...-review-round2.md
wave1-remediation-summary.md
wave1-independent-review-round2-final.md
```

原始 Ticket 规约继续保存在：

```text
.scratch/batch2-training-data-and-sampling/issues/
```

不得通过修改原始 Ticket 来弱化已经冻结的验收条件；如确需变更契约，必须单独记录维护者决策。

---

## 4. `current.md` 所有权

在统一分支模式下：

- 每次一个 Agent 完成一票代码返修后，可以在自己的 Summary 中记录状态；
- 不要求每个实现 Agent 都修改 `.handoff/current.md`；
- `current.md` 由集成负责人或独立 Reviewer 在关键节点统一更新；
- 关键节点包括：某票提交完成、Wave 集成测试完成、独立 Review 签发、依赖解锁。

实现者不得自行将状态改为：

```text
APPROVED
PASS
CLOSED
RESOLVED
```

上述状态只能由独立 Reviewer 签发。

---

## 5. 当前返修优先级

```text
P0-A：Ticket 16 确定性 worker/queue/thread 回收
P0-B：Ticket 17 unsigned trust、strict pre-write gate、strong 完整性
P0-C：Ticket 19 Trainer first/target/close/save-failure 状态机
```

之后处理：

```text
Ticket 17 bounded quick I/O、消除重复读取、incremental canonical contract
Ticket 19 range observability 与 degraded tracker warning
Ticket 16 Windows SAEHD 500 + save/exit/resume 200
Wave 1 完整 Batch smoke 与 shell exit code 0
```

---

## 6. 合并与 Review Gate

统一分支中的每票返修完成后，先分别做代码 Review，再做一次 Wave 集成 Review。

最终 PASS 前必须满足：

```text
Ticket 16 独立 PASS
Ticket 17 独立 PASS
Ticket 19 独立 PASS
Wave 1 integrated smoke PASS
完整 test_batch*.py discover exit 0
Windows SAEHD 验收完成
无残留 worker/thread/process
GitHub 无 CI 时明确标记为人工/本机证据，不得写 CI PASS
```

当前仍禁止合入 main，也不得解锁 Ticket 18/20 的最终签发。
