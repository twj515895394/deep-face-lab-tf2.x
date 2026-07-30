# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 15:58 +08:00  
> 当前交接：Batch 2 Wave 1 Round 3 返修已完成，独立 Review Round 3 已签发  
> 当前状态：`WAVE1-R3-REQUEST-CHANGES / T16-REQUEST-CHANGES / T17-REQUEST-CHANGES / T19-REQUEST-CHANGES`

---

## 1. 最新必读入口

按顺序阅读：

1. [Wave 1 独立 Review Round 3](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round3.md)
2. [Wave 1 Round 3 Remediation Evidence](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-round3-evidence.md)
3. [Wave 1 独立 Review Round 2](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round2.md)
4. [统一返修与 Review 工作分支约定](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-and-review-working-branch-policy.md)
5. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
6. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
7. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

---

## 2. 统一工作分支

当前唯一 Wave 1 返修、Review 与文档分支：

```text
codex/batch2-ticket19-loss-window
```

继续保持：

```text
一个 remediation commit 只处理一个 Ticket
跨票适配使用独立 integration/test commit
实现者不得自行签发 APPROVED / PASS / CLOSED
current.md 由独立 Reviewer 或集成负责人更新
```

---

## 3. 最新 Commit 锚点

```text
Wave 1 Review R3 Base：71e6982ce350915656fa0f745dc8238ada3e498f
Ticket 17 R3 fix：      cd143066ad006b9adf4ca7cfd0da1879bf0c5fcd
Ticket 19 R3 fix：      e58350d3b7413e08657d8692a4fbf519bd5b0927
Ticket 16 R3 fix：      2d82152d4f7d4ca145fcdb0af39a278074b5fc0a
Round 3 Evidence：      079ac517fc2f3a0b9184d3a71ad5e08e61f0f0f8
Wave 1 Review R3：      46602ee6ad2b5c300832efa4e830682a34e96220
```

历史：

```text
Ticket 14 Final：       37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 Final Review：4fd7d062cc817589fd964efdae3bd3e793247b68
Wave 1 Review R1：      c70b00daee84ff348534ec0681a75b2bfdc2d8d0
Wave 1 Review R2：      0f09e44314bc0bdbaf0c9406ed3ca41ca745679e
```

---

## 4. Round 3 权威结论

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED

Ticket 16：REQUEST_CHANGES
           SPAWN CORE ACCEPTED
           DISCOVER EXIT=0 ESTABLISHED FOR test_batch2*.py
           RESIDUAL ALIVE OBJECTS OPEN
           FULL test_batch*.py OPEN
           WINDOWS SAEHD GPU OPEN

Ticket 17：REQUEST_CHANGES
           CANONICAL FULL/INCREMENTAL BUILDER CLOSED
           TRUST / STRICT / BOUNDED IO ACCEPTED
           STRONG→QUICK MODE CONTRACT BROKEN
           PERF MATRIX OPEN

Ticket 19：REQUEST_CHANGES
           CONTROL FLOW / DEGRADED / TARGET=1 FIXED
           MAIN FATAL DETECTION ACCEPTED
           RICH ERROR CONTEXT MAY BE OVERWRITTEN
           REAL MAIN/THREAD HARNESS OPEN

Wave 1 Integration：REQUEST_CHANGES
```

实现侧 Summary 或 Evidence 不得覆盖本独立 Review。

---

## 5. Ticket 16 剩余阻断

### T16-R3-01：discover 后仍报告 ALIVE 非零

Round 3 Evidence 明确写入：

```text
部分测试路径仍可能残留少量 daemon host/queue feeder
ALIVE 非零，但已不导致 shell crash
```

`EXIT=0` 关闭了解释器崩溃，但 Ticket 16 要求的是：

```text
无残留 worker/process/thread/queue feeder
```

下一轮必须记录测试前后差集：

```text
thread name / target
Process pid / exitcode
Queue feeder thread
创建 owner
未调用 close 的路径
```

并真正消除残留，不得只依赖 daemon 随解释器退出。

### T16-R3-02：完整 discover 命令仍未执行

已运行：

```text
python -m unittest discover -s tests/smoke -p "test_batch2*.py" -q
Ran 233 / OK / EXIT=0
```

冻结要求：

```text
python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

