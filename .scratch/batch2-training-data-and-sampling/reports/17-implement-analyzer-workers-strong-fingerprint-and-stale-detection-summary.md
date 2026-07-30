# Ticket 17 — Analyzer Workers / Strong Fingerprint / Trusted Match 实施总结

> 当前状态：**IMPLEMENTATION COMPLETE / AWAITING WAVE-1 CENTRAL REVIEW**  
> 实现者自审：`PASS`（不得自行签发 APPROVED/PASS/CLOSED）  
> Independent Review：`PENDING`  
> Base Commit（含 Ticket 16）：`f9f846ab255a97005890a4ed7b6d3740ee4119e8`  
> 工作分支：`codex/batch2-ticket17-analyzer-workers`  
> 环境：Windows / Python 3.11.7 / spawn  
> `--options-json` 文档同步：**NA**

---

## 1. Signature Schema

```text
SampleSignature:
  sample_key, byte_size, mtime_ns?, packed_offset?,
  quick_hash?, content_sha256?
```

| Mode | 算法 | 字段 |
|---|---|---|
| quick | `sha256(first_chunk \|\| last_chunk \|\| size)`，chunk=65536 | + quick_hash |
| strong | 完整 `sha256(raw_bytes)` | + content_sha256（及 quick_hash） |

`analysis_config.signature` 持久化：

```json
{
  "mode": "quick|strong",
  "algorithm": "sha256_first_last_chunk_size|sha256_full",
  "chunk_size": 65536
}
```

Ordinary：读文件字节。  
Packed：`Sample.read_raw_file()` / worker 内 `packed_path+offset+size` 读取，不改 pak 格式。

---

## 2. Workers 架构

```text
resolve_worker_count(None) -> min(cpu_count, 8)
workers=1 -> 主进程顺序
workers=N -> multiprocessing.get_context("spawn").Pool
```

- 任务为可 pickle 的 descriptor（路径/offset/landmarks/config），不传完整 Sample、不传 BGR。
- 顶层函数 `analyze_sample_task` 供 Windows spawn。
- Worker 崩溃向上抛出，不静默跳过。
- 结果按 `sample_id` 稳定排序；workers=1/2 fingerprint 一致。
- Packed 多 worker：通过 packed_path+offset 已支持（本机测试 PASS）。

---

## 3. Trusted Match

Loader 区分：

```text
id_matched_count
signature_matched_count
stale_signature_count
missing_record_count
duplicate_count
trusted_matched_count  (== matched_count / matched_ratio)
record_matched         (== unique sample_id hit, Ticket 14 诊断语义)
```

- **Trusted**：id 命中 + signature 匹配（或 legacy 无 signature 字段记录）才装入 pose/quality。
- **同名替换**：id 命中、signature 失败 → stale，旧 quality/pose 不装入。
- Legacy 无 signature 的 sidecar：仍映射诊断字段，兼容旧 Ticket 14 测试。

---

## 4. 增量 mode 策略

| 迁移 | 行为 |
|---|---|
| quick→quick | 可按 signature 复用 |
| strong→strong | 可按 content_sha256 复用 |
| quick→strong | 全量重算（`SIGNATURE_MODE_UPGRADE_TO_STRONG_REQUIRES_RECOMPUTE`） |
| strong→quick | 禁止降级全量重算（`SIGNATURE_MODE_DOWNGRADE_FORBIDDEN`） |

---

## 5. 修改文件

| 文件 | 变更 |
|---|---|
| `samplelib/metadata/fingerprint.py` | content_sha256、quick/strong、signatures_match |
| `samplelib/metadata/analyzer.py` | workers pool、strong 模式、analysis_config.signature |
| `samplelib/metadata/loader.py` | trusted match / stale 统计 |
| `samplelib/metadata/incremental.py` | signature mode 兼容 |
| `mainscripts/FacesetAnalyzer.py` | 真正使用 --workers / --strong-fingerprint |
| 新测试 | fingerprint_strong / analyzer_workers / trusted_match_stale |

---

## 6. 测试证据

```text
python -m unittest \
  tests.smoke.test_batch2_fingerprint_strong \
  tests.smoke.test_batch2_analyzer_workers \
  tests.smoke.test_batch2_trusted_match_stale \
  tests.smoke.test_batch2_analyzer_core \
  tests.smoke.test_batch2_metadata_loader \
  tests.smoke.test_batch2_incremental \
  tests.smoke.test_batch2_analyzer_cli

Ran 53 tests / OK / EXIT=0
```

覆盖：Ordinary/Packed/Unicode、workers=1/2/auto、strong、同名替换 stale、CLI workers 日志。

### 性能（CLI fixture ~10 samples，参考）

```text
workers used=8, quick ordinary: ~7–15 samples/sec (小 fixture 开销主导)
incremental reuse 10: ~1289 samples/sec (几乎无重算)
```

未跑 1k/10k 大数据性能基准 → 记录为 **PARTIAL-PERF**。

---

## 7. Windows / Review 状态

```text
IMPLEMENTATION COMPLETE
WORKERS-SPAWN-PASS
STRONG-FP-PASS
TRUSTED-MATCH-PASS
PACKED-WORKERS-PASS
PENDING-LARGE-PERF-BENCH
AWAITING-WAVE1-CENTRAL-REVIEW
```

不得写 resolved / APPROVED / PASS / CLOSED。

---

## 8. 风险

1. 新 quick 含 `quick_hash` 后 dataset fingerprint 与极旧无 hash 记录不同 → 可能 PARTIAL_MATCH；loader 仍可 trusted 按样本匹配。
2. 大 faceset 上 strong + 多 worker 峰值 I/O 未量化。
3. Incremental reconcile 路径 summary 桶名仍有旧字段风格（pre-existing）。
4. 需中央 Review 后进入 Wave 1 集成。
