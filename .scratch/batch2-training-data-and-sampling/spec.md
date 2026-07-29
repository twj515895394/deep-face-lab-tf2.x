# Batch 2 Training Data Metadata and Sampling — Remediation Spec

Status: REVIEW-FAILED / FIXES-REQUIRED / PENDING-WINDOWS-GPU

> 本文件是 Batch 2 当前权威任务入口。  
> 原 Ticket 01—13 的实现与 summary 保留，但独立 Review 已证明其测试不足以签发正式完成。  
> 当前必须执行修复 Ticket 14—21。

---

## 1. 背景

Batch 2 原计划交付：

```text
Faceset Analyzer
+
Metadata Schema v1 / Sidecar
+
Pose-balanced Sampling
+
Quality + Pose Sampling
+
WeightedIndexHost / Multi-process Generator
+
配置、日志、回退
+
Loss Window 可观测性
```

Ticket 01—13 已有实现与 macOS 轻量测试，但 2026-07-29 独立代码 Review 发现端到端数据契约、配置、Windows spawn、增量报告、保存窗口和异常边界存在 P0/P1 问题。

当前结论：

```text
Legacy paths：继续保护与回归
Faceset Analyzer：可用于报告和开发验证
Metadata Sampling：NOT PRODUCTION READY
Windows GPU：PENDING
Batch 3：BLOCKED
```

独立 Review：

- `.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md`

完整用户说明：

- `docs/usage/faceset-analyzer-complete-guide.md`

---

## 2. Agent 执行入口

任何 Agent、Codex、Claude 或能力偏弱的编码模型领取修复 Ticket 前，必须依次阅读：

1. `AGENTS.md`
2. `.handoff/current.md`
3. `.handoff/handoff-20260729-batch2-independent-review-remediation.md`
4. 本 `spec.md`
5. 独立 Review 总计划
6. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
7. `.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md`
8. 当前 Ticket
9. 当前 Ticket 所有 `Blocked by` summary
10. Ticket 指定的真实源码
11. 涉及配置时阅读 `docs/implementation/options-json-training-configuration-reference.md`

不得只提供 Ticket 标题或 checklist。

弱模型开工前必须先输出源码事实复核：

```text
当前字段与调用链
当前测试是否走真实路径
当前实现与 Ticket 假设的冲突
计划修改文件
明确不修改文件
legacy 保护点
异常边界
测试步骤
```

---

## 3. 已冻结决策

- 正式训练验收固定 FP32 + AdaBelief；
- Lion 不进入本批；
- FP16/BF16 不进入正式验收；
- 动态 Loss-aware Sampling 延期；
- Identity Geometry、Source Shape Template、Shape-aware Merge 不进入本批；
- 所有增强默认关闭；
- 不修改 SAEHD 网络或 Loss 公式；
- 不修改 checkpoint、optimizer、DFM、Merge 或 `faceset.pak` 格式；
- Metadata 不写回图片；
- 不自动删除样本；
- Windows 以 spawn 为准；
- optional Metadata 可回退，核心错误必须抛出；
- macOS synthetic 测试不能代替 Windows GPU；
- Batch 3 在 Ticket 21 完成前 blocked。

---

## 4. 独立 Review 阻断问题

### P0

1. Analyzer 与 Loader 的 yaw/pitch bucket 名称不一致；
2. 旧使用指南配置没有顶层 `enhancements`；
3. 旧示例没有同时开启 `training.enabled` 与 `metadata_sampling`；
4. 文档宣称 `sampling.src/dst`，代码只解析扁平配置；
5. WeightedIndexHostClient 在 Windows spawn 下有 `_host_ref` pickle 风险。

### P1

1. `--workers` 参数未实际使用；
2. `--strong-fingerprint` 参数未实际使用；
3. 同名替换图片可能继续 trusted；
4. Incremental summary 使用旧顶层字段；
5. Loss Window 多统计保存后一个 batch；
6. Fallback 捕获范围可能吞 SampleLoader 核心错误；
7. 文档夸大支持模型和 options-json 文件能力；
8. `.handoff/current.md` 曾含冲突标记和互相矛盾状态。

---

## 5. 执行边界

允许修改：

```text
samplelib/metadata/*
samplelib/sampling/*
samplelib/SampleLoader.py
samplelib/SampleGeneratorFace.py
mainscripts/FacesetAnalyzer.py
mainscripts/Trainer.py
core/enhancements/config.py
core/joblib/SubprocessGenerator.py（仅 Ticket 16 必要范围）
models/Model_SAEHD/Model.py
models/ModelBase.py（仅配置警告、资源关闭等批准范围）
main.py
tests/*
docs/*
.scratch/batch2-training-data-and-sampling/*
.handoff/*
```

禁止：

- SAEHD 网络/Loss 改造；
- 新优化器；
- 动态 Loss-aware Sampling；
- Identity Geometry；
- Merge 改造；
- pak 格式变更；
- GUI 或服务化；
- broad fallback 掩盖核心错误；
- 通过降低测试断言迎合错误实现；
- 通过手工旧 Schema Fixture 代替真实 Analyzer；
- 通过 debug=True 代替多进程；
- 仅文档或 compileall 即标 resolved。

---

## 6. 修复 Ticket

### Ticket 14 — Schema 与 E2E

- `issues/14-unify-metadata-bucket-schema-and-e2e-contract.md`
- P0；无前置；阻塞 15/16/17/18/20/21。

### Ticket 15 — 配置契约

- `issues/15-fix-options-json-and-src-dst-sampling-contract.md`
- 前置 14；阻塞 20/21。

