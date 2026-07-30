# Batch 2 Wave 1 — Central Review Round 1（实现者对照审计）

> 审查日期：2026-07-30  
> 审查性质：**实现侧对照审计 / 集中回归证据**  
> **不是**独立 Reviewer 的 Final Approval  
> 按 AGENTS.md：实现者**不得**签发 `APPROVED / PASS / CLOSED`  
> 建议：另开独立 Reviewer 对每票给出正式结论

---

## 0. 范围与锚点

| Ticket | 分支 | Impl commit | 主题 |
|---|---|---|---|
| 16 | `codex/batch2-ticket16-windows-spawn` | `f9f846a` | WeightedIndexHost Windows spawn / lifecycle |
| 17 | `codex/batch2-ticket17-analyzer-workers` | `e0e619a` | Analyzer workers / strong FP / trusted match |
| 19 | `codex/batch2-ticket19-loss-window` | `3f7c4cb` | Loss window save boundary |

集成 HEAD（含 16+17+19）：`3f7c4cb` on `codex/batch2-ticket19-loss-window`

---

## 1. 组合回归证据

```text
python -m unittest \
  tests.smoke.test_batch2_weighted_index_host \
  tests.smoke.test_batch2_weighted_index_host_spawn \
  tests.smoke.test_batch2_generator_sampling_spawn \
  tests.smoke.test_batch2_fingerprint_strong \
  tests.smoke.test_batch2_analyzer_workers \
  tests.smoke.test_batch2_trusted_match_stale \
  tests.smoke.test_batch2_loss_window_logging \
  tests.smoke.test_batch2_trainer_save_window \
  tests.smoke.test_batch2_metadata_loader \
  tests.smoke.test_batch2_analyzer_core

Ran 82 tests / OK / process EXIT=0
```

环境：Windows / Python 3.11.7 / spawn。

---

## 2. Ticket 16 — 契约对照

| 验收项 | 状态 | 证据 |
|---|---|---|
| Client pickle `_host_ref=None` | **MEETS** | `__getstate__` + unit test |
| spawn child draw | **MEETS** | `test_batch2_weighted_index_host_spawn` |
| multi-child | **MEETS** | 4-way spawn |
| request_id stale discard | **MEETS** | unit test |
| close/fatal/timeout | **MEETS** | Events + short timeout |
| 禁止 Queue.empty() | **MEETS** | `queue.get(timeout=...)` |
| debug=False Ordinary/Packed | **MEETS** | generator spawn tests |
| SampleGeneratorFace finalize | **MEETS** | host 引用 + terminate |
| SAEHD 500 iter GPU | **GAP** | 未跑 → PENDING-WINDOWS-SAEHD-GPU |
| 全量 discover 进程退出 | **GAP** | 未在本轮跑完整 suite |

### 建议结论（给独立 Reviewer）

```text
RECOMMEND: CONDITIONAL PASS (unit/spawn)
BLOCK formal PASS until SAEHD GPU save/exit/resume evidence
```

### 发现 / 风险

1. **W1-16-01（中）** SAEHD 真训练与残留 worker 人工验收仍缺。  
2. **W1-16-02（低）** Host close 后 Queue handle 关闭，不能再 pickle Client 到新进程（设计如此，已测 spawn-before-close）。  
3. **W1-16-03（低）** 进程退出时偶发 daemon thread 异常日志（focused suite EXIT=0）。

---

## 3. Ticket 17 — 契约对照

| 验收项 | 状态 | 证据 |
|---|---|---|
| `--workers` 真实生效 | **MEETS** | Pool + analysis_config.workers + timing |
| `--strong-fingerprint` 读完整字节 | **MEETS** | content_sha256 + strong tests |
| signature mode 持久化 | **MEETS** | analysis_config.signature |
| Loader 逐样本 signature | **MEETS** | signatures_match |
| 同名替换 stale | **MEETS** | trusted_match_stale test |
| workers=1/2 输出一致 | **MEETS** | fingerprint equal |
| Ordinary/Packed/Unicode | **MEETS** | analyzer_workers + fingerprint |
| Incremental mode migration | **MEETS** | strong↔quick 策略 |
| 1k/10k 性能基准 | **GAP** | 仅 ~10 sample fixture → PARTIAL-PERF |
| 原子写失败保持旧 Sidecar | **PARTIAL** | 沿用既有 write_metadata_atomic；无新增 fail 注入测 |

