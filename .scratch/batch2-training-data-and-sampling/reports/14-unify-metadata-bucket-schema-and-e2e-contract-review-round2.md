# Ticket 14 — 第二轮独立代码 Review 与剩余返修要求

> Review 状态：**REQUEST_CHANGES / NEAR-PASS**  
> Review 日期：2026-07-29  
> Review 对象：第一次独立 Review 之后的最新返修提交  
> 对应 Summary：`14-unify-metadata-bucket-schema-and-e2e-contract-summary.md`  
> Review 方法：GitHub 最新分支静态源码与测试源码复核；本 Reviewer 未在本地重新运行 188 个测试，GitHub 当前也没有可引用的 CI workflow 证据。

---

## 1. 最终结论

```text
REQUEST_CHANGES
NEAR-PASS
CORE BUCKET MISMATCH FIXED
ORDINARY SAMPLING EFFECT PROVEN
SCHEMA CONTRACT NOT CLOSED
PACKED FULL E2E NOT PROVEN
```

本轮返修已经明显改善，以下核心内容可以确认已经完成：

- Loader 已移除 `rec.get("valid", True)`；
- Analyzer 与 Loader 使用同一套 canonical yaw/pitch bucket；
- Analyzer 已写入 bucket contract version 和 canonical lists；
- Ordinary fixture 可以产生多个有效 yaw bucket；
- Ordinary 路径新增非均匀权重、稀缺桶权重、`strength=0`、概率归一化和经验抽样测试；
- legacy alias 与 unknown warning 已采用聚合计数和最多 5 条 example；
- fixture 已加入中文文件名；
- Report 已不再读取旧顶层 `valid`。

但是，第一次 Review 的 24 项硬性验收标准尚未全部满足。当前至少还有两个明确阻断项：

1. Schema 没有实现 `pose` mapping、`pose.valid` 类型及 legacy alias issue 契约；
2. Packed 流程仍未完成 `Analyzer → JSON → Loader → Policy → probabilities → IndexHost → draw` 的完整验收。

因此 Ticket 14 仍不能由独立 Reviewer 签发 `APPROVED / PASS`，Ticket 15、16、17、18、20、21 继续保持 `BLOCKED-BY-14`。

---

## 2. 本轮实际变更范围

相对于第一次 Review 提交，本轮分支只新增了一个返修提交，修改：

```text
samplelib/metadata/analyzer.py
samplelib/metadata/loader.py
samplelib/metadata/report.py
tests/fixtures/batch2/build_synthetic_fixture.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
.scratch/.../14-unify-metadata-bucket-schema-and-e2e-contract-summary.md
```

值得注意：

```text
samplelib/metadata/schema.py
samplelib/metadata/contracts.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_pose.py
```

本轮没有修改。因此 Summary 中关于 Schema 完整校验和 Bucket unit test 全面通过的陈述，必须按真实源码重新判断。

---

## 3. 已确认通过的返修项

## 3.1 R14-01 的旧顶层 valid 默认漏洞已移除

Loader 已不再执行：

```python
metadata_valid[i] = rec.get("valid", True)
```

并开始分别计算：

```text
metadata_valid
pose_valid
quality_valid
```

`get_record_pose_valid()`、`get_record_quality_valid()`、`get_record_yaw_bucket()` 和 `get_record_pitch_bucket()` 已进入 Loader 主链路。

该部分可以从第一次 Review 的 P0 状态降级为“主要修复完成，但结构契约仍需收尾”。

## 3.2 Analyzer contract metadata 已补充

`analysis_config.pose` 已写入：

```text
bucket_contract_version: 1
canonical_yaw_buckets
canonical_pitch_buckets
yaw_thresholds
pitch_thresholds
```

R14-05 可以判定 PASS。

## 3.3 Ordinary Pose-balanced 效果测试明显加强

新增测试现在会检查：

- 至少两个有效 yaw bucket；
- `sample_weights` 非全 1；
- 稀缺 bucket 权重高于热门 bucket；
- `pose_balance_strength=0` 恢复等权；
- probabilities finite、positive、sum≈1；
- 执行 5,000 次 IndexHost 抽样。

相比第一次提交，这已经证明 Ordinary 健康 Metadata 路径不再静默退化为全均匀权重。

