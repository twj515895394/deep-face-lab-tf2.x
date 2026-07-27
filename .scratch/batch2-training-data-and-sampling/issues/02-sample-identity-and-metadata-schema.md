# 02 — 建立 Stable Sample Identity、Dataset Fingerprint 与 Metadata Schema v1

Status: open
Type: AFK
Blocked by: `01-baseline-and-fixtures.md`

**构建内容：** 为普通 aligned 目录与 Packed Faceset 定义同一套稳定样本身份、内容 signature、数据集 fingerprint 和版本化 Metadata Schema，使 Analyzer、Loader、采样器以及后续脸型模块可以复用同一个数据契约。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 01 summary，确认 fixture、ordinary/packed sample 顺序和 baseline helper
3. `samplelib/Sample.py` 的字段和 `get_config()`
4. `samplelib/SampleLoader.py` ordinary 加载路径
5. `samplelib/PackedFaceset.py` 中 pack/load、person_name、filename 与 offset 语义
6. 正式详细设计中的 Metadata Schema v1、sample identity、fingerprint 章节

不得只根据文件名设计 sample key。必须同时考虑 person faceset、Packed Faceset 和 Windows 路径。

## 当前源码事实必须先确认

在编码前记录：

- ordinary `Sample.filename` 是绝对路径还是相对路径；
- packed load 后 `Sample.filename`、`person_name`、`_filename_offset_size` 的值；
- `Sample.get_config()` 是否包含 `pitch_yaw_roll`；
- 同一个 basename 在不同 person 子目录是否可能共存；
- Packed Faceset 中样本 byte size 和 offset 从哪里取得；
- Ticket 01 fixture 中 ordinary 和 packed 对应关系。

## 目标

- 样本身份不依赖绝对路径和 Windows 盘符。
- 普通目录与 Packed Faceset 使用一致的逻辑 key。
- 逻辑身份与内容变化分开表示。
- JSON 不出现 NaN / Inf。
- Schema 能部分读取、逐记录降级和安全回退。
- 不修改 DFLJPG/PNG 与 `faceset.pak` 内部格式。

## 推荐数据契约

### Stable Sample Key

统一规则：

```text
普通单层 faceset: normalized filename
person faceset: normalized person_name/filename
Packed Faceset: 使用与打包前相同的 person_name/filename 规则
```

规范化只允许：

- 将 `\` 转成 `/`；
- 去掉多余 `./`；
- 拒绝绝对路径；
- 拒绝 `..`；
- 保留原始大小写作为 canonical key。

不要把绝对 faceset root、盘符或机器用户名写入 key。

### Sample ID

建议接口：

```python
def build_sample_id(sample_key: str, namespace: str = "dfl-faceset-v1") -> str:
    canonical = f"{namespace}\n{sample_key}".encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()[:32]
```

同一 sample key 必须稳定；内容变化不改变 ID。

### Signature

逻辑身份和内容变化必须分离：

```python
@dataclass(frozen=True)
class SampleSignature:
    sample_key: str
    byte_size: int
    mtime_ns: Optional[int]
    packed_offset: Optional[int]
    quick_hash: Optional[str]
```

ordinary 默认可使用 size + mtime；packed 使用 pak signature + offset + sample byte size。strong hash 只能显式启用。

### Metadata 顶层建议

```json
{
  "schema_version": 1,
  "analyzer_version": "...",
  "created_at": "...",
  "dataset": {
    "format": "ordinary|packed|person",
    "fingerprint": "...",
    "sample_count": 0
  },
  "analysis_config": {},
  "summary": {},
  "samples": []
}
```

每条 sample 记录至少包含：

```text
sample_id
sample_key
signature
image
landmarks
pose
quality
issues
```

字段缺失和字段非法必须区分。

## 建议施工顺序

### Step 1：先实现 path/key 纯函数

只创建 `identity.py` 和测试。覆盖 ordinary/person/packed/Windows/非法路径。此时不要写 Schema。

### Step 2：实现 sample ID 与 collision 检查

- 同 key 同 ID；
- 不同 key 不得在测试 fixture 中 collision；
- 输入重复 ID 时 Schema validator 必须报结构化错误，不能 dict 覆盖。

### Step 3：实现 signature

先 ordinary，再 packed。signature builder 只读取必要元数据，不读取全部图片像素，strong 模式除外。

### Step 4：实现 dataset fingerprint

建议：

```text
按 sample_key 排序
→ 每条 canonical JSON/UTF-8 编码
→ 持续更新 SHA256
```

禁止依赖 dict 插入顺序、文件系统遍历顺序或 Python hash。

### Step 5：实现 Schema 数据类和解析

推荐对象：

```python
@dataclass
class MetadataValidationIssue:
    code: str
    message: str
    sample_key: Optional[str] = None

