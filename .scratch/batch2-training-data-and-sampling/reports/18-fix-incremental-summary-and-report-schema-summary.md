# Ticket 18 — Incremental Summary / Report Schema Summary

> 状态：IMPLEMENTATION COMPLETE / AWAITING REVIEW  
> 分支：`codex/batch2-ticket19-loss-window`  
> `--options-json` 文档同步：**NA**（无训练参数 JSON Path 变更）

---

## 最终 Summary Schema

```text
total_samples
valid_samples                 # alias: total - invalid_samples
valid_image_samples
valid_pose_samples
valid_quality_samples
usable_pose_samples
usable_quality_samples
invalid_samples
yaw_bucket_counts
pitch_bucket_counts
unknown_yaw_count
unknown_pitch_count
quality_stats
normalization
```

公共 builder：`samplelib/metadata/summary_builder.build_canonical_summary`

## invalid / usable 定义

- `is_record_summary_invalid`：image invalid 或硬 issues（IMAGE_/SIGNATURE_/LOAD_…）；pose-only 不整体 invalid  
- `usable_pose`：image valid ∧ pose valid  
- `usable_quality`：image valid ∧ quality valid  

## 增量 vs full

- full / incremental 共用 builder  
- reconcile：deepcopy、duplicate key 失败、Pass2 全量重算  
- SampleLoader cache 在 Analyzer 入口按路径失效（修复 add/delete 看不见）  
- 等价测试：`tests/smoke/test_batch2_incremental_full_equivalence.py`

## 测试

```text
focused T18：PASS
full test_batch*.py：Ran 327 / OK / EXIT=0
```

实现者不得签发 APPROVED/PASS/CLOSED。
