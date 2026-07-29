# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29 23:14 +08:00  
> 当前交接：Batch 2 Ticket 14 第二轮独立 Review 与剩余返修  
> 当前状态：REVIEW-FAILED / TICKET14-NEAR-PASS / FIXES-REQUIRED / PENDING-WINDOWS-GPU

---

## 1. 最新交接

必须先阅读：

1. [Ticket 14 第二轮独立 Review 与剩余返修要求](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round2.md)
2. [Ticket 14 第一轮独立 Review 与返修要求](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review.md)
3. [Ticket 14 当前实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
4. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
5. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
6. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
7. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)

第二轮独立 Review 提交：

```text
973cc6a95e558e18633184066c8d3cf2a4a7f020
```

Ticket 14 Summary 中的自审 `RESOLVED / PASS` 不能覆盖独立 Reviewer 结论。当前权威状态以第二轮独立 Review 为准：

```text
REQUEST_CHANGES
NEAR-PASS
CORE BUCKET MISMATCH FIXED
ORDINARY SAMPLING EFFECT PROVEN
SCHEMA CONTRACT NOT CLOSED
PACKED FULL E2E NOT PROVEN
```

此前的综合 Review 报告和 Ticket 01—13 summary 仍保留为历史证据，但不能再单独作为“Batch 2 已完成”的依据。

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Issue 15 Unicode / 中文路径：已完成
预览阈值 400：已完成
Merger 参数双语：已完成
模型加载 OOM / 分块 assign：已修复并验证

Batch 2 Ticket 01—13：已有实现与轻量测试
Batch 2 独立 Review：FAIL，发现 P0/P1 契约与多进程问题
Ticket 14：ROUND-2 / NEAR-PASS / FIXES-REQUIRED
Metadata Sampling：NOT PRODUCTION READY
Windows spawn：未通过真实验收
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 REMEDIATION
```

### 2.1 Ticket 14 已确认通过

```text
Canonical yaw/pitch bucket 单一契约：PASS
Analyzer canonical 输出 → Loader 固定 ID：PASS
旧 rec.get("valid", True) 默认漏洞：已移除
Analyzer bucket contract version 与 canonical lists：PASS
Ordinary 多 yaw bucket fixture：PASS
Ordinary 非均匀权重：PASS
稀缺 bucket 权重高于热门 bucket：PASS
pose_balance_strength=0 恢复等权：PASS
Ordinary WeightedIndexHost 经验抽样：已建立
Legacy alias / unknown 聚合 warning：已建立
Unicode 目录与 Unicode 文件名：已进入 fixture
Report 旧顶层 valid 读取：已移除
```

### 2.2 Ticket 14 剩余阻断

```text
Schema pose mapping 校验：未完成
Schema pose.valid 类型校验：未完成
Schema legacy alias issue 契约：未完成
Loader metadata_valid 结构边界：仍需收紧
Packed 至少两个有效 yaw bucket：未证明
Packed probabilities → IndexHost → draw：未完成
Packed empirical distribution：未完成
Ordinary empirical test 的 uniform_mix：理论与实际配置需对齐
compact array memory footprint 旧断言：需恢复
legacy extreme → unknown / pose_valid=False 明确断言：需恢复
warning examples <= 5 的真实断言：需补强
不可变 before/after commit 与可复核测试证据：需补齐
独立 Reviewer 最终 PASS：未签发
```

### 2.3 安全判断

```text
legacy_random：继续回归和使用
legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：可用于报告与开发验证
pose_balanced：Ticket 14—21 最终验收前不用于正式训练结论
quality_pose_balanced：Ticket 14—21 最终验收前不用于正式训练结论
```

---

## 3. Batch 2 独立 Review 发现

### 3.1 原始 P0 阻断

1. Analyzer 与 Loader 的 yaw/pitch bucket 名称不一致；
2. 旧使用指南的 options JSON 缺少顶层 `enhancements`；
3. 旧示例没有同时开启 `training.enabled` 和 `metadata_sampling`；
4. 文档宣称 `sampling.src/dst`，代码只解析扁平全局配置；
5. WeightedIndexHostClient 在 Windows spawn 下存在 `_host_ref` 序列化风险。

其中第 1 项的 canonical 名称断裂已经由 Ticket 14 主体返修关闭，但 Ticket 14 的 Schema 与 Packed 完整验收仍未闭环，因此 Ticket 14 尚未通过。

### 3.2 P1 高优先级

1. `--workers` 参数未实际使用；
2. `--strong-fingerprint` 参数未实际使用；
3. 同名替换图片可能继续使用旧 Metadata；
4. Incremental summary 使用旧顶层字段；
5. Loss Window 多包含保存后一个 batch；
6. Optional fallback 可能吞掉 SampleLoader 核心异常。

---

## 4. 修复 Ticket 入口

按弱模型施工标准新增：

1. [Ticket 14：统一 Metadata Bucket Schema 与端到端契约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
   - [实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
   - [第一轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review.md)
   - [第二轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round2.md)
2. [Ticket 15：修复 options-json 与 SRC/DST Sampling 配置](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
3. [Ticket 16：修复 WeightedIndexHost Windows spawn](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
4. [Ticket 17：实现 Analyzer Workers、强指纹与 stale detection](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
5. [Ticket 18：修复 Incremental Summary 与 Report Schema](../.scratch/batch2-training-data-and-sampling/issues/18-fix-incremental-summary-and-report-schema.md)
6. [Ticket 19：修复 Loss Window 保存边界](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)
7. [Ticket 20：收窄 Fallback 异常边界](../.scratch/batch2-training-data-and-sampling/issues/20-narrow-fallback-exception-boundaries.md)
8. [Ticket 21：文档、Handoff 与 Windows GPU 最终验收](../.scratch/batch2-training-data-and-sampling/issues/21-docs-handoff-windows-gpu-final-acceptance.md)

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
Ticket 14：第二轮剩余返修
  ├── Schema contract
  ├── Loader metadata_valid 结构边界
  ├── Packed full E2E
  ├── uniform_mix 测试一致性
  └── 恢复并补强旧测试断言

Ticket 19：允许另一个独立 Agent 并行

Ticket 15 / 16 / 17 / 18 / 20 / 21：BLOCKED-BY-14
```

