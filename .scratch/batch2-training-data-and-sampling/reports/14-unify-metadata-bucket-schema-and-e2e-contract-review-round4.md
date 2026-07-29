# Ticket 14 — 第四轮独立代码 Review 与最终剩余返修

> Review 状态：**REQUEST_CHANGES / TWO-CONTRACT-GAPS-REMAIN**  
> Review 日期：2026-07-29  
> 被审实现 Commit：`7b482c9ced3631b7cde7dcdd3f07bff47ab28960`  
> 文档锚点 Commit：`c08f25ae50bbdab620b0798faaaf058b4aa49271`  
> Review 方法：GitHub 最新分支静态源码与测试源码复核。Reviewer 未独立运行 Windows 本机 135 tests；GitHub 当前无该提交的 Actions/status check。

---

## 1. 最终判定

```text
REQUEST_CHANGES
TWO-CONTRACT-GAPS-REMAIN
R3-01 WARNING BOUND: CLOSED
R3-02 BOOL NUMERIC/STRING RULE: MOSTLY CLOSED
R3-03 MALFORMED CHILD: CLOSED
R3-04 TEST MATRIX: MOSTLY CLOSED
R3-05 PACKED ORDER: CLOSED
TICKET 14 ORIGINAL VALIDITY CONTRACT: NOT FULLY CLOSED
```

Round-3 返修是真实代码修复，不是只改 Summary。以下内容已经通过静态复核：

- Schema issues 已按 code 聚合，RuntimeMetadata warning 总数和 examples 均有上限；
- bool helper 已拒绝其它整数和 float，Schema/Loader 复用公共 helper；
- 混合畸形 child 不再误标 metadata_valid；
- 精确 threshold、alias、canonical sets、Analyzer roundtrip、Unicode、ID 范围、LOADED 非全 pose valid 等测试已加入；
- Packed/Ordinary 对照测试已自包含，并覆盖 reversed/shuffled order；
- Summary 已使用不可变 Base/Head SHA，并记录 distribution 数值。

但是原 Ticket 第 4 节要求 Loader 区分完整记录有效性语义。当前仍有两个契约缺口，所以不得签发 `APPROVED / PASS`。

---

## 2. 已确认关闭的 Round-3 问题

### 2.1 Warning 有界与聚合

`_aggregate_schema_issues_to_warnings()` 将逐样本 issue 聚合为每个 code 一条 warning；`_MAX_RUNTIME_WARNINGS=32`，examples 最多 5 条。100k alias 测试也已加入。

### 2.2 bool 的数字、字符串和 float 边界

公共 helper 当前统一允许：

```text
True / False
exact int 0 / 1
string true / false / 1 / 0
```

并拒绝：

```text
2 / -1
1.0 / 0.0
空字符串
其它字符串
```

### 2.3 metadata_valid 混合畸形 child

`is_record_structurally_valid()` 要求至少一个已知 child 存在，且所有实际出现的已知 child 都必须为 mapping。`pose="BROKEN" + quality={}` 已正确返回 false。

### 2.4 强制测试矩阵大部分完成

精确 yaw/pitch threshold、alias/unknown/None/数字/空串、Analyzer canonical 输出、summary keys、JSON roundtrip、Unicode 文件名、Loader ID 范围和 Packed order 均已补入自动测试。

---

## 3. 剩余阻断问题

## R4-01 — 显式 `pose.valid: null` 仍违反共享 bool-compatible 契约

**等级：P0 / BLOCKER**

`contracts.py` 明确声明 `None` 不属于 bool-compatible，并且 `parse_bool_valid(None)` 返回 false。

但 Schema 当前执行：

```python
valid_val = pose_info.get("valid")
if valid_val is not None and not is_bool_compatible(valid_val):
    ... INVALID_POSE_VALID_TYPE ...
```

这无法区分：

```text
pose.valid 字段缺失
pose.valid 字段显式为 null
```

结果是显式 JSON：

```json
{"pose": {"valid": null, "yaw_bucket": "center"}}
```

不会产生 `INVALID_POSE_VALID_TYPE`。最新 consistency 测试也专门跳过了 `None` 的 Schema 断言。

这与 Round-3 Review 要求的“Schema 与 Loader 共用同一 bool-compatible 契约，并明确拒绝 None”不一致。

### 必须修复

使用字段存在性判断：

```python
if "valid" in pose_info and not is_bool_compatible(pose_info["valid"]):
    add INVALID_POSE_VALID_TYPE
```

语义固定为：

```text
字段缺失：允许，业务读取为 false
字段存在且为 null：INVALID_POSE_VALID_TYPE，业务读取为 false
```

### 必须新增/修改测试

```text
test_schema_pose_valid_missing_is_allowed
test_schema_pose_valid_explicit_null_is_invalid
test_bool_valid_contract_schema_loader_consistency 不能跳过 None
```

---

