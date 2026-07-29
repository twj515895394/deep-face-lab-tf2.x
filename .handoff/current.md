# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29 20:33 +08:00  
> 当前交接：Batch 2 独立 Review 与修复 Ticket 14—21  
> 当前状态：REVIEW-FAILED / FIXES-REQUIRED / PENDING-WINDOWS-GPU

---

## 1. 最新交接

必须先阅读：

- [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
- [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
- [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)

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
pose_balanced：修复前不用于正式训练结论
quality_pose_balanced：修复前不用于正式训练结论
```

---

## 3. Batch 2 独立 Review 发现

### P0 阻断

1. Analyzer 与 Loader 的 yaw/pitch bucket 名称不一致；
2. 旧使用指南的 options JSON 缺少顶层 `enhancements`；
3. 旧示例没有同时开启 `training.enabled` 和 `metadata_sampling`；
4. 文档宣称 `sampling.src/dst`，代码只解析扁平全局配置；
5. WeightedIndexHostClient 在 Windows spawn 下存在 `_host_ref` 序列化风险。

### P1 高优先级

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
Ticket 14
Ticket 19（允许另一个独立 Agent 并行）
```

---

## 5. Faceset Analyzer 使用结论

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
- 正式训练继续使用 legacy。

---

## 6. Agent 开工必读顺序

任何 Agent 领取 Ticket 14—21 前必须依次阅读：

1. 根目录 `AGENTS.md`
2. 本 `.handoff/current.md`
3. 最新 handoff
4. `.scratch/batch2-training-data-and-sampling/spec.md`
5. 独立 Review 总计划
6. 当前 Ticket
7. 当前 Ticket 所有 `Blocked by` summary
8. Ticket 指定的真实源码
9. `docs/implementation/options-json-training-configuration-reference.md`（涉及训练配置时）

不得只把 Ticket 标题发给弱模型。

---

## 7. 执行规则

- 弱模型一次只领取一个 Ticket；
- Ticket 14 必须先于 15、16、17、18；
- Ticket 19 可独立并行；
- Ticket 16、20 完成后必须强模型或人工独立 Review；
- 测试必须走真实 Analyzer record，不得手工构造错误旧 Schema；
- 多进程必须使用 spawn 测试和 `debug=False` Generator；
- 不得用 broad fallback 吞掉核心错误；
- 不得修改 SAEHD 网络、Loss、optimizer、DFM、Merge 或 pak 格式；
- 所有新增能力继续默认关闭；
- macOS 轻量测试不能代替 Windows GPU；
- 未执行 Windows 时不得写正式 done；
- 每个 Ticket 完成后必须生成同名 summary。

---

## 8. 最终完成定义

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

## 9. 历史 Batch 2 入口

历史设计与实现仍需保留：

- [Batch 2 详细设计](handoff-20260727-batch2-detailed-design.md)
- [Ticket 01 基线](handoff-20260729-batch2-ticket01-baseline.md)
- [Ticket 02 Metadata Schema](handoff-20260729-batch2-ticket02-metadata-schema.md)
- [Ticket 03 Analyzer Core](handoff-20260729-batch2-ticket03-analyzer-core.md)
- [Ticket 04 Analyzer CLI](handoff-20260729-batch2-ticket04-analyzer-cli.md)
- [Ticket 05 Metadata Loader](handoff-20260729-batch2-ticket05-metadata-loader.md)
- [Ticket 06 Sampling Policy](handoff-20260729-batch2-ticket06-sampling-policy.md)
- [Ticket 07 Pose-balanced](handoff-20260729-batch2-ticket07-pose-balanced-sampling.md)
- [Ticket 08 Quality Weighting](handoff-20260729-batch2-ticket08-quality-weighting.md)
- [Ticket 09 WeightedIndexHost](handoff-20260729-batch2-ticket09-weighted-index-host.md)
- [Ticket 10 SAEHD/Config/Fallback](handoff-20260729-batch2-ticket10-config-saehd-logging.md)
- [Ticket 11 Master Matrix](handoff-20260729-batch2-ticket11-master-matrix.md)
- [Ticket 12 Docs/Handoff](handoff-20260729-batch2-ticket12-docs-and-handoff.md)
- [Ticket 13 Loss Window](handoff-20260729-ticket13-loss-window-logging.md)
- [`--options-json` 权威参考交接](handoff-20260729-options-json-reference.md)

历史文档用于理解实现过程，不覆盖当前独立 Review 结论。