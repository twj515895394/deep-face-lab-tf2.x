# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 15:35 +08:00  
> 当前交接：Batch 2 Wave 1 返修已完成代码提交，独立 Review Round 2 已签发  
> 当前状态：`WAVE1-R2-REQUEST-CHANGES / T16-CODE-ACCEPTED-ACCEPTANCE-OPEN / T17-REQUEST-CHANGES / T19-REQUEST-CHANGES`

---

## 1. 最新必读入口

按顺序阅读：

1. [Wave 1 独立 Review Round 2](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round2.md)
2. [Wave 1 Remediation Summary](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-summary.md)
3. [统一返修与 Review 工作分支约定](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-and-review-working-branch-policy.md)
4. [Wave 1 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round1.md)
5. [Ticket 16 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-review-round1.md)
6. [Ticket 17 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-review-round1.md)
7. [Ticket 19 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/19-fix-loss-window-save-boundary-and-observability-review-round1.md)
8. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
9. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
10. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

---

## 2. 统一工作分支

当前唯一 Wave 1 返修、Review 与文档分支：

```text
codex/batch2-ticket19-loss-window
```

后续继续在该分支按 Ticket 独立提交，不再创建空的 integration 分支。

```text
一个 remediation commit 只处理一个 Ticket
跨票适配使用独立 integration/test commit
实现者不得自行签发 APPROVED / PASS / CLOSED
current.md 由独立 Reviewer 或集成负责人更新
```

---

## 3. Commit 锚点

```text
Wave 1 R2 Review Base： 1a9efbdb7efe3d5ae4c3d3db61bf7f986cd1cb0c
Ticket 16 remediation： bad8e83bb99de95624e3ccd6c95f43ab5bb4162f
Ticket 17 remediation： d818ce31791a32f20db1e9a2e4ce8a2da83216a0
Ticket 19 remediation： 3d017bf5f80d6984024cbf59bd9aa78adb21b7c0
Wave 1 remediation docs：7a83d1ec64f17b57d1874181c4f40dcb2ed76256
Wave 1 Review R2：     0f09e44314bc0bdbaf0c9406ed3ca41ca745679e
```

历史锚点：

```text
Ticket 14 Final：      37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 Final Review：4fd7d062cc817589fd964efdae3bd3e793247b68
Ticket 16 Impl R1：    f9f846ab255a97005890a4ed7b6d3740ee4119e8
Ticket 17 Impl R1：    e0e619ae7acc2b25e2f422db1b8efd5597723e55
Ticket 19 Impl R1：    3f7c4cb7e907021bb0ef8f5c2f1eb544fa1e1032
Wave 1 Review R1：     c70b00daee84ff348534ec0681a75b2bfdc2d8d0
```

---

## 4. Round 2 权威结论

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED

Ticket 16：CODE REMEDIATION ACCEPTED
           ACCEPTANCE EVIDENCE OPEN
           NOT PASS / NOT CLOSED

Ticket 17：REQUEST_CHANGES
           TRUST / STRICT / BOUNDED IO CORE FIXED
           INCREMENTAL CANONICAL CONTRACT BROKEN
           PERF / FAILURE MATRIX OPEN

Ticket 19：REQUEST_CHANGES
           CONTROL FLOW FOUNDATION ACCEPTED
           MAIN-THREAD FAILURE PROPAGATION BROKEN
           DEGRADED WARNING NOT BOUNDED
           TARGET=1 DUPLICATE SAVE OPEN

Wave 1 Integration：REQUEST_CHANGES
```

实现侧 Summary 或自审结论不能覆盖本独立 Review。

---

## 5. Ticket 16 当前状态

已确认关闭：

```text
worker terminate → join → kill → join
只有真实退出后清空 Process handle
测试保存 finalize 前原始 Process handle
active_children 无新增残留
Host thread join timeout 抛 RuntimeError
ModelBase/SampleGeneratorFace cleanup failure 不再无条件吞掉
```

仍需验收：

```text
完整 test_batch*.py discover：unittest OK + shell exit 0
Queue feeder thread 状态记录
Windows SAEHD FP32 + AdaBelief 500 iter
manual save / exit
resume 200 iter
训练结束无残留 worker/thread
```

Ticket 16 暂不要求推倒重写；先完成 Wave 1 代码返修和完整退出测试，再决定 Queue cleanup 是否还需调整。

---

## 6. Ticket 17 剩余阻断

### T17-R2-01：Incremental canonical builder 未统一

当前 incremental 路径虽然补回 `analysis_config.pose` canonical 字段，但仍使用旧的 `reconcile_and_finalize_samples()`，输出旧版：

```text
usable_for_sampling
pose_distribution_yaw
pose_distribution_pitch
quality_normalization
```

并读取旧顶层 record 字段：

```text
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

