# Ticket 14 — 独立代码 Review 与返修要求

> Review 状态：**REQUEST_CHANGES / FIXES-REQUIRED**  
> Review 日期：2026-07-29  
> 被审 Commit：`6c47df942a5219cd3a155275eaed89b6b104e630`  
> 基线 Commit：`6e0d7bf64d3d95d0da15293d2b779aadd86c7888`  
> Ticket：`14-unify-metadata-bucket-schema-and-e2e-contract.md`  
> Reviewer 结论：Canonical bucket 主方向正确，但 Ticket 14 的数据有效性契约和“采样实际生效”验收未闭环，当前不得标记 `RESOLVED`。

---

## 1. 最终判定

```text
REQUEST_CHANGES
FIXES-REQUIRED
P0 CONTRACT PARTIALLY FIXED
E2E SAMPLING EFFECT NOT PROVEN
```

本次实现已经完成以下重要修正：

- 新增 `samplelib/metadata/contracts.py`；
- 固定 7 个 canonical yaw bucket 和 3 个 canonical pitch bucket；
- Analyzer 新输出的 bucket 名称与 Loader 映射方向基本统一；
- `front`、`slight_left`、`left` 等 legacy alias 可以转换；
- 新增 Ordinary / Packed 流程测试文件；
- Loader 不再把 Analyzer canonical yaw 全部映射成 `-1`。

但是 Ticket 14 的完成条件不是“Sidecar 能显示 LOADED”或“测试数量增加”，而是：

```text
真实 Analyzer 输出
→ Loader 正确解释完整 record contract
→ Policy 产生非均匀有效权重
→ 稀缺 bucket 权重高于热门 bucket
→ WeightedIndexHost 实际抽样分布变化
```

当前提交没有证明以上完整条件，因此不能解锁后续 Ticket 15—18。

---

## 2. Review 范围

实际 Ticket 14 变更是一个提交，而不是 summary 中记录的 `c302087 .. HEAD`：

```text
Base : 6e0d7bf64d3d95d0da15293d2b779aadd86c7888
Head : 6c47df942a5219cd3a155275eaed89b6b104e630
```

变更文件：

```text
samplelib/metadata/contracts.py
samplelib/metadata/pose.py
samplelib/metadata/analyzer.py
samplelib/metadata/loader.py
samplelib/metadata/schema.py
samplelib/metadata/report.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
.scratch/.../reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md
```

本 Review 为静态源码与测试源码审查。GitHub 上没有该 commit 的 Actions workflow run 或 status check，因此 summary 中的 `185/185 PASS` 目前只能视为执行者自报结果，不能视为可复核 CI 证据。

---

## 3. 已通过的部分

### 3.1 Canonical bucket 常量

以下顺序符合 Ticket 固定决策：

```python
YAW_BUCKET_NAMES = (
    "extreme_left",
    "major_left",
    "minor_left",
    "center",
    "minor_right",
    "major_right",
    "extreme_right",
)

PITCH_BUCKET_NAMES = (
    "up",
    "level",
    "down",
)
```

ID 顺序也符合要求：yaw `0..6`，pitch `0..2`，unknown 为 `-1`。

### 3.2 Analyzer 与 Loader 的主要名称断裂已修正

`pose.py` 返回 canonical 名称；Loader 通过公共 helper 将 canonical yaw/pitch 映射为固定 ID。原先 Analyzer 输出全部落入 unknown 的核心问题已经得到直接修正。

### 3.3 Legacy extreme 没有猜方向

旧值 `extreme` 没有被错误猜成 `extreme_left` 或 `extreme_right`，而是落入 unknown。这一决策正确。

### 3.4 Ordinary / Packed 基本链路已经建立

新增测试真实调用了 Analyzer 和 Loader，不再只手工构造 canonical Analyzer record。该方向正确，应在返修中继续保留，不能退回纯 mock。

---

