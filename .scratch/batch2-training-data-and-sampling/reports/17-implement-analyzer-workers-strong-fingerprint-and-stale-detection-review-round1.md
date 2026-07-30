# Ticket 17 — Analyzer Workers / Strong Fingerprint / Stale Detection 独立 Review Round 1

> Review 状态：**REQUEST_CHANGES / FUNCTIONAL-PARTIAL / TRUST-AND-STRICT-CONTRACTS-OPEN**  
> Review 日期：2026-07-30  
> Base：`f9f846ab255a97005890a4ed7b6d3740ee4119e8`  
> 被审实现：`e0e619ae7acc2b25e2f422db1b8efd5597723e55`  
> 集成分支：`codex/batch2-ticket19-loss-window`  
> Review 方法：独立静态源码、测试源码、Ticket 与实现侧测试记录复核。Reviewer 未在本环境重新运行 Windows/performance 测试；GitHub 无 Actions/status check。

---

## 1. 结论

```text
REQUEST_CHANGES
WORKERS SPAWN PATH: IMPLEMENTED
STRONG SHA256: IMPLEMENTED
SAME-NAME STALE DETECTION: ESTABLISHED
UNSIGNED RECORDS STILL TRUSTED: CONTRACT BROKEN
STRICT MODE OVERWRITES SIDECAR BEFORE FAILURE: CONTRACT BROKEN
QUICK/STRONG IO PATH: SERIAL + DUPLICATED
INCREMENTAL CONTRACT/TESTS: NOT CLOSED
PERFORMANCE ACCEPTANCE: NOT DONE
TICKET 17: NOT PASS / NOT CLOSED
```

实现不是空壳：`--workers` 已接到 spawn Pool，`--strong-fingerprint` 会生成完整 SHA256，同名替换测试也能使新 Sidecar 记录变 stale。

但 trusted match、strict 原子语义和 incremental 路径仍存在阻断级问题，因此不能按实现侧建议签发 conditional PASS。

---

## 2. 已确认关闭

### 2.1 Workers 基础路径

- `workers=None` bounded 到最多 8；
- `workers=1` 走主进程；
- `workers>1` 使用 `multiprocessing.get_context("spawn").Pool`；
- worker target 为模块顶层函数；
- 传递 descriptor，不传完整 Sample/BGR；
- Ordinary、Packed、Unicode 有 smoke；
- records 按 sample_id 稳定排序。

### 2.2 Strong fingerprint 基础路径

- `SampleSignature` 增加 `quick_hash` / `content_sha256`；
- strong 模式对 raw bytes 计算完整 SHA256；
- signature mode、algorithm、chunk size 写入 analysis_config；
- Loader 能按保存模式生成 current signature；
- 同名内容替换会增加 stale count，并保持旧 pose/quality 为 neutral。

这些公共接口后续返修不得回退。

---

## 3. 阻断项

## T17-R1-01 — 无 signature 的记录仍被计入 trusted match

**等级：P0 / TRUST CONTRACT BLOCKER**

Loader 当前逻辑：

```python
saved_sig = rec.get("signature")
if saved_sig is None:
    sig_ok = True
    legacy_unsigned = True
...
trusted_matched_count += 1
```

这意味着只要 sample_id 相同，旧 unsigned record 仍会：

- 进入 trusted matched；
- 提高 matched_ratio；
- 装载旧 pose / quality；
- 可能使 Metadata Sampling 继续可用。

Ticket 17 的固定契约是：

```text
sample_id match
AND
signature match
才 trusted
```

没有 signature 无法证明同名图片未被替换。兼容读取可以保留 `record_matched=True`，但不得计入 trusted，也不得装载旧业务数组。

建议：

```text
unsigned record:
  id_matched=True
  signature_matched=False
  trusted=False
  unsigned_signature_count += 1
  pose/quality remain neutral
  warning + re-analyze reason
```

