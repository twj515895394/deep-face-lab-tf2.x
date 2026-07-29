# Ticket 14 — 第三轮独立代码 Review 与剩余返修要求

> Review 状态：**REQUEST_CHANGES / CLOSE-BUT-NOT-PASS**  
> Review 日期：2026-07-29  
> 被审返修 Commit：`18e3d74091cdb179b2410486b9da5f7dca2d3ca3`  
> 上一交接 Commit：`5609ddfaffa1281c9c4981367e35daeef22556b6`  
> Review 方法：GitHub 最新分支静态源码与测试源码复核。Reviewer 未独立运行本地 195 个测试；该 Commit 无 GitHub Actions workflow run 或 status check。

---

## 1. 最终判定

```text
REQUEST_CHANGES
CLOSE-BUT-NOT-PASS
CORE ANALYZER→LOADER→POLICY PATH FIXED
ORDINARY AND PACKED MAIN E2E ESTABLISHED
WARNING BOUND CONTRACT STILL BROKEN
BOOL-COMPATIBLE CONTRACT INCONSISTENT
MANDATORY TICKET TEST MATRIX INCOMPLETE
```

本轮返修不是只修改 Summary。以下内容已经真实进入代码和测试：

- Schema 增加 pose mapping、pose.valid、legacy alias 和 unknown bucket issue；
- Loader 不再允许仅靠顶层 `valid: true` 标记 `metadata_valid=True`；
- `uniform_mix=0.0` 已与 empirical test 对齐；
- Packed 测试已走到 Policy、probabilities、IndexHost 和 draw；
- 内存断言、legacy `extreme`、warning example 上限测试已恢复或新增。

但是 Ticket 14 仍存在两个实现级问题，且 Ticket 明文要求的自动测试矩阵尚未完成，因此不能签发独立 Reviewer `APPROVED / PASS`。

---

## 2. 已确认关闭的 Round 2 问题

### 2.1 顶层 valid-only 漏洞

Loader 当前至少要求 `pose`、`quality`、`image` 中存在一个 dict，不再把仅含顶层 `valid: true` 的 record 标记为 metadata valid。

### 2.2 字符串 `"false"` 真值陷阱

`get_record_pose_valid()` 已通过 `parse_bool_valid()` 读取，不再直接执行 `bool("false")`。

### 2.3 Ordinary / Packed 主链路

Ordinary 已覆盖非均匀权重、稀缺桶权重、strength=0、概率归一化和 empirical draw。

Packed 已覆盖：

```text
Analyzer
→ JSON
→ Loader
→ 多 yaw bucket
→ 非均匀 weights
→ probabilities
→ WeightedIndexHost
→ draw
```

### 2.4 被削弱断言已部分恢复

- `test_compact_array_memory_footprint` 恢复 `< 2MB`；
- legacy `extreme` 明确断言 unknown、pose invalid 和 warning；
- alias warning example 数量增加 `<= 5` 断言。

---

## 3. 剩余阻断问题

## R3-01 — RuntimeMetadata warnings 仍会逐样本无限增长

**等级：P0 / BLOCKER**

Schema 会为每个 legacy alias、unknown bucket 或 pose 问题生成一条 `val_res.issues`。Loader 随后执行：

```python
for issue in val_res.issues:
    if issue.code in (...):
        warnings.append(f"SCHEMA_ISSUE [{issue.code}] {issue.message}")
```

这意味着 100,000 个 legacy alias 样本可能生成约 100,000 条 `RuntimeMetadata.warnings`，之后 Loader 又额外生成一条聚合 warning。

Ticket 14 明确要求：

```text
warnings 不得逐样本无限增长，超过阈值应汇总
```

当前 `test_loader_alias_warnings_are_aggregated_and_bounded` 只检查 `LEGACY_YAW_ALIAS_USED` 这一条 warning 的 examples 数量，没有检查：

```text
len(runtime.warnings)
SCHEMA_ISSUE 数量
每个 issue code 的聚合数量
```

