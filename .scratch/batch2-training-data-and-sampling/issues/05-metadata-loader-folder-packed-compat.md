# 05 — 实现 Metadata Loader、运行时匹配、缓存与普通/Packed 兼容

Status: open
Type: AFK
Blocked by: `04-analyzer-cli-atomic-store-and-incremental.md`

**构建内容：** 在训练启动时安全读取 Metadata sidecar，将 ordinary / packed 的运行时 Sample 映射到紧凑 Metadata 数组；对缺失、部分匹配、fingerprint mismatch、schema 不支持和 collision 给出明确状态与 fallback 建议。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 02、04 summary，确认 sample identity、Schema、默认 sidecar 路径和原子文件格式
3. `samplelib/SampleLoader.py`
4. `samplelib/PackedFaceset.py`
5. Ticket 01 ordinary/packed/person fixtures
6. 正式详细设计中的 Loader、partial match、fallback 和 compact runtime 章节

## 当前源码事实必须先确认

- `SampleLoader.load()` 返回的对象类型、顺序和缓存语义；
- ordinary、person、packed 的 `Sample.filename/person_name` 实际值；
- `MPSharedList` 是否适合附加任意属性；
- Generator 子进程如何接收 `samples`；
- Metadata 默认路径是否与 Ticket 04 完全一致；
- 训练启动中 src 和 dst 是否分别调用 Loader。

## 目标

- JSON 只在训练启动时解析一次。
- src 和 dst 分别加载、匹配和报告。
- 普通与 Packed 使用同一个 Loader API。
- 部分 Metadata 缺失时使用中性默认，不给零权重。
- 匹配率过低时整体回退，不把错误 Metadata 应用到别的 faceset。
- Loader 不依赖 TensorFlow。

## 建议状态对象

```python
class FacesetMetadataStatus(Enum):
    LOADED = "loaded"
    MISSING = "missing"
    UNSUPPORTED_SCHEMA = "unsupported_schema"
    INVALID_FILE = "invalid_file"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    PARTIAL_MATCH = "partial_match"
    SAMPLE_KEY_COLLISION = "sample_key_collision"

@dataclass
class RuntimeMetadata:
    status: FacesetMetadataStatus
    sample_count: int
    matched_count: int
    matched_ratio: float
    quality_scores: np.ndarray
    yaw_bucket_ids: np.ndarray
    pose_valid: np.ndarray
    quality_valid: np.ndarray
    metadata_valid: np.ndarray
    warnings: list
    fallback_reason: Optional[str]
```

数组长度必须严格等于当前 `samples` 长度，并与其索引一一对应。

## 建议施工顺序

### Step 1：只实现文件读取与 Schema 状态

覆盖：missing、invalid JSON、unsupported schema、valid。此阶段不要做样本匹配。

### Step 2：实现 runtime sample identity 映射

先为当前 Sample 列表计算 `sample_id`。建立：

```text
metadata_by_id
runtime_id_by_index
```

匹配规则：

1. 精确 sample_id；
2. sample_key 只用于诊断和显式受控恢复；
3. collision 不得自动选择；
4. extra Metadata 只记录，不进入数组。

### Step 3：构建中性数组

先建立安全默认：

```python
quality_scores = np.ones(N, dtype=np.float32)
yaw_bucket_ids = np.full(N, UNKNOWN_BUCKET_ID, dtype=np.int16)
metadata_valid = np.zeros(N, dtype=np.bool_)
```

再把成功匹配且字段合法的记录填入。单条非法字段只使对应 valid flag 为 False。

### Step 4：实现 fingerprint 和 match ratio 决策

建议决策顺序：

```text
Schema 不可用
→ fallback

Schema 可用
→ 计算精确匹配
→ 检查 collision
→ matched_ratio
→ fingerprint 相同: loaded
→ fingerprint 不同但 ratio >= threshold: partial_match
→ ratio < threshold: fallback recommendation
```

fingerprint mismatch 不应先于 sample matching 直接把所有记录作废。

### Step 5：实现 ordinary/person/packed 对照测试

同一逻辑样本在 ordinary 和 packed 中必须匹配到同一个 sample ID。不同 person 下同名文件不能冲突。

### Step 6：测量内存

summary 至少记录 N=1k/10k/100k 时紧凑数组估算或实测字节数。禁止把完整 JSON record list复制给每个 worker。

## 详细任务

### Loader API

