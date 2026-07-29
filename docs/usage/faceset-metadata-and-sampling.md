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

## 当前功能状态

```text
Faceset Analyzer：可用于报告与开发验证
legacy_random：可继续使用与回归
legacy_uniform_yaw：可继续使用与回归
pose_balanced：修复前不用于正式训练结论
quality_pose_balanced：修复前不用于正式训练结论
Windows spawn：PENDING
Windows FP32 + AdaBelief：PENDING
```

独立 Review 与修复计划：

- [Batch 2 独立代码审查、问题汇总与修复总计划](../../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
- [当前项目交接入口](../../.handoff/current.md)

---

## 为什么旧内容不能继续使用

旧文档曾包含以下错误或尚未实现的声明：

1. 将配置写在顶层 `training` / `sampling`，而真实 SAEHD 读取顶层 `enhancements`；
2. 只设置 `metadata_sampling=true`，遗漏 `training.enabled=true`；
3. 宣称 `sampling.src` / `sampling.dst` 已生效，但当前代码只解析扁平配置；
4. 宣称 `--options-json` 可以传配置文件，但当前只接受 JSON 字符串；
5. 宣称 AMP、Quick96 等全量模型已接入，但当前真实运行时接线主要位于 SAEHD；
6. 宣称 `--workers` 和 `--strong-fingerprint` 已生效，但当前实现尚未可靠消费参数；
7. 没有提示 Analyzer 与 Loader 的 pose bucket Schema 漂移；
8. 没有提示 Windows spawn 链路尚未真实验收。

因此本文件不再保留可复制的旧命令，避免弱模型、GUI 或用户继续复制错误配置。

---

## 修复入口

修复任务已拆分为 Ticket 14—21，入口见：

```text
.scratch/batch2-training-data-and-sampling/issues/
```

第一优先执行：

```text
14-unify-metadata-bucket-schema-and-e2e-contract.md
```

可由另一个独立 Agent 并行执行：

```text
19-fix-loss-window-save-boundary-and-observability.md
```

全部修复并完成 Windows GPU 验收前，不得重新把本功能标记为生产可用。