必须改为：

```text
full 与 incremental 使用同一 canonical finalize/builder
summary key set 完全一致
nested pose/quality contract 一致
bucket counts 一致
dataset fingerprint 一致
```

新增测试至少覆盖：

```text
full → incremental no-change exact parity
partial-change incremental exact contract parity
quick→quick / strong→strong structured reuse
quick→strong recompute
strong→quick 冻结策略
worker fatal 保持旧 Sidecar bytes/sha
```

仍需补 1k/10k workers/perf/RSS 记录。

---

## 7. Ticket 19 剩余阻断

### T19-R2-01：`op=error` 被主线程忽略

Controller 和 trainerThread 会发送结构化 error，但 `Trainer.main()` 当前只处理：

```text
no_preview：close
preview：show / close
```

随后 trainerThread 无条件发送 normal close，因此 save failure 仍可表现为正常结束。

必须：

```text
主线程显式处理 op=error
保留 reason / iter / error_type / traceback
fatal 不得按 normal close 结束
CLI/测试路径 raise 或返回非零
GUI 显示 fatal 并设置失败状态
测试 manual/scheduled/target/exit save failure
```

### T19-R2-02：degraded warning 不 bounded

当前 loss 记录异常会每个 iter 打 warning，且成功 commit 后 degraded 状态未重置。

必须：

```text
每个窗口只首次 warning
记录 degraded_count
save log 标记 window_incomplete
成功 commit 后重置当前窗口 degraded 状态
```

### T19-R2-03：target=1 重复保存

iter=1 时会先 `initial_iter` save，再同一步 `target_reached` save，第二次通常为空窗口。

必须冻结为单次 checkpoint save，并新增 save count/reason 断言。

---

## 8. 推荐返修顺序

```text
1. fix(ticket17): unify incremental canonical finalize contract
2. fix(ticket19): propagate trainer fatal errors to main
3. fix(ticket19): bound degraded warnings and dedupe target=1 save
4. test(wave1): run full discover and record shell exit 0
5. test(ticket16): record Process/Host/Queue feeder lifecycle state
6. Windows GPU: SAEHD 500 + save/exit/resume 200
7. test(ticket17): 1k/10k perf/RSS matrix
8. Independent Review Round 3
```

允许 Ticket 17 与 Ticket 19 再次并行返修；Ticket 16 的 GPU/exit 验收可同步准备。

---

## 9. 测试证据与限制

实现侧记录：

```text
Windows / Python 3.11.7 / spawn
compileall：OK
focused suite：Ran 90 / OK / EXIT=0
```

尚未完成：

```text
完整 Batch 2 discover + shell exit 0
Windows SAEHD 500 + resume 200
Ticket 17 1k/10k perf/RSS
真实 Trainer.main fatal propagation harness
```

GitHub：

```text
Actions workflow runs：none
combined status checks：none
```

独立 Reviewer 当前环境：

```text
git clone BLOCKED：无法解析 github.com
```

不得把 focused 记录写成独立 CI PASS。

---

## 10. 后续依赖与安全判断

```text
Ticket 18：BLOCKED-BY-TICKET17-REMEDIATION
Ticket 20：BLOCKED-BY-TICKET16+17-REMEDIATION
Ticket 21：BLOCKED-BY-TICKET14—20 + WINDOWS GPU
Metadata Sampling：NOT PRODUCTION READY
Batch 3：BLOCKED
```

```text
legacy_random / legacy_uniform_yaw：可继续回归和使用
Faceset Analyzer：仅开发验证
pose_balanced / quality_pose_balanced：不得用于正式生产结论
禁止合入 main
禁止签发 Batch 2 DONE
```
