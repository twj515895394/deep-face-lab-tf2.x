# Batch 2 Wave 1 — Independent Review Round 4

> Review 日期：2026-07-30  
> 工作分支：`codex/batch2-ticket19-loss-window`  
> Review Base：`46602ee6ad2b5c300832efa4e830682a34e96220`  
> 被审实现 Head：`f619192b61c21c38a1a6fdd8c79e0530a64f8e04`  
> 实现证据：`wave1-remediation-round4-evidence.md`  
> Reviewer 方法：独立静态源码、测试源码、Ticket 冻结规约与实现侧 Windows 测试证据复核。GitHub 无 Actions/status check；Reviewer 当前环境未重新执行 GPU 与大规模性能测试。

---

## 1. 维护者验收决策

本轮采用维护者明确确认的签发策略：

```text
如果代码契约与控制流没有已知阻断缺陷，
仅因 GPU、规模数据或特定环境无法完全覆盖的测试，
可以先签发代码 PASS；
未完成项目作为 Environment Validation Debt 保留，
不得伪写成已经实测通过。
```

因此本报告区分：

```text
PASS-CODE
ENV-VALIDATION-DEFERRED
CLOSED
```

`PASS-CODE` 可以解锁代码依赖；`ENV-VALIDATION-DEFERRED` 仍必须在最终生产签发前补齐。

---

## 2. Final Verdict

```text
Ticket 16：APPROVED / PASS-CODE
           SPAWN + IPC + PROCESS/HOST CLEANUP CODE GATE CLOSED
           WINDOWS GPU / LIFECYCLE ATTRIBUTION DEFERRED

Ticket 17：APPROVED / PASS-CODE
           WORKERS + SIGNATURE + TRUST + INCREMENTAL CODE GATE CLOSED
           1K/10K PERF/RSS VALIDATION DEFERRED

Ticket 19：APPROVED / PASS / CLOSED
           TRAINER SAVE WINDOW + CONTROL FLOW + FATAL PROPAGATION CLOSED

Wave 1 Integration：APPROVED / CODE-PASS
                    ENVIRONMENT VALIDATION DEBT OPEN

Ticket 18：UNBLOCKED
Ticket 20：UNBLOCKED
Ticket 21：BLOCKED-BY-TICKET18+20 + FINAL ENV VALIDATION
Batch 2：NOT DONE / NOT YET PRODUCTION-SIGNED
```

本轮没有发现需要继续修改 Ticket 16、17、19 核心代码的明确阻断缺陷。

---

## 3. Ticket 16 Review

### 3.1 已确认的代码契约

以下实现达到 Ticket 16 的核心并发与生命周期设计，后续不得回退：

```text
Host 只存在于训练主进程
spawn worker 只持有 Client
Client pickle 后 _host_ref=None
closed/fatal 使用可 pickle Event 传播
每个 Client 独立 response Queue
request ID 拒绝 stale response
Client 使用 get(timeout)，不依赖 Queue.empty 读取响应
fatal/closed/timeout 有区分的失败语义
```

Generator 与资源回收：

```text
SubprocessGenerator：terminate → join → kill → join
只有确认 Process 退出后才清空句柄
失败时保留 live Process handle 并抛 RuntimeError
Queue 显式 close/cancel_join_thread
SampleGeneratorFace 显式关闭 generators 与 index hosts
cleanup error 聚合后向上抛出，允许 retry
WeightedIndexHost join timeout 不再伪装成功
IndexHost / Index2DHost 增加 close
ModelBase finalize 不再静默吞掉 generator cleanup failure
```

### 3.2 自动测试与 Windows spawn 证据

实现侧记录：

```text
Windows / Python 3.11.7 / spawn
python -m unittest discover -s tests/smoke -p "test_batch*.py"
Ran 311 tests
OK
shell EXIT=0
ACTIVE_CHILDREN=[]
无 WeightedIndexHost / IndexHost host_thread 残留
无 live multiprocessing.Process children
```

这关闭了历史 Windows shell 非零退出、空壳 Host、worker 句柄被清空掩盖残留和完整 Batch smoke 未执行等问题。

### 3.3 非阻断验证债务

完整 suite 后仍观察到：

```text
1 × QueueFeederThread (daemon)
1 × interact-style daemon Thread
```

目前没有证据证明这两个线程是 Ticket 16 新增或由 WeightedIndexHost / Generator 未关闭导致：

```text
Ticket-owned Process：0
WeightedIndexHost thread：0
IndexHost thread：0
shell exit：0
```

因此本轮不把未归属线程直接判定为代码缺陷，但保留验证要求：

```text
记录 suite 前后 threading.enumerate() 差集
定位 QueueFeederThread Queue owner
证明 pre-existing before==after，或消除新增 delta
```

Windows GPU 仍需补：

```text
SAEHD FP32 + AdaBelief ≥500 iter
manual save
exit
resume ≥200 iter
无 30 秒 timeout
无静默 fallback
训练结束资源差集可解释
```

签发：

```text
APPROVED / PASS-CODE / ENV-VALIDATION-DEFERRED
```

---

## 4. Ticket 17 Review

### 4.1 strong → quick 契约已关闭

CLI 现在在正式分析与写盘之前检查既有 Sidecar：

