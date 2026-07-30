# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 14:20 +08:00  
> 当前交接：Batch 2 Wave 1（Ticket 16 / 17 / 19）独立 Review Round 1 与分票返修  
> 当前状态：`WAVE1-REVIEW-FAILED / T16-REQUEST-CHANGES / T17-REQUEST-CHANGES / T19-REQUEST-CHANGES / REMEDIATION-REQUIRED`

---

## 1. 最新必读入口

按顺序阅读：

1. [Wave 1 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round1.md)
2. [Ticket 16 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-review-round1.md)
3. [Ticket 17 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-review-round1.md)
4. [Ticket 19 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-review-round1.md)
5. [Ticket 16 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-summary.md)
6. [Ticket 17 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md)
7. [Ticket 19 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-summary.md)
8. [实现侧 Wave 1 集中对照审计](../.scratch/batch2-training-data-and-sampling/reports/wave1-central-review-round1.md)
9. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
10. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
11. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

---

## 2. 分支与 Commit 锚点

实际远端开发分支：

```text
codex/batch2-ticket19-loss-window
```

该分支包含 Ticket 15 已 Review/PASS 的配置工作，以及按顺序提交的 Ticket 16、17、19。虽然没有三个可直接访问的独立远端分支，但 implementation commits 可以分别审查：

```text
Ticket 15 Final Review：4fd7d062cc817589fd964efdae3bd3e793247b68

Ticket 16 Base：       0bb1fa094c3ddf0304eaf6cfcb9b11aac2eff400
Ticket 16 Impl：       f9f846ab255a97005890a4ed7b6d3740ee4119e8

Ticket 17 Base：       f9f846ab255a97005890a4ed7b6d3740ee4119e8
Ticket 17 Impl：       e0e619ae7acc2b25e2f422db1b8efd5597723e55

Ticket 19 Base：       c342cc56ad2fbe6402c8b0b3c64c73eaab3cbb55
Ticket 19 Impl：       3f7c4cb7e907021bb0ef8f5c2f1eb544fa1e1032

实现侧集中审计：      6991b0d7b5ce29741fe3fe8ddad91bdb3462169d
Ticket 16 Review R1： d55b657cfdafb99cfc44bf41acb8e5ec8055130a
Ticket 17 Review R1： 61e562fe8bfc11279cd12f08ee6ace52d4b87951
Ticket 19 Review R1： cd2af36789babc359868f43a3ac8efb7d383536f
Wave 1 Review R1：   c70b00daee84ff348534ec0681a75b2bfdc2d8d0
```

当前分支已经承担 Wave 1 集成与 Review 入口，不需要再为了命名额外创建一个空的 `codex/batch2-wave1-integration` 分支。

---

## 3. 独立 Reviewer 权威结论

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED

Ticket 16：REQUEST_CHANGES
  SPAWN CORE FIXED
  WORKER / QUEUE / THREAD DETERMINISTIC REAP NOT CLOSED
  WINDOWS SAEHD SAVE / EXIT / RESUME NOT PROVEN

Ticket 17：REQUEST_CHANGES
  WORKERS + STRONG HASH FOUNDATION EXISTS
  UNSIGNED TRUST CONTRACT BROKEN
  STRICT ATOMIC WRITE CONTRACT BROKEN
  QUICK/STRONG IO DUPLICATED
  INCREMENTAL / PERF MATRIX NOT CLOSED

Ticket 19：REQUEST_CHANGES
  LOSS WINDOW TRACKER FOUNDATION ACCEPTED
  REAL TRAINER INITIAL / TARGET / EXIT CONTROL FLOW BROKEN
  SAVE FAILURE PROPAGATION NOT CLOSED

