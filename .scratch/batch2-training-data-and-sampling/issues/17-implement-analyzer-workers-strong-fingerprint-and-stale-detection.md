# Ticket 17 — 实现 Analyzer Workers、Strong Fingerprint 与逐样本 Stale Detection

> 状态：OPEN / P1 HIGH  
> Blocked by：Ticket 14  
> Blocks：18、20、21  
> 风险：Packed I/O、多进程、缓存一致性  
> 原则：CLI 参数必须“真正生效或删除”，不得继续空壳

---

## 1. 问题背景

当前 CLI 暴露：

```text
--workers
--strong-fingerprint
```

但运行时没有使用这两个参数。当前 signature 主要依赖 sample key、size、mtime 和 packed offset，Loader 又主要按 sample ID 计算 matched ratio。文件内容变化但文件名不变时，旧 Metadata 可能仍被视为可用。

本 Ticket 必须同时解决三个相关问题：

1. `--workers` 真实影响 Analyzer 执行；
2. `--strong-fingerprint` 真实读取样本内容并持久化强哈希；
3. Loader 逐样本比较 signature，以 trusted match 而不是 key match 决定采样可用性。

---

## 2. 开工前必读

1. `AGENTS.md`
2. Ticket 14 summary
3. `mainscripts/FacesetAnalyzer.py`
4. `samplelib/metadata/analyzer.py`
5. `samplelib/metadata/fingerprint.py`
6. `samplelib/metadata/incremental.py`
7. `samplelib/metadata/loader.py`
8. `samplelib/metadata/schema.py`
9. `samplelib/SampleLoader.py`
10. PackedFaceset 与 Sample raw bytes API
11. `core.cv2ex`
12. 相关 tests

必须先确认：

- Ordinary Sample 如何安全获得 raw bytes；
- Packed Sample 是否提供 `read_raw_file()`；
- Sample 对象是否可 pickle；
- landmarks、filename、person_name 如何序列化；
- Windows spawn 下 worker function 是否为模块顶层函数。

---

## 3. Signature v1.1 契约

推荐扩展 `SampleSignature`：

```python
@dataclass(frozen=True)
class SampleSignature:
    sample_key: str
    byte_size: int
    mtime_ns: Optional[int] = None
    packed_offset: Optional[int] = None
    quick_hash: Optional[str] = None
    content_sha256: Optional[str] = None
```

不得修改 Metadata schema_version=1 的基本兼容性；可通过 `analyzer_version`、`analysis_config.signature_mode` 或可选字段扩展。

### 3.1 Quick mode

普通文件：

```text
sample_key + byte_size + mtime_ns
```

推荐增加 bounded quick hash：

```text
SHA256(first chunk + last chunk + size)
```

但必须记录实际算法和 chunk size。

Packed：

```text
sample_key + byte_size + packed_offset + packed container stat
```

仅 offset/size 不足以检测原位内容变化；如果能低成本读取 raw sample bytes，应计算 quick hash。

### 3.2 Strong mode

`--strong-fingerprint` 必须对每个样本完整原始字节计算：

```text
content_sha256 = sha256(raw_sample_bytes)
```

Ordinary：读取文件字节。  
Packed：通过项目 Sample/PackedFaceset API 读取该样本 raw bytes，不得自行重新解析或修改 pak 格式。

Strong mode 的 dataset fingerprint 必须纳入 `content_sha256`。

### 3.3 Signature mode 持久化

Metadata 至少记录：

```json
"analysis_config": {
  "signature": {
    "mode": "quick" | "strong",
    "algorithm": "...",
    "chunk_size": 65536
  }
}
```

Loader 必须知道保存记录使用的 mode。不能将 strong Sidecar 与只计算 quick current signature 直接判为相等。

---

## 4. Trusted Match 契约

Runtime 必须区分：

```text
id_matched_count
signature_matched_count
stale_signature_count
missing_record_count
duplicate_count
trusted_matched_count
trusted_match_ratio
```