```text
existing Sidecar mode=strong
current request=quick
→ return 7
→ formal Sidecar bytes/sha 不变
→ 提示使用 --strong-fingerprint 或删除 Sidecar 后重新建立 quick
```

`build_incremental_plan()` 对 forbidden downgrade 不再填充 `added_sample_keys`，文案、plan 与 CLI 行为已经一致。

端到端测试覆盖：

```text
strong + incremental quick → exit 7 / bytes unchanged
strong + force quick → exit 7 / bytes unchanged
最终 mode 保持 strong
strong → strong incremental → reused_count>0 / fingerprint unchanged
```

### 4.2 已确认的代码契约

```text
--workers 真实进入 spawn Pool
workers=1/2/auto 路径存在
worker target 顶层可 pickle
quick 使用 bounded first/last raw read
strong 使用完整 raw SHA256
full/force 不再主进程预扫后由 worker 重复读取
unsigned legacy record 不计 trusted，不装载旧 pose/quality
同名替换 signature mismatch 后保持 neutral
strict invalid 在正式 write 前失败
worker fatal 不覆盖旧 Sidecar
strong read/hash failure 不写半完整 strong record
full/incremental 使用同一 canonical summary builder
Ticket 14 pose bucket contract 未回退
```

增量算法按每个 `sample_key + signature` 独立分类；signature 不变进入 reuse，只有 mismatch key 进入 recompute，新增与删除分别处理。代码层面不存在全量误重算的已知逻辑缺陷。

### 4.3 非阻断验证债务

建议补一条真实 CLI 精确计数断言：

```text
替换同名图片一个样本
recomputed_count=1
reused_count=N-1
added_count=0
removed_count=0
```

性能矩阵仍未记录：

```text
1k / 10k
ordinary / packed
quick / strong
workers=1 / 2 / auto
elapsed / samples/sec / peak RSS
结果确定性
```

这些属于规模与环境验收，不再阻塞代码依赖解锁，但必须在最终生产签发前完成。

签发：

```text
APPROVED / PASS-CODE / PERF-VALIDATION-DEFERRED
```

---

## 5. Ticket 19 Review

### 5.1 保存窗口与控制流

`TrainerSaveController` 已真实接入 `trainerThread`，并建立：

```text
训练组前处理 close/save
每次 train_one_iter 后立即记录 loss
每一步后检查 initial_iter / target
warmup 不越过 target
pre-queued close 不训练额外 batch
target=1 只保存一次 target_reached
保存前 freeze
model.save 成功后统计并 commit
保存失败不消费窗口
range/start/end 与 degraded_count 可观测
```

### 5.2 rich fatal context 已关闭

保存失败由 Controller 发送：

```text
op=error
reason
iter
error
error_type
traceback
```

随后：

```text
prefer_richer_error 保留信息更完整的 payload
trainerThread 检测 ctrl.last_error 后不重复发送 generic error
TrainerClientState 收到 close 后以 exit_error 结束
Trainer.main 最终 raise_if_fatal()
```

新增测试覆盖：

```text
rich → generic → close
manual / scheduled / target_reached / exit 的 reason+iter
normal close 不 raise
失败窗口保留
```

原 Ticket 要求的是“Trainer integration with fake model”；当前测试直接使用真实 Controller 与 FakeModel，并覆盖 Trainer.main 的消息消费状态。完整 `models.import_model + GPU` 联合运行可作为系统验收，但不构成 Ticket 19 代码阻断。

签发：

```text
APPROVED / PASS / CLOSED
```

---

## 6. Test Evidence Assessment

实现侧证据：

```text
Focused suites：OK
Full freeze：Ran 311 / OK / shell EXIT=0
Windows start method：spawn
ACTIVE_CHILDREN=[]
```

GitHub：

```text
Actions/status checks：none
```

所以本报告是：

```text
独立源码与测试设计 Review
+
实现侧 Windows 测试证据复核
```

不得描述成 GitHub CI PASS，也不得声称 GPU/1k/10k 已完成。

---

## 7. Dependency Frontier

代码依赖现在可以继续：

```text
Lane A：Ticket 18（依赖 Ticket 17）→ UNBLOCKED
Lane B：Ticket 20（依赖 Ticket 16 + 17）→ UNBLOCKED
Lane C：环境验证债务 → 与 18/20 并行
```

环境验证 Lane：

```text
Ticket 16 Windows SAEHD 500 + save/exit + resume 200
Ticket 16 full-suite thread baseline/delta 与 QueueFeeder owner
Ticket 17 1k/10k perf/RSS matrix
Ticket 17 同名替换精确 recompute report count
可选：Ticket 19 真实 GPU Trainer save failure smoke
```

Ticket 21 仍需：

```text
Ticket 18 PASS
Ticket 20 PASS
环境验证债务完成或由维护者再次明确豁免
```

---

## 8. Final Sign-off

```text
BATCH 2 WAVE 1
INDEPENDENT REVIEW ROUND 4

TICKET 16: APPROVED / PASS-CODE / ENV VALIDATION DEFERRED
TICKET 17: APPROVED / PASS-CODE / PERF VALIDATION DEFERRED
TICKET 19: APPROVED / PASS / CLOSED
WAVE 1: APPROVED / CODE-PASS

UNLOCK TICKET 18
UNLOCK TICKET 20
KEEP FINAL PRODUCTION SIGN-OFF BLOCKED
```