## 4. 阻断问题

## R14-01 — Loader 仍违反 Metadata 有效性契约

**等级：P0 / BLOCKER**

Ticket 明确禁止继续使用：

```python
rec.get("valid", True)
```

但当前 `samplelib/metadata/loader.py` 仍然执行：

```python
metadata_valid[i] = rec.get("valid", True)
```

真实 Analyzer record 没有顶层 `valid` 字段，因此这里会默认得到 `True`。这意味着：

- 只要 sample_id 匹配，结构残缺的 record 也可能被标为 `metadata_valid=True`；
- `image.valid`、`landmarks.valid`、`pose.valid`、quality 可解析性没有被正确区分；
- 新增的 `get_record_image_valid()`、`get_record_pose_valid()`、`get_record_quality_valid()` accessor 没有真正进入 Loader 主链路；
- 测试中的 `np.all(runtime.metadata_valid)` 只是验证了旧默认值，不能证明完整 record contract。

### 必须修复

Loader 至少应明确计算：

```text
record_matched
image_valid
pose_valid
quality_valid
metadata_valid
```

建议规则：

```text
record_matched = sample_id 唯一匹配
metadata_valid = record_matched 且 record 是 mapping 且必要子结构可安全解析
pose_valid = metadata_valid 且 pose.valid=True 且 yaw bucket 可识别
quality_valid = metadata_valid 且 quality_score 存在且 finite
```

`metadata_valid` 不得由 image 是否清晰、pose 是否有效决定；但也不得对任意匹配 ID 的畸形 record 默认 true。

### 必须新增测试

```text
test_loader_metadata_valid_uses_nested_contract
test_loader_matched_but_malformed_record_is_not_metadata_valid
test_loader_image_invalid_pose_valid_are_independent
test_loader_quality_invalid_does_not_fake_quality_valid
```

---

## R14-02 — E2E 没有证明 Pose-balanced Sampling 实际产生变化

**等级：P0 / BLOCKER**

当前 E2E 只断言：

```text
sample_weights 长度正确
sample_weights finite
sample_weights > 0
IndexHost 返回合法索引
```

但没有断言 Ticket 要求的核心结果：

```text
sample_weights 不是全 1
probabilities 不是全均匀
稀缺 bucket 单样本权重高于热门 bucket
pose_balance_strength=0 恢复等权
probabilities.sum() ≈ 1
经验抽样分布接近期望分布
```

因此即使所有样本仍落在同一个 bucket、Policy 返回全 1，现有测试也会通过。

此外 synthetic fixture 的 `left_yaw` / `right_yaw` 当前只是把全部 landmark 的 `center_x` 整体平移。整体平移不等同于可靠的头部几何 yaw 变化，测试也没有断言 Analyzer 最终确实生成至少两个不同 yaw bucket。

### 必须修复

构建一个**可证明不均衡**的真实 Analyzer fixture。测试必须先断言：

```python
unique_valid_buckets >= 2
max(bucket_count) > min(nonzero_bucket_count)
```

然后断言：

```python
not np.allclose(sample_weights, np.ones_like(sample_weights))
rare_bucket_sample_weight > common_bucket_sample_weight
np.isfinite(probabilities).all()
(probabilities > 0).all()
abs(probabilities.sum() - 1.0) < tolerance
```

最后至少执行固定 seed 的经验抽样：

```text
expected distribution
vs
empirical distribution
```

容差应在测试中固定，不得只检查抽到的索引是否合法。

### 必须新增测试

```text
test_e2e_analyzer_produces_multiple_yaw_buckets
test_e2e_pose_weights_are_non_uniform
test_e2e_rare_bucket_has_higher_per_sample_weight
test_e2e_balance_strength_zero_is_uniform
test_e2e_probabilities_are_normalized
test_e2e_empirical_draws_match_expected_distribution
```

---

## R14-03 — Legacy alias 与 unknown 没有 warning

