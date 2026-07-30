# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Wave 1 三票实现完成 + 实现侧集中对照审计）  
> 当前交接：Ticket 16/17/19 均 IMPLEMENTATION COMPLETE；等待**独立** Wave 1 Final Review  
> 当前状态：`TICKET14-PASS / TICKET15-PASS-CLOSED / WAVE1-IMPL-COMPLETE / AWAITING-INDEPENDENT-REVIEW`

---

## 1. 最新必读入口

1. [Wave 1 集中对照审计 R1](../.scratch/batch2-training-data-and-sampling/reports/wave1-central-review-round1.md)
2. [Ticket 19 Summary](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-summary.md)
3. [Ticket 17 Summary](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md)
4. [Ticket 16 Summary](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-summary.md)
5. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
6. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
7. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)
8. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)

### Commit 锚点

```text
Ticket 15 Review R2 Final：4fd7d062cc817589fd964efdae3bd3e793247b68
Ticket 16 impl：           f9f846ab255a97005890a4ed7b6d3740ee4119e8
Ticket 17 impl：           e0e619ae7acc2b25e2f422db1b8efd5597723e55
Ticket 19 impl：           3f7c4cb7e907021bb0ef8f5c2f1eb544fa1e1032
含 16+17+19 的开发分支：  codex/batch2-ticket19-loss-window @ 3f7c4cb
推荐集成分支名：           codex/batch2-wave1-integration（待创建/推送）
```

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED
Ticket 16：IMPLEMENTATION COMPLETE / UNIT-SPAWN PASS / PENDING-SAEHD-GPU / AWAITING INDEPENDENT REVIEW
Ticket 17：IMPLEMENTATION COMPLETE / FUNCTIONAL PASS / PARTIAL-PERF / AWAITING INDEPENDENT REVIEW
Ticket 19：IMPLEMENTATION COMPLETE / CONTRACT PASS / AWAITING INDEPENDENT REVIEW
           （实现者不得签发 APPROVED/PASS/CLOSED）
Ticket 18：WAVE 2 / provisional OK after 17 SHA e0e619a
Ticket 20：WAVE 2 / provisional OK after 16+17
```

---

## 2. Wave 1 执行模式（回顾）

```text
多 Agent 并行 → 独立分支/commit → Wave 集成 → 集中 Review → remediation → Final Review
```

本会话单 Agent 串行完成 16 → 17 → 19，commits 仍可拆开审查。

---

## 3. 组合测试证据（实现侧）

```text
Ran 82 focused tests / OK / EXIT=0
覆盖：Host spawn、Generator debug=False、strong FP、workers、stale、loss window、loader、analyzer core
```

---

## 4. 实现侧审计摘要（非正式签发）

详见 `wave1-central-review-round1.md`。

```text
16：MEETS unit/spawn；GAP SAEHD GPU
17：MEETS functional；GAP large perf
19：MEETS contract
交叉：无阻塞性冲突
```

---

## 5. Wave 2 入口

```text
Ticket 18：依赖 17 → base e0e619a
Ticket 20：依赖 16+17
Ticket 21：依赖 14—20 全部 + Windows GPU
```

---

## 6. 安全判断

```text
legacy_random / legacy_uniform_yaw：继续可用
pose_balanced / quality_pose_balanced：独立 Review + SAEHD GPU + Wave2 前不用于正式生产结论
```

---

## 7. 建议下一步

1. 独立 Reviewer 阅读 wave1-central-review-round1.md 并按票签发  
2. `git checkout -b codex/batch2-wave1-integration` 从当前 HEAD 推送  
3. Windows GPU SAEHD 验收关闭 Ticket 16 剩余 GAP  
4. 启动 Ticket 18 / 20  
