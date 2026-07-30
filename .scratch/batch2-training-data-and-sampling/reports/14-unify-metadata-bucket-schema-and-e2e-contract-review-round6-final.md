# Ticket 14 — 第六轮独立代码 Review 与最终 PASS

> Review 状态：**APPROVED / PASS**  
> Review 日期：2026-07-30  
> 被审实现 Commit：`37e99255e195d73dbd3720858ec1a93b4c8619cc`  
> Round-5 Review Commit：`77f507ed3087b1effcdd00b5e838023abf637e72`  
> Review 方法：GitHub 分支最新源码、测试源码与施工测试记录的独立静态复核。Reviewer 未在本环境重新运行 Windows 测试；GitHub 当前无该实现提交的 Actions/status check。

---

## 1. 最终结论

```text
APPROVED
PASS
TICKET 14 CONTRACT CLOSED
CANONICAL METADATA BUCKET CONTRACT CLOSED
ANALYZER → LOADER → POLICY E2E CLOSED
PER-SAMPLE VALIDITY CONTRACT CLOSED
TICKETS 15 / 16 / 17 UNBLOCKED
TICKET 19 REMAINS INDEPENDENTLY OPEN
```

Ticket 14 的源码、端到端契约和强制测试矩阵现已闭环。施工 Summary 的自审 PASS 经过本轮独立复核后，可以升级为正式 Reviewer PASS。

本 PASS 只表示 Ticket 14 完成，不表示 Batch 2 已生产可用。Windows spawn、SRC/DST 配置、stale detection、Incremental、fallback、Loss Window 与 Windows GPU 最终验收仍由 Ticket 15—21 完成。

---

## 2. R5-01 最后缺口确认关闭

Round-5 唯一阻断是：整体记录中某个 sibling 结构畸形时，Loader 过早 `continue`，导致其它可独立解析的 child flags 被清零。

最新 Loader 已改为：

```text
1. 唯一 sample_id 命中 → record_matched=True
2. 独立读取 image_valid / landmarks_valid
3. 独立读取 quality_valid / quality_score
4. 独立读取 pose/bucket
5. 最后单独计算 metadata_valid=is_record_structurally_valid(record)
```

已经不存在结构失败前的提前 `continue`。

对于：

```json
{
  "image": {"valid": true},
  "landmarks": {"valid": true},
  "pose": "BROKEN",
  "quality": {"quality_score": 0.8}
}
```

契约结果为：

```text
record_matched=True
metadata_valid=False
image_valid=True
landmarks_valid=True
quality_valid=True
pose_valid=False
usable_for_pose_sampling=False
usable_for_quality_sampling=False
```

采样安全没有降低，因为 usable masks 仍严格要求：

```text
metadata_valid & pose_valid
metadata_valid & quality_valid
```

新增 `test_loader_malformed_sibling_preserves_independent_child_flags` 对上述结果进行了完整断言。

---

## 3. Ticket 14 最终验收矩阵

| 契约 | 结果 |
|---|---|
| Canonical yaw 7 buckets 与固定 ID | PASS |
| Canonical pitch 3 buckets 与固定 ID | PASS |
| Legacy alias 只读兼容 | PASS |
| 无方向 `extreme` → unknown / pose invalid / warning | PASS |
| Analyzer 只写 canonical bucket | PASS |
| Analyzer analysis_config 写入 contract version、canonical lists、thresholds | PASS |
| Schema 检查 pose mapping、valid 类型、alias 与 unknown bucket | PASS |
| `pose.valid` 缺失与显式 null 语义分离 | PASS |
| Schema / Loader bool-compatible 单一契约 | PASS |
| Loader 不再使用顶层 `rec.get("valid", True)` | PASS |
| `record_matched` 逐样本数组 | PASS |
| `image_valid` 逐样本数组 | PASS |
| `landmarks_valid` 逐样本数组 | PASS |
| `pose_valid` / `quality_valid` / `metadata_valid` 语义独立 | PASS |
| 畸形 sibling 不清零其它安全 child flags | PASS |
| Runtime warnings 按 code 聚合、examples 有界、总数有界 | PASS |
| Ordinary Analyzer → Loader → Policy → IndexHost → draw | PASS |
| Packed Analyzer → Loader → Policy → IndexHost → draw | PASS |
| 非均匀权重、稀缺 bucket 增权、strength=0 等权 | PASS |
| probabilities finite / positive / sum=1 | PASS |
| empirical distribution 测试与 uniform_mix 对齐 | PASS |
| Ordinary / Packed 文件名映射一致 | PASS |
| reversed / shuffled sample order 语义不变 | PASS |
| Unicode 目录与 Unicode 文件名 | PASS |
| 100k compact arrays 轻量内存断言 | PASS |
| JSON roundtrip bucket 不变 | PASS |
| 旧测试未通过删除断言或放宽主契约规避 | PASS |

