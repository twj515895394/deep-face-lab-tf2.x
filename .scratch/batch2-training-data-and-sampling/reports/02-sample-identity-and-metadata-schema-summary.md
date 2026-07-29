# Ticket 02 — Sample Identity, Dataset Fingerprint 与 Metadata Schema v1 总结报告

- **更新时间**: 2026-07-29

## 测试与状态总览

- **测试状态**: PASS (macOS 轻量级验证已通过)
- **单元测试包含**: 94 项全量 Smoke 测试全通过（包含 9 项 Metadata Identity & Schema 专项测试）
- **`--options-json` 文档同步**: NA (本 Ticket 不涉及训练参数 CLI 选项变更)

## 详细 API 与数据结构规范

### 1. Stable Sample Key 与 Sample ID

- **Sample Key 规则**:
  - 普通单层 faceset: `00001.jpg`
  - Person faceset: `person_10/00001.jpg`
  - Packed faceset: 使用与打包前相同的 `person_10/00001.jpg` 或 `00001.jpg`
  - 路径统一使用 `/` 作为分隔符，自动剥离 `./`，拒绝绝对路径（盘符/根路径）与 `..` 越界；保留原始大小写。
- **Sample ID**:
  - `build_sample_id(sample_key, namespace="dfl-faceset-v1")` -> 生成 32 字符长度的 SHA256 hex。同一逻辑 key 在任何平台/机器上计算均完全一致。

### 2. Sample Signature 与 Dataset Fingerprint

- **SampleSignature**:
  - 包含 `sample_key`, `byte_size`, `mtime_ns`, `packed_offset`, `quick_hash`；
- **Dataset Fingerprint**:
  - `build_dataset_fingerprint(signatures)` 严格按照 `sample_key` 字典序升序进行累计 UTF-8 SHA256 哈希计算，保证多进程/跨语言遍历顺序无关的跨平台确定性。

### 3. Metadata Schema v1 与 JSON 有限清洗

- **`sanitize_finite_json(val)`**:
  - 递归清理数值，将 `NaN` 与 `Inf` 强制转换为 `None` (`null`)，并记录对应的 `MetadataValidationIssue`。
- **`FacesetMetadataV1`**:
  - 支持 `from_mapping(raw)` / `validate()` / `to_dict()` / `dump_json()` / `load_json()`；
  - 高版本 Schema 自动标记 `is_supported=False`；支持单条坏样本不崩溃而继续解析其它有效样本。

## 可供 Ticket 03 直接调用的模块与 API

```python
from samplelib.metadata import (
    build_sample_key,
    build_sample_id,
    build_sample_signature,
    build_dataset_fingerprint,
    FacesetMetadataV1,
    MetadataValidationResult,
    sanitize_finite_json,
)
```
