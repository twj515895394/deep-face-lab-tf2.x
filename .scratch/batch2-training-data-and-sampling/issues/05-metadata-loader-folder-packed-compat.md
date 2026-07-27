# 05 — 实现 Metadata Loader、运行时匹配、缓存与普通/Packed 兼容

Status: open
Type: AFK
Blocked by: `04-analyzer-cli-atomic-store-and-incremental.md`

**构建内容：** 在训练启动时安全读取 Metadata sidecar，将 ordinary / packed 的运行时 Sample 映射到紧凑 Metadata 数组；对缺失、部分匹配、fingerprint mismatch、schema 不支持和 collision 给出明确状态与 fallback 建议。

## 目标

- JSON 只在训练启动时解析一次。
- src 和 dst 分别加载、匹配和报告。
- 普通与 Packed 使用同一个 Loader API。
- 部分 Metadata 缺失时使用中性默认，不给零权重。
- 匹配率过低时整体回退，不把错误 Metadata 应用到别的 faceset。
- Loader 不依赖 TensorFlow。

## 详细任务

### Loader API

- [ ] 新增 `samplelib/metadata/loader.py`。
- [ ] 定义 `FacesetMetadataStatus`：loaded、missing、unsupported_schema、invalid_file、fingerprint_mismatch、partial_match、sample_key_collision。
- [ ] 定义返回对象，包含 records、紧凑数组、warnings、matched_ratio、fallback_reason。
- [ ] 支持显式 metadata_path 和自动默认路径。
- [ ] 支持 strict=False/True。

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

- [ ] 构建与 Sample 顺序一致的 `quality_scores: float32[N]`。
- [ ] 构建 `yaw_bucket_ids: int16/int32[N]`。
- [ ] 构建 `pose_valid`, `quality_valid`, `metadata_valid` bool arrays。
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

runtime.status
runtime.matched_ratio
runtime.quality_scores
runtime.yaw_bucket_ids
runtime.metadata_valid
runtime.fallback_reason
```

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

## 验收标准

- [ ] Loader 不会把错误 faceset Metadata 静默应用到训练。
- [ ] 缺失记录使用中性权重，不被排除。
- [ ] 所有状态都有结构化原因和日志字段。
- [ ] src / dst 可以一个 loaded、一个 fallback。
- [ ] ordinary / packed 测试通过。
- [ ] 无 Metadata 时运行时成本接近零且 legacy 不变。

## 回退

Loader 返回非 loaded 状态时，上层可以直接选择 legacy policy；不修改 SampleLoader 原有样本输出。

## 不在本 ticket

- 不创建 Sampling Policy。
- 不实现权重公式。
- 不修改 Generator。
- 不在训练时自动运行 Analyzer。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/05-metadata-loader-folder-packed-compat-summary.md`，记录状态机、匹配规则、内存结构、普通/Packed 结果和 fallback 证据。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 04 完成。
