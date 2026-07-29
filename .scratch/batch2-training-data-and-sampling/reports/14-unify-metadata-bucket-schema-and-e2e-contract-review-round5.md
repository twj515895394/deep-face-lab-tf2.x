# Ticket 14 — 第五轮独立代码 Review 与最后一次语义返修

> Review 状态：**REQUEST_CHANGES / ONE-SEMANTICS-GAP-REMAINS**  
> Review 日期：2026-07-30  
> Round-4 开工前 Base：`5fc3b9ee007ee771cfbb6ab77cc98f84bce11b7d`  
> 被审实现 Commit：`b6b0e79d6866c089deff905e00bb900a58da547f`  
> Review 方法：GitHub 最新分支静态源码与测试源码复核。Reviewer 未独立运行 Windows 测试；GitHub 当前无该提交的 Actions/status check。

---

## 1. 最终判定

```text
REQUEST_CHANGES
ONE-SEMANTICS-GAP-REMAINS
R4-01 EXPLICIT NULL POSE.VALID: CLOSED
R4-02 ARRAYS AND ACCESSORS: IMPLEMENTED
R4-02 INDEPENDENT READ SEMANTICS: NOT FULLY CLOSED
TICKET 14: VERY CLOSE, BUT NOT PASS
```

Round-4 返修是真实代码修复。以下内容已经通过静态复核：

- 显式 `pose.valid: null` 现在会产生 `INVALID_POSE_VALID_TYPE`；缺失字段仍允许；
- `KNOWN_RECORD_CHILD_KEYS` 已包含 `landmarks`；
- 已新增 `get_record_landmarks_valid()`；
- `RuntimeMetadata` 已增加 `record_matched`、`image_valid`、`landmarks_valid` compact arrays；
- neutral return 与正常 return 均返回新增 arrays；
- Loader 会在唯一 `sample_id` 命中时设置 `record_matched=True`；
- Analyzer valid pose canonical 断言已经收紧；
- 原有 warning、bool、metadata structure、Ordinary/Packed E2E 与 order 测试没有被重新设计。

但是逐样本有效性仍未完全实现“互相独立”的读取语义，因此暂不签发 `APPROVED / PASS`。

---

## 2. 已确认关闭

### 2.1 R4-01：缺失与显式 null

Schema 当前使用字段存在性判断：

```python
if "valid" in pose_info and not is_bool_compatible(pose_info["valid"]):
    add INVALID_POSE_VALID_TYPE
```

固定语义已经成立：

```text
pose.valid 缺失：允许，业务读取 false
pose.valid 显式 null：Schema issue，业务读取 false
```

相关 consistency 测试已覆盖 `None`，不再跳过 Schema 断言。

### 2.2 R4-02：数组、accessor 与结构集合

已实现：

```text
record_matched: bool[N]
image_valid: bool[N]
landmarks_valid: bool[N]
```

以及：

```text
get_record_landmarks_valid(record)
KNOWN_RECORD_CHILD_KEYS = pose / quality / image / landmarks
```

`usable_for_pose_sampling()` 与 `usable_for_quality_sampling()` 也已按 `metadata_valid & business_valid` 返回逐样本 mask。

---

## 3. 剩余阻断

## R5-01 — 结构畸形 sibling 会把可独立读取的有效性一起清零

**等级：P0 / ORIGINAL-CONTRACT BLOCKER**

当前 Loader 顺序是：

```python
record_matched[i] = True

if not is_record_structurally_valid(rec):
    metadata_valid[i] = False
    continue

metadata_valid[i] = True
image_valid[i] = get_record_image_valid(rec)
landmarks_valid[i] = get_record_landmarks_valid(rec)
# quality / pose extraction follows
```

这意味着以下记录：

```json
{
  "image": {"valid": true},
  "landmarks": {"valid": true},
  "pose": "BROKEN",
  "quality": {"quality_score": 0.8}
}
```

运行结果会是：