## 3.4 Warning 聚合实现方向正确

Loader 已分别统计：

```text
LEGACY_YAW_ALIAS_USED
LEGACY_PITCH_ALIAS_USED
UNKNOWN_YAW_BUCKET
UNKNOWN_PITCH_BUCKET
```

warning 只保留总 count 和最多 5 条 examples，不会为十万级样本逐条追加字符串。

## 3.5 Unicode 文件名已经进入真实 Fixture

Fixture 新增：

```text
00005_中文文件名_dark.jpg
```

它随 Ordinary Analyzer、JSON Sidecar、Loader 和 Packed 构建一起执行，方向正确。

---

## 4. 剩余阻断问题

## R2-01 — Schema validation 实际仍未完成

**等级：P1 / BLOCKER FOR TICKET ACCEPTANCE**

Summary 的第 6 项写为：

```text
Schema 检查 pose mapping 与 valid 类型：PASS
```

但最新 `samplelib/metadata/schema.py` 与第一次 Review 时完全相同，本轮未修改。

当前逻辑仍然只有：

```python
pose_info = sample.get("pose")
if isinstance(pose_info, dict) and pose_info.get("valid", False):
    ...检查 yaw/pitch bucket...
```

仍未实现：

- `pose` 存在但不是 mapping 时产生 `INVALID_POSE_MAPPING`；
- `pose.valid` 不是 bool 或允许的 0/1 时产生 `INVALID_POSE_VALID_TYPE`；
- legacy yaw alias 产生 `LEGACY_YAW_BUCKET_ALIAS`；
- legacy pitch alias 产生 `LEGACY_PITCH_BUCKET_ALIAS`；
- canonical 与 legacy alias 的验证结果区分；
- Loader 将 Schema optional issues 聚合进 `RuntimeMetadata.warnings`。

### 实际风险

公共 accessor 当前使用：

```python
bool(pose_info.get("valid", False))
```

因此：

```python
pose.valid = "false"
```

在 Python 中会被解释为 `True`。只要 yaw bucket 可识别，该畸形 record 可能被标为 `pose_valid=True`。

这不是单纯文档问题，而是输入契约错误。

### 必须修复

修改：

```text
samplelib/metadata/schema.py
samplelib/metadata/contracts.py（如需要公共 bool parser）
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
```

至少新增：

```text
test_schema_rejects_non_mapping_pose
test_schema_rejects_invalid_pose_valid_type
test_schema_reports_legacy_yaw_alias
test_schema_reports_legacy_pitch_alias
test_schema_reports_unknown_bucket
test_loader_does_not_treat_string_false_as_pose_valid
test_loader_surfaces_schema_bucket_warnings
```

完成前 Summary 第 6 项不得标记 PASS。

---

## R2-02 — Loader 的 metadata_valid 结构判定仍过宽

**等级：P1 / BLOCKER FOR CONTRACT CLOSURE**

当前 Loader 认为 record 结构有效的规则是：

```python
isinstance(rec.get("pose"), dict)
or isinstance(rec.get("quality"), dict)
or isinstance(rec.get("image"), dict)
or "valid" in rec
```

这意味着以下记录仍可能被标为 `metadata_valid=True`：

```json
{
  "sample_id": "...",
  "sample_key": "...",
  "valid": true,
  "pose": "BROKEN"
}
```

因为仅存在旧顶层 `valid` 字段就能通过结构判定。

另外：

- `get_record_image_valid` 被导入，但没有进入 Loader 主链路；
- `record_matched` 与 `image_valid` 没有对应 RuntimeMetadata 数组或明确局部判定结果；
- Summary 声称“严格区分 record_matched、metadata_valid、image_valid、pose_valid、quality_valid”，与当前数据结构不一致。

### 修复要求

本 Ticket 不一定必须扩展所有 RuntimeMetadata 公共字段，但必须至少做到：

```text
metadata_valid = unique sample_id matched
                 AND record is mapping
                 AND known child fields have valid container types
```

不能再允许旧顶层 `valid` 单独证明结构有效。

建议增加 helper：

```python
is_record_structure_valid(record)
```

并测试：