### 必须修复

Schema issue 进入 RuntimeMetadata 时按 code 聚合，例如：

```text
SCHEMA_ISSUE LEGACY_YAW_BUCKET_ALIAS count=100000 examples=[最多5条]
SCHEMA_ISSUE INVALID_POSE_MAPPING count=27 examples=[最多5条]
```

不得逐 issue append。

### 必须新增测试

```text
test_loader_schema_warnings_are_aggregated_by_code
test_loader_total_warning_count_is_bounded
test_loader_100k_alias_records_do_not_create_100k_runtime_warnings
```

---

## R3-02 — Schema 与 parse_bool_valid 的 bool-compatible 规则不一致

**等级：P0 / BLOCKER**

Schema 当前把所有 int 都视为 bool-compatible：

```python
isinstance(valid_val, (bool, int))
```

因此 `2`、`-1` 不产生 `INVALID_POSE_VALID_TYPE`。

但 `parse_bool_valid()` 只把等于 `1` 的值当 true、等于 `0` 的值当 false。更重要的是，它在类型检查前执行：

```python
val == 1
val == 0
```

所以浮点数 `1.0` 会被 Loader 当作 true；Schema 却会把 `1.0` 标记为 invalid type。结果可能出现：

```text
Schema：INVALID_POSE_VALID_TYPE
Loader：pose_valid=True
```

这违反单一契约原则。

### 必须修复

建立唯一 bool-compatible helper，同时供 Schema 和 accessor 使用。建议只允许：

```text
True / False
整数 1 / 0
字符串 true / false / 1 / 0（忽略大小写与两端空格）
```

明确拒绝：

```text
2、-1、1.0、0.0、空字符串、任意其他字符串、None
```

若决定允许 float 0.0/1.0，也必须由 Schema 与 Loader 同时允许，并写入固定测试；不得两套规则不同。

### 必须新增测试

```text
test_bool_valid_contract_true_values
test_bool_valid_contract_false_values
test_bool_valid_contract_rejects_other_ints
test_bool_valid_contract_schema_loader_consistency
```

---

## R3-03 — metadata_valid 对“混合畸形子结构”仍过宽

**等级：P1**

当前结构判定只要求任意一个 child 是 dict：

```python
isinstance(rec.get("pose"), dict)
or isinstance(rec.get("quality"), dict)
or isinstance(rec.get("image"), dict)
```

因此下面的 record 仍会被标为 `metadata_valid=True`：

```json
{
  "pose": "BROKEN",
  "quality": {}
}
```

Schema 虽然会报告 `INVALID_POSE_MAPPING`，但 Loader 的 record-level `metadata_valid` 仍为 true。

Ticket 定义是：

```text
metadata_valid = record_matched 且结构可解析
```

建议规则：至少存在一个已知子结构，并且所有实际出现的已知子结构均为 mapping。子结构内部业务有效性继续由 image/pose/quality valid 独立表达。

### 必须新增测试

```text
test_loader_mixed_valid_and_malformed_child_is_not_metadata_valid
```

---

## R3-04 — Ticket 明文要求的自动测试矩阵仍未完成

**等级：P1 / ACCEPTANCE BLOCKER**

Ticket 14 第 8 节明确要求，但最新提交仍缺少：

### Bucket unit tests

- 精确 threshold 边界：`-0.8/-0.4/-0.15/0.15/0.4/0.8`；
- 左右方向边界不反转；
- canonical 7 yaw / 3 pitch 完整集合；
- alias helper；
- `extreme`；
- None、数字、空字符串、未知字符串。

当前 pose 测试只使用 `-0.9/-0.5/-0.2/0/0.2/0.5/0.9`，并未测试真实边界值。

### Analyzer output tests

仍缺少明确断言：

- 所有 valid pose bucket 属于 canonical set；
- summary keys 与 canonical + unknown 固定集合完全一致；
- JSON roundtrip 后 bucket 名称不变；
- Unicode 文件名对应 record 可被精确查找并保持 bucket；
- analysis_config contract/version 的自动断言。

