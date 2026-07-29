# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29  
> 当前交接编号：H-014 + Batch 2 Options JSON Reference

请先阅读本分支最新交接：

- [`--options-json` 训练配置权威参考交接](handoff-20260729-options-json-reference.md)

主分支最近交接：

- [预览阈值 400 + Merger 中文化落地：handoff-20260729-121246.md](handoff-20260729-121246.md)

Batch 2 开发必须依次阅读：

1. [根目录 AGENTS.md 研发规范](../AGENTS.md)
2. [Batch 2 Metadata 与 Sampling 详细设计交接](handoff-20260727-batch2-detailed-design.md)
3. [Batch 2 ticket 总入口](../.scratch/batch2-training-data-and-sampling/spec.md)
4. [Batch 2 正式详细设计](../docs/development/batch2-training-data-and-sampling-tasks.md)
5. [`--options-json` 训练配置权威参考](../docs/implementation/options-json-training-configuration-reference.md)
6. [Batch 2 最终审计补充契约](../.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md)
7. [Batch 2 Agent 施工规范](../.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md)
8. [Batch 2 首个 ticket：基线与 fixture](../.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md)

其他重要交接与规范：

1. [Issue 15 全项目中文路径兼容 + 原需求 A/B 说明](handoff-20260729-113305.md)
2. [Issue 15 中文路径前一轮交接](handoff-20260728-161030.md)
3. [模型加载 OOM 修复 handoff](handoff-20260727-165500.md)
4. [Ticket 11 Batch 1 兼容矩阵与 handoff 汇总](handoff-20260726-203448.md)
5. [Batch 1 详细设计](../docs/development/batch1-correctness-and-extension-foundation-tasks.md)
6. [Batch 1 ticket 总入口](../.scratch/batch1-correctness-foundation/spec.md)
7. [文档总索引](../docs/README.md)
8. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
9. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)

当前状态：

```text
Batch 1 全量 Ticket (01-11)：已完成（macOS 轻量验证已通过）
Issue 15 全项目中文路径与 Unicode 编码兼容：已完成
需求 A（简化）：训练预览 5 列阈值 256→400 已完成
需求 B：Merger 参数双语 + 中文帮助图 已完成
模型加载 OOM / 64MiB 分块 assign：已修复并实际验证
AGENTS.md 研发规范：已创建并沉淀

Batch 2 正式详细设计：已完成
Batch 2 .scratch ticket 拆分：已完成（12 个 tickets）
Batch 2 弱模型施工引导：已完成
Batch 2 最终审计补充：已完成
--options-json 权威参数文档：已创建（v1.0）
Batch 2 运行时代码：未开始
Batch 2 Windows FP32 验收：未开始

Python 基线：最低 3.9，推荐 3.11 / 3.12
```

Batch 2 最终审计新增冻结内容：

```text
- Unicode/NFC Sample Identity 与 UTF-8 JSON
- Analyzer v1 姿态、清晰度、曝光、质量公式
- Loader 状态优先级与 usable_for_sampling
- training.enabled + metadata_sampling 双 gate
- --options-json 嵌套配置形状和优先级
- --options-json 参数文档同步规则
- Pose/Quality golden values
- WeightedIndexHost cycle、timeout、统计容差
- Windows 性能量化验收门槛
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
领取 Batch 2 Ticket 01：
.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md
```

执行规则：

- 弱模型一次只领取一个 Ticket。
- 每个 Ticket 必须同时提供当前 Ticket、AGENTS.md、Agent 规范、最终审计契约和前置 summary。
- 涉及训练参数的 Ticket 必须同时阅读并同步 `docs/implementation/options-json-training-configuration-reference.md`。
- 新增、删除、重命名或改变训练参数语义时，必须在同一提交/PR 更新权威参数文档、示例、变更记录和测试。
- 不得直接跳到 WeightedIndexHost 或 SAEHD 接入。
- 先固定 ordinary/Packed fixture、legacy 索引分布和 Generator tensor contract。
- 所有新增能力默认关闭。
- Batch 2 不修改 SAEHD 网络、Loss、checkpoint、DFM 或 Merge。
- Metadata 不写回图片，不修改 faceset.pak，不自动删除样本。
- 图像 I/O 走 `cv2ex`，文本使用 UTF-8，路径必须兼容 Unicode。
- `--options-json` 配置不得被后续交互静默覆盖。
- macOS/CPU 轻量测试不能代替 Windows GPU 真实训练。
- 完整 `done` 必须通过 FP32 + AdaBelief、多进程、ordinary/Packed、fallback、save/exit/resume 和性能记录。
- Ticket 09、10 完成后必须由较强模型或人工进行独立 review。
- 每个 ticket 完成后写入 `.scratch/batch2-training-data-and-sampling/reports/`。

维护规则：

- 每次重要阶段结束时新建带时间戳 handoff。
- 更新本文件，使其始终指向最新 handoff。
- 不删除历史 handoff。
- handoff 必须明确实际文件、函数、测试结果、风险和下一步。
