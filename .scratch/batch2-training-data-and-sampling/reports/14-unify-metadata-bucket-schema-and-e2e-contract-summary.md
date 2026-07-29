# Ticket 14 — 统一 Metadata Bucket Schema 与端到端契约 实施总结（Round 3 返修）

> 状态：**IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEWER**  
> 自审：`PASS`（不覆盖独立 Reviewer Gate）  
> Base Commit（Round 3 开工前 HEAD）：`4ce52ce4d17f3daf64c74229564fc23bdc08e655`  
> 被审 Round-2 返修 Commit：`18e3d74091cdb179b2410486b9da5f7dca2d3ca3`  
> Round-3 Review 文档 Commit：`436dfb2105d293ce4527661fc553cd114dd567f7`  
> Head Commit（Round 3 实现）：`7b482c9ced3631b7cde7dcdd3f07bff47ab28960`  
> 运行环境：Windows 11 / Python 3.11.7（pyenv：`C:\Users\Administrator\.pyenv\pyenv-win\versions\3.11.7\python.exe`）  
> `--options-json` 文档同步：**NA**（本轮未改训练配置参数）

---

## 1. 本轮目标

关闭 Round-3 独立 Review 剩余阻断：

| ID | 等级 | 结果 |
|---|---|---|
| R3-01 | P0 | RuntimeMetadata schema warnings 按 code 聚合且有界 |
| R3-02 | P0 | Schema / Loader 共用 bool-compatible 契约 |
| R3-03 | P1 | 混合畸形 child 不得 metadata_valid |
| R3-04 | P1 | Ticket 强制自动测试矩阵补齐 |
| R3-05 | P1 | Packed/Ordinary 对照自包含 + sample order 语义不变 |
| R3-06 | P2 | Summary 使用不可变 Base SHA、表与数值 |

已通过的 canonical bucket 主链路、Ordinary/Packed E2E 主路径 **未回退**。

---

## 2. 实际修改文件 / 函数

### 源码

| 文件 | 变更 |
|---|---|
| `samplelib/metadata/contracts.py` | 新增 `is_bool_compatible`、`is_record_structurally_valid`、`KNOWN_RECORD_CHILD_KEYS`；重写 `parse_bool_valid`（拒绝 float/其它 int） |
| `samplelib/metadata/schema.py` | `pose.valid` 类型检查改为 `is_bool_compatible` |
| `samplelib/metadata/loader.py` | `_aggregate_schema_issues_to_warnings`、`_append_bounded_warning`；metadata_valid 改用 `is_record_structurally_valid`；duplicate collision 聚合 |

### 测试

| 文件 | 变更 |
|---|---|
| `tests/smoke/test_batch2_pose.py` | 精确 threshold、alias/extreme/非法输入、canonical set |
| `tests/smoke/test_batch2_metadata_schema.py` | bool 契约 true/false/reject/consistency |
| `tests/smoke/test_batch2_metadata_loader.py` | warning 聚合/有界/100k、混合畸形、ID 范围、LOADED≠全 pose valid、语义分离 |
| `tests/smoke/test_batch2_analyzer_core.py` | canonical buckets、summary keys、roundtrip、Unicode record |
| `tests/smoke/test_batch2_metadata_sampling_e2e.py` | Packed/Ordinary 自包含 + reversed/shuffled |

### 文档

| 文件 | 变更 |
|---|---|
| 本 Summary | Round 3 返修记录 |

---

## 3. Canonical / Alias 表（冻结）

### Yaw

| ID | Canonical | Legacy aliases |
|---|---|---|
| 0 | extreme_left | — |
| 1 | major_left | left |
| 2 | minor_left | slight_left |
| 3 | center | front, pitch_center_yaw_center |
| 4 | minor_right | slight_right |
| 5 | major_right | right |
| 6 | extreme_right | — |
| -1 | unknown | extreme（无方向，不可猜 left/right） |

### Pitch

| ID | Canonical | Legacy aliases |
|---|---|---|
| 0 | up | — |
| 1 | level | center |
| 2 | down | — |
| -1 | unknown | — |

### Bool-compatible（Schema + Loader 共用）

允许：`True` / `False` / 整型 `0` / `1` / 字符串 `true|false|1|0`（忽略大小写与两端空白）  
拒绝：`2`、`-1`、`1.0`、`0.0`、空串、其它字符串、`None`（`None` 不产生 INVALID_POSE_VALID_TYPE，解析为 False）

### metadata_valid 结构规则

至少存在一个已知 child（`pose` / `quality` / `image`），且**所有出现的已知 child 均为 mapping**。  
`pose="BROKEN" + quality={}` → `metadata_valid=False`。

---