只有：

```text
sample_id match
AND
signature match under compatible signature mode
```

才计入 trusted matched。

`RuntimeMetadata.matched_count` 可保留兼容，但语义必须明确改为 trusted matched，或新增字段并同步全部调用方。不得继续让名称模糊。

状态建议：

```text
LOADED：trusted ratio=1 且 fingerprint match
PARTIAL_MATCH：trusted ratio>=threshold 但 <1
FINGERPRINT_MISMATCH：trusted ratio<threshold
STALE_SIGNATURE：可作为 warning/reason，不一定新增 enum
```

### 4.1 同名替换图片

必须出现：

```text
id matched = true
signature matched = false
trusted = false
stale_signature_count += 1
```

旧 quality/pose 不得装入 runtime arrays。

### 4.2 Partial usable

trusted ratio 达阈值时允许剩余可信样本进入智能采样；stale/missing 样本使用 neutral/unknown 值。启动日志必须明确数量。

---

## 5. Analyzer Workers 设计

### 5.1 参数语义

```text
workers=None：自动，范围受限
workers=1：严格单进程
workers=N：最多 N 个 worker
workers<=0：配置错误
```

自动值必须 bounded，例如：

```text
min(cpu_count, 8)
```

不得默认创建数十个进程压垮磁盘。

### 5.2 Worker 输入

不得直接假设完整 Sample 对象可 pickle。推荐 parent 构建可序列化 descriptor：

```python
{
  "sample_key": ...,
  "sample_id": ...,
  "person_name": ...,
  "ordinary_path": ...,
  "packed_descriptor": ...,
  "landmarks": ndarray/list,
  "signature options": ...,
}
```

如果 Packed descriptor 无法在 worker 安全重建：

- 必须先设计可 pickle 的 raw-byte provider；
- 或对 Packed 明确回退 workers=1 并输出原因；
- 但最终 Ticket 21 Windows Packed 性能验收前应完成可靠方案。

不得把全部 decoded BGR 预先放入任务队列，避免峰值内存爆炸。

### 5.3 Worker 输出

只返回小型 mapping：

```text
sample_id
sample_key
signature
image validation
pose
quality_raw
issues
```

不得返回 BGR 像素。

### 5.4 确定性

无论 workers 数量：

- 最终 records 按 sample_id 稳定排序；
- dataset fingerprint 相同；
- quality normalization 相同；
- summary 相同；
- JSON 除 created_at/timing 外一致。

### 5.5 异常

非 strict：

- 单样本损坏记录 issues；
- 继续其他样本；
- worker 崩溃属于核心异常，不得只跳过。

strict：

- 任何 invalid sample 导致最终非零；
- worker pool 正常关闭；
- 临时输出不得覆盖旧 Metadata。

---

## 6. 增量与 Signature

增量复用必须满足：

```text
old analyzer version compatible
old signature mode compatible
old record signature == current signature
```

Strong old record + quick current run：

- 不允许假定相等；
- 默认重算或保持 strong；
- 日志说明 signature mode changed。

Quick old record + strong current run：

- 需要计算 strong；
- 重算或至少重签；
- 为避免质量指标重复计算，可设计“metrics reuse + signature upgrade”，但必须单独测试；
- 弱模型若难以安全实现，优先完整重算。

---

## 7. 原子写入

- 所有 worker 完成并校验后才写临时文件；
- worker fatal 时旧 Sidecar 保持；
- strong hash 计算失败不得写半完整记录；
- report 写失败不能破坏 Metadata；
- Metadata 写失败返回非零；
- `.tmp` 清理；
- `.bak` 与当前文件一致。

---

## 8. 允许修改文件

```text
mainscripts/FacesetAnalyzer.py
samplelib/metadata/analyzer.py
samplelib/metadata/fingerprint.py
samplelib/metadata/incremental.py
samplelib/metadata/loader.py
samplelib/metadata/schema.py
samplelib/metadata/report.py
相关 tests
使用文档
```

