# Ticket 14 — 统一 Metadata Bucket Schema 与端到端契约 实施总结（Round 4 返修）

> 状态：**IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEWER**  
> 自审：`PASS`（不覆盖独立 Reviewer Gate）  
> Base Commit（Round 4 开工前 HEAD）：`5fc3b9ee007ee771cfbb6ab77cc98f84bce11b7d`  
> Round-4 被审实现（R3 落地）：`7b482c9ced3631b7cde7dcdd3f07bff47ab28960`  
> Round-4 Review 文档：`420f15bd61d1fc76f607fb15720440f260699111`  
> Head Commit（Round 4 实现）：`b6b0e79d6866c089deff905e00bb900a58da547f`  
> 运行环境：Windows 11 / Python 3.11.7（pyenv）  
> `--options-json` 文档同步：**NA**

---

## 1. 本轮目标

关闭 Round-4 独立 Review 剩余阻断：

| ID | 等级 | 结果 |
|---|---|---|
| R4-01 | P0 | 显式 `pose.valid: null` → `INVALID_POSE_VALID_TYPE`；缺失字段允许 |
| R4-02 | P0 | RuntimeMetadata 逐样本 `record_matched` / `image_valid` / `landmarks_valid` |

R3 已关闭项未回退。

---

## 2. 实际修改

### 源码

| 文件 | 变更 |
|---|---|
| `samplelib/metadata/contracts.py` | `KNOWN_RECORD_CHILD_KEYS` 含 `landmarks`；新增 `get_record_landmarks_valid` |
| `samplelib/metadata/schema.py` | `"valid" in pose_info and not is_bool_compatible(...)` |
| `samplelib/metadata/loader.py` | `record_matched` / `image_valid` / `landmarks_valid` 数组与主链路填充；`usable_for_pose/quality_sampling` helper |

### 测试

| 文件 | 变更 |
|---|---|
| `test_batch2_metadata_schema.py` | missing vs explicit null；consistency 不再跳过 None |
| `test_batch2_metadata_loader.py` | R4 强制测试 + 全契约数组内存 |
| `test_batch2_analyzer_core.py` | valid pose 必须严格 canonical |

---

## 3. 契约语义（冻结）

### pose.valid

| 情况 | Schema | 业务读取 |
|---|---|---|
| 字段缺失 | 允许 | false |
| 字段存在且 null | `INVALID_POSE_VALID_TYPE` | false |
| True/False/0/1/"true"/... | 允许 | 按 parse_bool_valid |
| 2/-1/1.0/空串/其它 | `INVALID_POSE_VALID_TYPE` | false |

### 逐样本有效性

| 数组 | 含义 |
|---|---|
| `record_matched` | sample_id 唯一命中 sidecar（结构畸形也算 matched） |
| `metadata_valid` | matched 且结构可解析（已知 child 均为 mapping） |
| `image_valid` | nested `image.valid` bool-compatible true |
| `landmarks_valid` | nested `landmarks.valid` bool-compatible true |
| `pose_valid` | pose.valid 且 yaw bucket 可识别 |
| `quality_valid` | quality_score 存在且 finite |

`usable_for_pose_sampling` = `metadata_valid & pose_valid`  
`usable_for_quality_sampling` = `metadata_valid & quality_valid`

### Canonical / Alias

与 Round 3 相同（7 yaw / 3 pitch；legacy alias 表不变）。

---

## 4. Round 4 验收勾选

- [x] 显式 `pose.valid:null` 产生 `INVALID_POSE_VALID_TYPE`
- [x] 缺失 `pose.valid` 与显式 null 有固定测试
- [x] RuntimeMetadata 提供 `record_matched` / `image_valid` / `landmarks_valid`
- [x] Loader 主链路实际填充
- [x] metadata/image/landmarks/pose/quality 语义独立测试
- [x] compact-array 含全部契约 arrays
- [x] Ordinary/Packed E2E、warning、bool、order 回归
- [x] Summary Base SHA 与实现说明
- [ ] **独立 Reviewer APPROVED / PASS**

---

## 5. 测试证据

```text
核心模块（schema/loader/analyzer/e2e）：49 tests OK (~7.7s)
```

全量 `test_batch2_*.py` 见本轮命令输出（施工本机；非 GitHub Actions CI）。

---

## 6. 未完成

| 项 | 状态 |
|---|---|
| 独立 Reviewer 最终 PASS | 待签发 |
| Ticket 15–18 / 20–21 | BLOCKED-BY-14 |
| Windows GPU / spawn | PENDING（Ticket 16/21） |

---

## 7. 结论

Round-4 两个契约缺口已在允许范围内闭环。  
**最终状态以独立 Reviewer 报告为准。**
