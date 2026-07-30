# Batch 2 Wave 1 — Independent Review Round 2

> Review 日期：2026-07-30  
> 工作分支：`codex/batch2-ticket19-loss-window`  
> Review Base：`1a9efbdb7efe3d5ae4c3d3db61bf7f986cd1cb0c`  
> Review Head：`7a83d1ec64f17b57d1874181c4f40dcb2ed76256`  
> Remediation commits：
> - Ticket 16：`bad8e83bb99de95624e3ccd6c95f43ab5bb4162f`
> - Ticket 17：`d818ce31791a32f20db1e9a2e4ce8a2da83216a0`
> - Ticket 19：`3d017bf5f80d6984024cbf59bd9aa78adb21b7c0`
> - Wave 1 Summary：`7a83d1ec64f17b57d1874181c4f40dcb2ed76256`
> Review 方法：独立静态源码、测试源码、Round 1 finding 与实现侧测试记录复核。Reviewer 当前执行环境无法解析 `github.com`，未能独立 clone/rerun；GitHub 无 Actions/status check。

---

## 1. Final Verdict

```text
Ticket 16：CODE REMEDIATION ACCEPTED / ACCEPTANCE EVIDENCE OPEN / NOT PASS
Ticket 17：REQUEST_CHANGES
Ticket 19：REQUEST_CHANGES
Wave 1 Integration：REQUEST_CHANGES
Ticket 18：仍 BLOCKED-BY-TICKET17
Ticket 20：仍 BLOCKED-BY-TICKET16+17
Batch 2：NOT DONE / NOT PRODUCTION READY
```

本轮返修不是无效工作。三个 Ticket 都有实质改进：

- Ticket 16 已建立 terminate → join → kill → join、原始 Process handle 验证、Host timeout 硬失败；
- Ticket 17 已关闭 unsigned trust、strict-before-write、full/force 主进程重复预读和 quick bounded signature scan；
- Ticket 19 已抽取真实 Controller，首次/目标/close 边界改为逐步检查，并增加 range 日志。

但仍存在两个 P0 代码阻断与若干验收缺口，不能签发 PASS/CLOSED。

---

## 2. Ticket 16 Review

### 2.1 已关闭的 Round 1 finding

```text
T16-R1-01  worker handle 只在确认死亡后清空：CLOSED
T16-R1-02  测试保存 finalize 前原始 Process handle：CLOSED
T16-R1-03  SubprocessGenerator 增加显式 close/finalize 与 Queue cleanup：IMPLEMENTED
T16-R1-04  Host thread join timeout 抛 RuntimeError：CLOSED
```

代码现已做到：

```text
terminate
→ join(timeout)
→ kill（必要时）
→ join(timeout)
→ 若仍 alive 则 RuntimeError
→ 只有确认退出后 p=None
```

`SampleGeneratorFace.finalize()` 与 `ModelBase.finalize()` 不再无条件吞掉 worker/host cleanup failure。测试也不再只读取已清空的 `g.p`，而是保存原始 Process 对象并检查 `is_alive()==False`、`exitcode is not None` 和 `multiprocessing.active_children()`。

### 2.2 仍开放：T16-R1-05 / Acceptance Gate

实现侧明确仍未提供：

```text
完整 python -m unittest discover -s tests/smoke -p "test_batch*.py" 的 shell exit 0
Queue feeder thread 的最终状态记录
Windows SAEHD FP32 + AdaBelief 500 iter
manual save / exit
resume 200 iter
真实训练结束后无残留 worker/thread
```

当前 Queue cleanup 使用 `close()` + `cancel_join_thread()` 的 best-effort 路径，focused tests 证明了 Process/Host thread，但没有记录 Queue feeder thread 状态。此项先作为 acceptance evidence open；若完整 discover 仍出现解释器退出异常，再回到 cleanup 实现修复。

### 2.3 Ticket 16 签发

```text
CODE REMEDIATION ACCEPTED
WINDOWS SPAWN UNIT PATH ACCEPTED
FULL PROCESS EXIT NOT PROVEN
WINDOWS SAEHD GPU NOT PROVEN
NOT PASS / NOT CLOSED
```

---

## 3. Ticket 17 Review

### 3.1 已关闭的 Round 1 finding