### 建议结论

```text
RECOMMEND: CONDITIONAL PASS (functional)
Optional follow-up: large-scale perf numbers for Ticket 21
```

### 发现 / 风险

1. **W1-17-01（中）** Legacy 无 signature 字段的 sidecar 仍按 id 装载 quality（兼容 Ticket 14）；新 analyzer 总会写 signature。  
2. **W1-17-02（中）** quick 默认写入 `quick_hash` 会改变 dataset fingerprint 相对“极旧无 hash”记录 → 可能 PARTIAL_MATCH，但 trusted 仍可按样本。  
3. **W1-17-03（低）** Incremental reconcile 路径 summary 桶名风格仍有历史遗留（非本票引入）。  
4. **W1-17-04（低）** 性能未测 1k/10k。

---

## 4. Ticket 19 — 契约对照

| 验收项 | 状态 | 证据 |
|---|---|---|
| 保存前冻结窗口 | **MEETS** | freeze before model.save |
| 成功后立即统计 | **MEETS** | 无 after_save 延迟 |
| 不含保存后 batch | **MEETS** | trainer_save_window test |
| 失败不消费 | **MEETS** | fail retain test |
| resume 不混旧 history | **MEETS** | empty tracker on start |
| 空窗口不复用 last | **MEETS** | window=0 (empty) |
| initial/manual/scheduled/target/exit | **MEETS** | reasons + tests |
| history 压缩不影响窗口 | **MEETS** | session buffer |
| 不改 Loss/checkpoint | **MEETS** | 仅 Trainer + loss_stats |

### 建议结论

```text
RECOMMEND: PASS (implementation contract)
Still needs independent Reviewer sign-off
```

### 发现 / 风险

1. **W1-19-01（低）** Trainer 集成用 FakeModel 镜像 `model_save` 语义，未拉起完整 `trainerThread` GUI 循环（可接受，ticket 允许 fake model）。  
2. **W1-19-02（低）** `exit` 时若 `is_reached_goal` 已真，`model_save` 直接 no-op（与旧逻辑一致：达目标后不再 save）。  
3. **W1-19-03（信息）** 日志格式异常被吞掉以免伤训练；save 本身异常仍传播。

---

## 5. 交叉影响

| 交互 | 评估 |
|---|---|
| 16 spawn Host × 17 Analyzer workers | 独立 IPC；均用 spawn；无共享状态冲突 |
| 16 Generator finalize × 19 Trainer finalize | ModelBase.finalize 调 gen.finalize；19 不改 finalize 语义 |
| 17 Metadata × 16 sampling | trusted match 改善采样质量；16 修复运行时卡死 |
| 19 日志 × 训练 | 不改 loss_history checkpoint 切片 |

---

## 6. 分票结论（实现侧建议，非正式签发）

```text
Ticket 16：MEETS-UNIT / GAP-SAEHD-GPU     → 建议独立 Reviewer: CHANGES NOT REQUIRED for code; HOLD formal PASS on GPU
Ticket 17：MEETS-FUNCTIONAL / GAP-PERF     → 建议独立 Reviewer: CONDITIONAL PASS
Ticket 19：MEETS-CONTRACT                 → 建议独立 Reviewer: PASS
Wave 1 Integration (this HEAD)：
  focused 82 OK
  NOT a substitute for independent Final Review
  NOT full tests/smoke discover exit-code proof
```

**明确禁止状态字：**

本文件**不**包含 `APPROVED` / `PASS` / `CLOSED` 作为 Ticket 最终状态签发。

---

## 7. 建议后续动作

1. 独立 Reviewer 按票出具 R1 正式结论（可并行）。  
2. 合入 `codex/batch2-wave1-integration`（保留各 ticket commit）。  
3. Windows GPU：SAEHD 500+200 resume（关 Ticket 16 正式 PASS）。  
4. 可选：1k analyzer 性能表写入 Ticket 17/21。  
5. Wave 2：Ticket 18 / 20 provisional 基于 `e0e619a` + `f9f846a`。

---

## 8. 必读 Summary

- `16-fix-weighted-index-host-windows-spawn-summary.md`
- `17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md`
- `19-fix-loss-window-save-boundary-and-observability-summary.md`