### Loader tests

仍缺少明确断言：

- 所有 valid yaw ID 均在 `0..6`；
- 所有 valid pitch ID 均在 `0..2`；
- `LOADED` 不代表所有 pose 都 valid；
- image/landmarks/pose/quality/metadata 语义分离。

### Packed sample-order semantics

新增测试只比较 Ordinary/Packed 的部分 common filename，没有实际改变 sample order。Ticket 明确要求：

```text
sample order 不改变 bucket ID 语义
```

必须对 reversed/shuffled samples 再次 Loader.load，并按 sample key/name 比较 ID。

---

## R3-05 — Packed/Ordinary 对照测试存在顺序依赖且断言过弱

**等级：P1**

`setUpClass()` 只构建 fixture，不生成 sidecar。`test_packed_and_ordinary_share_canonical_bucket_ids` 自身也不运行 Analyzer 和 dump JSON，而是依赖其他测试先执行并写入 sidecar。

此外当前只断言：

```python
len(common_names) > 0
```

即使只重合一个样本也会通过，不能证明“100% 一致”。

### 必须修复

该测试应自包含地生成 Ordinary/Packed sidecar，并断言：

```text
ordinary valid-name set == packed valid-name set
ordinary name→bucket map == packed name→bucket map
reversed/shuffled order 后 map 仍相同
```

---

## R3-06 — Summary 仍不满足自身宣称的准确性

**等级：P2 / PROCESS**

Summary 同时出现：

```text
Commit 范围：1d03494 .. HEAD
基线：973cc6a
验收项 22：973cc6a .. HEAD
```

三者不一致，且 `HEAD` 是可移动引用。Round 2 实际返修提交是：

```text
Base: 5609ddfaffa1281c9c4981367e35daeef22556b6
Head: 18e3d74091cdb179b2410486b9da5f7dca2d3ca3
```

Summary 仍缺少 Ticket 要求的：

- canonical 名称和 ID 完整表；
- alias 完整表；
- 实际修改函数；
- probability / bucket distribution 具体前后数值；
- 未完成项；
- 独立 Reviewer 结论。

`195/195 PASS` 是执行者本机日志摘录。GitHub 当前没有该 Commit 的 Actions workflow run 或 status check，不能表述为独立 CI 证据。

---

## 4. 最小返修范围

只需处理以下内容，不要重做已通过主链路：

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
tests/smoke/test_batch2_pose.py
tests/smoke/test_batch2_analyzer_core.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
Ticket 14 summary
```

禁止进入 Ticket 15、16、17、18、20 的实现范围。

---

## 5. 重新 Review 的通过条件

只有以下全部满足才能签发 Ticket 14 PASS：

- [ ] RuntimeMetadata schema warnings 按 code 聚合且总数有上限；
- [ ] Schema 与 Loader 共用同一 bool-compatible 契约；
- [ ] `2/-1/1.0/空字符串` 等边界行为有固定测试；
- [ ] 混合畸形 child 不误标 metadata_valid；
- [ ] 精确 yaw/pitch threshold 边界测试完成；
- [ ] contracts 的 alias/unknown/None/数字/空串测试完成；
- [ ] Analyzer canonical set、summary keys、roundtrip、Unicode record 测试完成；
- [ ] Loader yaw/pitch ID 范围与 LOADED 非全-valid 测试完成；
- [ ] Packed 测试自包含；
- [ ] Packed reversed/shuffled sample-order 语义不变；
- [ ] Summary 使用完整不可变 Base/Head SHA；
- [ ] Summary 记录实际 distribution 数值和独立 Reviewer 状态；
- [ ] 全量 smoke 继续通过且旧测试未削弱。

---

## 6. 后续 Ticket 状态

```text
Ticket 14：ROUND-3 / FIXES-REQUIRED / CLOSE-BUT-NOT-PASS
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：可独立并行
```
