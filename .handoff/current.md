# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-27  
> 当前交接编号：H-011

请先阅读最新交接文档：

- [Batch 2 Metadata 与 Sampling 详细设计：handoff-20260727-batch2-detailed-design.md](handoff-20260727-batch2-detailed-design.md)

然后继续阅读：

1. [Batch 2 正式详细设计](../docs/development/batch2-training-data-and-sampling-tasks.md)
2. [Batch 2 ticket 总入口](../.scratch/batch2-training-data-and-sampling/spec.md)
3. [Batch 2 首个 ticket：基线与 fixture](../.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md)
4. [模型加载 OOM 修复 handoff](handoff-20260727-165500.md)
5. [Ticket 11 Batch 1 兼容矩阵与 handoff 汇总](handoff-20260726-203448.md)
6. [Batch 1 详细设计](../docs/development/batch1-correctness-and-extension-foundation-tasks.md)
7. [Batch 1 ticket 总入口](../.scratch/batch1-correctness-foundation/spec.md)
8. [文档总索引](../docs/README.md)
9. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
10. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)

当前状态：

```text
Batch 1 详细设计与 macOS 轻量实现：已完成
Batch 1 Windows FP32 真实训练：已有实际训练和大 optimizer 加载证据，完整兼容矩阵仍需按验收清单补齐
模型加载 OOM / 64MiB 分块 assign：已修复并实际验证

Batch 2 正式详细设计：已完成
Batch 2 .scratch ticket 拆分：已完成（12 个 tickets）
Batch 2 运行时代码：未开始
Batch 2 Windows FP32 验收：未开始
```

Batch 2 已确定边界：

```text
交付：
- Metadata Schema v1
- Stable Sample Identity / Dataset Fingerprint
- Lightweight Faceset Analyzer
- Analyzer CLI / Atomic Store / Incremental Update
- Ordinary + Packed Metadata Loader
- legacy_random / legacy_uniform_yaw
- pose_balanced
- quality_pose_balanced
- WeightedIndexHost / Multi-process Generator
- Config / Logs / Fallback
- Windows FP32 + AdaBelief Acceptance

明确延期：
- Dynamic Loss-aware Sampling
- Identity Geometry / 脸型 Loss
- Source Shape Template
- Shape-aware Merge
- Lion 后续开发
- FP16 / BF16 正式验收
```

当前下一步：

```text
领取 Ticket 01：
.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md
```

执行规则：

- 不得直接跳到 WeightedIndexHost 或 SAEHD 接入。
- 先固定 ordinary/Packed fixture、legacy 索引分布和 Generator tensor contract。
- 所有新增能力默认关闭。
- Batch 2 不修改 SAEHD 网络、Loss、checkpoint、DFM 或 Merge。
- Metadata 不写回图片，不修改 faceset.pak，不自动删除样本。
- macOS/CPU 轻量测试不能代替 Windows GPU 真实训练。
- 完整 `done` 必须通过 FP32 + AdaBelief、多进程、ordinary/Packed、fallback、save/exit/resume 和性能记录。
- 每个 ticket 完成后写入 `.scratch/batch2-training-data-and-sampling/reports/`。

维护规则：

- 每次重要阶段结束时新建带时间戳 handoff。
- 更新本文件，使其始终指向最新 handoff。
- 不删除历史 handoff。
- handoff 必须明确实际文件、函数、测试结果、风险和下一步。
