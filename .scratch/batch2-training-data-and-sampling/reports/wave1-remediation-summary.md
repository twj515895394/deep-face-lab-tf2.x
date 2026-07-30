# Batch 2 Wave 1 — Remediation Summary (Tickets 16 / 17 / 19)

> 日期：2026-07-30  
> 分支：`codex/batch2-ticket19-loss-window`  
> 实现者状态：`REMEDIATION IMPLEMENTED / AWAITING INDEPENDENT REVIEW`  
> **不得**由实现者签发 `APPROVED / PASS / CLOSED / RESOLVED`

---

## 1. 范围

按 `wave1-remediation-and-review-working-branch-policy.md` 在统一分支上返修 P0：

| Ticket | 主题 |
|---|---|
| 16 | Worker / Queue / Host thread 确定性回收 |
| 17 | unsigned trust / strict gate / strong 完整性 / quick bounded I/O / incremental contract |
| 19 | Trainer initial / target / close / save-failure 状态机 + range 可观测性 |

未改：采样概率公式、SAEHD 网络、checkpoint 格式、options-json 权威参数、Merge。

---

## 2. Ticket 16 改动

### 代码

- `core/joblib/SubprocessGenerator.py`：`close()/finalize()`；terminate→join→kill→join；确认死亡后才清空 `p`；Queue `close` + `cancel_join_thread`
- `samplelib/SampleGeneratorFace.py`：通过 generator.close 回收；失败聚合后 re-raise；幂等但允许残留时重试
- `samplelib/sampling/weighted_index_host.py`：host thread join 超时 → `RuntimeError`（不再伪装成功）
- `models/ModelBase.py`：cleanup 错误不再静默吞掉

### 测试

- `tests/smoke/test_batch2_generator_sampling_spawn.py`：finalize 前保存 Process 句柄；`active_children` 无新增残留
- `tests/smoke/test_batch2_weighted_index_host.py`：close join timeout 失败语义

### 仍开放

- Windows SAEHD 500 + save/exit/resume 200（需 GPU 人工）
- 完整 `discover -s tests/smoke -p "test_batch*.py"` shell exit 0（本机 focused 已过）

---

## 3. Ticket 17 改动

### 代码

- `samplelib/metadata/loader.py`：unsigned → `record_matched` 可真，**不 trusted**，不装载 pose/quality；`unsigned_signature_count` + warning
- `samplelib/metadata/fingerprint.py`：quick bounded first/last I/O；strong 才 full read；packed EOF clamp 与 `read_raw_file` 一致
- `samplelib/metadata/analyzer.py`：strong 缺 hash → issues，计 invalid
- `mainscripts/FacesetAnalyzer.py`：
  - full/force 不在主进程预扫全部 signature
  - strict gate **在** formal Sidecar write **之前**
  - incremental 保留 Ticket 14 canonical pose contract 字段

### 测试

- unsigned not trusted
- strict 失败保留旧 Sidecar bytes/sha
- incremental 保留 canonical buckets
- quick bounded hash ≡ full-bytes hash
- 既有 loader 手写 fixture 补 matching signature

### 仍开放

- 1k/10k workers perf / peak RSS 矩阵
- worker fatal 保持旧 Sidecar 专项注入（strict invalid 已覆盖）

---

## 4. Ticket 19 改动

### 代码

- 新增 `mainscripts/trainer_save_control.py`：`TrainerSaveController`
  - 训练组前处理 close/save
  - 每次 `train_one_iter` 后检查 initial/target
  - warmup 不越过 target
  - pre-queued close → 0 train + exit save
  - save 失败 → `c2s` error + re-raise + 不 commit
- `mainscripts/Trainer.py`：接入 controller
- `samplelib/sampling/loss_stats.py`：iter range；`format_loss_window_log` 含 `range=` / `window_incomplete`

### 测试

- 重写 `test_batch2_trainer_save_window.py` 使用真实 controller（非复制 helper）
- 覆盖 target=1/2、resume、close、save failure、initial_iter

### 仍开放

- 完整 discover exit code
- 真实 GPU Trainer 长跑

---

## 5. 验证证据

```text
环境：Windows / Python 3.11.7 / spawn
compileall: OK
Focused suite: Ran 90 tests / OK / EXIT=0

覆盖模块：
  weighted_index_host (+ spawn)
  generator_sampling_spawn
  trusted_match_stale
  fingerprint_strong
  analyzer_cli / workers
  metadata_loader
  trainer_save_window
  loss_window_logging
```

```text
--options-json 文档同步：NA
文档版本：v1.1（未改训练参数）
```

GitHub 无 Actions；**不得**写 CI PASS。

---

## 6. 签发边界

实现者结论：

```text
Ticket 16：REMEDIATION IMPLEMENTED / UNIT-SPAWN PASS / PENDING-SAEHD-GPU / AWAITING INDEPENDENT REVIEW
Ticket 17：REMEDIATION IMPLEMENTED / CONTRACT FOCUSED PASS / PERF MATRIX OPEN / AWAITING INDEPENDENT REVIEW
Ticket 19：REMEDIATION IMPLEMENTED / CONTROLLER HARNESS PASS / AWAITING INDEPENDENT REVIEW
Wave 1：AWAITING INDEPENDENT REVIEW ROUND 2
```

禁止合入 main；禁止解锁 Ticket 18/20 最终签发，直至独立 Reviewer 复核。