**等级：P1 / BLOCKER FOR TICKET ACCEPTANCE**

Ticket 明确要求：

- alias Sidecar 可读取并产生 warning；
- 旧 `extreme` 返回 unknown；
- 添加 warning；
- `pose_valid=False`；
- warning 不得逐样本无限增长。

当前实现只完成了映射结果：

```text
front -> center
slight_left -> minor_left
extreme -> unknown
```

Loader 没有为 alias、unknown yaw、unknown pitch 添加汇总 warning。新增 E2E 测试也只检查 ID 和 pose_valid，没有检查 warning。

### 必须修复

建议 warning 采用聚合形式，例如：

```text
LEGACY_YAW_ALIAS_USED count=12 examples=[...]
LEGACY_PITCH_ALIAS_USED count=5 examples=[...]
UNKNOWN_YAW_BUCKET count=3 examples=[...]
UNKNOWN_PITCH_BUCKET count=2 examples=[...]
```

示例数量必须有上限，例如 5 或 10，不能对十万样本逐条追加 warning。

### 必须新增测试

```text
test_loader_legacy_alias_emits_aggregated_warning
test_loader_extreme_emits_unknown_warning
test_loader_unknown_pitch_does_not_disable_valid_yaw
test_loader_warning_count_is_bounded
```

---

## R14-04 — Schema validation 没有达到 Ticket 要求

**等级：P1 / BLOCKER FOR TICKET ACCEPTANCE**

当前 Schema 只在：

```python
isinstance(pose_info, dict) and pose_info.get("valid", False)
```

时检查 bucket。

未完成：

- `pose` 非 mapping 时产生 validation issue；
- `pose.valid` 的 bool-compatible 校验；
- legacy alias 与 canonical 的区别记录；
- 非 canonical 新写文件产生 issue/warning；
- invalid sample ID 或畸形 record 与 Loader warning 对接；
- Loader 将 Schema validation issues 暴露到 RuntimeMetadata warnings。

因为 alias helper 直接返回 valid，Schema 当前会把 alias 当作完全 canonical，不会产生任何兼容读取提示。

### 必须修复

至少增加 issue code：

```text
INVALID_POSE_MAPPING
INVALID_POSE_VALID_TYPE
LEGACY_YAW_BUCKET_ALIAS
LEGACY_PITCH_BUCKET_ALIAS
INVALID_YAW_BUCKET
INVALID_PITCH_BUCKET
```

Loader 对 optional、可降级 issue 应汇总进 `RuntimeMetadata.warnings`；JSON parse、unsupported schema 等状态保持现有安全回退语义。

### 必须新增测试

```text
test_schema_rejects_non_mapping_pose
test_schema_rejects_invalid_pose_valid_type
test_schema_reports_legacy_alias
test_schema_reports_unknown_bucket
test_loader_surfaces_schema_bucket_warnings
```

---

## R14-05 — Analyzer 没有记录 bucket contract/version

**等级：P1**

Ticket Step 4 要求在 analysis config 中记录 bucket contract/version。当前 `analysis_config.pose` 只保存 threshold：

```text
yaw_thresholds
pitch_thresholds
```

没有保存：

```text
bucket_contract_version
canonical_yaw_buckets
canonical_pitch_buckets
```

这样未来 bucket 规则演进时，旧 Sidecar 无法明确声明其生成契约。

### 必须修复

建议写入：

```json
{
  "pose": {
    "bucket_contract_version": 1,
    "yaw_buckets": [
      "extreme_left",
      "major_left",
      "minor_left",
      "center",
      "minor_right",
      "major_right",
      "extreme_right"
    ],
    "pitch_buckets": ["up", "level", "down"],
    "yaw_thresholds": [-0.8, -0.4, -0.15, 0.15, 0.4, 0.8],
    "pitch_thresholds": [-0.15, 0.15]
  }
}
```

