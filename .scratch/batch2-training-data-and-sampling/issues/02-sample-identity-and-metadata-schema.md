# 02 — 建立 Stable Sample Identity、Dataset Fingerprint 与 Metadata Schema v1

Status: open
Type: AFK
Blocked by: `01-baseline-and-fixtures.md`

**构建内容：** 为普通 aligned 目录与 Packed Faceset 定义同一套稳定样本身份、内容 signature、数据集 fingerprint 和版本化 Metadata Schema，使 Analyzer、Loader、采样器以及后续脸型模块可以复用同一个数据契约。

## 目标

- 样本身份不依赖绝对路径和 Windows 盘符。
- 普通目录与 Packed Faceset 使用一致的逻辑 key。
- 逻辑身份与内容变化分开表示。
- JSON 不出现 NaN / Inf。
- Schema 能部分读取、逐记录降级和安全回退。
- 不修改 DFLJPG/PNG 与 `faceset.pak` 内部格式。

## 详细任务

### Stable Sample Key / ID

- [ ] 新增 `samplelib/metadata/identity.py`。
- [ ] 定义普通目录相对 key、person faceset `person_name/filename` 和 packed basename 规则。
- [ ] 统一 `/` 分隔符，拒绝 `..` 越界。
- [ ] 定义大小写匹配策略：精确匹配优先，受控 case-fold 只用于诊断/fallback。
- [ ] 定义 `sample_id = sha256(namespace + sample_key)[:32]`。
- [ ] 对普通、person、packed、Windows 路径写稳定性测试。
- [ ] 检测 sample key / sample id collision，不静默覆盖。

### Signature / Fingerprint

- [ ] 新增 `samplelib/metadata/fingerprint.py`。
- [ ] 普通文件 signature 包含 key、size、mtime_ns，可选 quick/strong hash。
- [ ] Packed signature 包含 key、pak size/mtime、offset、sample byte size。
- [ ] 定义强 fingerprint 仅由显式参数启用。
- [ ] 定义 dataset fingerprint 的排序和编码，保证跨进程稳定。
- [ ] 新增 add/modify/delete/rename 测试。

### Schema v1

- [ ] 新增 `samplelib/metadata/schema.py`。
- [ ] 定义顶层 manifest、analysis_config、summary、samples。
- [ ] 定义 image、landmarks、pose、quality、issues 子结构。
- [ ] 定义 issue code 常量或 Enum。
- [ ] 数值序列化前把非 finite 转为 `null` 并记录 issue。
- [ ] 高版本 schema 默认返回 unsupported，不尝试猜测。
- [ ] 未知字段可忽略；核心字段类型错误只使该记录无效。
- [ ] 定义 roundtrip、partial、unsupported、duplicate-id fixture。

## 建议 API

```python
sample_key = build_sample_key(sample, faceset_root, packed)
sample_id = build_sample_id(sample_key)
signature = build_sample_signature(...)
fingerprint = build_dataset_fingerprint(records)
metadata = FacesetMetadataV1.from_mapping(raw)
metadata.validate()
metadata.to_dict()
```

## 建议文件

- `samplelib/metadata/__init__.py`
- `samplelib/metadata/identity.py`
- `samplelib/metadata/fingerprint.py`
- `samplelib/metadata/schema.py`
- `tests/smoke/test_batch2_metadata_schema.py`
- `tests/fixtures/batch2/metadata_v1_*.json`

## 验收标准

- [ ] 同一逻辑样本移动 faceset 根目录后 sample_id 不变。
- [ ] 普通与 packed 对应样本可得到同一 sample_key。
- [ ] 内容变化后 sample_id 不变、signature/fingerprint 改变。
- [ ] person_name 防止同名文件冲突。
- [ ] JSON roundtrip 保持核心字段。
- [ ] NaN/Inf 不进入文件。
- [ ] unsupported schema 不导致传统训练失败。
- [ ] 本 ticket 不导入 TensorFlow，不修改训练路径。

## 回退

所有新模块未被调用时，当前 SampleLoader、Generator 和训练行为完全不变。

## 不在本 ticket

- 不读取图片计算 pose / quality。
- 不实现 Analyzer CLI。
- 不实现权重或采样。
- 不扩展 `Sample.__slots__` 保存全部 Metadata。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/02-sample-identity-and-metadata-schema-summary.md`，列出最终字段、兼容规则、示例和测试结果。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 01 完成后实施。