如维护者确实要允许 unsigned trusted，必须修改 Ticket/安全模型并明确承担 stale 风险；当前不能由实现自行放宽。

## T17-R1-02 — strict mode 在失败前已覆盖写入 Sidecar

**等级：P0 / ATOMICITY BLOCKER**

CLI 当前顺序：

```text
analyze
→ write_metadata_atomic(output_file, final_metadata)
→ generate report
→ if strict and invalid_samples > 0: return 5
```

因此 strict 运行遇到 invalid sample 时，会先覆盖旧 Sidecar，再返回非零。

Ticket 明确要求：

```text
strict invalid → 非零
worker/pool 正常关闭
临时输出不得覆盖旧 Metadata
```

必须把 strict validity gate 移到 atomic write 之前。建议先基于 AnalyzerResult/final metadata 计算 invalid count，strict 不通过时仅输出诊断到 stderr/临时 report，不替换正式 Sidecar。

必须新增旧 Sidecar sentinel 测试：strict 失败后 bytes/sha 完全不变。

## T17-R1-03 — quick 模式实际读取完整文件，且主进程与 worker 重复读取

**等级：P1 HIGH / PERFORMANCE-ARCHITECTURE**

`build_signature_from_sample()` 当前存在：

```python
if data is None and (mode == SIGNATURE_MODE_STRONG or True):
    data = read_sample_raw_bytes(...)
```

`or True` 使 quick/strong 均完整读取 raw bytes。所谓 bounded quick hash 只是在已经完整加载到内存后截取 first/last chunk，并不 bounded I/O 或峰值内存。

更严重的是 CLI 在创建 incremental plan 前，对全部样本串行调用 `build_signature_from_sample()`；随后 full Analyzer worker 又重新读取同一 raw bytes、重新 quick/strong hash、重新 decode。

结果：

```text
full quick: main serial full read + worker full read
full strong: main serial full SHA + worker full SHA
```

这使最重的 signature I/O 先在单进程执行，`--workers` 无法并行化核心工作，并把 I/O 翻倍。

必须重构为：

- full/force run 不在主进程预先读取全部 signature；
- incremental 才做 current signature scan；
- quick 模式 ordinary 使用 seek/read first+last chunk，不读取全文；
- Packed 使用已知 offset/size 做 bounded reads；
- strong 只完整读取一次，并由 worker result 提供 signature；
- 记录实际 I/O/perf 数据。

## T17-R1-04 — strong raw read/hash 失败仍可写出标记为 strong 的半完整记录

**等级：P0 / SIGNATURE INTEGRITY**

worker 对 raw read 异常仅追加 issue：

```text
RAW_READ_ERROR_xxx
```

随后仍返回 signature，其中 `content_sha256=None`，full non-strict 流程仍会写入 `analysis_config.signature.mode=strong` 的 Sidecar。

Ticket 要求 strong hash 失败不得写半完整记录。至少应：

- record 明确 invalid/untrusted；
- strong sidecar 中不能把缺 hash 记录视为已签名；
- strict 时不得覆盖旧 Sidecar；
- 对 hash/read failure 增加失败注入测试。

## T17-R1-05 — incremental 输出回退了 Ticket 14 的 canonical analysis_config

**等级：P0 / REGRESSION**

full Analyzer 写入 pose contract：

```text
bucket_contract_version
canonical_yaw_buckets
canonical_pitch_buckets
yaw_thresholds
pitch_thresholds
```

但 CLI incremental reconcile 新建 `FacesetMetadataV1` 时只写 thresholds，丢失前三项。Ticket 14 已冻结这些公共字段，后续 Ticket 不得回退。

同时 incremental summary 仍基于旧顶层：

```text
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

Ticket 18 会负责完整 summary 修复，但 Ticket 17 至少不能生成一个比 full path 更弱、丢失 canonical contract 的 Sidecar。

## T17-R1-06 — Incremental/migration 测试仍验证旧 Schema，未证明 Summary 所称 PASS

**等级：P1 HIGH / TEST CONTRACT**

现有 `test_batch2_incremental.py` 仍手工构造：

```text
signature: "sig_01"  # string
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

