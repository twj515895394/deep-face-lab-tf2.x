# Ticket 14 — 统一 Metadata Bucket Schema 与端到端契约 最终实施总结

> 状态：**IMPLEMENTATION COMPLETE / INDEPENDENT REVIEW APPROVED / PASS / CLOSED**  
> Base Commit（Round 5 开工前）：`e8d0a0b07ea13bfc1d321c168ba9f8f5c7e9579a`  
> 最终实现 Commit：`37e99255e195d73dbd3720858ec1a93b4c8619cc`  
> 最终独立 Review：`14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md`  
> Final Review Commit：`94f57f9ec9c488d140eb37fbe0ba03fa26f1b020`  
> 运行环境：Windows 11 / Python 3.11.7（施工侧）  
> `--options-json` 文档同步：**NA**（由 Ticket 15 处理）

---

## 1. 最终结论

```text
Ticket 14：APPROVED / PASS / CLOSED
Canonical Metadata Bucket Contract：CLOSED
Analyzer → Loader → Policy E2E：CLOSED
Per-sample Validity Contract：CLOSED
```

Ticket 14 的五轮返修与第六轮独立 Review 已完成。施工自审 PASS 现已由独立 Reviewer 正式确认。

本结论不表示 Batch 2 已完成；Ticket 15—21 和 Windows GPU 验收仍未关闭。

---

## 2. 最终冻结契约

### 2.1 Canonical Yaw

| ID | Canonical | Legacy aliases |
|---|---|---|
| 0 | extreme_left | — |
| 1 | major_left | left |
| 2 | minor_left | slight_left |
| 3 | center | front, pitch_center_yaw_center |
| 4 | minor_right | slight_right |
| 5 | major_right | right |
| 6 | extreme_right | — |
| -1 | unknown | extreme（无方向，不猜测） |

### 2.2 Canonical Pitch

| ID | Canonical | Legacy aliases |
|---|---|---|
| 0 | up | — |
| 1 | level | center |
| 2 | down | — |
| -1 | unknown | — |

### 2.3 Bool-compatible

允许：

```text
True / False
exact int 0 / 1
string true / false / 1 / 0（忽略大小写和两端空白）
```

拒绝：

```text
其它整数、float、空字符串、其它字符串、None
```

`pose.valid` 字段缺失允许并读取为 false；字段存在且显式为 null 时产生 `INVALID_POSE_VALID_TYPE`。

### 2.4 逐样本有效性

| 数组 | 含义 |
|---|---|
| `record_matched` | sample_id 唯一命中 sidecar；结构畸形仍算 matched |
| `metadata_valid` | record matched 且已知 child 结构可解析 |
| `image_valid` | nested `image.valid`，不依赖其它 sibling |
| `landmarks_valid` | nested `landmarks.valid`，不依赖其它 sibling |
| `pose_valid` | pose.valid 且 yaw bucket 可识别 |
| `quality_valid` | quality_score 存在且 finite |

采样可用性：

```text
usable_for_pose_sampling = metadata_valid & pose_valid
usable_for_quality_sampling = metadata_valid & quality_valid
```

---

## 3. 最后缺口 R5-01

最新 Loader 在唯一 record 命中后：

```text
先读取 image / landmarks / quality / pose 独立 flags
再单独计算 metadata_valid
```

因此畸形 `pose` sibling 不会再把可安全读取的 image、landmarks、quality flags 清零；同时 usable masks 仍因 `metadata_valid=False` 而保持 false。

对应自动测试：

```text
test_loader_malformed_sibling_preserves_independent_child_flags
```

---

## 4. 最终验收结果

- [x] 7 yaw / 3 pitch canonical buckets 与固定 IDs
- [x] legacy alias 只读兼容
- [x] Analyzer 只写 canonical 名称
- [x] Schema / Loader 共用 bool-compatible 契约
- [x] 显式 null 与缺失 valid 字段语义固定
- [x] Runtime warning 按 code 聚合且总数有界
- [x] record/image/landmarks/pose/quality/metadata validity 语义分离
- [x] 畸形 sibling 保留其它安全 child flags
- [x] Ordinary 完整 E2E
- [x] Packed 完整 E2E
- [x] 非均匀权重与 empirical distribution
- [x] strength=0 等权
- [x] probabilities finite / positive / sum=1
- [x] reversed / shuffled order 语义不变
- [x] JSON roundtrip
- [x] Unicode 路径与文件名
- [x] 100k warning 与 compact-array 边界
- [x] 独立 Reviewer APPROVED / PASS

---

## 5. 测试证据

施工侧记录：

```text
Python 3.11.7
compileall samplelib/metadata samplelib/sampling
exit code: 0

核心 schema/loader/analyzer/e2e
Ran 50 tests
OK
shell exit code: 0

新增 R5-01 单测
Ran 1 test
OK
shell exit code: 0

全量 test_batch2_*.py
Ran 143 tests
OK（无 failures / errors）
shell exit code: -1073740791
```

全量命令的非零退出发生于 unittest 报告 OK 后的解释器关闭阶段，关联 daemon host thread / stderr 锁，已转入 Ticket 16。GitHub 当前无 Actions/status check，因此不得描述为 CI PASS。

---

## 6. 后续可依赖接口

```text
samplelib.metadata.contracts
  canonical bucket 常量与 ID
  legacy alias
  bool-compatible helpers
  record validity accessors

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

Ticket 15—21 禁止重新维护第二套 bucket、bool 或 record validity 解释。

---

## 7. 解锁状态

```text
Ticket 14：PASS / CLOSED
Ticket 15：UNBLOCKED / OPEN
Ticket 16：UNBLOCKED / OPEN / HIGH RISK
Ticket 17：UNBLOCKED / OPEN
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT
Ticket 20：BLOCKED-BY-15+16+17
Ticket 21：BLOCKED-BY-14—20
```

Batch 2 仍为：

```text
REMEDIATION IN PROGRESS
METADATA SAMPLING NOT PRODUCTION READY
PENDING WINDOWS SPAWN
PENDING WINDOWS GPU
```
