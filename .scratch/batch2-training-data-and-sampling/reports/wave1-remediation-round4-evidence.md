# Batch 2 Wave 1 — Remediation Round 4 Evidence

> 日期：2026-07-30  
> 分支：`codex/batch2-ticket19-loss-window`  
> 实现侧状态：`CODE REMEDIATION COMPLETE / AWAITING INDEPENDENT REVIEW ROUND 4`  
> **禁止**实现者签发 `APPROVED / PASS / CLOSED / RESOLVED`

---

## 1. 范围（对应 R3 REQUEST_CHANGES）

| Finding | 处理 |
|---|---|
| T17-R3-01 strong→quick 文案与行为冲突 | CLI 拒绝 exit=7，不覆盖 strong Sidecar |
| T19-R3-01 rich error 被 generic 覆盖 | prefer_richer_error + outer except 跳过重复 put |
| T19-R3-02 缺序列测试 | rich→generic→close + manual/scheduled/target/exit reason 测试 |
| T16-R3-01 ALIVE 非零 | 补 IndexHost close 路径；测试 finally close；bare Queue 清理 |
| T16-R3-02 完整 discover | 运行 `test_batch*.py` 并记录 EXIT=0 |

仍开放：

```text
Windows SAEHD 500 + resume 200（GPU）
Analyzer 1k/10k perf/RSS
完整 ALIVE=0（仍见 1×QueueFeederThread + 1×interact daemon Thread）
```

---

## 2. 代码改动摘要

### Ticket 17

- `mainscripts/FacesetAnalyzer.py`：若 formal Sidecar 已是 strong 且当前为 quick → `return 7`，不写盘
- `samplelib/metadata/incremental.py`：DOWNGRADE plan 不再填 `added_sample_keys`（禁止静默全量列表）
- 测试：CLI strong→quick refuse + strong→strong reuse

### Ticket 19

- `prefer_richer_error()` / `TrainerClientState` 保留 reason/iter
- `trainerThread`：`ctrl.last_error` 已上报时不重复 put generic error
- 测试：rich→generic→close；四类 save reason

### Ticket 16

- 测试路径强制 `IndexHost/Index2DHost.close()`（baseline / legacy adapters）
- bare mp.Queue 测试 finally close/cancel_join_thread
- sticky join timeout 测试恢复后确保 real thread 退出

---

## 3. 测试证据

```text
环境：Windows / Python 3.11.7 / spawn

Focused：
  test_batch2_trainer_save_window / analyzer_cli / legacy / baseline hosts
  → OK

Full freeze command：
  python -m unittest discover -s tests/smoke -p "test_batch*.py"
  Ran 311 tests
  OK
  shell EXIT=0

Lifecycle residual (after full suite stopTestRun)：
  ACTIVE_CHILDREN: []
  residual alive threads: 2
    - QueueFeederThread (daemon)
    - Thread-N (daemon, interact-style background)
  no WeightedIndexHost / IndexHost host_thread residuals
  no live multiprocessing.Process children
```

`--options-json` 文档同步：**NA**

---

## 4. 策略冻结说明（Ticket 17）

```text
strong existing Sidecar + quick current request
  → refuse exit code 7
  → formal Sidecar bytes unchanged
  → re-run with --strong-fingerprint to keep/refresh strong
  → or delete Sidecar to start a new quick analysis
```

---

## 5. 风险与未完成

```text
1. 仍非严格 ALIVE=0：1 个 QueueFeederThread + 1 个全局 daemon Thread
2. Windows GPU SAEHD 500/resume 200 未跑
3. 1k/10k Analyzer perf/RSS 未记
4. 真实 trainerThread + models.import_model 端到端仍用 FakeModel 序列模拟
5. 实现者不得签发 PASS/CLOSED
```
