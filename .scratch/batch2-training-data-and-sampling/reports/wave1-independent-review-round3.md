# Batch 2 Wave 1 — Independent Review Round 3

> Review 日期：2026-07-30  
> 工作分支：`codex/batch2-ticket19-loss-window`  
> Review Base：`71e6982ce350915656fa0f745dc8238ada3e498f`  
> Review Head：`079ac517fc2f3a0b9184d3a71ad5e08e61f0f0f8`  
> Round 3 commits：
> - Ticket 17：`cd143066ad006b9adf4ca7cfd0da1879bf0c5fcd`
> - Ticket 19：`e58350d3b7413e08657d8692a4fbf519bd5b0927`
> - Ticket 16：`2d82152d4f7d4ca145fcdb0af39a278074b5fc0a`
> - Evidence：`079ac517fc2f3a0b9184d3a71ad5e08e61f0f0f8`
> 
> Review 方法：独立静态源码、测试源码、Ticket 规约、Round 2 finding 与实现侧 Windows 测试记录复核。Reviewer 当前环境无法解析 `github.com`，未能独立 clone/rerun；GitHub 无 Actions/status check。

---

## 1. Verdict

```text
Ticket 16：REQUEST_CHANGES / DISCOVER EXIT FIXED / RESIDUAL LIFECYCLE + GPU OPEN
Ticket 17：REQUEST_CHANGES / CANONICAL BUILDER FIXED / STRONG→QUICK CONTRACT OPEN
Ticket 19：REQUEST_CHANGES / FATAL DETECTION FIXED / RICH ERROR PROPAGATION OPEN
Wave 1 Integration：REQUEST_CHANGES
Ticket 18：仍 BLOCKED-BY-TICKET17
Ticket 20：仍 BLOCKED-BY-TICKET16+17
Batch 2：NOT DONE / NOT PRODUCTION READY
```

Round 3 再次取得了实质进展，不需要推倒重来：

- Ticket 17 的 full/incremental canonical summary builder 已统一；
- Ticket 19 的主线程已经能识别 fatal 并最终 raise，degraded warning 和 target=1 双保存也已修正；
- Ticket 16 的 Batch 2 discover 已从历史非零退出改善为实现侧记录的 `EXIT=0`。

但当前仍有三个明确契约缺口，因此不能签发 PASS/CLOSED。

---

## 2. Ticket 17 Review

### 2.1 已关闭：T17-R2-01 canonical builder

新增 `samplelib/metadata/summary_builder.py`，full Analyzer 与 incremental reconcile 均调用 `build_canonical_summary()`。

已确认：

```text
canonical summary key set 统一
nested pose/quality 作为主契约
legacy flat pose 仅作为迁移 fallback
full → incremental no-change parity 测试存在
partial-change canonical contract 测试存在
worker fatal 保持旧 Sidecar bytes/sha 测试存在
```

该部分接受，后续不得回退。

### 2.2 T17-R3-01 — strong → quick 的 plan 文案与 CLI 实际行为仍冲突

**等级：P0 / SIGNATURE MODE CONTRACT / ACCEPTANCE BLOCKER**

`build_incremental_plan()` 对 strong old metadata + quick current run 返回：

```text
is_incremental=False
reason=SIGNATURE_MODE_DOWNGRADE_FORBIDDEN_STRONG_TO_QUICK
```

但 `mainscripts/FacesetAnalyzer.py` 对任何 `plan.is_incremental=False` 都继续执行当前请求模式的 full analysis。当前请求未带 `--strong-fingerprint` 时，Analyzer 会按 quick 模式重算并覆盖 formal Sidecar。

真实行为因此是：

```text
日志/plan：DOWNGRADE_FORBIDDEN
实际：full quick recompute → strong Sidecar 被 quick Sidecar 覆盖
```

这既不满足“strong→quick 不降级”的 Ticket 测试要求，也不满足 Round 2 要求的“策略、reason、行为一致”。

现有 `test_signature_mode_migration_plans()` 只断言 plan reason 包含 `DOWNGRADE`，没有执行 CLI，也没有检查最终 Sidecar 的 `analysis_config.signature.mode`。

必须冻结一种真实策略：

```text
推荐：strong old + quick current → 保持 strong 或明确拒绝并返回非零
```

如果维护者明确允许用户请求 quick 时完整降级，则必须：