```text
record_matched = true
metadata_valid = false
image_valid = false       # 实际 nested image.valid 是 true
landmarks_valid = false   # 实际 nested landmarks.valid 是 true
quality_valid = false     # quality 本身可独立解析
pose_valid = false
```

这仍不符合原 Ticket 第 4 节的字段定义：

```text
image_valid：image.valid
landmarks_valid：landmarks.valid
quality_valid：quality_score finite
metadata_valid：record_matched 且整体结构可解析
```

这些数组的目的就是区分“已命中、整体结构畸形、但某个业务 child 自身仍可解析”的诊断状态。安全性由：

```text
usable_for_pose_sampling = metadata_valid & pose_valid
usable_for_quality_sampling = metadata_valid & quality_valid
```

保证，因此独立读取 image/landmarks/quality 不会让畸形记录进入采样。

### 必须修复

在唯一 record 命中后，先独立读取可安全解析的 child，再单独计算整体结构状态：

```python
record_matched[i] = True

image_valid[i] = get_record_image_valid(rec)
landmarks_valid[i] = get_record_landmarks_valid(rec)

# quality / pose accessors 都应保持异常安全并独立填充
# ...

metadata_valid[i] = is_record_structurally_valid(rec)
```

也可以先计算：

```python
record_is_structurally_valid = is_record_structurally_valid(rec)
```

但不得因一个 sibling 畸形而在读取其它安全 child 前直接 `continue`。

### 必须新增测试

新增一个混合记录测试，例如：

```text
test_loader_malformed_sibling_preserves_independent_child_flags
```

要求：

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

同时保留现有：

```text
pose="BROKEN" + quality={} -> metadata_valid=False
```

---

## 4. 测试证据状态

Summary 记录核心模块 `49 tests OK`，但没有记录完整 `test_batch2_*.py` 的 `Ran N tests / OK / shell exit code`。GitHub 也没有 Actions/status check。

本项不是新的代码设计问题，但最终 PASS 前必须补充：

```bash
python -m compileall samplelib/metadata samplelib/sampling
python -m unittest tests.smoke.test_batch2_metadata_schema
python -m unittest tests.smoke.test_batch2_metadata_loader
python -m unittest tests.smoke.test_batch2_analyzer_core
python -m unittest tests.smoke.test_batch2_metadata_sampling_e2e
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

必须记录：

```text
Python 版本
Ran N tests
OK / failures / skips
shell exit code
```

Ticket 16 所属的 daemon 退出告警可单独记录，但不得省略实际 shell exit code。

---

## 5. 最小返修范围

只修改：

```text
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_loader.py
Ticket 14 summary
.handoff/current.md
```

除非测试发现直接相关问题，否则不要再次修改：

```text
contracts.py
schema.py
canonical bucket 主逻辑
Analyzer / Packed fixture
Policy 权重公式
Ticket 15/16/17/18/20 实现
```

---

## 6. 最终 PASS 条件

只有以下全部满足才能签发 Ticket 14 PASS：

- [ ] 畸形 sibling 不再阻止其它安全 child 的独立有效性读取；
- [ ] `metadata_valid=False` 时，独立 image/landmarks/quality flags 可按各自 nested 内容保持正确；
- [ ] usable masks 继续要求 `metadata_valid & business_valid`；
- [ ] 新增混合 sibling 自动测试；
- [ ] 现有 R4-01/R4-02 测试继续通过；
- [ ] 完整 Batch 2 smoke 结果与 shell exit code 被记录；
- [ ] 独立 Reviewer 复核后签发 `APPROVED / PASS`。

---

## 7. 后续 Ticket 状态

```text
Ticket 14：ROUND-5 / ONE-MICRO-FIX / FIXES-REQUIRED
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：可独立并行
```

Ticket 14 PASS 后立即并行启动：

```text
Ticket 15：SRC/DST options-json Sampling 配置
Ticket 16：Windows spawn / WeightedIndexHost 生命周期
Ticket 17：workers / strong fingerprint / stale detection
Ticket 19：若未完成则继续
```

其中 Ticket 16 优先处理已观察到的 daemon 退出告警与非零 shell exit code。
