# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 16:01 +08:00  
> 当前交接：Batch 2 Wave 1 独立 Review Round 4 已签发，Ticket 18 / 20 代码依赖解锁  
> 当前状态：`WAVE1-CODE-PASS / T16-PASS-CODE / T17-PASS-CODE / T19-PASS-CLOSED / ENV-VALIDATION-DEFERRED`

---

## 1. 最新必读入口

按顺序阅读：

1. [Wave 1 独立 Review Round 4](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round4.md)
2. [Wave 1 Round 4 Remediation Evidence](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-round4-evidence.md)
3. [Wave 1 独立 Review Round 3](../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round3.md)
4. [统一返修与 Review 工作分支约定](../.scratch/batch2-training-data-and-sampling/reports/wave1-remediation-and-review-working-branch-policy.md)
5. [Ticket 16 规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
6. [Ticket 17 规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
7. [Ticket 19 规约](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

---

## 2. 统一工作分支

当前 Wave 1、后续 Ticket 18/20 集成、Review 与文档入口：

```text
codex/batch2-ticket19-loss-window
```

继续保持：

```text
每个 Ticket 使用可独立识别的 implementation/remediation commit
跨票适配使用独立 integration/test commit
实现者不得自行把新 Ticket 标记 APPROVED / PASS / CLOSED
current.md 由独立 Reviewer 或集成负责人统一更新
```

---

## 3. 最新 Commit 锚点

```text
Wave 1 Review R3：       46602ee6ad2b5c300832efa4e830682a34e96220
Round 4 被审实现 Head： f619192b61c21c38a1a6fdd8c79e0530a64f8e04
Wave 1 Review R4：       0742381d10ad49848c9cfba33fc72a622c567e52
```

历史：

```text
Ticket 14 Final：        37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 Final Review： 4fd7d062cc817589fd964efdae3bd3e793247b68
Wave 1 Review R1：       c70b00daee84ff348534ec0681a75b2bfdc2d8d0
Wave 1 Review R2：       0f09e44314bc0bdbaf0c9406ed3ca41ca745679e
```

---

## 4. 维护者验收策略

维护者已明确：

```text
代码逻辑与契约没有已知阻断缺陷时，
仅因 GPU、规模数据或特定环境无法完全覆盖的测试，
允许先签发代码 PASS。
```

未执行项必须记录为：

```text
ENV-VALIDATION-DEFERRED
PERF-VALIDATION-DEFERRED
```

不得写成已经实测通过，也不阻止代码依赖继续开发。

---

## 5. Round 4 权威结论

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED

Ticket 16：APPROVED / PASS-CODE
           SPAWN / IPC / PROCESS REAP / HOST CLOSE CODE GATE CLOSED
           WINDOWS GPU + THREAD ATTRIBUTION VALIDATION DEFERRED

Ticket 17：APPROVED / PASS-CODE
           WORKERS / SIGNATURE / TRUST / STRICT / INCREMENTAL CODE GATE CLOSED
           1K/10K PERF/RSS VALIDATION DEFERRED

Ticket 19：APPROVED / PASS / CLOSED
           LOSS WINDOW / TRAIN CONTROL / FATAL PROPAGATION CLOSED

Wave 1 Integration：APPROVED / CODE-PASS
```

实现侧 Summary 或 Evidence 不得覆盖独立 Reviewer 结论；环境债务也不得被误写为完成。

---

## 6. Ticket 16 已确认关闭

```text
Client spawn 后 _host_ref=None
closed/fatal Event 状态传播
独立 response Queue + request ID
stale response 拒绝
有限 timeout 与错误区分
SubprocessGenerator terminate→join→kill→join
确认 Process 死亡后才清空句柄
Queue 显式 cleanup
SampleGeneratorFace 显式关闭 worker 与 hosts
cleanup failure 向上抛出
WeightedIndexHost close timeout 明确失败
IndexHost / Index2DHost 显式 close
完整 test_batch*.py：Ran 311 / OK / EXIT=0
ACTIVE_CHILDREN=[]
无 WeightedIndexHost / IndexHost host_thread
无 live multiprocessing.Process children
```

非阻断环境验证债务：

```text
定位 full suite 后 1×QueueFeederThread 的 before/after owner
确认 interact daemon 为 pre-existing 全局线程或记录来源
Windows SAEHD FP32 + AdaBelief ≥500 iter
manual save / exit / resume ≥200 iter
无 timeout / 无 fallback / 资源差集可解释
```

---

## 7. Ticket 17 已确认关闭

```text
--workers 真实进入 spawn Pool
quick bounded first/last raw read
strong 完整 raw SHA256
full/force 不重复主进程预读 + worker 重读
unsigned record 不 trusted，不装载旧 pose/quality
同名替换 signature mismatch 后 neutral
strict invalid 在 formal write 前失败
worker fatal 不覆盖旧 Sidecar
strong hash 失败不写半完整 record
full/incremental canonical summary builder 统一
Ticket 14 pose contract 保持
strong→quick：exit 7，Sidecar bytes/sha/mode 不变
strong→strong：incremental reuse 成立
```

非阻断验证债务：

```text
同名替换真实 CLI report 精确计数：recompute=1 / reuse=N-1
1k / 10k ordinary+packed
quick / strong
workers=1 / 2 / auto
elapsed / samples/sec / peak RSS / determinism
```

---

## 8. Ticket 19 已关闭

```text
TrainerSaveController 已接入 trainerThread
训练组前处理 close/save
每次 train 后检查 initial/target
warmup 不越过 target
pre-queued close 不训练额外 batch
target=1 不双保存
保存前 freeze，成功后 stats+commit
失败不消费窗口
range/degraded 可观测
rich error 保留 reason/iter/error_type/traceback
outer except 不覆盖 Controller rich error
TrainerClientState 在 close 后 raise fatal
manual/scheduled/target_reached/exit 失败上下文测试覆盖
```

状态：

```text
APPROVED / PASS / CLOSED
```

真实 GPU Trainer 联合运行可以继续作为系统验收，但不再是 Ticket 19 代码阻断。

---

## 9. 测试证据

```text
环境：Windows / Python 3.11.7 / spawn
Focused suites：OK
python -m unittest discover -s tests/smoke -p "test_batch*.py"
Ran 311 tests
OK
shell EXIT=0
ACTIVE_CHILDREN=[]
```

GitHub：

```text
Actions/status checks：none
```

所以不得描述为 GitHub CI PASS，也不得声称 GPU/1k/10k 已完成。

---

## 10. 当前 Frontier

现在允许并行启动：

```text
Lane A：Ticket 18 — UNBLOCKED-BY-TICKET17-CODE-PASS
Lane B：Ticket 20 — UNBLOCKED-BY-TICKET16+17-CODE-PASS
Lane C：Environment Validation Debt
```

执行规则：

```text
Ticket 18 与 Ticket 20 使用独立 implementation commits
不要同时把 18/20 代码混成一个 commit
每票单独 Summary + focused tests
合并后统一跑完整 test_batch*.py
再进行独立 Review
```

---

## 11. 后续依赖

```text
Ticket 18：UNBLOCKED / READY
Ticket 20：UNBLOCKED / READY
Ticket 21：BLOCKED-BY-TICKET18+20 + FINAL ENV VALIDATION
Batch 3：BLOCKED-BY-BATCH2 FINAL SIGN-OFF
```

Ticket 21 前必须补齐或由维护者再次明确豁免：

```text
Ticket 16 Windows GPU / lifecycle attribution
Ticket 17 1k/10k perf/RSS
```

---

## 12. 安全判断

```text
legacy_random / legacy_uniform_yaw：可继续使用与回归
Faceset Analyzer：代码契约已通过，可进入 Ticket 18/20 集成验证
pose_balanced / quality_pose_balanced：可用于开发测试
正式生产签发：仍等待 Ticket 18/20 + 环境验证债务
禁止签发 Batch 2 DONE
```
