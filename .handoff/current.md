# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 14:47 +08:00  
> 当前交接：Batch 2 Wave 1（Ticket 16 / 17 / 19）独立 Review Round 1 与统一分支返修  
> 当前状态：`WAVE1-REVIEW-FAILED / T16-REQUEST-CHANGES / T17-REQUEST-CHANGES / T19-REQUEST-CHANGES / SINGLE-BRANCH-REMEDIATION`

---

## 1. 最新必读入口

按顺序阅读：

1. [统一返修与 Review 工作分支约定](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-and-review-working-branch-policy.md)
2. [Wave 1 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round1.md)
3. [Ticket 16 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-review-round1.md)
4. [Ticket 17 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-review-round1.md)
5. [Ticket 19 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-review-round1.md)
6. [Ticket 16 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-summary.md)
7. [Ticket 17 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md)
8. [Ticket 19 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-summary.md)
9. [实现侧 Wave 1 集中对照审计](../.scratch/batch2-training-data-and-sampling/reports/wave1-central-review-round1.md)
10. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
11. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
12. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

---

## 2. 统一工作分支

当前唯一 Wave 1 返修、Review 与文档存储分支：

```text
codex/batch2-ticket19-loss-window
```

该分支已包含 Ticket 15、16、17、19 的完整演进链，后续不再强制创建三个独立远端 remediation 分支，也不额外创建空的 `codex/batch2-wave1-integration` 分支。

统一存储：

```text
Ticket 16/17/19 待修复问题
修复建议和设计说明
每票 remediation commits
每票 Summary
独立 Review Round N
Wave 集成 Review
测试与 Windows/GPU 验收证据
.handoff/current.md
```

单分支不等于混合提交。必须继续保持：

```text
Ticket 16 独立 remediation commit(s)
Ticket 17 独立 remediation commit(s)
Ticket 19 独立 remediation commit(s)
必要的跨票 integration commit
每票独立 Summary 与 focused tests
```

禁止把三个 Ticket 的代码修复压成一个无法拆分的巨型 commit。

---

## 3. Commit 锚点

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
工作分支约定：        374e16eaaaf04913e92ffd4748df2d58ebea50c1
```

---

## 4. 独立 Reviewer 权威结论

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

实现侧 Summary 或 `wave1-central-review-round1.md` 的自审建议不能覆盖以上独立结论。实现 Agent 不得自行签发 `APPROVED / PASS / CLOSED / RESOLVED`。

---

## 5. Ticket 16 剩余阻断

```text
T16-R1-01  finalize join 超时后无条件 g.p=None，可能丢失活 worker 句柄
T16-R1-02  现有测试读取已清空的 g.p，残留 worker 可伪通过
T16-R1-03  SubprocessGenerator IPC Queue / feeder thread 无显式 cleanup
T16-R1-04  Host thread join 超时仍被标记为成功 close
T16-R1-05  完整 discover exit=0 与 Windows SAEHD 500+200 save/exit/resume 未完成
```

固定返修目标：

```text
terminate → join → kill（必要时）→ join → 确认 exitcode
只有真实退出后才能清空 Process 句柄
Queue / feeder thread / Host thread cleanup 幂等且可验证
测试保存 finalize 前的原始 Process 句柄
multiprocessing.active_children() 无新增残留
完整 Batch smoke shell exit code 0
Windows SAEHD 500 iter + manual save + exit + resume 200 iter
无 timeout / 无静默 fallback / 无残留 worker
```

---

## 6. Ticket 17 剩余阻断

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
unsigned/stale record 不得装载旧 pose/quality
strict invalid / worker fatal / strong hash failure：旧 Sidecar 保持不变
Ticket 14 canonical bucket contract 不得回退
full/force run 不在主进程预读全部 signature
quick 使用 bounded first/last reads
strong bytes/hash 只读取计算一次
incremental 输出与 full 输出使用同一 canonical builder
```

---

## 7. Ticket 19 剩余阻断

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

固定返修目标：

```text
每次 train_one_iter 后立即检查 initial / target boundary
训练前先处理高优先级 close/save 控制命令
target 不得被 warmup 越过
close 已排队时不得再执行完整训练组
save failure 必须向主线程结构化传播，不得伪装为普通 close
日志包含 reason、checkpoint iter、window count、start/end range
tracker degraded 必须有 bounded warning
测试真实 Controller 或 trainerThread harness，不得复制理想 helper
```

---

## 8. 统一分支返修执行规则

允许不同 Agent 依次或并行准备修改，但写入该远端分支时必须保持提交边界清晰：

```text
Lane A：Ticket 16 生命周期 / Windows 验收返修
Lane B：Ticket 17 trust / strict / bounded I/O / incremental 返修
Lane C：Ticket 19 Trainer 保存状态机返修
```

提交规则：

1. 一个 remediation commit 只处理一个 Ticket；
2. commit message 必须包含 Ticket 号或明确主题；
3. 每票只更新自己的代码、测试和 Summary；
4. 跨票适配单独提交 integration commit；
5. 不要求每个实现 Agent 修改 `current.md`；
6. `current.md` 由集成负责人或独立 Reviewer 在关键节点统一更新；
7. Review 文档全部存入 `.scratch/batch2-training-data-and-sampling/reports/`；
8. 不再创建仅用于存储 Review 文档的额外分支。

推荐提交形态：

```text
fix(ticket16): ...
docs(ticket16): update remediation summary
fix(ticket17): ...
docs(ticket17): update remediation summary
fix(ticket19): ...
docs(ticket19): update remediation summary
test(wave1): record integrated regression
review(wave1): issue independent round2 conclusion
```

---

## 9. 后续依赖

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

## 10. Wave 1 Final Review 前测试要求

每票 focused tests 之外，统一分支完成全部返修后必须执行：

```bash
python -m compileall core/joblib samplelib mainscripts models
python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

必须记录：

```text
完整 Base / Head SHA
每个 Ticket remediation commit SHA
Windows / Python / multiprocessing start method
Ran N tests
OK / failures / errors / skips
shell exit code
multiprocessing.active_children()
Host thread / worker Process / Queue feeder thread 状态
```

Ticket 16 另外必须执行 Windows SAEHD：

```text
FP32 + AdaBelief 至少 500 iter
manual save
exit
resume 至少 200 iter
无残留 worker / 无 timeout / 无静默 fallback
```

Ticket 17 另外必须记录 1k/10k：

```text
workers=1 / 2 / auto
quick / strong
ordinary / packed
elapsed / samples per second / peak RSS
```

GitHub 当前无 Actions/status check，不得描述为 CI PASS。

---

## 11. 安全判断

```text
legacy_random / legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：仅开发验证；Ticket 17 返修前不得信任 unsigned legacy Sidecar
pose_balanced / quality_pose_balanced：Wave 1 + Ticket 18/20 + Windows GPU 完成前不用于正式生产结论
禁止合入 main
禁止签发 Batch 2 DONE
```
