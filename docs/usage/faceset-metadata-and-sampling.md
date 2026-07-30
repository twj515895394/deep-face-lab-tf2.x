# Faceset Metadata 与智能采样使用指南（已迁移）

> 状态：SUPERSEDED / DO NOT USE AS CONFIGURATION REFERENCE  
> 更新日期：2026-07-29  
> 原因：独立代码 Review 发现旧版文档中的配置层级、双 Gate、SRC/DST 配置、模型支持范围及 Analyzer CLI 能力与当前源码不一致。

---

## 新的权威使用说明

请改为阅读：

- [Faceset Analyzer 完整使用说明](faceset-analyzer-complete-guide.md)

该文档包含：

- Faceset Analyzer 与 XSeg 的区别；
- 是否每套素材都需要分析；
- SRC/DST 分别分析的正确流程；
- Ordinary 与 Packed 工作流；
- `--incremental`、`--force`、`--strict`；
- 当前 `--workers` 与 `--strong-fingerprint` 的 Review 状态；
- 正确的顶层 `enhancements` 配置；
- `training.enabled` + `metadata_sampling` 双 Gate；
- 当前扁平配置与计划中的 SRC/DST side config；
- Metadata stale、fallback 和故障排查；
- Windows spawn 与 GPU 最终验收要求。

---

## 当前功能状态（2026-07-30）

```text
Faceset Analyzer：代码契约可用（workers / strong / incremental / strict）
legacy_random：可继续使用与回归
legacy_uniform_yaw：可继续使用与回归
pose_balanced：开发可用；生产签发仍待 Windows GPU 最终验收
quality_pose_balanced：开发可用；生产签发仍待 Windows GPU 最终验收
Windows spawn 单元 / test_batch*.py：PASS（实现侧）
Windows SAEHD FP32 + AdaBelief 500/resume：PENDING-WINDOWS-GPU
Batch 2 合并 main：禁止（Ticket 21 最终门未关闭）
```

独立 Review 与交接：

- [Wave 1 Independent Review Round 4](../../.scratch/batch2-training-data-and-sampling/reports/wave1-independent-review-round4.md)
- [当前项目交接入口](../../.handoff/current.md)
- [Ticket 21 最终验收](../../.scratch/batch2-training-data-and-sampling/issues/21-docs-handoff-windows-gpu-final-acceptance.md)

---

## 为什么旧内容不能继续使用

旧文档曾包含以下错误或尚未实现的声明：

1. 将配置写在顶层 `training` / `sampling`，而真实 SAEHD 读取顶层 `enhancements`；
2. 只设置 `metadata_sampling=true`，遗漏 `training.enabled=true`；
3. 宣称 `sampling.src` / `sampling.dst` 已生效，但当前代码只解析扁平配置；
4. 宣称 `--options-json` 可以传配置文件，但当前只接受 JSON 字符串；
5. 宣称 AMP、Quick96 等全量模型已接入，但当前真实运行时接线主要位于 SAEHD；
6. 早期宣称 `--workers` / `--strong-fingerprint` 为空壳——**Ticket 17 后已实现**，以完整使用说明为准；
7. Analyzer / Loader pose bucket Schema 已由 Ticket 14 统一；
8. Windows spawn 单元与 batch smoke 已通过；**SAEHD GPU 500/resume 仍待 Ticket 21**。

因此本文件不再保留可复制的旧错误命令。请以 [faceset-analyzer-complete-guide.md](faceset-analyzer-complete-guide.md) 与 `options-json` 权威参考为准。

---

## 修复与验收入口

```text
Ticket 14—20：代码关口（见 reports/*-summary.md）
Ticket 21：文档 + Windows GPU 最终验收 + 是否签发 Batch 2 DONE
.handoff/current.md
```

**Windows GPU 最终验收完成前，不得把 Batch 2 Metadata Sampling 标记为生产 DONE / 合入 main。**