Wave 1 Integration：REQUEST_CHANGES
```

实现侧 Summary 或 `wave1-central-review-round1.md` 的自审建议不能覆盖以上独立结论。

---

## 4. Ticket 16 剩余阻断

```text
T16-R1-01  finalize join 超时后无条件 g.p=None，可能丢失活 worker 句柄
T16-R1-02  现有测试读取已清空的 g.p，残留 worker 可伪通过
T16-R1-03  SubprocessGenerator IPC Queue / feeder thread 无显式 cleanup
T16-R1-04  Host thread join 超时仍被标记为成功 close
T16-R1-05  完整 discover exit=0 与 Windows SAEHD 500+200 save/exit/resume 未完成
```

返修目标：

```text
terminate → join → kill（必要时）→ join → 确认 exitcode
只有真实退出后才能清空 Process 句柄
Queue/thread cleanup 幂等且可验证
完整 Batch smoke 进程 exit code 0
Windows SAEHD 无残留 worker
```

---

## 5. Ticket 17 剩余阻断

```text
T17-R1-01  unsigned legacy record 仍被计入 trusted 并装载旧 pose/quality
T17-R1-02  strict invalid 在正式 Sidecar 写入后才返回非零
T17-R1-03  quick 因 `or True` 完整读取文件，不是 bounded I/O
T17-R1-04  CLI 主进程预读/hash + worker 再读/hash，重活串行且 I/O 翻倍
T17-R1-05  strong raw/hash 失败可写出半完整 strong record
T17-R1-06  incremental output 丢失 Ticket 14 canonical analysis_config 字段
T17-R1-07  incremental tests 仍使用旧顶层 Schema / 字符串 signature
T17-R1-08  trusted/strict/fatal/migration/1k/10k/RSS 验收矩阵未完成
```

固定安全语义：

```text
ID hit 但没有 signature：record_matched=True，trusted=False
不得装载旧 pose/quality
strict invalid / worker fatal：旧 Sidecar 保持不变
Ticket 14 canonical bucket contract 不得回退
```

---

## 6. Ticket 19 剩余阻断

```text
T19-R1-01  每轮先 3 warmup + 1 timed，之后检查 iter==1，initial save 不可达
T19-R1-02  target 可被同一训练组越过多个 batch
T19-R1-03  close 已排队仍会先训练额外 batch
T19-R1-04  save 异常被 trainerThread 最外层转换成普通 close
T19-R1-05  日志缺 start/end iter 或 index range
T19-R1-06  _record_train_loss broad except 静默丢统计
T19-R1-07  FakeModel 测试复制 helper，未执行真实 Trainer 控制流
T19-R1-08  完整 discover 与 shell exit code 未记录
```

返修必须测试真实 Controller/Trainer control flow，不得继续只验证复制出来的 `_model_save_helper`。

---

## 7. 当前 Frontier 与返修安排

三票可以由不同 Agent 并行返修，但每票必须保持独立 commit 和独立 Summary：

```text
Lane A：Ticket 16 生命周期 / Windows 验收返修
Lane B：Ticket 17 trust / strict / bounded I/O / incremental 返修
Lane C：Ticket 19 Trainer 保存状态机返修
```

建议从 `codex/batch2-ticket19-loss-window` 最新 HEAD 创建返修分支：

```text
codex/batch2-wave1-r1-ticket16-remediation
codex/batch2-wave1-r1-ticket17-remediation
codex/batch2-wave1-r1-ticket19-remediation
```

规则：

1. 一个 Agent 一次只负责一票；
2. 不在三个返修分支同时修改 `.handoff/current.md`；
3. 每个 Agent 只更新自己的 Ticket Summary；
4. 集成负责人合并三票后统一更新 `current.md`；
5. 不得把三个返修压成无法拆分的单 commit；
6. 实现者不得自行签发 APPROVED/PASS/CLOSED。

---

## 8. 后续依赖

```text
Ticket 18：BLOCKED-BY-TICKET17-REMEDIATION
Ticket 20：BLOCKED-BY-TICKET16+17-REMEDIATION
Ticket 21：BLOCKED-BY-TICKET14—20 + WINDOWS GPU
Batch 3：BLOCKED
```

如果 Ticket 18/20 已提前开始 provisional 开发，必须标记：

```text
PENDING-UPSTREAM-REMEDIATION
```

不得基于当前 Ticket 16/17 接口签发完成。

---

## 9. 测试要求

每票 focused tests 之外，Wave 1 重新集成后必须执行：

```bash
python -m compileall core/joblib samplelib mainscripts models
python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

必须记录：

```text
完整 Base / Head SHA
Windows / Python / multiprocessing start method
Ran N tests
OK / failures / errors / skips
shell exit code
multiprocessing.active_children() / Host thread / worker exit 状态
```

Ticket 16 另外必须执行 Windows SAEHD：

```text
FP32 + AdaBelief 至少 500 iter
manual save
exit
resume 至少 200 iter
无残留 worker / 无 timeout / 无静默 fallback
```

GitHub 当前无 Actions/status check，不得描述为 CI PASS。

---

## 10. 安全判断

```text
legacy_random / legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：仅开发验证；Ticket 17 返修前不得信任 unsigned legacy sidecar
pose_balanced / quality_pose_balanced：Wave 1 + Ticket 18/20 + Windows GPU 完成前不用于正式生产结论
禁止合入 main
禁止签发 Batch 2 DONE
```