## 4. Distribution 数值（Ordinary fixture 实测）

命令（本机）：

```text
PoseBalancedPolicy strength=0.8 uniform_mix=0.0 seed=42
```

| 指标 | 数值 |
|---|---|
| unique valid yaw IDs | `[2, 3, 4]`（minor_left / center / minor_right） |
| bucket_counts | `[0, 0, 2, 6, 2, 0, 0]` |
| bucket_weights | `[1.0, 1.0, 1.0, 0.5, 1.0, 1.0, 1.0]` |
| expected_distribution | `[0.0, 0.0, 0.2857143, 0.4285715, 0.2857143, 0.0, 0.0]` |

稀缺桶（count=2）每样本权重 1.0 > 热门桶（count=6）每样本权重 0.5。

---

## 5. Round 3 验收勾选

- [x] RuntimeMetadata schema warnings 按 code 聚合且总数有上限（`_MAX_RUNTIME_WARNINGS=32`，examples≤5）
- [x] Schema 与 Loader 共用同一 bool-compatible 契约
- [x] `2/-1/1.0/空字符串` 等边界固定测试
- [x] 混合畸形 child 不误标 metadata_valid
- [x] 精确 yaw/pitch threshold 边界测试
- [x] contracts alias/unknown/None/数字/空串测试
- [x] Analyzer canonical set、summary keys、roundtrip、Unicode record 测试
- [x] Loader yaw/pitch ID 范围与 LOADED 非全-valid 测试
- [x] Packed 测试自包含
- [x] Packed reversed/shuffled sample-order 语义不变
- [x] Summary 使用完整不可变 Base SHA 与 distribution 数值
- [x] 相关 smoke 通过且旧断言未削弱
- [ ] **独立 Reviewer APPROVED / PASS**（施工 Agent 不可自签）

---

## 6. 测试证据

### 相关模块（Ticket 14 核心）

```text
python -m unittest tests.smoke.test_batch2_pose \
  tests.smoke.test_batch2_metadata_schema \
  tests.smoke.test_batch2_analyzer_core \
  tests.smoke.test_batch2_metadata_loader \
  tests.smoke.test_batch2_metadata_sampling_e2e -v

Ran 51 tests in 7.395s
OK
```

### 全量 Batch2 smoke

```text
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"

Ran 135 tests in 18.954s
OK
```

说明：进程退出时 WeightedIndexHost daemon 线程可能在 interpreter finalizing 阶段触发 stderr 锁告警，导致 shell exit code 非 0；**unittest 结果为 OK，断言全部通过**。此线程关闭问题不在 Ticket 14 范围（Ticket 16/20 边界）。

环境：本机 `.venv` 未装 numpy/cv2；使用 pyenv 3.11.7 全局 site-packages 执行。

---

## 7. 未完成 / 明确不在本轮

| 项 | 状态 |
|---|---|
| 独立 Reviewer 最终 PASS | 待签发 |
| Ticket 15 SRC/DST options-json | BLOCKED-BY-14 / 未做 |
| Ticket 16 Windows spawn | BLOCKED-BY-14 / 未做 |
| Ticket 17 workers / fingerprint / stale | 未做 |
| Ticket 18 Incremental summary 旧字段（CLI 复用路径仍可能打印旧 yaw 名） | 未做（属 18） |
| Windows GPU 正式验收 | PENDING |
| 施工 Agent 不得自行将 Ticket 14 标为独立 PASS | 遵守 |

---

## 8. Legacy 回归与 Unicode

- compact array `<2MB` 断言保留
- `extreme` → unknown + pose_valid=False + warning 保留
- top-level `valid` only → metadata_valid=False 保留
- string `"false"` 不视为 True 保留
- Unicode 目录 / `00005_中文文件名_dark.jpg` 进入 Analyzer 精确断言

---

## 9. 下一 Ticket 可依赖接口

```text
samplelib.metadata.contracts
  YAW_BUCKET_NAMES / PITCH_BUCKET_NAMES
  YAW_BUCKET_NAME_TO_ID / PITCH_BUCKET_NAME_TO_ID
  UNKNOWN_BUCKET_ID
  LEGACY_YAW_ALIASES / LEGACY_PITCH_ALIASES
  is_bool_compatible / parse_bool_valid
  is_record_structurally_valid
  normalize_* / get_*_bucket_id / get_record_*

samplelib.metadata.loader
  FacesetMetadataLoader.load → RuntimeMetadata
  warnings 有界、按 code 聚合
```

---

## 10. 结论

Round-3 实现与强制测试矩阵已在施工范围内闭环。  
**最终状态以独立 Reviewer 报告为准**：当前 Summary 自审为 PASS，**不得**替代 `APPROVED / PASS`。