@dataclass
class FacesetMetadataV1:
    schema_version: int
    dataset: dict
    analysis_config: dict
    summary: dict
    samples: list

    @classmethod
    def from_mapping(cls, raw): ...
    def validate(self): ...
    def to_dict(self): ...
```

复杂内部结构可先使用受控 mapping，但不能让上层依赖任意裸 dict 字段。

### Step 6：实现 finite JSON 清洗

递归遍历数值：

- finite float 保留；
- NaN/Inf 转 `None`；
- 同时追加 issue code；
- 使用 `json.dump(..., allow_nan=False)` 作为最后防线。

### Step 7：写兼容测试

必须测试 unsupported schema、未知字段、单条坏记录、duplicate ID 和 roundtrip。

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
validation = metadata.validate()
serialized = metadata.to_dict()
```

`validate()` 建议返回结构化结果而非只抛异常：

```python
validation.is_valid
validation.is_supported
validation.issues
validation.invalid_sample_ids
```

## 建议文件

- `samplelib/metadata/__init__.py`
- `samplelib/metadata/identity.py`
- `samplelib/metadata/fingerprint.py`
- `samplelib/metadata/schema.py`
- `tests/smoke/test_batch2_metadata_identity.py`
- `tests/smoke/test_batch2_metadata_schema.py`
- `tests/fixtures/batch2/metadata_v1_*.json`

## 最小测试命令

```bash
python -m compileall samplelib/metadata
python -m unittest \
  tests.smoke.test_batch2_metadata_identity \
  tests.smoke.test_batch2_metadata_schema
```

## 禁止捷径与常见错误

- 不允许 sample_id 基于绝对路径。
- 不允许将 filename `.lower()` 后直接作为 canonical key；会掩盖真实 collision。
- 不允许 dataset fingerprint 依赖遍历顺序。
- 不允许把内容 hash 当作 sample ID，否则图片修改会丢失逻辑身份。
- 不允许 `json.dump` 默认输出 NaN。
- 不允许遇到一条坏记录就让整个 Metadata 无法读取；顶层结构损坏除外。
- 不允许修改 `Sample.__slots__` 塞入全部 Metadata。

## 验收标准

- [ ] 同一逻辑样本移动 faceset 根目录后 sample_id 不变。
- [ ] 普通与 packed 对应样本可得到同一 sample_key。
- [ ] 内容变化后 sample_id 不变、signature/fingerprint 改变。
- [ ] person_name 防止同名文件冲突。
- [ ] JSON roundtrip 保持核心字段。
- [ ] NaN/Inf 不进入文件。
- [ ] unsupported schema 不导致传统训练失败。
- [ ] 本 ticket 不导入 TensorFlow，不修改训练路径。
- [ ] Ticket 03 能直接复用明确的 Schema/API，而无需重新解释字段。

## 回退

所有新模块未被调用时，当前 SampleLoader、Generator 和训练行为完全不变。

## 不在本 ticket

- 不读取图片计算 pose / quality。
- 不实现 Analyzer CLI。
- 不实现权重或采样。
- 不扩展 `Sample.__slots__` 保存全部 Metadata。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/02-sample-identity-and-metadata-schema-summary.md`，列出最终字段、兼容规则、示例和测试结果。
- [ ] summary 必须给出 ordinary/person/packed 的 sample key 示例。
- [ ] summary 必须列出 Ticket 03 应调用的最终 API 和不可依赖的内部细节。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 01 完成后实施。
- 2026-07-27：补充弱模型执行顺序、数据契约骨架、finite JSON 和常见错误。