```text
test_loader_top_level_valid_only_is_not_metadata_valid
test_loader_non_mapping_pose_is_not_metadata_valid
test_loader_non_mapping_quality_is_not_metadata_valid
test_loader_image_pose_quality_validity_are_independent
```

---

## R2-03 — Packed E2E 仍未达到完整验收标准

**等级：P1 / BLOCKER FOR TICKET ACCEPTANCE**

Summary 声称：

```text
Packed Fixture 至少 2 个有效 Yaw Buckets：PASS
Packed 完整 E2E：PASS
```

但当前 `test_e2e_packed_faceset_pipeline` 只执行：

```text
Analyzer
→ JSON
→ Loader
→ Policy.build_weights
→ assert weights finite
```

没有断言：

- Packed 至少两个有效 yaw bucket；
- Packed bucket counts 确实不均衡；
- Packed sample weights 非全 1；
- probabilities finite、positive、sum≈1；
- 构建 WeightedIndexHost；
- client.multi_get(draw_count)；
- empirical distribution；
- Packed 与 Ordinary 的同名 sample canonical bucket ID 一致；
- sample order 改变后 bucket ID 语义不变。

### 必须修复

扩展 Packed 测试，至少执行：

```text
Analyzer
→ JSON roundtrip
→ Loader
→ unique valid buckets >= 2
→ non-uniform weights
→ probabilities
→ WeightedIndexHost
→ draw
```

建议新增独立测试：

```text
test_e2e_packed_pose_balanced_sampling_effect
test_packed_and_ordinary_share_canonical_bucket_ids
test_packed_sample_order_does_not_change_bucket_semantics
```

完成前 Summary 第 11、18 项不得标记 PASS。

---

## 5. 高优先级测试问题

## R2-04 — Empirical test 的 expected distribution 与实际 Host 配置不一致

**等级：P1 / TEST VALIDITY**

Ordinary 经验抽样测试创建：

```python
SamplingConfig(..., pose_balance_strength=0.8, seed=42)
```

但没有显式设置 `uniform_mix`，因此使用默认值：

```text
uniform_mix = 0.1
```

Policy 构建 IndexHost 时会使用 `uniform_mix=0.1`。

测试单独计算 probabilities 时却使用：

```python
weights_to_probabilities(..., uniform_mix=0.0)
```

随后 empirical bucket distribution 又与 `pose_res.expected_distribution` 比较；该 expected distribution 也没有包含 Host 的 0.1 uniform mix。

因此当前测试比较的是：

```text
实际 Host 分布（含 10% uniform mix）
vs
理论分布（不含 uniform mix）
```

`0.08` 的宽容差可能掩盖这一配置不一致。

### 修复方式二选一

方案 A，推荐：

```python
cfg = SamplingConfig(..., uniform_mix=0.0)
```

让 Host 和 expected_distribution 使用同一条件。

方案 B：

根据实际 `cfg.uniform_mix` 计算最终 sample probabilities 和最终 bucket expected distribution，再与 empirical draws 比较。

必须避免测试看似验证 expected distribution，实际比较的是不同配置。

---

## R2-05 — 返修过程中削弱了已有测试

**等级：P1 / REGRESSION**

`test_compact_array_memory_footprint` 原来应计算：

```python
mb_size = total_bytes / (1024 * 1024)
self.assertLess(mb_size, 2.0)
```

最新文件在计算 `total_bytes` 后直接进入下一个测试函数，原断言被删除。该 test method 现在没有任何 assertion。

这违反 Ticket 规则：

```text
不得通过降低断言或削弱旧测试来通过返修
```

必须恢复内存 footprint 断言。

此外：

- legacy alias E2E 删除了旧 `extreme -> unknown / pose_valid=False` 的明确断言；
- warning bounded 测试只检查 warning 包含 `count=`，没有真正断言 examples 数量 `<=5`；
- 没有明确断言 `UNKNOWN_YAW_BUCKET` warning 包含 legacy `extreme`。

建议补回：

```text
test_loader_extreme_maps_unknown_and_emits_warning
test_loader_warning_examples_are_at_most_five
```

---

## 6. Summary 准确性问题

## R2-06 — 24 项自审清单仍有多项误报 PASS

**等级：P2 / PROCESS**