---

## 9. 禁止范围

- 不修改 pak 格式；
- 不把强 hash 写回图片；
- 不以 Python 内置 hash 作为持久化 hash；
- 不把 absolute path 纳入跨机器 sample identity；
- 不使用非确定排序；
- 不让 workers 参数接受但无效；
- 不为性能跳过 finite 校验；
- 不因某个样本异常吞掉整个 worker crash；
- 不让 stale 样本继续使用旧质量分数。

---

## 10. 必须新增测试

### Signature

- Ordinary quick 稳定；
- Ordinary strong 稳定；
- 内容变化但文件名/size 尽量保持时 strong 必变；
- mtime 变化但内容不变的 strong 内容 hash不变；
- Packed strong；
- Unicode path；
- dataset fingerprint 顺序无关。

### Trusted match

- 完全匹配；
- 同名替换；
- 删除；
- 新增；
- duplicate ID；
- threshold 上下边界；
- stale arrays 保持 neutral；
- startup stats 正确。

### Workers

- workers=1；
- workers=2；
- auto；
- invalid workers；
- 1 与 2 输出契约一致；
- 单样本损坏；
- worker fatal；
- strict；
- Ordinary；
- Packed；
- 中文目录。

### Incremental

- quick→quick reuse；
- strong→strong reuse；
- quick→strong 重算/升级；
- strong→quick 不降级；
- 替换同名图片只重算该样本；
- dataset fingerprint 更新。

---

## 11. 性能验收

至少记录 1k、10k 样本（可用受控 fixture 或真实匿名数据）：

```text
workers=1 elapsed
workers=2 elapsed
workers=auto elapsed
peak RSS
samples/sec
quick vs strong
ordinary vs packed
```

不要求并行一定线性加速，但：

- workers 参数必须实际改变执行；
- 不得显著增加内存到不可接受；
- strong 模式允许更慢，但行为必须真实；
- 结果必须确定一致。

---

## 12. 测试命令

```bash
./.venv/bin/python -m compileall mainscripts/FacesetAnalyzer.py samplelib/metadata
./.venv/bin/python -m unittest tests.smoke.test_batch2_analyzer_core
./.venv/bin/python -m unittest tests.smoke.test_batch2_analyzer_cli
./.venv/bin/python -m unittest tests.smoke.test_batch2_incremental
./.venv/bin/python -m unittest tests.smoke.test_batch2_metadata_loader
./.venv/bin/python -m unittest tests.smoke.test_batch2_fingerprint_strong
./.venv/bin/python -m unittest tests.smoke.test_batch2_analyzer_workers
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

---

## 13. 验收标准

- [ ] `--workers` 真实生效；
- [ ] `--strong-fingerprint` 真实读取完整字节；
- [ ] Signature mode 被持久化；
- [ ] Loader 逐样本 signature 校验；
- [ ] 同名替换不再 trusted；
- [ ] stale 样本不使用旧 pose/quality；
- [ ] trusted ratio 决定 usability；
- [ ] workers=1/2 输出一致；
- [ ] Ordinary PASS；
- [ ] Packed PASS；
- [ ] incremental mode compatibility PASS；
- [ ] Unicode PASS；
- [ ] 原子失败保持旧 Sidecar；
- [ ] 性能记录完成；
- [ ] 文档不再宣称空壳能力。

如果 Packed 多 worker 尚未完成，Ticket 不能 resolved，只能标记 `BLOCKED-BY-PACKED-WORKER-DESIGN` 或明确拆新 Ticket，经维护者批准。

---

## 14. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md
```

必须记录：

- Signature Schema；
- quick/strong 算法；
- workers 架构；
- Ordinary/Packed 差异；
- trusted match 统计；
- 同名替换测试；
- 增量 mode migration；
- 性能数据；
- 全量测试；
- Windows 状态；
- Reviewer 结论。