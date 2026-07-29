# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29 23:55 +08:00  
> 当前交接：Batch 2 Ticket 14 Round-3 返修已落地，等待独立 Reviewer Gate  
> 当前状态：`TICKET14-IMPL-COMPLETE / AWAITING-INDEPENDENT-REVIEW / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 当前实施 Summary（Round 3 返修）](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
2. [Ticket 14 第三轮独立 Review 与剩余返修要求](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第二轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round2.md)
5. [Ticket 14 第一轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review.md)
6. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
7. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
8. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)

### Commit 锚点

```text
Round-3 开工前 Base：4ce52ce4d17f3daf64c74229564fc23bdc08e655
Round-2 被审返修：  18e3d74091cdb179b2410486b9da5f7dca2d3ca3
Round-3 Review 文档：436dfb2105d293ce4527661fc553cd114dd567f7
Round-3 实现提交：  7b482c9ced3631b7cde7dcdd3f07bff47ab28960
```

Ticket 14 Summary 中的自审 `PASS` **不能**覆盖独立 Reviewer 结论。当前权威状态：

```text
IMPLEMENTATION COMPLETE
AWAITING INDEPENDENT REVIEWER
R3-01..R3-06 ADDRESSED IN CODE AND TESTS
ORDINARY AND PACKED E2E STILL PASS
INDEPENDENT REVIEWER APPROVED/PASS NOT ISSUED
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Issue 15 Unicode / 中文路径：已完成
预览阈值 400：已完成
Merger 参数双语：已完成
模型加载 OOM / 分块 assign：已修复并验证

Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：ROUND-3 IMPL COMPLETE / AWAITING INDEPENDENT REVIEW
Metadata Sampling：NOT PRODUCTION READY（待 14 PASS + 后续 Ticket）
Windows spawn：未通过真实验收
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 REMEDIATION
```

安全判断：

```text
legacy_random：继续回归和使用
legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：可用于报告与开发验证
pose_balanced：Ticket 14—20 完成前不用于正式训练结论
quality_pose_balanced：Ticket 14—20 完成前不用于正式训练结论
```

---

## 3. Ticket 14 已确认通过（含 Round-3 关闭项）

```text
Canonical yaw/pitch bucket 单一契约：PASS
Analyzer canonical 输出 → Loader 固定 ID：PASS
旧 rec.get("valid", True) 默认漏洞：已移除
顶层 valid-only record：不再 metadata_valid
Analyzer bucket contract version 与 canonical lists：PASS
Ordinary 多 yaw bucket / 非均匀权重 / strength=0：PASS
Ordinary empirical draw：PASS
Packed Analyzer→Loader→Policy→IndexHost→draw：PASS
uniform_mix empirical 基线 0.0：PASS
Legacy extreme：unknown + pose invalid + warning
Unicode 目录与 Unicode 文件名：PASS
compact-array <2MB：PASS

Round-3 新增关闭：
RuntimeMetadata schema warnings 按 code 聚合且有界：PASS（自测）
Schema/Loader 共用 bool-compatible 契约：PASS（自测）
混合畸形 child 不误标 metadata_valid：PASS（自测）
Ticket 强制测试矩阵（threshold/alias/Analyzer/Loader/order）：PASS（自测）
Packed/Ordinary 对照自包含 + reversed/shuffled：PASS（自测）
Summary Base SHA / distribution 数值：PASS（文档）
```

这些部分不得在下一轮重新设计或回退。

---

## 4. Ticket 14 剩余阻断

```text
独立 Reviewer Round-4 Gate：未签发 APPROVED / PASS
（施工 Agent 自审不能替代）

若 Reviewer 仍 REQUEST_CHANGES：仅修新问题，不扩大范围
```

Round-3 报告中的 R3-01—R3-06 已在实现与测试中处理，详见 Summary。

---

## 5. 当前 Ticket 依赖与 Frontier

```text
Ticket 14：AWAITING-INDEPENDENT-REVIEW
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：允许另一个独立 Agent 并行
```

依赖关系：

```text
14
├── 15
├── 16
└── 17
     ↓
18

19 可独立并行

15 + 16 + 17
     ↓
20

14—20 全部完成
     ↓
21
```

当前 frontier：

```text
Ticket 14 独立 Reviewer Gate（Round 4）
Ticket 19（可由另一个独立 Agent 并行）
```

---

## 6. Round-3 实际改动范围（已落地）

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
.handoff/current.md
```

关键行为：

```text
is_bool_compatible / parse_bool_valid 单一契约
is_record_structurally_valid 收紧 metadata_valid
_aggregate_schema_issues_to_warnings 按 code 聚合
_MAX_RUNTIME_WARNINGS = 32，examples <= 5
```