没有测试：

- quick→quick structured signature reuse；
- strong→strong reuse；
- quick→strong full recompute；
- strong→quick policy；
- 同名替换只重算该样本；
- incremental output 保留 Ticket 14 canonical analysis_config；
- strict failure 保持旧 Sidecar；
- worker fatal 保持旧 Sidecar。

因此 Summary 中“incremental mode migration PASS”的证据不足。

## T17-R1-07 — 必做 workers/Trusted/performance 矩阵未完成

**等级：P1 / ACCEPTANCE EVIDENCE**

新增 workers 测试只有基础 1/2/auto、Packed strong、Unicode；未覆盖 Ticket 明列的：

```text
single-sample damage
worker fatal
strict
threshold upper/lower boundary
add/delete/duplicate ID
startup stats exactness
1k / 10k ordinary+packed quick/strong performance
peak RSS
```

实现侧只记录约 10 样本 fixture，且没有完整 discover shell exit 证据。

---

## 4. 其它需要修正

### 4.1 `signature_matched_count` 与 trusted 的统计语义

当前 unsigned record trusted，但 `signature_matched_count` 不增加，形成：

```text
trusted_matched_count > signature_matched_count
```

若 unsigned 改为 untrusted，该歧义会自然消失。建议新增 `unsigned_signature_count`，启动日志分别打印。

### 4.2 Strong→quick 文案与实际行为

Incremental plan 使用 `SIGNATURE_MODE_DOWNGRADE_FORBIDDEN`，但随后 full quick 分析仍会覆盖 strong Sidecar。必须冻结真实策略并使 reason、行为、文档一致：

```text
拒绝并返回非零
或
明确 full recompute to quick（不是“forbidden”）
或
自动保持 strong
```

---

## 5. 测试证据判断

实现侧记录：

```text
53 focused tests / OK / EXIT=0
Wave 组合 82 focused tests / OK / EXIT=0
```

这些证明基础功能可运行，但没有覆盖上述 contract gaps。GitHub 无 CI status，不能宣称 CI PASS。

---

## 6. 最小返修范围

```text
samplelib/metadata/fingerprint.py
samplelib/metadata/analyzer.py
samplelib/metadata/loader.py
samplelib/metadata/incremental.py
mainscripts/FacesetAnalyzer.py
tests/smoke/test_batch2_fingerprint_strong.py
tests/smoke/test_batch2_analyzer_workers.py
tests/smoke/test_batch2_trusted_match_stale.py
tests/smoke/test_batch2_incremental.py
tests/smoke/test_batch2_analyzer_cli.py
Ticket 17 summary / current.md
```

不得修改 pak 格式、Ticket 14 canonical contracts、采样概率或 SAEHD 网络。

---

## 7. Final PASS 条件

- [ ] unsigned record 不再 trusted，不装载旧 pose/quality；
- [ ] strict invalid/worker fatal 不覆盖旧 Sidecar；
- [ ] quick hash 是 bounded I/O；
- [ ] full analysis 不再 main+worker 重复读取/重复 hash；
- [ ] strong record hash failure 有明确安全语义；
- [ ] incremental output 保留 Ticket 14 canonical analysis_config；
- [ ] structured signature migration tests 完整；
- [ ] trusted stats/delete/add/duplicate/threshold tests 完整；
- [ ] 1k/10k ordinary+packed quick/strong workers/RSS 性能记录；
- [ ] 完整相关 smoke + shell exit code 0；
- [ ] 独立 Reviewer 复核签发 APPROVED/PASS。

---

## 8. 当前签发

```text
Ticket 17
REQUEST_CHANGES
FUNCTIONAL FOUNDATION EXISTS
TRUST / STRICT / INCREMENTAL / PERF CONTRACTS OPEN
```