- [ ] 新增 `samplelib/metadata/loader.py`。
- [ ] 定义结构化状态和返回对象。
- [ ] 支持显式 metadata_path 和自动默认路径。
- [ ] 支持 strict=False/True。
- [ ] 所有状态提供 machine-readable reason。

### Runtime Matching

- [ ] 对当前 Sample 列表生成 sample_key/id。
- [ ] 精确 sample_id 匹配优先。
- [ ] sample_key 仅作为诊断或受控 fallback，不静默 case-insensitive 覆盖。
- [ ] 统计 matched/missing/extra/collision。
- [ ] 缺失记录使用：quality=1.0、pose=unknown、metadata_valid=False。
- [ ] extra Metadata 记录忽略并报告。
- [ ] collision 记录不得应用权重。

### Fingerprint

- [ ] 完全一致返回 loaded。
- [ ] fingerprint 不一致但 matched_ratio 达标返回 partial_match。
- [ ] 默认 `min_metadata_match_ratio=0.90`。
- [ ] 低于阈值返回 fallback 建议。
- [ ] strict 模式可以拒绝智能采样，但不得破坏 legacy 训练入口。

### Runtime Cache

- [ ] `quality_scores: float32[N]`。
- [ ] `yaw_bucket_ids: int16/int32[N]`。
- [ ] `pose_valid`, `quality_valid`, `metadata_valid` bool arrays。
- [ ] 保存 summary 和 dataset fingerprint。
- [ ] 不把完整 raw JSON 复制给每个 Generator 子进程。
- [ ] 明确多进程传输/共享方式和内存成本。

### Packed 兼容

- [ ] person_name/filename 与普通目录 key 对齐。
- [ ] Packed Sample 的 basename 不与不同 person 冲突。
- [ ] `faceset.pak` 重新打包后 mismatch 行为明确。
- [ ] 不要求解包，不修改 offsets。

## 建议 API

```python
runtime = FacesetMetadataLoader.load(
    samples_path=path,
    samples=samples,
    metadata_path=None,
    min_match_ratio=0.90,
    strict=False,
)
```

不要让上层通过异常文本解析状态。

## 测试场景

- [ ] Metadata 完整匹配。
- [ ] 文件缺失。
- [ ] invalid JSON。
- [ ] unsupported schema。
- [ ] 95% 匹配允许 partial。
- [ ] 50% 匹配回退。
- [ ] extra records。
- [ ] duplicate sample_id。
- [ ] ordinary 与 packed 相同 key。
- [ ] person faceset 同名文件不冲突。
- [ ] 大数组 dtype 与内存大小检查。

## 最小测试命令

```bash
python -m compileall samplelib/metadata/loader.py
python -m unittest tests.smoke.test_batch2_metadata_loader
```

## 禁止捷径与常见错误

- 不允许按数组位置假设 Metadata 顺序和 Sample 顺序一致。
- 不允许 filename basename 作为所有 faceset 的唯一 key。
- 不允许 mismatch 时把 Metadata 记录应用到“最像”的文件名。
- 不允许 missing record 赋 0 权重或 quality=0。
- 不允许把整个 `FacesetMetadataV1` 对象复制给每个 worker。
- 不允许 Loader 自动运行 Analyzer。
- 不允许 strict 模式让 legacy train 无法启动；它只决定智能模式是否可启用。

## 验收标准

- [ ] Loader 不会把错误 faceset Metadata 静默应用到训练。
- [ ] 缺失记录使用中性权重，不被排除。
- [ ] 所有状态都有结构化原因和日志字段。
- [ ] src / dst 可以一个 loaded、一个 fallback。
- [ ] ordinary / packed 测试通过。
- [ ] 无 Metadata 时运行时成本接近零且 legacy 不变。
- [ ] Ticket 06 可只依赖 `RuntimeMetadata`，不读取 raw JSON。

## 回退

Loader 返回非 loaded/allowed-partial 状态时，上层可以直接选择 legacy policy；不修改 SampleLoader 原有样本输出。

## 不在本 ticket

- 不创建 Sampling Policy。
- 不实现权重公式。
- 不修改 Generator。
- 不在训练时自动运行 Analyzer。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/05-metadata-loader-folder-packed-compat-summary.md`，记录状态机、匹配规则、内存结构、普通/Packed 结果和 fallback 证据。
- [ ] 给出 Ticket 06 可依赖的最终 `RuntimeMetadata` 字段和状态表。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 04 完成。
- 2026-07-27：补充弱模型匹配顺序、紧凑数组骨架、决策状态机和禁止捷径。