```text
T17-R1-01  unsigned record 不再 trusted、不装载旧 pose/quality：CLOSED
T17-R1-02  strict invalid 在 formal Sidecar write 前拦截：CLOSED
T17-R1-03  full/force 不再主进程预扫全部 signature：CLOSED
             quick current-signature scan 使用 first/last bounded reads：CLOSED
T17-R1-04  strong 缺 content hash 被标记 issue/untrusted：CLOSED AT CONTRACT LEVEL
```

Loader 现在保留 `record_matched=True` 作为 ID 诊断，但 unsigned record 不增加 trusted match，业务数组保持 neutral，并产生 `UNSIGNED_SIGNATURE` warning。

### 3.2 T17-R2-01 — Incremental 仍未使用 full path 的 canonical builder

**等级：P0 / TICKET 14 REGRESSION / ROUND 1 NOT CLOSED**

`mainscripts/FacesetAnalyzer.py` 的 incremental 路径虽然手工补回：

```text
bucket_contract_version
canonical_yaw_buckets
canonical_pitch_buckets
```

但它仍调用旧的：

```python
reconcile_and_finalize_samples(plan, newly_analyzed_records)
```

该函数生成的 summary 仍是旧契约：

```text
usable_for_sampling
pose_distribution_yaw
pose_distribution_pitch
quality_normalization
```

并继续读取旧顶层 record 字段：

