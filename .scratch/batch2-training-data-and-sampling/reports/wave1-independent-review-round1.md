# Batch 2 Wave 1 — Ticket 16 / 17 / 19 独立 Review Round 1

> Wave 状态：**REQUEST_CHANGES / REMEDIATION REQUIRED**  
> Review 日期：2026-07-30  
> 集成开发分支：`codex/batch2-ticket19-loss-window`  
> 实现侧审计 HEAD：`6991b0d7b5ce29741fe3fe8ddad91bdb3462169d`  
> Review 方法：按独立 implementation SHA 拆票静态复核，并检查集成后的控制流与交叉影响。Reviewer 未在本环境重新运行 Windows/GPU/性能测试；GitHub 无 Actions/status check。

---

## 1. 分支与提交边界确认

尽管当前远端只有一个集成开发分支可直接访问，三个 Ticket 的 implementation commits 仍可独立审查：

| Ticket | Base | Implementation SHA | 独立范围 |
|---|---|---|---|
| 16 | `0bb1fa094c3ddf0304eaf6cfcb9b11aac2eff400` | `f9f846ab255a97005890a4ed7b6d3740ee4119e8` | WeightedIndexHost / Generator spawn 与生命周期 |
| 17 | `f9f846ab255a97005890a4ed7b6d3740ee4119e8` | `e0e619ae7acc2b25e2f422db1b8efd5597723e55` | Analyzer workers / signature / trusted match |
| 19 | `c342cc56ad2fbe6402c8b0b3c64c73eaab3cbb55` | `3f7c4cb7e907021bb0ef8f5c2f1eb544fa1e1032` | Loss window / Trainer 保存时序 |

Ticket 15 的配置实现与独立 Final Review 已在更早提交完成，本轮没有重新打开 Ticket 15。

---

## 2. Wave 总结论

```text
Ticket 16: REQUEST_CHANGES
  SPAWN CORE FIXED
  DETERMINISTIC WORKER/QUEUE REAP NOT CLOSED
  WINDOWS SAEHD SAVE/EXIT/RESUME NOT PROVEN

Ticket 17: REQUEST_CHANGES
  WORKERS + STRONG HASH FOUNDATION EXISTS
  UNSIGNED TRUST / STRICT ATOMICITY / IO DUPLICATION OPEN
  INCREMENTAL CONTRACT + PERF MATRIX OPEN

Ticket 19: REQUEST_CHANGES
  TRACKER FOUNDATION ACCEPTED
  REAL TRAINER INITIAL/TARGET/EXIT/FAILURE CONTROL FLOW BROKEN
  TESTS MIRROR HELPER INSTEAD OF REAL LOOP

Wave 1 Integration: REQUEST_CHANGES
  COMMITS ARE SEPARABLE
  NO DIRECT FILE CONFLICT BETWEEN CORE FEATURES
  ACCEPTANCE CLAIMS ARE OVERSTATED
  DO NOT MERGE TO MAIN / DO NOT START FINAL WAVE 2 CLOSEOUT
```

一个 Ticket 的失败不自动否定其它 Ticket；但本轮三票均各自存在阻断项，因此 Wave 1 整体不能签发 PASS。

---

## 3. Ticket 16 独立结论

独立报告：

```text
16-fix-weighted-index-host-windows-spawn-review-round1.md
```

### 已成立

- Client spawn 后 `_host_ref=None`；
- Queue/Event IPC 和 request ID；
- stale response 拒绝；
- focused Windows spawn child / multi-child；
- Ordinary/Packed `debug=False` Generator 主链路。

### 阻断

1. `SampleGeneratorFace.finalize()` 在 join timeout 后无条件清空 `g.p`，可能丢失仍存活 worker 句柄；
2. 测试读取已被清空的 `g.p`，会把残留 worker 误判为已退出；
3. SubprocessGenerator Queue/feeder thread 没有显式 cleanup contract；
4. Host thread join timeout 后仍标记 close 成功并关闭 Queue；
5. 完整 discover exit code、SAEHD 500 iter、save/exit/resume 200 iter、无残留进程仍未完成。

当前状态：

```text
TICKET16-R1 / REQUEST_CHANGES / LIFECYCLE+WINDOWS-ACCEPTANCE
```

---

## 4. Ticket 17 独立结论

独立报告：

```text
17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-review-round1.md
```

### 已成立

- workers 参数真实进入 spawn Pool；
- strong 对完整 raw bytes 计算 SHA256；
- signature mode 写入 Metadata；
- 同名替换的新签名 Sidecar 可检测 stale；
- Ordinary/Packed/Unicode 基础 smoke。

### 阻断

1. 无 signature 的旧记录仍按 sample ID 计入 trusted，并装载旧 pose/quality，违反 ID+signature 固定契约；
2. strict invalid 在正式 Sidecar 已 atomic write 后才返回非零，会覆盖旧 Metadata；
3. quick 路径因 `or True` 完整读取文件，不是 bounded I/O；
4. CLI 主进程先串行读取/hash全部样本，full Analyzer worker 再读取/hash一次，I/O 翻倍且重活未并行；
5. strong raw read/hash 失败仍可写出标为 strong 的半完整 record；
6. incremental output 丢失 Ticket 14 canonical bucket contract 字段；
7. incremental 测试仍使用旧顶层 Schema 和字符串 signature；
8. mandatory trusted/strict/fatal/migration/1k/10k/RSS 测试矩阵未完成。

当前状态：