### Ticket 16 — Windows spawn

- `issues/16-fix-weighted-index-host-windows-spawn.md`
- 前置 14；高风险；阻塞 20/21。

### Ticket 17 — Workers / Fingerprint / Stale

- `issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md`
- 前置 14；阻塞 18/20/21。

### Ticket 18 — Incremental / Report

- `issues/18-fix-incremental-summary-and-report-schema.md`
- 前置 14、17；阻塞 21。

### Ticket 19 — Loss Window Boundary

- `issues/19-fix-loss-window-save-boundary-and-observability.md`
- 无前置，可独立并行；阻塞 21。

### Ticket 20 — Fallback Boundary

- `issues/20-narrow-fallback-exception-boundaries.md`
- 前置 15、16、17；高风险；阻塞 21。

### Ticket 21 — Docs / Handoff / Windows GPU Final

- `issues/21-docs-handoff-windows-gpu-final-acceptance.md`
- 前置 14—20 全部 PASS；最终签发门。

---

## 7. 依赖与 Frontier

```text
14
├── 15
├── 16
└── 17
     ↓
18

19 可由独立 Agent 并行

15 + 16 + 17
     ↓
20

14—20 全部 PASS
     ↓
21
```

当前 frontier：

```text
Ticket 14
Ticket 19（可并行）
```

禁止：

- 跳过 14 直接做 15/16/17/18；
- 让同一弱模型并行 16 与 20；
- 在前置 summary 缺失时开始后续 Ticket；
- 在 21 之前启动 Batch 3 正式代码开发。

---

## 8. 通用完成定义

单个 Ticket 只有同时满足以下条件才可 resolved：

```text
前置依赖 PASS
+
源码事实复核有记录
+
实现严格在范围内
+
对应自动测试实际通过
+
legacy 关闭路径回归
+
Unicode/UTF-8 验证
+
summary 已生成
+
Windows 未执行项明确
+
独立 Review（高风险 Ticket）
```

以下不算完成：

- 只创建接口；
- 只通过 compileall；
- 测试全部 skip；
- 只测纯函数但 Ticket 要求时序/进程；
- 只测 debug=True；
- 只测主进程；
- 通过 fallback 让测试不崩；
- 未生成 summary；
- 没有 commit 和命令证据；
- 文档声称完成但 Windows 未运行。

---

## 9. 测试分层

### Layer 0：纯函数

- bucket；
- config；
- signature；
- weights/probabilities；
- Loss Window；
- exception classification。

### Layer 1：组件

- Analyzer；
- Loader；
- Incremental；
- Policy；
- Host；
- Store；
- Report。

### Layer 2：真实 E2E CPU

```text
Fixture
→ Analyzer
→ Sidecar
→ Loader
→ Policy
→ Host
→ Draw
```

Ordinary/Packed 都必须覆盖。

### Layer 3：Spawn

```text
multiprocessing.get_context("spawn")
```

Client pickle、child draw、多 child、close/fatal/timeout、debug=False Generator。

### Layer 4：SAEHD 初始化

options-json、双 Gate、side config、startup log、fallback/strict、legacy。

### Layer 5：Windows GPU

FP32 + AdaBelief、四种 mode、Ordinary/Packed、save/exit/resume、采样分布、性能。

---

## 10. 平台状态

macOS/CPU 可以签发：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
```

不能签发：

```text
PASS-WINDOWS-GPU
DONE
```

Windows GPU 必须实际执行 Ticket 21 矩阵。

---

## 11. Summary 约定

每个 Ticket 完成后生成：

```text
.scratch/batch2-training-data-and-sampling/reports/<ticket-name>-summary.md
```

至少记录：

- before/after commit；
- 修改文件、函数和接口；
- 数据/配置契约；
- 自动测试命令与原始摘要；
- legacy 回归；
- Unicode；
- options-json 文档同步；
- spawn/Windows 状态；
- 未完成项；
- 风险；
- 下一 Ticket 可依赖接口；
- Reviewer 结论。

Ticket 16、20 必须独立 Reviewer。

---

## 12. 最终 DONE 定义

只有：

```text
14—20 PASS
+
Full regression PASS
+
Analyzer→Loader→Policy E2E PASS
+
Canonical buckets PASS
+
Stale detection PASS
+
Incremental == Force Full
+
Windows spawn PASS
+
Windows FP32 + AdaBelief PASS
+
Ordinary/Packed PASS
+
四种 mode PASS
+
SRC/DST side config PASS
+
Fallback boundary PASS
+
Save/Exit/Resume PASS
+
Loss Window offline recompute PASS
+
Docs/Handoff consistency PASS
```

才可由 Ticket 21 重新签发：

```text
Status: done
```

否则必须使用：

```text
PENDING-WINDOWS
FIXES-REQUIRED
BLOCKED-BY-XX
FAIL
```

---

## 13. 历史 Ticket 01—13

历史实现文档继续保留：

```text
01-baseline-and-fixtures.md
02-sample-identity-and-metadata-schema.md
03-lightweight-faceset-analyzer-core.md
04-analyzer-cli-atomic-store-and-incremental.md
05-metadata-loader-folder-packed-compat.md
06-sampling-policy-and-legacy-adapters.md
07-pose-balanced-sampling.md
08-quality-aware-weighting.md
09-weighted-index-host-and-generator-integration.md
10-config-saehd-logging-and-fallback.md
11-batch2-test-matrix-and-windows-acceptance.md
12-compatibility-docs-and-handoff.md
13-loss-window-logging-and-observability.md
```

这些文件是历史实现上下文，不覆盖 Ticket 14—21 的修复要求。