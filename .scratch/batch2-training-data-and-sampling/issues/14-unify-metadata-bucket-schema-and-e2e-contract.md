# Ticket 14 — 统一 Metadata Bucket Schema 与 Analyzer→Loader→Policy 端到端契约

> 状态：OPEN / P0 BLOCKER  
> 优先级：最高  
> 可否并行：不得与 Ticket 15 同一 Agent 并行施工  
> Blocked by：无  
> Blocks：15、16、17、18、20、21  
> 强制 Reviewer：完成后必须由独立强模型或人工 Review

---

## 1. 问题背景

当前 Analyzer 输出的姿态桶名称与 Loader 识别的名称不一致。

Analyzer yaw：

```text
extreme_left
major_left
minor_left
center
minor_right
major_right
extreme_right
```

Loader yaw：

```text
pitch_center_yaw_center
front
slight_left
slight_right
left
right
extreme
```

Analyzer pitch：

```text
up
level
down
```

Loader pitch：

```text
up
center
down
```

结果是 Sidecar 可以显示 `LOADED`，但 `yaw_bucket_ids` 可能全为 `-1`、`pose_valid` 全为 `False`，`pose_balanced` 静默退化。

本 Ticket 必须先修复统一数据契约，再允许后续配置、多进程和 GPU 验收继续。

---

## 2. 开工前必读

必须读取：

1. `AGENTS.md`
2. `.handoff/current.md`
3. `.scratch/batch2-training-data-and-sampling/spec.md`
4. `.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md`
5. `.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md`
6. `samplelib/metadata/pose.py`
7. `samplelib/metadata/analyzer.py`
8. `samplelib/metadata/schema.py`
9. `samplelib/metadata/loader.py`
10. `samplelib/metadata/incremental.py`
11. `samplelib/metadata/report.py`
12. `samplelib/sampling/policies.py`
13. `samplelib/sampling/weights.py`
14. 相关 tests

开工前必须输出源码事实复核，记录所有现有 bucket 字符串和读取路径。

---

## 3. 固定设计决策

### 3.1 Canonical yaw buckets