## R4-02 — RuntimeMetadata 未实现原 Ticket 要求的完整逐样本有效性语义

**等级：P0 / ORIGINAL-CONTRACT BLOCKER**

Ticket 14 第 4 节明确要求 Loader 区分：

```text
record_matched
image_valid
landmarks_valid
pose_valid
quality_valid
metadata_valid
usable_for_pose_sampling
usable_for_quality_sampling
```

当前 `RuntimeMetadata` 只有：

```text
pose_valid
quality_valid
metadata_valid
```

缺少逐样本：

```text
record_matched
image_valid
landmarks_valid
```

并且：

- `get_record_image_valid()` 虽然被 Loader import，但主链路没有使用；
- 没有 `get_record_landmarks_valid()`；
- `KNOWN_RECORD_CHILD_KEYS` 只有 `pose/quality/image`，没有 `landmarks`；
- `matched_count` 只是聚合数字，无法区分“未匹配”和“已匹配但结构畸形”的具体样本；
- `test_loader_image_pose_quality_metadata_semantics_separated` 实际没有断言 image_valid 或 landmarks_valid，因为 RuntimeMetadata 根本没有这些数组。

因此当前实现仍无法兑现原 Ticket 的“必须区分”要求。

### 必须修复

建议 RuntimeMetadata 增加 compact bool arrays：

```text
record_matched: bool[N]
image_valid: bool[N]
landmarks_valid: bool[N]
```

并增加公共 accessor：

```text
get_record_landmarks_valid(record)
```

Loader 主链路应：

```text
sample_id 唯一命中 -> record_matched[i] = True
image_valid[i] = get_record_image_valid(rec)
landmarks_valid[i] = get_record_landmarks_valid(rec)
pose_valid / quality_valid 保持现有独立语义
metadata_valid 只表达 record matched + structure parseable
```

`is_record_structurally_valid()` 的已知 child 集合应覆盖 Analyzer 实际写出的 `landmarks`，但业务 valid=false 不应使 metadata_valid=false。

100k compact-array 测试需要纳入新增数组，并继续满足 Ticket 的轻量内存目标。

### 必须新增/修改测试

```text
test_loader_record_matched_distinguishes_unmatched_and_malformed
test_loader_image_valid_uses_nested_contract
test_loader_landmarks_valid_uses_nested_contract
test_loader_validity_arrays_are_independent
test_compact_array_memory_footprint_includes_all_contract_arrays
```

---

## 4. 非阻断观察

### 4.1 Analyzer canonical 测试仍可更严格

`test_analyzer_valid_buckets_are_canonical` 当前允许 `pose.valid=True` 时 bucket 为 `unknown`，随后只在不等于 unknown 时检查 canonical。实现目前正常，但测试最好直接要求 valid pose 的 yaw/pitch 均属于 canonical set，避免未来回归。

### 4.2 Windows 测试命令退出码问题属于 Ticket 16

Summary 记录 unittest 显示 OK，但 WeightedIndexHost daemon 在解释器退出阶段可能产生 stderr 锁告警并导致 shell exit code 非 0。该问题不作为 Ticket 14 新阻断，继续由 Ticket 16 的 Windows spawn/生命周期验收处理。

### 4.3 CI 证据仍缺失

当前 GitHub 无 Actions/status check。施工侧 `135 tests OK` 可作为本机证据，但不能描述为独立 CI 结果。

---

## 5. 最小返修范围

只修改：

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_analyzer_core.py（仅收紧 canonical 断言，可选）
Ticket 14 summary
.handoff/current.md
```

不得重新设计 canonical bucket、Policy 权重、Packed fixture，也不得进入 Ticket 15/16/17/18/20 的实现。

---

## 6. 最终通过条件

只有以下全部满足才能签发 Ticket 14 PASS：

- [ ] 显式 `pose.valid:null` 产生 `INVALID_POSE_VALID_TYPE`；
- [ ] 缺失 `pose.valid` 与显式 null 的语义有固定测试；
- [ ] RuntimeMetadata 提供逐样本 record_matched；
- [ ] RuntimeMetadata 提供逐样本 image_valid；
- [ ] RuntimeMetadata 提供逐样本 landmarks_valid；
- [ ] Loader 主链路实际填充上述 arrays；
- [ ] metadata/image/landmarks/pose/quality 语义独立测试通过；
- [ ] compact-array 内存测试包含全部契约 arrays；
- [ ] 原有 Ordinary/Packed E2E、warning、bool、order 测试继续通过；
- [ ] Summary 更新实际 Base/Head、测试输出与独立 Reviewer 状态；
- [ ] 独立 Reviewer 最终签发 `APPROVED / PASS`。

---

## 7. 后续 Ticket 状态

```text
Ticket 14：ROUND-4 / FIXES-REQUIRED / TWO-CONTRACT-GAPS-REMAIN
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：可独立并行
```