字段名可调整，但必须固定、测试并进入文档。

---

## R14-06 — 自动测试矩阵缺失多项硬性验收

**等级：P1**

### Bucket 测试不足

当前只测试了若干代表值，没有覆盖精确阈值边界：

```text
-0.8
-0.4
-0.15
0.15
0.4
0.8
```

也没有公共 contract helper 的 None、数字、空字符串、未知字符串、alias、extreme 测试。

### Analyzer 测试不足

没有断言：

- 每个 valid pose bucket 都属于 canonical set；
- summary keys 与 canonical + unknown 完全一致；
- Metadata JSON roundtrip 后 bucket 不变；
- Unicode **文件名** 正常。当前只使用中文目录，fixture 文件名仍是 ASCII；
- analysis_config 包含 bucket contract/version。

### Loader 测试不足

没有断言：

- valid yaw ID 全部在 0..6；
- valid pitch ID 全部在 0..2；
- LOADED 不等于所有 pose 都 valid；
- unknown pitch 保留有效 yaw；
- alias warning；
- malformed matched record 的 metadata_valid。

### Packed 测试不足

Packed E2E 只走到 `build_weights()` 且只检查 finite，没有：

- 构建 IndexHost；
- draw；
- 非均匀权重；
- sample order 改变后 bucket ID 语义不变；
- Ordinary 与 Packed canonical contract 对照。

### Summary 要求未满足

实施 summary 缺少：

- 正确的 before/after commit；
- 概率分布前后对比；
- Unicode 文件名状态；
- 未完成项；
- 独立 Reviewer 结论；
- 可复核原始测试日志或 CI 链接。

---

## R14-07 — 实施 Summary 存在不准确陈述

**等级：P2 / PROCESS**

需要修正：

1. `修改 Commit：c302087 .. HEAD` 包含大量非 Ticket 14 历史提交，不能作为本 Ticket 变更范围；
2. 实际 Ticket 14 commit 是 `6c47df942a5219cd3a155275eaed89b6b104e630`；
3. 文档中的 `file:///t:/...` 链接只在执行者本机有效，GitHub 无法访问；
4. summary 声称 `report.py` 使用统一 contracts，但当前 `report.py` 没有导入或调用新 accessors，仍存在旧顶层 `valid` 读取；
5. summary 在独立 Review 前直接写 `RESOLVED / PASS`，与 Ticket 的强制 Reviewer Gate 冲突；
6. GitHub 当前没有该 commit 的 workflow run/status check，不能把自报 `185/185` 等同于可复核 CI 结论。

返修后 summary 应改为事实记录，并引用本 Review 的最终复核结论。

---

## 5. 返修边界

本轮只返修 Ticket 14，不得顺手进入：

```text
Ticket 15：SRC/DST config
Ticket 16：Windows spawn
Ticket 17：workers / strong fingerprint / stale signature
Ticket 18：完整 Incremental 重构
Ticket 19：Loss Window
Ticket 20：fallback exception boundary
```

允许为 Ticket 14 调整：

```text
samplelib/metadata/contracts.py
samplelib/metadata/pose.py
samplelib/metadata/analyzer.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
samplelib/metadata/report.py（仅当前 contract 读取与 warning）
tests/fixtures/batch2/build_synthetic_fixture.py
tests/smoke/test_batch2_pose.py
tests/smoke/test_batch2_analyzer_core.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
Ticket 14 summary
```

不得通过降低断言、移除真实 Analyzer、把所有 bucket 强制映射 center 或手工伪造 Analyzer 输出解决。

---

## 6. 推荐返修顺序

### Step 1：补失败测试

先新增能够在当前 commit 失败的测试：

1. malformed matched record 不得 metadata_valid；
2. alias / extreme 必须有 warning；
3. Analyzer fixture 至少生成两个有效 yaw bucket；
4. 权重必须非全 1；
5. 稀缺 bucket 权重高于热门 bucket；
6. empirical draw 接近期望分布；
7. Schema 非 mapping pose 和 invalid valid type 产生 issue。

