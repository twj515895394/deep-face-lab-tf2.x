# Batch 2 Ticket 05 — Metadata Loader & Ordinary/Packed Compatibility 研发总结

> 完成时间：2026-07-29  
> 状态：PASS (macOS / venv 验证通过)

## 1. 概述与核心变更

本 Ticket 落地了 **`FacesetMetadataLoader`** (`samplelib/metadata/loader.py`)，负责在训练启动时安全解析 Metadata Sidecar，并将运行时映射到内存极轻量的 1D NumPy 紧凑数组：

1. **`FacesetMetadataStatus` (Enum)**:
   - `LOADED`: Sidecar 存在且 Dataset Fingerprint 完美匹配；
   - `PARTIAL_MATCH`: 指纹或样本有变动，但匹配率 $\ge 90\%$，允许用于智能采样；
   - `MISSING`: 侧边栏文件不存在，提供 `METADATA_FILE_NOT_FOUND` fallback 原因；
   - `UNSUPPORTED_SCHEMA`: Schema 版本不支持；
   - `INVALID_FILE`: JSON 损坏或结构非法；
   - `FINGERPRINT_MISMATCH`: 匹配比例 $< 90\%$，推荐降级回 Legacy 采样模式。

2. **`RuntimeMetadata` (Dataclass)**:
   - 包含紧凑型 1D NumPy 数组：`quality_scores: float32[N]`, `yaw_bucket_ids: int16[N]`, `pitch_bucket_ids: int16[N]`, `pose_valid: bool[N]`, `quality_valid: bool[N]`, `metadata_valid: bool[N]`。
   - `is_usable_for_sampling(min_ratio=0.90)`: 供上层采样策略无缝判断是否可以使用元数据。
   - 未匹配或缺失样本赋予中性默认值 (`quality_score = 1.0`, `metadata_valid = False`)，不会被误打 0 权重或排除出训练。

3. **Ordinary / Person / Packed 兼容性与匹配**:
   - 基于 Ticket 02 实现的 `build_sample_key` 与 `build_sample_id` 统一 Identity。
   - Packed faceset (`faceset.pak`) 和 Ordinary 文件夹相同样本识别为完全一致的 Sample ID。

---

## 2. 自动化与内存测试验证

### 2.1 单元测试套件
```bash
./.venv/bin/python -m compileall samplelib/metadata/loader.py
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_*.py"
```
- 测试结果：**122/122 PASS (100% 通过)**。

### 2.2 内存评估 (Compact Array Footprint)
- 实测 100,000 (10万) 样本级别下，`RuntimeMetadata` 所有 1D NumPy 数组整体内存开销约 **1.05 MB** ($< 2.0 \text{ MB}$)，适合跨 Generator 进程共享，绝不拷贝庞大 JSON/字典。

---

## 3. `--options-json` 训练配置同步状态

```text
--options-json 文档同步：NA
文档版本：v1.0
修改章节：无（本 Ticket 为 Sidecar Loader 核心，无新增 CLI 训练参数）
```

---

## 4. Ticket 06 可依赖的接口与字段

- **Loader 入口**：
  ```python
  runtime = FacesetMetadataLoader.load(
      samples_path=path,
      samples=samples,
      metadata_path=None,
      min_match_ratio=0.90,
      strict=False
  )
  ```
- **采样器判断**：`runtime.is_usable_for_sampling()`
- **数据访问**：直接读写 `runtime.quality_scores` (float32), `runtime.yaw_bucket_ids` (int16), `runtime.pitch_bucket_ids` (int16) 数组。

---

## 5. Windows / GPU 待办

- **Windows 验收**：`PENDING-WINDOWS-GPU`