```text
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

而 full Analyzer 使用的是 Ticket 14 canonical summary：

```text
total_samples
valid_samples
invalid_samples
yaw_bucket_counts
pitch_bucket_counts
quality_stats
normalization
```

因此当前只是“补了 analysis_config 三个字段”，没有满足 Round 1 固定目标：

```text
incremental 输出与 full 输出使用同一 canonical builder
Ticket 14 canonical bucket contract 不得回退
```

现有测试只断言 `analysis_config.pose` 存在 canonical 字段，没有比较 full/incremental 的 summary key set、bucket counts、nested record contract 或 dataset fingerprint。

### 3.3 T17-R2-02 — Incremental / failure / performance 验收矩阵仍开放

仍缺：

```text
quick→quick structured signature reuse
strong→strong reuse
quick→strong full recompute
strong→quick 冻结策略与行为一致性
同名替换只重算目标样本
worker fatal 保持旧 Sidecar bytes/sha
add/delete/duplicate ID
1k/10k ordinary+packed quick/strong workers=1/2/auto
elapsed / samples per second / peak RSS
完整 discover shell exit 0
```

这些可以在修复 canonical builder 后集中补测，不要求重新设计 workers/hash 基础。

### 3.4 Ticket 17 最小返修

1. 抽取或复用一个 full/incremental 共用的 canonical finalize/builder；
2. 不再让 `reconcile_and_finalize_samples()` 输出旧顶层 summary/bucket 字段；
3. 新增 full → incremental no-change 与 partial-change 的 exact contract parity 测试；
4. 增加 worker fatal sentinel，证明旧 formal Sidecar 不变；
5. 补 structured migration 与最低必要 performance 记录。

### 3.5 Ticket 17 签发

```text
REQUEST_CHANGES
TRUST / STRICT / BOUNDED IO CORE FIXED
INCREMENTAL CANONICAL CONTRACT BROKEN
PERFORMANCE / FAILURE MATRIX OPEN
NOT PASS / NOT CLOSED
```

---

## 4. Ticket 19 Review

### 4.1 已关闭的 Round 1 finding

```text
T19-R1-01  iter=0 后逐步检查，initial_iter 可达：CLOSED
T19-R1-02  每个 train step 后检查 target，不被 warmup 越过：CLOSED
T19-R1-03  训练组前处理 close，组内每步前再检查：CLOSED AT CONTROLLER LEVEL
T19-R1-05  save 日志增加 range=start..end：CLOSED
T19-R1-07  测试使用真实 TrainerSaveController：CLOSED
```

Controller 抽取方向正确，测试不再复制理想 helper。

### 4.2 T19-R2-01 — 主线程忽略 `op=error`，save failure 仍可表现为普通 close

**等级：P0 / FAILURE SEMANTICS / ROUND 1 NOT CLOSED**

`TrainerSaveController.model_save()` 和 `trainerThread` outer exception 都会向 `c2s` 放入：

```python
{"op": "error", ...}
```

但 `Trainer.main()` 的两个消费循环只处理：

```text
no_preview：close
preview：show / close
```

没有处理 `op=error`，随后 trainerThread 仍无条件发送：

```python
c2s.put({"op": "close"})
```

结果是：

```text
save failure
→ error message 入队但被主线程忽略
→ close message 到达
→ UI/CLI 正常退出循环
→ 调用方无法区分失败与正常关闭
```

这仍属于 Round 1 指出的“save failure 被伪装为普通 close”。仅仅把错误放入一个无人处理的队列，不构成完整传播。

必须：

1. 主线程显式处理 `op=error`；
2. 保留 error_type / reason / iter / traceback；
3. 不得在 fatal 后按正常 close 语义结束；
4. CLI/测试路径应 raise 或返回非零；GUI 路径至少显示 fatal 并设置失败状态；
5. 增加 trainerThread/main harness，验证 manual/scheduled/target/exit save failure。

### 4.3 T19-R2-02 — degraded warning 未实现 bounded 语义

**等级：P1 / OBSERVABILITY**

`record_train_loss()` 的 docstring 写的是 bounded warning，但每次异常都会直接 `_log()`。若 history/tracker 持续异常，会每个 iteration 打一条 warning。

同时：

```text
self.degraded=True
loss_window.degraded=True（如有）
```

成功 save/commit 后未重置，后续所有窗口可能永久携带 `window_incomplete`，即使新窗口记录已恢复正常。

建议冻结为：

```text
每个窗口第一次失败记录一次 warning
后续失败计数但不逐 iter 刷屏
save log 输出 degraded_count/window_incomplete
成功 commit 后重置当前窗口 degraded 状态
```

### 4.4 T19-R2-03 — target=1 会同一 iteration 连续保存两次

**等级：P1 / BOUNDARY DEDUPLICATION**

`after_train_step()` 在 iter=1 时先执行：

```text
initial_iter save
```

然后同一调用继续判断 target，target=1 时再执行：

```text
target_reached save
```

第二次保存的窗口已被第一次 commit，通常得到空窗口并重复写 checkpoint。现有 `test_target_one` 只断言出现 target save，没有断言 save 次数或 reason 去重。

应冻结语义，例如：

```text
target=1：单次 save，reason 可为 target_reached（附 initial=true）
或明确只执行 initial_iter，并同时标记 reached_goal
```

不得同一步无意重复保存。

### 4.5 Ticket 19 签发

```text
REQUEST_CHANGES
CONTROL FLOW FOUNDATION ACCEPTED
MAIN-THREAD FAILURE PROPAGATION BROKEN
DEGRADED WARNING NOT BOUNDED
TARGET=1 DUPLICATE SAVE OPEN
NOT PASS / NOT CLOSED
```

---

## 5. Test Evidence

实现侧记录：

```text
Windows / Python 3.11.7 / spawn
compileall: OK
focused suite: Ran 90 / OK / EXIT=0
```

仍缺：

```text
完整 Batch 2 discover + shell exit 0
Windows SAEHD 500 + save/exit/resume 200
Ticket 17 1k/10k performance/RSS
真实 main/trainer fatal propagation harness
```

GitHub：

```text
Actions workflow runs：none
combined status checks：none
```

Reviewer 独立 clone/rerun：

```text
BLOCKED：执行环境无法解析 github.com
```

因此 focused test 记录可以作为实现侧证据，但不能写作独立 CI PASS。

---

## 6. Recommended Remediation Order

```text
1. Ticket 17：统一 full/incremental canonical builder + parity tests
2. Ticket 19：主线程 fatal/error 处理 + nonzero/raise harness
3. Ticket 19：bounded degraded state + target=1 save dedupe
4. Wave tests：完整 discover，确认 shell exit 0
5. Ticket 16：记录 Queue feeder/active children/thread 状态
6. Windows GPU：SAEHD 500 + save/exit/resume 200
7. Ticket 17：1k/10k perf/RSS matrix
8. Independent Review Round 3
```

返修应继续保持 Ticket 边界：

```text
fix(ticket17): unify incremental canonical finalize contract
fix(ticket19): propagate trainer fatal errors to main and dedupe save boundaries
test(wave1): record full discover and lifecycle evidence
docs(wave1): update remediation evidence
```

---

## 7. Current Gate

```text
禁止合入 main
禁止签发 Ticket 16/17/19 PASS/CLOSED
禁止解锁 Ticket 18/20 最终签发
legacy_random / legacy_uniform_yaw 可继续回归
Metadata Sampling 仍 NOT PRODUCTION READY
```