正式 canonical 顺序固定为：

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
```

ID 固定：

```text
0 extreme_left
1 major_left
2 minor_left
3 center
4 minor_right
5 major_right
6 extreme_right
```

### 3.2 Canonical pitch buckets

```python
PITCH_BUCKET_NAMES = (
    "up",
    "level",
    "down",
)
```

ID 固定：

```text
0 up
1 level
2 down
```

### 3.3 公共定义位置

新增单一公共模块，推荐：

```text
samplelib/metadata/contracts.py
```

不得在 Analyzer、Loader、Incremental、Tests 中重复手写映射。

公共模块至少提供：

```python
YAW_BUCKET_NAMES
PITCH_BUCKET_NAMES
YAW_BUCKET_NAME_TO_ID
PITCH_BUCKET_NAME_TO_ID
UNKNOWN_BUCKET_ID
normalize_yaw_bucket_name(name)
normalize_pitch_bucket_name(name)
is_valid_yaw_bucket(name)
is_valid_pitch_bucket(name)
```

### 3.4 兼容别名

允许只读兼容旧 Sidecar：

```text
front -> center
pitch_center_yaw_center -> center
slight_left -> minor_left
slight_right -> minor_right
left -> major_left
right -> major_right
center(pitch) -> level
```

旧 `extreme` 无方向信息，不得猜测为 left 或 right，应：

- 返回 unknown；
- 添加 warning；
- `pose_valid=False`；
- 不抛出为核心崩溃。

Analyzer 新写入文件只能输出 canonical 名称。

---

## 4. 样本记录有效性契约

Loader 不得继续使用：

```python
rec.get("valid", True)
```

作为全部 Metadata 有效性的默认依据。

必须区分：

```text
record_matched：sample_id 与 signature 匹配
image_valid：image.valid
landmarks_valid：landmarks.valid
pose_valid：pose.valid 且 bucket 可识别
quality_valid：quality_score 存在且 finite
metadata_valid：record_matched 且结构可解析
usable_for_pose_sampling：metadata_valid 且 pose_valid
usable_for_quality_sampling：metadata_valid 且 quality_valid
```

Ticket 14 只建立结构和读取 helper；逐样本 signature 的严格 stale 判断在 Ticket 17 完成。

推荐增加公共 accessor：

```python
get_record_image_valid(record)
get_record_pose_valid(record)
get_record_quality_valid(record)
get_record_yaw_bucket(record)
get_record_pitch_bucket(record)
```

Incremental 和 Report 后续必须复用，禁止再次写第二套字段解释。

---

## 5. 允许修改文件

主要允许：

```text
samplelib/metadata/contracts.py
samplelib/metadata/pose.py
samplelib/metadata/analyzer.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
samplelib/metadata/incremental.py（仅调用公共 accessor，不做完整 Ticket 18）
samplelib/metadata/report.py（仅 canonical 名称）
tests/smoke/test_batch2_pose.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_analyzer_core.py
新增端到端测试文件
```

---

## 6. 禁止范围

本 Ticket 不得：

- 修改 SAEHD 网络或 Loss；
- 修改 Sampling 配置形状；
- 修复 Windows spawn；
- 实现 workers；
- 实现 strong fingerprint；
- 重构全部 Incremental；
- 修改 `faceset.pak`；
- 用 broad `except Exception` 隐藏 bucket 错误；
- 为通过测试把所有 bucket 强制映射成 center；
- 删除 unknown 样本；
- 将 invalid pose 误标为 valid。

---

## 7. 施工步骤

### Step 1：冻结现状

新增失败测试，证明当前真实 Analyzer 输出进入 Loader 后：

- 至少存在 canonical bucket 字符串；
- 当前 Loader 不能识别；
- 测试在修复前必须失败。

不得先改实现后再补一个永远通过的测试。

### Step 2：建立公共 constants/contracts

- 定义 canonical 顺序；
- 定义 id 映射；
- 定义 alias；
- 输入非字符串、空字符串、未知字符串返回 unknown；
- 不产生 NaN/Inf；
- API 具有类型注解。

### Step 3：修改 pose.py

- `assign_yaw_bucket()` 只能返回 canonical yaw；
- `assign_pitch_bucket()` 只能返回 canonical pitch；
- thresholds 与 bucket 数量校验；
- 非有限 angle 必须由上层标 invalid；
- 不改变现有角度估计算法。

### Step 4：修改 Analyzer

- 新 Metadata 只写 canonical；
- analysis config 中记录 bucket contract/version；
- summary bucket keys 使用 canonical 完整集合，即使 count=0 也保留；
- unknown 单独统计，不混入 center。

### Step 5：修改 Loader

- 从公共模块导入映射；
- alias 只用于读取旧 Metadata；
- canonical bucket 映射为固定 ID；
- unknown 保持 `-1`；
- pose valid 只有在 `pose.valid=True` 且 yaw bucket 可识别时为 true；
- pitch unknown 不应破坏 yaw 可用性，但必须记录 pitch warning；
- warnings 不得逐样本无限增长，超过阈值应汇总。

### Step 6：修改 Schema validation

Schema validation 至少检查：

- `pose` 是 mapping；
- pose.valid 为 bool-compatible；
- valid pose 的 yaw/pitch bucket 是否 canonical 或兼容 alias；
- 非 canonical 新写文件应产生 issue；
- 不支持的字符串不得静默视为 valid；
- duplicate sample ID 规则保持。

### Step 7：真实端到端测试

新增：

```text
tests/smoke/test_batch2_metadata_sampling_e2e.py
```

真实流程：

```text
build_ordinary_fixture
→ FacesetAnalyzer.analyze
→ write_metadata_atomic / dump_json
→ FacesetMetadataLoader.load
→ PoseBalancedPolicy.build_weights
→ build_index_host
→ draw
```

不得手工拼 Metadata record 替代 Analyzer 输出。

---

## 8. 必须新增的自动测试

### 8.1 Bucket unit tests

- 每个 threshold 边界；
- 左右方向不反转；
- 7 个 yaw 名称完整；
- 3 个 pitch 名称完整；
- alias 正常；
- `extreme` 旧值进入 unknown；
- None、数字、空字符串进入 unknown。

### 8.2 Analyzer output tests

- 所有 valid pose bucket 属于 canonical set；
- summary keys 与 canonical set 完全一致；
- Metadata JSON roundtrip 后名称不变；
- Unicode 文件名不影响 bucket。

### 8.3 Loader tests

- Analyzer 输出后 `pose_valid.any() == True`；
- valid yaw IDs 均在 0..6；
- valid pitch IDs 均在 0..2；
- 不能只断言数组长度；
- alias Sidecar 可读并产生 warning；
- unknown 不误标 valid；
- metadata status LOADED 不自动意味着 pose 全部 valid。

### 8.4 Policy tests

构造姿态分布明显不均衡的真实 Fixture，断言：

- `sample_weights` 不是全 1；
- probabilities finite；
- probabilities > 0；
- sum 约等于 1；
- 稀缺 bucket 单样本权重高于热门 bucket；
- `pose_balance_strength=0` 恢复等权；
- empirical draws 与 expected distribution 在容差内。

### 8.5 Packed tests

- Packed Analyzer 输出可被 Loader 识别；
- bucket contract 与 Ordinary 相同；
- sample order 不改变 bucket ID 语义。

---

## 9. 测试命令

macOS 必须使用：

```bash
./.venv/bin/python -m compileall samplelib/metadata samplelib/sampling
./.venv/bin/python -m unittest tests.smoke.test_batch2_pose
./.venv/bin/python -m unittest tests.smoke.test_batch2_metadata_loader
./.venv/bin/python -m unittest tests.smoke.test_batch2_metadata_sampling_e2e
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

测试失败不得通过降低断言、移除真实 Analyzer 或改用手工 record 解决。

---

## 10. 验收标准

### 自动验收

- [ ] 公共 bucket contract 只有一处定义；
- [ ] Analyzer 只输出 canonical；
- [ ] Loader 可识别 Analyzer 输出；
- [ ] `pose_valid` 非全 false；
- [ ] yaw IDs 非全 unknown；
- [ ] Policy probabilities 非均匀；
- [ ] Ordinary E2E PASS；
- [ ] Packed E2E PASS；
- [ ] legacy tests 不受影响；
- [ ] Unicode tests PASS；
- [ ] 全量 Batch 测试 PASS。

### 人工验收

从真实或 synthetic Metadata 随机抽查至少 10 条：

- 左侧 bucket 方向正确；
- 右侧 bucket 方向正确；
- center 不吞并 extreme；
- pitch 使用 level；
- Analyzer report 与 sample record 一致。

### 完成判定

仅满足以下情况才能 `RESOLVED`：

```text
真实 Analyzer → Loader → Policy 测试通过
AND
Reviewer 确认不是手工 Schema 测试
AND
概率分布有实际变化
```

仅 `LOADED`、compileall、测试数量增加，不算完成。

---

## 11. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
14-unify-metadata-bucket-schema-and-e2e-contract-summary.md
```

必须记录：

- 修改前后 commit；
- canonical 名称和 ID；
- alias 列表；
- 实际修改函数；
- E2E 测试数据流；
- 概率分布前后对比；
- Ordinary/Packed 状态；
- Unicode 状态；
- 全量测试输出；
- 未完成项；
- Reviewer 结论。