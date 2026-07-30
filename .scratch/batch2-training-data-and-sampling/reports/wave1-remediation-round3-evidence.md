# Batch 2 Wave 1 — Remediation Round 3 Evidence

> 日期：2026-07-30  
> 分支：`codex/batch2-ticket19-loss-window`  
> 实现侧状态：`CODE REMEDIATION COMPLETE / AWAITING INDEPENDENT REVIEW ROUND 3`  
> **禁止**实现者签发 `APPROVED / PASS / CLOSED / RESOLVED`

---

## 1. 范围（对应 R2 REQUEST_CHANGES）

| Finding | 处理 |
|---|---|
| T17-R2-01 Incremental 未使用 canonical builder | 抽取 `summary_builder.build_canonical_summary`，full/incremental 共用 |
| T17-R2-02 failure/parity 矩阵缺口 | 补 full→incremental parity、partial-change、worker fatal、mode migration 测试 |
| T19-R2-01 主线程忽略 `op=error` | `TrainerClientState` + `main()` 显式处理；fatal 后 raise |
| T19-R2-02 degraded warning 无界 | 每窗口首次 warning + count；commit 后重置 |
| T19-R2-03 target=1 双保存 | 合并为单次 `target_reached` |
| T16 discover shell exit ≠ 0 | `mplib.IndexHost/Index2DHost.close()` + Host `__del__` 不再 full close |

未做（仍开放验收）：

```text
Windows SAEHD FP32 + AdaBelief 500 / save-exit / resume 200
Ticket 17 1k/10k workers perf / peak RSS 矩阵
实现者不得签发 PASS/CLOSED
```

---

## 2. 主要代码改动

### Ticket 17

- 新增 `samplelib/metadata/summary_builder.py`
  - `CANONICAL_SUMMARY_KEYS`
  - `build_canonical_summary` / `extract_pose_buckets`
- `samplelib/metadata/incremental.py`
  - `reconcile_and_finalize_samples` 输出 Ticket 14 summary（不再写 legacy 顶层字段）
  - 可选 `quality_config`；legacy flat pose 升级为 nested `pose`
- `samplelib/metadata/analyzer.py`
  - `_finalize_result` 改用同一 builder
- `mainscripts/FacesetAnalyzer.py`
  - incremental 传入 `quality_config`

### Ticket 19

- `mainscripts/trainer_save_control.py`
  - bounded degraded + `window_degraded_count`
  - save log `degraded_count` / `window_incomplete`
  - commit 后 `_reset_window_degraded`
  - target=1 单次 `target_reached`
- `samplelib/sampling/loss_stats.py`
  - `commit()` 清 `degraded`；`format_loss_window_log(..., degraded_count=)`
- `mainscripts/Trainer.py`
  - `TrainerClientState` 处理 error/close
  - `no_preview` / GUI 路径 fatal 后 `raise_if_fatal`
  - trainerThread 异常路径 `e.set()` 避免 main 永久等待

### Ticket 16 residual（discover exit）

- `core/mplib/__init__.py`：`IndexHost` / `Index2DHost` 增加 stop + `close()`
- `samplelib/sampling/weighted_index_host.py`：`__del__` 不再调用完整 `close()`（避免解释器退出时 stderr 死锁）

### 测试契约对齐

- `tests/smoke/test_batch2_metadata_sampling_e2e.py`
  - legacy alias 需签名才 trusted；unsigned 断言 neutral pose（对齐 T17 trust）

---

## 3. 测试证据

```text
环境：Windows / Python 3.11.7（pyenv） / spawn
命令：
  python -m compileall <changed paths>   → OK
  python -m unittest discover -s tests/smoke -p "test_batch2*.py" -q
结果：
  Ran 233 tests in ~50s
  OK
  shell EXIT=0
```

Focused 覆盖（含 R2 阻断）：

```text
test_batch2_incremental
test_batch2_analyzer_cli（parity / worker fatal / mode migration）
test_batch2_trainer_save_window（error 传播 / degraded / target=1 dedupe）
test_batch2_analyzer_core / loss_window_logging
test_batch2_metadata_sampling_e2e（legacy alias + unsigned）
```

`--options-json` 文档同步：**NA**（本轮无训练参数变更）

---

## 4. 仍开放 / 风险

```text
1. 部分测试路径仍可能残留少量 daemon host/queue feeder（discover 后 ALIVE 非零但已不导致 shell crash）
2. Windows GPU SAEHD 500 + resume 200 未跑
3. Analyzer 1k/10k perf/RSS 未记
4. 实现者不得签发 Ticket 16/17/19 PASS/CLOSED
5. Independent Review Round 3 待跑
```

---

## 5. 建议 commit 切分（待用户确认后提交）

```text
fix(ticket17): unify incremental canonical summary builder
fix(ticket19): propagate trainer fatal errors and bound save windows
fix(ticket16): close mplib index hosts for discover clean exit
test(wave1): parity/fatal/error harness and discover EXIT=0 evidence
docs(wave1): record round3 remediation evidence
```