```text
删除 FORBIDDEN 文案
明确记录 FULL_RECOMPUTE_TO_QUICK
增加端到端测试证明这是有意行为
同步 Ticket/安全文档
```

在当前冻结规约下，优先不得降级。

### 2.3 Ticket 17 验收证据仍开放

仍缺完整要求：

```text
strong→strong 真实 CLI incremental reuse
strong→quick 最终 Sidecar 行为
同名替换只重算目标样本的精确计数
1k/10k ordinary+packed quick/strong workers=1/2/auto
elapsed / samples per second / peak RSS
```

### 2.4 Ticket 17 签发

```text
REQUEST_CHANGES
CANONICAL FULL/INCREMENTAL SUMMARY: CLOSED
TRUST / STRICT / BOUNDED IO: ACCEPTED
STRONG→QUICK MODE CONTRACT: BROKEN
PERFORMANCE MATRIX: OPEN
NOT PASS / NOT CLOSED
```

---

## 3. Ticket 19 Review

### 3.1 已关闭的 Round 2 finding

```text
T19-R2-02  每窗口首次 degraded warning + degraded_count：CLOSED
             成功 commit 后重置：CLOSED
T19-R2-03  target=1 单次 target_reached save：CLOSED
T19-R2-01  主线程识别 op=error，close 后 raise：PARTIALLY CLOSED
```

`TrainerClientState` 已使 fatal 不再被纯粹当作正常 close；no-preview 与 GUI 路径在退出后调用 `raise_if_fatal()`。这是正确方向。

### 3.2 T19-R3-01 — 详细 save error 会被外层通用 error 覆盖

**等级：P0 / FAILURE CONTEXT / ROUND 2 NOT FULLY CLOSED**

保存失败时消息序列实际为：

```text
1. TrainerSaveController.model_save()
   → c2s.put({op:error, reason, iter, error_type, traceback})
   → re-raise

2. trainerThread 最外层 except
   → c2s.put({op:error, error_type, traceback})
   # 不含 reason / iter

3. trainerThread
   → c2s.put({op:close})
```

`TrainerClientState.on_message()` 对每条 error 都无条件执行：

```python
self.fatal_error = msg
```

因此第二条通用 error 会覆盖第一条更完整的 save error，最终 `raise_if_fatal()` 很可能得到：

```text
reason=unknown
iter 缺失
```

这违反 Round 2 明确要求：保留 `reason / iter / error_type / traceback`。

现有测试只模拟：

```text
单条 rich error → close
```

没有模拟真实序列：

```text
rich save error → generic outer error → close
```

最小修复任选其一：

1. `TrainerClientState` 保留第一条或信息更丰富的 error，不让通用 error 覆盖；
2. `trainerThread` 检测 Controller 已发送结构化错误时，不再重复发送通用 error；
3. 通用 error 继承 Controller 的 `reason/iter` 与原始 cause。

必须增加真实消息序列测试，并分别覆盖：

```text
manual
scheduled
target_reached
exit
```

### 3.3 T19-R3-02 — 测试仍未执行真实 Trainer.main / trainerThread 联合序列

**等级：P1 / INTEGRATION EVIDENCE**

新增测试验证了 `TrainerClientState` 和 Controller，但没有把 `trainerThread` 产生的两条 error 与 close 真实送入 `Trainer.main()` 消费路径。正因为没有真实联合序列，才遗漏了 rich error 被覆盖的问题。

应增加可注入 FakeModel 的 trainerThread/main harness，至少验证：

```text
save failure → main raise
normal close → 不 raise
fatal message 保留 reason/iter
thread 正常结束
fatal 不生成成功 preview/save 语义
```

### 3.4 Ticket 19 签发

```text
REQUEST_CHANGES
INITIAL / TARGET / CLOSE CONTROL FLOW: ACCEPTED
BOUNDED DEGRADED WINDOW: ACCEPTED
TARGET=1 DEDUPE: ACCEPTED
MAIN FATAL DETECTION: ACCEPTED
RICH FAILURE CONTEXT: BROKEN
REAL MAIN/THREAD HARNESS: OPEN
NOT PASS / NOT CLOSED
```

---

## 4. Ticket 16 Review

### 4.1 已改善：discover shell exit

实现侧记录：