---

## 5. Ticket 14 下一轮施工边界

下一轮只修复第二轮 Review 的剩余项，不得重新改动已经通过的 canonical bucket 主逻辑。

允许修改：

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
samplelib/metadata/report.py（仅必要契约读取）
tests/fixtures/batch2/build_synthetic_fixture.py
tests/smoke/test_batch2_pose.py
tests/smoke/test_batch2_analyzer_core.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_metadata_sampling_e2e.py
Ticket 14 summary
```

必须完成：

```text
1. Schema 对 pose 非 mapping 产生 INVALID_POSE_MAPPING
2. Schema 对 pose.valid 非 bool 产生 INVALID_POSE_VALID_TYPE
3. Schema 区分 canonical、legacy alias 和 unknown
4. Loader 不得由旧顶层 valid 单独证明 metadata_valid
5. Packed 执行 Analyzer → JSON → Loader → Policy → probabilities → IndexHost → draw
6. Packed 证明至少两个有效 yaw bucket 和非均匀权重
7. empirical expected distribution 与实际 uniform_mix 配置一致
8. 恢复 compact memory footprint 断言
9. 恢复 extreme → unknown / pose_valid=False 断言
10. warning bounded 测试真实验证 examples <= 5
11. Summary 记录完整、不可变 before/after commit SHA
12. 独立 Reviewer 重新签发 APPROVED / PASS
```

不得：

- 为通过测试把所有 bucket 强制映射为 center；
- 用手工最终 Metadata 替代 Analyzer E2E；
- 削弱或删除旧断言；
- 顺手进入 Ticket 15、16、17、18、20；
- 由施工 Agent 自己把 Ticket 14 标记为最终独立 PASS。

---

## 6. Faceset Analyzer 使用结论

Faceset Analyzer 不是所有训练都必须执行，也不等同于 XSeg。

只有启用：

```text
pose_balanced
quality_pose_balanced
```

才需要先分析 faceset。

SRC 和 DST 需要分别分析，但同一个 aligned faceset 被多个模型复用时不需要重复分析。faceset 新增、删除、替换、重新 Extract/Align 或重新 Pack 后需要更新 Metadata。

当前修复完成前：

- Analyzer 可以生成 Metadata 和报告；
- 不得仅凭 `effective: pose_balanced` 判断真实姿态采样生效；
- Ordinary 测试证明不等于 Packed 与 Windows 正式验收完成；
- 正式训练继续使用 legacy。

---

## 7. Agent 开工必读顺序

任何 Agent 领取 Ticket 14—21 前必须依次阅读：

1. 根目录 `AGENTS.md`
2. 本 `.handoff/current.md`
3. 最新 handoff
4. `.scratch/batch2-training-data-and-sampling/spec.md`
5. 独立 Review 总计划
6. 当前 Ticket
7. 当前 Ticket 已有 summary
8. 当前 Ticket 所有独立 Review 报告
9. 当前 Ticket 所有 `Blocked by` summary
10. Ticket 指定的真实源码
11. `docs/implementation/options-json-training-configuration-reference.md`（涉及训练配置时）

Ticket 14 返修 Agent 必须优先读取第二轮 Review，不得只读取实施 Summary，也不得只把 Ticket 标题发给弱模型。

---

## 8. 执行规则

- 弱模型一次只领取一个 Ticket；
- Ticket 14 必须通过独立 Reviewer 后才能开始 15、16、17、18；
- Ticket 19 可独立并行；
- Ticket 16、20 完成后必须强模型或人工独立 Review；
- 每个高风险 Ticket 的施工 Agent 不得自行替代独立 Reviewer Gate；
- Summary 中的自审 PASS 不覆盖独立 Review 的 REQUEST_CHANGES；
- 测试必须走真实 Analyzer record，不得手工构造错误旧 Schema；
- Ordinary 和 Packed 都必须执行到 WeightedIndexHost draw；
- 多进程必须使用 spawn 测试和 `debug=False` Generator；
- 不得用 broad fallback 吞掉核心错误；
- 不得修改 SAEHD 网络、Loss、optimizer、DFM、Merge 或 pak 格式；
- 所有新增能力继续默认关闭；
- macOS 轻量测试不能代替 Windows GPU；
- 未执行 Windows 时不得写正式 done；
- 每个 Ticket 完成后必须生成同名 summary；
- Review 失败后必须新增下一轮 Review 报告，不覆盖历史 Review 证据。

---

## 9. 最终完成定义

Batch 2 只有同时满足以下条件才能重新签发 DONE：

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

## 10. 历史 Batch 2 入口

历史设计与实现仍需保留：

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