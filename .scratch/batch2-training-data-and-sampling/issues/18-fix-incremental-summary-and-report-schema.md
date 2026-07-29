# Ticket 18 — 修复 Incremental Reconcile、Summary 与 Report Schema 一致性

> 状态：OPEN / P1 HIGH  
> Blocked by：Ticket 14、Ticket 17  
> Blocks：21  
> 目标：增量结果必须与同一数据集全量重算结果等价

---

## 1. 问题背景

当前 Analyzer 真实样本记录使用嵌套字段：

```text
image.valid
landmarks.valid
pose.valid
pose.yaw_bucket
pose.pitch_bucket
quality_raw.valid
quality.quality_score
```

增量汇总却读取旧顶层字段：

```text
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

现有增量测试也手工构造旧顶层 Schema，因此测试通过并不能证明真实 Analyzer 增量流程正确。

本 Ticket 的核心完成定义：

```text
同一最终 faceset
全量分析结果
与
先全量、再增量更新结果
在可比较字段上等价
```

---

## 2. 开工前必读

1. `AGENTS.md`
2. Ticket 14 summary
3. Ticket 17 summary
4. `samplelib/metadata/contracts.py`
5. `samplelib/metadata/analyzer.py`
6. `samplelib/metadata/incremental.py`
7. `samplelib/metadata/report.py`
8. `samplelib/metadata/schema.py`
9. `mainscripts/FacesetAnalyzer.py`
10. `tests/smoke/test_batch2_incremental.py`
11. `tests/smoke/test_batch2_analyzer_cli.py`

---

## 3. 固定契约

### 3.1 唯一 Record Accessor

增量和报告不得直接猜字段，必须复用 Ticket 14 公共 accessor，例如：

```python
record_image_valid(record)
record_pose_valid(record)
record_quality_valid(record)
record_usable_for_pose(record)
record_usable_for_quality(record)
record_yaw_bucket(record)
record_pitch_bucket(record)
```

### 3.2 Summary 标准字段

建议统一为：

```json
{
  "total_samples": 0,
  "valid_image_samples": 0,
  "valid_pose_samples": 0,
  "valid_quality_samples": 0,
  "usable_pose_samples": 0,
  "usable_quality_samples": 0,
  "invalid_samples": 0,
  "yaw_bucket_counts": {},
  "pitch_bucket_counts": {},
  "unknown_yaw_count": 0,
  "unknown_pitch_count": 0,
  "quality_stats": {},
  "normalization": {}
}
```

如为兼容保留旧字段，必须：

- 明确 alias；
- 由同一 helper 派生；
- 测试新旧值一致；
- 不允许两套逻辑分别维护。

### 3.3 增量计数

Report 固定记录：

```text
reused_count
recomputed_count
added_count
removed_count
stale_signature_count
signature_upgraded_count
```

计数必须与 plan 中具体 key 集合长度一致。

### 3.4 等价性

允许不同：

- created_at；
- elapsed time；
- incremental flag；
- reused/recomputed 运行统计。

必须相同：

- sample count；
- sample IDs；
- sample order；
- signatures；
- image/pose/quality values；
- quality normalization；
- yaw/pitch counts；
- valid/usable counts；
- dataset fingerprint；
- Schema/analyzer version。

浮点可使用明确 tolerance，不得宽泛忽略。

---

## 4. Reconcile 施工要求

### Step 1：删除旧测试 Schema 依赖

测试 Fixture 必须来自：

```text
FacesetAnalyzer.analyze()
```

或从真实写出的 Metadata JSON 读取。

不得手工构造 `pose_bucket_yaw`、`valid` 等旧字段作为主要路径。

### Step 2：合并 reused + new

- reused record 必须深拷贝必要层级，避免原对象被 Pass 2 原地修改；
- removed record 不进入结果；
- recomputed 使用新记录覆盖旧记录；
- duplicate key/id 立即 validation failure；
- 最终按稳定 sample_id 排序。

### Step 3：重新执行全局质量归一化

由于质量分数是 faceset 全局百分位相对值，即使只新增一张样本，也必须对全体 raw quality 重新执行 Pass 2。

要求：

- reused record 必须保留完整 `quality_raw`；
- 缺失 raw metrics 的旧记录不能伪造；
- 可选择重算该记录或标记不兼容；
- 不得直接沿用旧 normalized score。

### Step 4：重新生成 Summary

从 `finalized_samples` 离线重算全部 summary。不得用增量差值拼接旧 summary，因为：

- normalization 可能变化；
- invalid/usable 规则可能升级；
- bucket alias 可能规范化。

### Step 5：Report 使用 Metadata Summary

`generate_analyzer_report()` 应优先读取已验证的 Metadata summary，运行统计单独附加。不得再扫描 samples 形成另一套不一致统计，除非调用同一个 `recompute_summary()` helper 并断言一致。

---

## 5. Invalid Sample 定义

必须明确：

```text
invalid sample != quality low
```

建议：

- image invalid：invalid；
- identity/signature invalid：invalid；
- pose invalid但 image valid：可用于 quality sampling，不一定整体 invalid；
- quality invalid但 pose valid：可用于 pose sampling；
- unknown pitch 不影响 yaw pose sampling；
- issues 仅为 warning 不一定 invalid。

最终定义写入公共函数和文档，不能散落在 report 中。

---

## 6. 允许修改文件

```text
samplelib/metadata/incremental.py
samplelib/metadata/report.py
samplelib/metadata/analyzer.py（抽取 summary helper）
samplelib/metadata/contracts.py
mainscripts/FacesetAnalyzer.py
相关 tests
使用文档
```

---

## 7. 禁止范围

- 不重新设计 quality 算法；
- 不改 pose thresholds；
- 不修改 Sampling 权重；
- 不用旧 normalized score 代替全局重算；
- 不通过删除 summary 字段逃避不一致；
- 不把所有 pose invalid 样本整体删除；
- 不让 Report 写失败覆盖 Metadata 成功状态；
- 不修改 pak 格式。

---

## 8. 必须新增测试矩阵

### 8.1 无变化增量

```text
full A
→ incremental A
```

断言：

- reused=N；
- recomputed=0；
- samples/summary/fingerprint 等价。

### 8.2 新增样本

```text
full A
→ add one sample
→ incremental B
→ force full B
```

比较 incremental B 与 full B。

### 8.3 修改同名样本

- signature stale；
- recomputed=1；
- reused=N-1；
- quality normalization 与 full 等价；
- 旧 pose/quality 不残留。

### 8.4 删除样本

- removed=1；
- 最终 samples 无旧 record；
- summary count 减少；
- fingerprint 更新。

### 8.5 混合变化

同一轮包含：

- reuse；
- add；
- modify；
- remove；
- invalid sample。

### 8.6 Ordinary/Packed

两种格式都比较 incremental vs force full。

### 8.7 Unicode

中文目录、空格文件名、组合 Unicode 文件名。

### 8.8 Analyzer version/signature mode change

- analyzer version changed → full/recompute；
- quick→strong；
- strong→strong reuse；
- incompatible old record 不复用。

---

## 9. Report 验收

报告必须包含：

```text
faceset_format
dataset_fingerprint
total_samples
valid_image_samples
valid_pose_samples
valid_quality_samples
invalid_samples
pose distributions
quality stats
incremental counts
elapsed
samples/sec
warnings
```

必须检查：

- JSON finite；
- UTF-8；
- summary 与 Metadata 一致；
- zero denominator 安全；
- elapsed 非负；
- samples/sec finite；
- report path 自定义可用；
- report 写失败记录错误但不破坏已成功 Metadata。

---

## 10. 测试命令

```bash
./.venv/bin/python -m compileall samplelib/metadata mainscripts/FacesetAnalyzer.py
./.venv/bin/python -m unittest tests.smoke.test_batch2_incremental
./.venv/bin/python -m unittest tests.smoke.test_batch2_analyzer_cli
./.venv/bin/python -m unittest tests.smoke.test_batch2_incremental_full_equivalence
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

---

## 11. 验收标准

- [ ] 无旧顶层字段主路径；
- [ ] 测试使用真实 Analyzer record；
- [ ] 无变化增量与原 full 等价；
- [ ] add/modify/remove 混合增量与新 full 等价；
- [ ] quality Pass 2 全体重算；
- [ ] summary 单一 helper；
- [ ] report 与 Metadata summary 一致；
- [ ] stale、signature mode change 正确；
- [ ] Ordinary/Packed PASS；
- [ ] Unicode PASS；
- [ ] 全量回归 PASS。

完成证据必须提供一个结构化 diff，证明 incremental 和 force-full 仅在允许字段上不同。

---

## 12. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
18-fix-incremental-summary-and-report-schema-summary.md
```

必须记录：

- 最终 Summary Schema；
- invalid/usable 定义；
- 公共 helper；
- 增量与 full 对比方法；
- add/modify/remove 结果；
- Ordinary/Packed；
- Unicode；
- signature mode；
- 全量测试；
- Reviewer 结论。