---

## 4. 测试证据判断

施工侧记录：

```text
Python 3.11.7
compileall samplelib/metadata samplelib/sampling → exit code 0
核心 schema/loader/analyzer/e2e → Ran 50 tests / OK / exit code 0
新增 R5-01 单测 → Ran 1 test / OK / exit code 0
全量 test_batch2_*.py → Ran 143 tests / unittest OK
全量命令 shell exit code -1073740791
```

全量命令在 unittest 已报告全部通过之后，于解释器 finalizing 阶段因 daemon host thread / stderr 锁触发非零退出。该问题已经有明确复现事实，并属于 Ticket 16 的 Windows spawn 与生命周期范围。

因此本 Review 的处理为：

```text
Ticket 14 assertions：PASS
Ticket 14 code contract：PASS
Windows process lifecycle：NOT WAIVED，转入 Ticket 16
GitHub Actions CI：无，不能宣称 CI PASS
```

---

## 5. 不得回退的公共接口

后续 Ticket 可以依赖：

```text
samplelib.metadata.contracts
  YAW_BUCKET_NAMES / PITCH_BUCKET_NAMES
  YAW_BUCKET_NAME_TO_ID / PITCH_BUCKET_NAME_TO_ID
  UNKNOWN_BUCKET_ID
  LEGACY_YAW_ALIASES / LEGACY_PITCH_ALIASES
  is_bool_compatible / parse_bool_valid
  is_record_structurally_valid
  get_record_image_valid
  get_record_landmarks_valid
  get_record_pose_valid
  get_record_quality_valid
  get_record_yaw_bucket
  get_record_pitch_bucket

samplelib.metadata.loader.RuntimeMetadata
  record_matched
  image_valid
  landmarks_valid
  pose_valid
  quality_valid
  metadata_valid
  usable_for_pose_sampling()
  usable_for_quality_sampling()
```

Ticket 15—21 不得重新实现第二套 bucket、bool 或 record validity 解释。

---

## 6. 后续依赖状态

```text
Ticket 14：PASS / CLOSED

立即解锁并行：
- Ticket 15：options-json、双 Gate、SRC/DST Sampling 配置
- Ticket 16：WeightedIndexHost Windows spawn 与生命周期
- Ticket 17：Analyzer workers、strong fingerprint、stale detection

继续独立开放：
- Ticket 19：Loss Window 保存边界与可观测性

后续：
Ticket 17 → Ticket 18
Ticket 15 + 16 + 17 → Ticket 20
Ticket 14—20 全部 PASS → Ticket 21
```

Ticket 16 必须优先纳入本轮已经观察到的 daemon 退出 stderr 锁与 shell 非零退出问题，并接受独立强 Review。

---

## 7. 最终签发

```text
Ticket 14
APPROVED / PASS / CLOSED
```

Batch 2 总状态仍为：

```text
REMEDIATION IN PROGRESS
METADATA SAMPLING NOT PRODUCTION READY
PENDING WINDOWS SPAWN
PENDING WINDOWS GPU
BATCH 3 BLOCKED BY BATCH 2 FINAL ACCEPTANCE
```
