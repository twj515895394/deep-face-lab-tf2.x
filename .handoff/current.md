# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29 23:26 +08:00  
> 当前交接：Batch 2 Ticket 14 第三轮独立 Review 与剩余返修  
> 当前状态：`REVIEW-FAILED / TICKET14-CLOSE-BUT-NOT-PASS / FIXES-REQUIRED / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 第三轮独立 Review 与剩余返修要求](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
2. [Ticket 14 当前实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第二轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round2.md)
5. [Ticket 14 第一轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review.md)
6. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
7. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
8. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)

第三轮被审返修 Commit：

```text
18e3d74091cdb179b2410486b9da5f7dca2d3ca3
```

第三轮 Review 文档提交：

```text
436dfb2105d293ce4527661fc553cd114dd567f7
```

Ticket 14 Summary 中的自审 `RESOLVED / PASS` 不能覆盖独立 Reviewer 结论。当前权威状态为：

```text
REQUEST_CHANGES
CLOSE-BUT-NOT-PASS
CORE ANALYZER→LOADER→POLICY PATH FIXED
ORDINARY AND PACKED MAIN E2E ESTABLISHED
WARNING BOUND CONTRACT STILL BROKEN
BOOL-COMPATIBLE CONTRACT INCONSISTENT
MANDATORY TICKET TEST MATRIX INCOMPLETE
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
Ticket 14：ROUND-3 / CLOSE-BUT-NOT-PASS / FIXES-REQUIRED
Metadata Sampling：NOT PRODUCTION READY
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

## 3. Ticket 14 已确认通过

```text
Canonical yaw/pitch bucket 单一契约：PASS
Analyzer canonical 输出 → Loader 固定 ID：PASS
旧 rec.get("valid", True) 默认漏洞：已移除
顶层 valid-only record：不再 metadata_valid
Analyzer bucket contract version 与 canonical lists：PASS
Ordinary 多 yaw bucket fixture：PASS
Ordinary 非均匀权重：PASS
稀缺 bucket 权重高于热门 bucket：PASS
pose_balance_strength=0 恢复等权：PASS
Ordinary empirical draw：已建立
Packed Analyzer→Loader→Policy→IndexHost→draw：已建立
uniform_mix empirical 基线：已对齐为 0.0
Legacy extreme：unknown + pose invalid + warning
Unicode 目录与 Unicode 文件名：已进入 fixture
compact-array <2MB 旧断言：已恢复
```

这些部分不得在下一轮重新设计或回退。

---

## 4. Ticket 14 剩余阻断

### 4.1 RuntimeMetadata warnings 仍未有界

Loader 会把 `val_res.issues` 逐条追加为 `SCHEMA_ISSUE`。大规模 alias 或 invalid bucket 会产生与样本数量线性增长的 warnings。

必须按 issue code 聚合，并限制 examples 和总 warning 数量。

### 4.2 bool-compatible 契约不一致

当前：

```text
Schema：所有 int 都视为 compatible
Loader：val == 1 / val == 0，并会意外接受 1.0 / 0.0
```

必须由 Schema 与 Loader 共用同一 helper，并固定 `2/-1/1.0/空串/任意字符串` 等边界行为。

### 4.3 metadata_valid 混合畸形 child

当前只要 `pose/quality/image` 任意一个是 dict，就可能 metadata_valid。`pose="BROKEN" + quality={}` 仍会通过 record-level 判定。

所有实际出现的已知 child 必须结构可解析。

### 4.4 Ticket 明文自动测试仍缺失

必须补齐：

```text
精确 yaw threshold：-0.8/-0.4/-0.15/0.15/0.4/0.8
精确 pitch threshold：-0.15/0.15
contracts alias/extreme/None/数字/空字符串/未知字符串
Analyzer valid bucket canonical set
Analyzer summary keys 精确集合
Metadata JSON roundtrip bucket 不变
Unicode filename 对应 record 精确断言
Loader valid yaw IDs 全部 0..6
Loader valid pitch IDs 全部 0..2
LOADED 不等于所有 pose valid
Packed reversed/shuffled sample order 语义不变
```

### 4.5 Packed/Ordinary 对照测试不自包含

当前对照测试依赖其他测试先生成 sidecar，只要求至少一个 common filename，没有证明全部映射一致，也没有真正改变 sample order。

### 4.6 Summary 不准确

Summary 的 `1d03494 .. HEAD`、基线 `973cc6a`、验收项 `973cc6a .. HEAD` 三处不一致。

第三轮实际返修范围：

```text
Base: 5609ddfaffa1281c9c4981367e35daeef22556b6
Head: 18e3d74091cdb179b2410486b9da5f7dca2d3ca3
```

Summary 还需补 canonical ID 表、alias 表、实际函数、distribution 数值、未完成项和独立 Reviewer 结论。

GitHub 当前没有该 Commit 的 Actions workflow run 或 status check；`195/195 PASS` 只能视为执行者本机日志摘录。

---

## 5. 当前 Ticket 依赖与 Frontier

```text
Ticket 14：ROUND-3 / FIXES-REQUIRED
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
Ticket 14 Round 3 剩余返修
Ticket 19（可由另一个独立 Agent 并行）
```

---

## 6. 下一轮 Agent 施工范围

只允许修改：

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

不得重新修改已通过的 canonical bucket 主逻辑，不得进入：

```text
Ticket 15：SRC/DST config
Ticket 16：Windows spawn
Ticket 17：workers / strong fingerprint / stale signature
Ticket 18：完整 Incremental 重构
Ticket 20：fallback exception boundary
SAEHD 网络 / Loss / optimizer / DFM / Merge / pak 格式
```

---

## 7. Agent 开工必读顺序

1. 根目录 `AGENTS.md`
2. 本 `.handoff/current.md`
3. Ticket 14 Round 3 Review
4. Ticket 14 施工规约
5. Ticket 14 当前 Summary
6. `.scratch/batch2-training-data-and-sampling/spec.md`
7. Ticket 指定的真实源码和测试
8. 所有 Blocked-by 文档

不得只把 Ticket 标题发给弱模型。

---

## 8. 执行规则

- 弱模型一次只领取一个 Ticket；
- Ticket 14 必须先于 15、16、17、18、20、21；
- Ticket 19 可独立并行；
- 测试必须走真实 Analyzer record；
- 不得用 broad fallback 吞掉核心错误；
- 不得降低断言、依赖测试执行顺序或只增加测试数量；
- 所有新增能力继续默认关闭；
- macOS 轻量测试不能代替 Windows GPU；
- 未执行 Windows 时不得写正式 Batch 2 DONE；
- 每个 Ticket 完成后必须生成同名 summary；
- Summary 自审 PASS 不能代替独立 Reviewer Gate。

---

## 9. Ticket 14 最终通过条件

```text
RuntimeMetadata schema warnings 按 code 聚合且有界
+
Schema / Loader 共用 bool-compatible 契约
+
metadata_valid 混合畸形 child 测试 PASS
+
所有 Ticket 8.1—8.5 明文自动测试完成
+
Packed 测试自包含且 sample order 语义不变
+
Summary 使用不可变 Base/Head SHA 并记录 distribution 数值
+
全量 smoke PASS 且旧测试未削弱
+
独立 Reviewer APPROVED / PASS
```

---

## 10. Batch 2 最终完成定义

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

## 11. 历史 Batch 2 入口

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

历史文档用于理解实现过程，不覆盖当前第三轮独立 Review 结论。