当前至少以下项目不能标为 PASS：

```text
6  Schema 检查 pose mapping 与 valid 类型       FAIL
11 Packed Fixture 至少 2 个有效 Yaw Buckets     NOT PROVEN
16 经验抽样频率符合期望分布                     PARTIAL / CONFIG MISMATCH
18 Packed 完整 E2E                              FAIL
20 Legacy tests PASS                            PARTIAL / MEMORY ASSERTION REMOVED
22 Summary 使用准确 Commit 范围                 PARTIAL / 使用可移动 HEAD
23 Summary 包含原始测试日志证据                  PARTIAL / 仅三行摘录
24 自审清单 24 项全勾选                         FAIL
```

Summary 状态应暂时改为：

```text
FIXES-REQUIRED / ROUND-2 REVIEW
```

而不是：

```text
RESOLVED / PASS
```

Commit 范围应使用两个不可变 SHA，而不是 `6c47df9 .. HEAD`，因为 HEAD 会继续移动。

测试日志至少应记录：

```text
exact commit SHA
Python executable / version
完整命令
Ran N tests in Xs
OK / failures / skips
```

自审不能代替 Ticket 规定的独立 Reviewer Gate。

---

## 7. 第二轮 24 项验收矩阵

| # | 验收标准 | 第二轮结论 |
|---|---|---|
| 1 | Loader 不再使用 `rec.get("valid", True)` | PASS |
| 2 | 公共 Accessors 接入 Loader 主链路 | PARTIAL：image accessor 未使用 |
| 3 | metadata/pose/quality valid 语义分离 | PARTIAL：结构判定仍过宽 |
| 4 | Analyzer 只写 canonical | PASS |
| 5 | analysis_config 记录 contract/version | PASS |
| 6 | Schema 检查 pose mapping 与 valid 类型 | FAIL |
| 7 | Alias 兼容读取产生有界 warning | PASS-IN-CODE / TEST PARTIAL |
| 8 | Unknown yaw 不误标 pose valid | PASS-IN-CODE / EXTREME TEST MISSING |
| 9 | Unknown pitch 不破坏有效 yaw | PASS |
| 10 | Ordinary 至少两个有效 yaw bucket | PASS |
| 11 | Packed 至少两个有效 yaw bucket | NOT PROVEN |
| 12 | Sample weights 非全 1 | PASS（Ordinary） |
| 13 | 稀缺 bucket 权重更高 | PASS（Ordinary） |
| 14 | strength=0 恢复等权 | PASS（Ordinary） |
| 15 | probabilities finite/positive/sum≈1 | PASS（Ordinary） |
| 16 | empirical 与 expected distribution 一致 | PARTIAL：uniform_mix 不一致 |
| 17 | Ordinary 完整 E2E | PASS（主进程 Host） |
| 18 | Packed 完整 E2E | FAIL |
| 19 | Unicode 目录和文件名 | PASS-IN-FIXTURE |
| 20 | Legacy tests PASS 且未削弱 | FAIL：memory assertion 被删除 |
| 21 | 全量 smoke PASS | SELF-REPORTED 188/188，未独立复跑 |
| 22 | Summary 使用准确 commit 范围 | PARTIAL |
| 23 | Summary 含概率对比和原始证据 | PARTIAL |
| 24 | 独立 Reviewer 签发 PASS | FAIL |

---

## 8. 最小返修范围

下一轮只需集中修改：

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
Ticket 14 summary
```

不需要重做 canonical bucket 主实现，也不得进入 Ticket 15—20。

推荐施工顺序：

```text
1. 补 Schema 与 string-false 失败测试
2. 收紧 metadata_valid 结构判定
3. 修复 Schema issue/warning 对接
4. 补 Packed 完整 E2E
5. 统一 empirical test 的 uniform_mix
6. 恢复 memory footprint assertion
7. 补 extreme warning 和 warning bound 精确断言
8. 重新运行定向测试与全量 smoke
9. 用不可变 commit SHA 更新 Summary
10. 提交第三轮独立 Review
```

---

## 9. 后续 Ticket 状态

在本 Review 通过前：

```text
Ticket 14：FIXES-REQUIRED / ROUND-2
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
```

Ticket 19 仍可独立并行。