不得进入：

```text
Ticket 15：SRC/DST config
Ticket 16：Windows spawn
Ticket 17：workers / strong fingerprint / stale signature
Ticket 18：完整 Incremental 重构
Ticket 20：fallback exception boundary
SAEHD 网络 / Loss / optimizer / DFM / Merge / pak 格式
```

---

## 7. 本轮测试证据（施工侧）

```text
核心 5 模块：51 tests OK
全量 test_batch2_*.py：135 tests OK
环境：Windows / Python 3.11.7（pyenv）
.venv 缺 numpy/cv2 时需用系统/pyenv 解释器
```

进程退出时 WeightedIndexHost daemon 可能触发 stderr 锁告警（exit code 非 0），unittest 结果仍为 OK。属 Ticket 16 边界，非 Ticket 14 范围。

---

## 8. Agent 开工必读顺序

1. 根目录 `AGENTS.md`
2. 本 `.handoff/current.md`
3. Ticket 14 Round-3 Summary
4. Ticket 14 Round-3 Review（对照是否还有遗漏）
5. Ticket 14 施工规约
6. 真实源码：`contracts.py` / `schema.py` / `loader.py`
7. 相关 smoke 测试

独立 Reviewer 必须重新读源码与测试，不得仅根据 Summary 自审 PASS 签发。

---

## 9. 执行规则

- 弱模型一次只领取一个 Ticket；
- Ticket 14 必须先于 15、16、17、18、20、21；
- Ticket 19 可独立并行；
- Summary 自审 PASS 不能代替独立 Reviewer Gate；
- 测试必须走真实 Analyzer record；
- 不得用 broad fallback 吞掉核心错误；
- 不得降低断言、依赖测试执行顺序或只增加测试数量；
- 所有新增能力继续默认关闭；
- macOS 轻量测试不能代替 Windows GPU；
- 未执行 Windows 时不得写正式 Batch 2 DONE。

---

## 10. Ticket 14 最终通过条件

```text
独立 Reviewer 确认 R3-01..R3-06 已关闭
+
全量 smoke PASS 且旧测试未削弱
+
APPROVED / PASS 签发
```

---

## 11. Batch 2 最终完成定义

```text
Ticket 14—20 全部 PASS
+
Analyzer → Loader → Policy E2E PASS
+
Canonical bucket PASS
+
Stale signature PASS
+
Incremental == Force Full
+
Windows spawn PASS
+
Windows FP32 + AdaBelief PASS
+
Ordinary + Packed PASS
+
四种 mode PASS
+
SRC/DST side config PASS
+
Fallback boundary PASS
+
Save / Exit / Resume PASS
+
Loss Window 离线重算一致
+
文档与 Handoff 一致
```

Windows 未执行时最多状态：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
PENDING-WINDOWS-GPU
```

---

## 12. 历史 Batch 2 入口

- [Batch 2 详细设计](handoff-20260727-batch2-detailed-design.md)
- [Ticket 01 基线](handoff-20260729-batch2-ticket01-baseline.md)
- [Ticket 02 Metadata Schema](handoff-20260729-batch2-ticket02-metadata-schema.md)
- [Ticket 03 Analyzer Core](handoff-20260729-batch2-ticket03-analyzer-core.md)
- [Ticket 04 Analyzer CLI](handoff-20260729-batch2-ticket04-analyzer-cli.md)
- [Ticket 05 Metadata Loader](handoff-20260729-batch2-ticket05-metadata-loader.md)
- [Ticket 06 Sampling Policy](handoff-20260729-batch2-ticket06-sampling-policy.md)
- [Ticket 07 Pose-balanced](handoff-20260729-batch2-ticket07-pose-balanced-sampling.md)
- [Ticket 08 Quality Weighting](handoff-20260729-batch2-ticket08-quality-aware-weighting.md)
- [Ticket 09 WeightedIndexHost](handoff-20260729-batch2-ticket09-weighted-index-host.md)
- [Ticket 10 SAEHD/Config/Fallback](handoff-20260729-batch2-ticket10-config-saehd-logging.md)
- [Ticket 11 Master Matrix](handoff-20260729-batch2-ticket11-master-matrix.md)
- [Ticket 12 Docs/Handoff](handoff-20260729-batch2-ticket12-docs-and-handoff.md)
- [Ticket 13 Loss Window](handoff-20260729-ticket13-loss-window-logging.md)
- [`--options-json` 权威参考交接](handoff-20260729-options-json-reference.md)

历史文档用于理解实现过程，不覆盖当前独立 Review 结论。