```text
TICKET17-R1 / REQUEST_CHANGES / TRUST+STRICT+INCREMENTAL+PERF
```

---

## 5. Ticket 19 独立结论

独立报告：

```text
19-fix-loss-window-save-boundary-and-observability-review-round1.md
```

### 已成立

- session-local tracker；
- save 前 freeze；
- save 成功后立即 stats + commit；
- save helper 失败时 buffer 不消费；
- empty 和 history compression 语义合理。

### 阻断

1. 真实 Trainer 每轮先执行 3 次 warmup + 1 次 timed train，随后才判断 `iter==1`，所以 initial save 不可达；
2. target 可被同一 warmup 组越过多个 batch；
3. 已排队 close 在训练组之后才处理，退出前仍会训练额外 batch；
4. save 异常虽离开 helper，但被 trainerThread 最外层捕获并转换成普通 close；
5. 日志没有 start/end iter 或 index；
6. `_record_train_loss()` broad except 静默丢统计；
7. FakeModel 测试复制 helper，没有执行真实 trainerThread warmup/queue/target/preview/outer-exception 控制流；
8. 完整 discover 与 shell exit code 未记录。

当前状态：

```text
TICKET19-R1 / REQUEST_CHANGES / TRAINER-CONTROL-FLOW
```

---

## 6. 集成交叉检查

| 交互 | 结论 |
|---|---|
| Ticket 16 Generator finalize × Ticket 19 Trainer finalize | 有直接关系：Trainer 最终调用 ModelBase.finalize，但 Ticket16 cleanup failure 被 swallow，不能证明退出可靠 |
| Ticket 17 trusted Loader × Ticket 16 weighted sampling | 有安全关系：unsigned record 被 trusted 后会进入 Ticket16 已修好的采样运行时，形成“运行稳定但数据不可信”风险 |
| Ticket 17 workers × Ticket 16 spawn | IPC 对象不同，未发现直接状态冲突；但完整 Windows process exit 尚未统一验证 |
| Ticket 19 save failure × Ticket 16 cleanup | save 失败进入外层 catch 后会 finalize；当前 finalize 又可能掩盖残留 worker，因此错误诊断与退出可靠性相互放大 |
| Ticket 15 config × Ticket 16/17 | 未发现本轮修改回退 Ticket15配置契约；Ticket15保持 CLOSED |

因此实现侧“无阻塞性交叉冲突”结论不完整。文件级冲突不大，但错误传播、数据可信度和进程退出存在真实跨票风险。

---

## 7. 测试证据判断

实现侧记录：

```text
Ticket16 focused: 26 OK / EXIT=0
Ticket17 focused: 53 OK / EXIT=0
Ticket19 focused: 20 OK / EXIT=0
Wave selected focused: 82 OK / EXIT=0
```

这些是有效的局部证据，但不构成 Final PASS，原因：

- Ticket16 cleanup assertion 可被 `g.p=None` 伪通过；
- Ticket17 mandatory strict/unsigned/incremental/perf cases 缺失；
- Ticket19 tests 未执行真实 Trainer control flow；
- 未运行完整 `discover -s tests/smoke -p "test_batch*.py"` 并证明 shell exit 0；
- 无 GitHub Actions/status check；
- Windows GPU SAEHD 验收未完成。

---

## 8. Remediation 安排

建议保持分票修复，不提交不可拆分的大型综合 commit。

### Lane 16 — 生命周期返修

```text
优先级：P0
目标：真实 worker/queue/thread 确定性回收 + full discover exit 0
之后：Windows SAEHD 500 + save/exit/resume 200
```

### Lane 17 — Trust/Strict/IO 返修

```text
优先级：P0
先修：unsigned untrusted、strict pre-write gate、canonical incremental output
再修：bounded quick I/O、消除双重读取、structured migration tests
最后：1k/10k/RSS 性能表
```

### Lane 19 — Trainer 状态机返修

```text
优先级：P0
目标：逐 train call 检查 first/target/close，save failure 明确传播
测试：抽取真实 controller 或 trainerThread harness，禁止复制 helper
```

三个 Lane 可由不同 Agent 并行，但必须：

- 从同一 Wave 1 集成 HEAD 开始；
- 每票独立 remediation commit；
- 不同时修改同一份 `current.md`，由集成负责人最后统一；
- 合并后再跑一次 Wave focused + 完整 Batch smoke；
- 再进行 Wave 1 Final Review。

---

## 9. 依赖与 Frontier

```text
Ticket 14: PASS / CLOSED
Ticket 15: PASS / CLOSED
Ticket 16: REQUEST_CHANGES
Ticket 17: REQUEST_CHANGES
Ticket 19: REQUEST_CHANGES

Ticket 18: BLOCKED-BY-TICKET17-REMEDIATION
Ticket 20: BLOCKED-BY-TICKET16+17-REMEDIATION
Ticket 21: BLOCKED-BY-14—20 + WINDOWS GPU
Batch 3: BLOCKED
```

即使 Ticket18/20 已开始 provisional 工作，也必须标记为 `PENDING-UPSTREAM-REMEDIATION`，不得基于当前 16/17 接口签发完成。

---

## 10. 最终签发

```text
BATCH 2 WAVE 1
INDEPENDENT REVIEW ROUND 1
REQUEST_CHANGES
THREE TICKETS REQUIRE SEPARATE REMEDIATION
NO MERGE TO MAIN
NO FINAL WAVE 2 CLOSEOUT
```