必须保留修复前失败证据。

### Step 2：修复公共 record contract

将 accessor 设计完整，并让 Loader 真正调用，而不是只定义未使用函数。

### Step 3：修复 Schema 与 warning 聚合

区分 canonical、legacy alias 和 unknown，向 RuntimeMetadata 暴露有界 warning。

### Step 4：修复 Analyzer contract metadata

写入 bucket contract/version 与 canonical 名称列表。

### Step 5：构建真实不均衡 fixture

不要只整体平移 landmarks。可以：

- 使用经验证能得到不同 yaw 的 synthetic landmark geometry；
- 或在 Analyzer pose estimator 层使用最小范围、确定性 patch，但仍必须由 Analyzer 生成最终 record；
- 不得直接手写最终 Metadata record替代 Analyzer。

### Step 6：完成 Ordinary / Packed 全链路

两类数据都至少执行：

```text
Analyzer
→ JSON roundtrip
→ Loader
→ Policy weights
→ probabilities
→ WeightedIndexHost
→ draw
```

### Step 7：更新 summary

记录准确 commit、测试命令、原始输出、概率对比、Unicode、未完成项和 Reviewer 状态。

---

## 7. 返修后的最低测试清单

```bash
python -m compileall samplelib/metadata samplelib/sampling
python -m unittest tests.smoke.test_batch2_pose
python -m unittest tests.smoke.test_batch2_analyzer_core
python -m unittest tests.smoke.test_batch2_metadata_schema
python -m unittest tests.smoke.test_batch2_metadata_loader
python -m unittest tests.smoke.test_batch2_metadata_sampling_e2e
python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

Windows 执行时还应记录：

```text
Python 版本
commit SHA
完整命令
Ran N tests in Xs
OK / failures / skips
```

GitHub Actions 若未配置，应把终端原始输出保存进 summary 或独立 acceptance artifact，而不是只写结论数字。

---

## 8. 重新 Review 的硬性验收标准

只有以下全部满足，Reviewer 才能改为 `APPROVED / PASS`：

- [ ] Loader 不再使用 `rec.get("valid", True)`；
- [ ] 公共 accessor 真正进入 Loader 主链路；
- [ ] metadata_valid、pose_valid、quality_valid 语义分离；
- [ ] Analyzer 只写 canonical bucket；
- [ ] analysis_config 记录 bucket contract/version；
- [ ] Schema 检查 pose mapping 与 valid 类型；
- [ ] alias 兼容读取产生有界 warning；
- [ ] unknown yaw 不误标 pose valid；
- [ ] unknown pitch 不破坏有效 yaw；
- [ ] Ordinary fixture 至少两个有效 yaw bucket；
- [ ] Packed fixture 至少两个有效 yaw bucket；
- [ ] sample weights 非全 1；
- [ ] 稀缺 bucket 权重高于热门 bucket；
- [ ] strength=0 恢复等权；
- [ ] probabilities finite、positive、sum≈1；
- [ ] empirical draw 与 expected distribution 在固定容差内；
- [ ] Ordinary 完整 E2E PASS；
- [ ] Packed 完整 E2E PASS；
- [ ] Unicode 目录和 Unicode 文件名 PASS；
- [ ] legacy tests PASS；
- [ ] 全量 Batch smoke PASS；
- [ ] summary 使用准确 commit 范围；
- [ ] summary 包含概率前后对比和原始测试证据；
- [ ] 独立 Reviewer 重新签发 PASS。

---

## 9. 后续 Ticket 状态

在本 Review 通过前：

```text
Ticket 14：FIXES-REQUIRED
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
```

Ticket 19 与 Ticket 14 无直接依赖，可由另一个独立 Agent 继续执行，但不得借此把 Batch 2 标记完成。
