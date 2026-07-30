# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 17:30 +08:00  
> 当前交接：Ticket 18/20 代码已实现；Ticket 21 文档与证据已推进；**Windows GPU 最终验收仍未关闭**  
> 当前状态：`T14-15-19-CLOSED / T16-17-PASS-CODE / T18-20-IMPL-AWAITING-REVIEW / T21-DOCS-PARTIAL-GPU-PENDING / BATCH2-NOT-DONE`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 21 规约](../.scratch/batch2-training-data-and-sampling/issues/21-docs-handoff-windows-gpu-final-acceptance.md)
2. [Ticket 21 Summary](../.scratch/batch2-training-data-and-sampling/reports/21-docs-handoff-windows-gpu-final-acceptance-summary.md)
3. [Windows GPU 验收记录](../.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md)
4. [Wave 1 Independent Review Round 4](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round4.md)
5. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)
6. [options-json 权威参考](../docs/implementation/options-json-training-configuration-reference.md)
7. Ticket 18 / 20 summary（reports 目录）

---

## 2. 统一工作分支

```text
codex/batch2-ticket19-loss-window
```

```text
实现者不得自行签发 APPROVED / PASS / CLOSED / Batch 2 DONE
current.md 可由实现者更新事实状态，但最终签发仍归独立 Reviewer / 集成负责人
```

---

## 3. Commit 锚点（实现侧）

```text
Unicode paths：     e173ea6
Ticket 20：         1ca7f17
Ticket 18：         9a2c28b
Wave 1 Review R4：  0742381
```

以 `git log -1` / `git rev-parse HEAD` 为准。

---

## 4. 权威状态

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED
Ticket 16：APPROVED / PASS-CODE（GPU/thread 归因 deferred）
Ticket 17：APPROVED / PASS-CODE（1k/10k perf deferred）
Ticket 19：APPROVED / PASS / CLOSED

Ticket 18：IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEW
Ticket 20：IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEW
           --options-json §9.1–9.2 已同步

Ticket 21：DOCS + HANDOFF PARTIAL
           Windows GPU SAEHD 矩阵：PENDING-WINDOWS-GPU
           本机验收 Python：无 TensorFlow
           禁止 Batch 2 DONE
```

---

## 5. 测试证据（非 GPU）

```text
Windows / Python 3.11.7 / spawn
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
→ OK / EXIT=0（实现侧最近记录约 Ran 327）
含 Unicode 中文路径用例
```

---

## 6. Frontier（下一步）

```text
1. 独立 Review Ticket 18 + 20
2. 在装有 TF+CUDA 的 Windows 机上执行 Ticket 21 Matrix A/B（SAEHD fp32 + AdaBelief ≥500，save/exit/resume ≥200）
3. 填写 windows-gpu-acceptance.md 实机段落
4. 独立 Reviewer 决定是否签发 Batch 2 DONE / 允许合入 main
```

```text
Ticket 21：未 resolved（缺 GPU 证据）
Batch 3：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```

---

## 7. 安全判断

```text
legacy_random / legacy_uniform_yaw：可继续使用
Analyzer：开发/验收可用；中文路径必须支持
pose_balanced / quality_pose_balanced：可用于开发测试
生产签发 / 合入 main：禁止，直到 Ticket 21 GPU 门关闭
```