必须补 Batch 1 + Batch 2 完整回归、shell exit code 与退出后生命周期差集。

### Windows GPU 仍开放

```text
SAEHD FP32 + AdaBelief 500 iter
manual save
exit
resume 200 iter
训练结束无残留 worker/thread/queue feeder
```

---

## 6. Ticket 17 剩余阻断

### T17-R3-01：strong → quick 策略与行为冲突

当前 plan 返回：

```text
SIGNATURE_MODE_DOWNGRADE_FORBIDDEN_STRONG_TO_QUICK
is_incremental=False
```

但 CLI 随后按当前请求的 quick 模式执行 full analysis，并覆盖旧 strong Sidecar。

即：

```text
文案：禁止降级
实际：full quick 降级覆盖
```

现有测试只检查 plan reason，没有执行 CLI，也没有检查最终 Sidecar mode。

必须冻结：

```text
推荐：strong old + quick current → 保持 strong 或明确拒绝非零
```

如确实允许完整降级，必须同步修改 reason、Ticket/安全文档，并新增端到端明确同意的降级测试。

仍需：

```text
strong→strong 真实 CLI reuse
strong→quick 最终 Sidecar 行为
同名替换精确 recompute count
1k/10k ordinary+packed quick/strong workers/RSS
```

---

## 7. Ticket 19 剩余阻断

### T19-R3-01：rich save error 会被 generic error 覆盖

真实消息序列：

```text
Controller：error(reason, iter, error_type, traceback)
trainerThread outer except：error(error_type, traceback)
trainerThread：close
```

`TrainerClientState` 当前每次都：

```python
self.fatal_error = msg
```

第二条通用 error 会覆盖第一条 rich error，最终可能丢失：

```text
reason
iter
```

必须保留第一条或信息更丰富的 error，或避免 outer except 重复发送通用 error。

新增测试必须模拟：

```text
rich error → generic error → close
```

并覆盖：

```text
manual
scheduled
target_reached
exit
```

### T19-R3-02：缺真实 main/thread 联合 harness

现有测试分别验证 Controller 和 `TrainerClientState`，没有运行真实 trainerThread 产生的两条 error + close 序列。

应增加可注入 FakeModel 的联合 harness，证明：

```text
save failure → main raise
normal close → 不 raise
fatal 保留 reason/iter
thread 正常结束
失败不产生成功 preview/save 语义
```

---

## 8. 最小 Round 4 返修

```text
fix(ticket17): enforce strong-to-quick signature mode policy
fix(ticket19): preserve first rich trainer fatal context
fix(ticket16): close remaining host and queue feeder lifecycle gaps
test(wave1): add real mode/error sequence and full test_batch discover evidence
docs(wave1): record round4 evidence
```

保持 Ticket 边界，不要重新混成巨型提交。

---

## 9. 测试证据与限制

实现侧：

```text
Windows / Python 3.11.7 / spawn
compileall：OK
Batch 2 discover：Ran 233 / OK / EXIT=0
```

仍开放：

```text
完整 test_batch*.py
ALIVE=0 生命周期证据
Windows SAEHD 500 + resume 200
Ticket 17 1k/10k perf/RSS
真实 Trainer.main/trainerThread fatal sequence
```

GitHub：

```text
Actions workflow runs：none
combined status checks：none
```

Reviewer 当前环境：

```text
git ls-remote / clone BLOCKED：无法解析 github.com
```

不得把实现侧记录描述为独立 CI PASS。

---

## 10. 后续依赖与安全判断

```text
Ticket 18：BLOCKED-BY-TICKET17
Ticket 20：BLOCKED-BY-TICKET16+17
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