```text
Windows / Python 3.11.7 / spawn
python -m unittest discover -s tests/smoke -p "test_batch2*.py" -q
Ran 233 tests
OK
shell EXIT=0
```

`IndexHost` / `Index2DHost` 新增 stop/close，历史 Windows 解释器退出崩溃已得到实质改善。

### 4.2 T16-R3-01 — 实现侧仍报告 ALIVE 非零

**等级：P0 / LIFECYCLE ACCEPTANCE**

Round 3 Evidence 主动记录：

```text
部分测试路径仍可能残留少量 daemon host/queue feeder
发现后 ALIVE 非零，但已不导致 shell crash
```

Ticket 16 的通过条件不是“解释器能强制带着 daemon 退出”，而是：

```text
无残留 worker/process/thread/queue feeder
```

因此 `EXIT=0` 关闭了历史 crash，但 `ALIVE 非零` 表明生命周期契约仍未关闭。必须定位残留对象归属，至少记录：

```text
thread name / target
Process pid / exitcode
Queue feeder thread
创建路径与未调用 close 的 owner
测试前后差集
```

不得仅依赖 daemon 属性或解释器终止清理。

### 4.3 T16-R3-02 — discover 命令范围仍小于冻结要求

本轮运行：

```text
-p "test_batch2*.py"
```

交接与 Ticket 冻结命令是：

```text
-p "test_batch*.py"
```

当前证据排除了 Batch 1 回归测试，不能替代要求的完整 Batch smoke。下一轮必须执行并记录完整命令、Ran N、OK、shell exit code 与退出后生命周期差集。

### 4.4 Windows GPU 验收仍开放

仍缺：

```text
SAEHD FP32 + AdaBelief 500 iter
manual save
exit
resume 200 iter
训练结束无残留 worker/thread/queue feeder
```

### 4.5 Ticket 16 签发

```text
REQUEST_CHANGES
SPAWN CORE: ACCEPTED
DETERMINISTIC SUBPROCESS REAP: ACCEPTED
DISCOVER SHELL EXIT=0: ESTABLISHED FOR test_batch2*.py
RESIDUAL ALIVE OBJECTS: OPEN
FULL test_batch*.py: OPEN
WINDOWS SAEHD GPU: OPEN
NOT PASS / NOT CLOSED
```

---

## 5. Test Evidence Assessment

实现侧证据：

```text
compileall：OK
Batch 2 discover：Ran 233 / OK / EXIT=0
```

GitHub：

```text
Actions workflow runs：none
combined status checks：none
```

Reviewer 独立复跑：

```text
git ls-remote / clone：BLOCKED
原因：当前执行环境无法解析 github.com
```

因此实现侧 Windows 记录可作为有效工程证据，但不能描述为独立 CI PASS。

---

## 6. Minimal Round 4 Remediation

保持单分支、按 Ticket 独立提交：

```text
fix(ticket17): enforce strong-to-quick signature mode policy
fix(ticket19): preserve first rich trainer fatal context
fix(ticket16): close remaining host and queue feeder lifecycle gaps
test(wave1): add real mode/error sequence and full test_batch discover evidence
docs(wave1): record round4 evidence
```

### Ticket 17

- 冻结 strong→quick：拒绝、保持 strong，或经规约变更后明确完整降级；
- 增加真实 CLI 端到端测试，检查最终 Sidecar mode；
- 不得只测 plan reason。

### Ticket 19

- rich error 不得被 generic error 覆盖；
- 增加 `rich error → generic error → close` 序列测试；
- 最好增加可注入 FakeModel 的 trainerThread/main harness。

### Ticket 16

- 定位并消除 discover 后 ALIVE 非零；
- 运行 `test_batch*.py` 而不是仅 `test_batch2*.py`；
- 记录 Process/Host/Queue feeder 差集；
- 完成 Windows SAEHD 500 + save/exit/resume 200。

---

## 7. Current Gate

```text
Ticket 14：PASS / CLOSED
Ticket 15：PASS / CLOSED
Ticket 16：REQUEST_CHANGES
Ticket 17：REQUEST_CHANGES
Ticket 19：REQUEST_CHANGES
Wave 1：REQUEST_CHANGES
Ticket 18：BLOCKED-BY-17
Ticket 20：BLOCKED-BY-16+17
Metadata Sampling：NOT PRODUCTION READY
禁止合入 main
禁止签发 Batch 2 DONE
```
