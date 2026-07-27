# 12 — 完成兼容矩阵、用户文档、状态收口与下一批次 handoff

Status: open
Type: AFK
Blocked by: `11-batch2-test-matrix-and-windows-acceptance.md`

**构建内容：** 基于实际实现与 Windows FP32 验收结果，完成 Batch 2 的兼容矩阵、Analyzer/训练使用教程、限制说明、状态索引、handoff 和后续 Batch 3 入口；确保文档只描述已验证事实，不把延期能力写成已实现。

## 目标

- 用户能够独立生成 Metadata、选择模式、查看报告、排查 fallback。
- 开发者能知道稳定接口、默认行为和后续可依赖边界。
- Batch 2 状态与真实验证一致。
- 动态 Loss sampler、脸型训练、Lion、低精度继续明确延期。

## 兼容矩阵

至少覆盖：

- [ ] 旧模型，无 enhancements。
- [ ] 新模型，全部增强关闭。
- [ ] uniform_yaw False / True。
- [ ] Metadata Sampling master flag False。
- [ ] legacy_random / legacy_uniform_yaw。
- [ ] pose_balanced / quality_pose_balanced。
- [ ] Metadata missing / invalid / unsupported。
- [ ] partial match above/below threshold。
- [ ] src/dst 单侧 fallback。
- [ ] ordinary / Packed / person faceset。
- [ ] debug / single worker / multi worker。
- [ ] eyes_mouth False / True。
- [ ] FP32 + AdaBelief save/resume。
- [ ] Merge / DFM 不受影响。

## 用户文档

建议新增或更新：

- [ ] `docs/usage/faceset-metadata-and-sampling.md`。
- [ ] Analyzer CLI 参数和示例。
- [ ] Metadata 文件位置、备份和增量更新。
- [ ] 四种 sampling mode 的区别。
- [ ] 默认参数和保守调节建议。
- [ ] 日志 requested/effective/fallback 解读。
- [ ] ordinary / Packed 使用方式。
- [ ] 如何检查报告中的低质量和姿态样本。
- [ ] 明确程序不自动删除图片。
- [ ] Metadata 损坏或删除后的恢复方式。
- [ ] 明确 quality score 不是最终换脸质量评分。

## 开发文档

- [ ] 更新 `docs/README.md`。
- [ ] 更新总实施计划 Batch 2 状态。
- [ ] 记录 Schema v1、Sampling Policy 和 WeightedIndexHost 稳定接口。
- [ ] 记录 Windows 验收环境和结果链接。
- [ ] 记录性能基线。
- [ ] 记录已知限制和后续 schema 扩展规则。

## Handoff

- [ ] 新建带时间戳 handoff。
- [ ] 更新 `.handoff/current.md` 指向最新交接。
- [ ] 列出实际 commit、文件、函数、测试命令和结果。
- [ ] 标记 macOS/CPU 与 Windows GPU 各自完成范围。
- [ ] 列出未完成风险。
- [ ] 下一步明确进入 Batch 3 Loss Hook 前置设计，而不是顺手开发动态 sampler。

## 状态规则

只有 Ticket 11 Windows 验收通过后，spec 才能从：

```text
ready-for-implementation
```

更新为：

```text
done
```

若只有 CPU/macOS 轻量验证：

```text
done-macos-lightweight-pending-windows
```

不得写成完整完成。

## 明确延期

文档必须明确：

- [ ] Dynamic Loss-aware Sampling：deferred / future experimental。
- [ ] Identity Geometry / 脸型 Loss：Batch 4。
- [ ] Source Shape Template：Batch 5。
- [ ] Shape-aware Merge：Batch 6。
- [ ] Lion 后续开发：paused。
- [ ] FP16/BF16 正式验收：paused / experimental。

## 验收标准

- [ ] 用户按照文档可以完成 Analyzer + 训练闭环。
- [ ] 文档中的命令在目标平台验证。
- [ ] 所有默认值与代码一致。
- [ ] 所有完成状态有测试/报告依据。
- [ ] 延期功能未被误写为 Batch 2 已完成。
- [ ] `.scratch` issues、reports、正式设计和 handoff 互相链接。
- [ ] 下一 Agent 能从 `.handoff/current.md` 和 spec 继续。

## 回退

文档提交不改变运行时；历史 handoff 不删除。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/12-compatibility-docs-and-handoff-summary.md`，汇总最终产品能力、验证结果、限制和下一步。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；本 ticket 负责批次收口，不负责补做未完成代码。
