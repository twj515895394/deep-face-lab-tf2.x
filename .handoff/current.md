# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29  
> 当前交接编号：H-013

请先阅读最新交接文档：

- [预览阈值 400 + Merger 中文化落地：handoff-20260729-121246.md](handoff-20260729-121246.md)

然后继续阅读：

1. [Issue 15 全项目中文路径兼容 + 原需求 A/B 说明](handoff-20260729-113305.md)
2. [Issue 15 中文路径前一轮交接](handoff-20260728-161030.md)
3. [Ticket 11 Batch 1 兼容矩阵与 handoff 汇总](handoff-20260726-203448.md)
4. [Ticket 09 训练保存恢复 smoke](handoff-20260726-201010.md)
5. [Ticket 07 Finite Gradient Gate 与 Loss Scaling](handoff-20260726-195000.md)
6. [Ticket 06 Lion v2 与 Legacy State](handoff-20260726-184945.md)
7. [Ticket 05/10 Optimizer Roundtrip 与 Merge Smoke](handoff-20260726-181947.md)
8. [Ticket 04/08 Precision 与 Feature Flag](handoff-20260726-174706.md)
9. [Ticket 03 训练异常语义](handoff-20260726-165523.md)
10. [Batch 1 首轮实现与 Ticket 化](handoff-20260726-161235.md)
11. [Batch 1 详细设计补齐](handoff-20260726-batch1-detailed-design.md)
12. [首次完整项目交接](handoff-20260726-initial-project-state.md)
13. [Batch 1 ticket 总入口](../.scratch/batch1-correctness-foundation/spec.md)
14. [Batch 1：P0 正确性与扩展安全骨架详细设计](../docs/development/batch1-correctness-and-extension-foundation-tasks.md)
15. [文档总索引](../docs/README.md)
16. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
17. [训练正确性审计规范](../docs/optimization/training-correctness-audit.md)
18. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)
19. [AGENTS.md 研发规范](../AGENTS.md)

当前状态：

```text
Batch 1 全量 Ticket (01-11)：已完成（macOS 轻量验证已通过）
Issue 15 全项目中文路径与 Unicode 编码兼容：已完成
需求 A（简化）：训练预览 5 列阈值 256→400 已完成
需求 B：Merger 参数双语 + 中文帮助图 已完成
AGENTS.md 研发规范：已创建并沉淀
Python 基线：最低 3.9，推荐 3.11 / 3.12
下一步：Windows GPU 补证 + Batch 2 最小 ticket 边界
```

当前下一步：

```text
1. 在完整 DFL/GPU 环境回归 merge smoke 与交互式合并中文帮助
2. 建立 Batch 2 最小 ticket 边界，勿一次引入大功能
3. 可选：help_merger_face_avatar.jpg 中文版替换
详见最新交接文档 handoff-20260729-121246.md 第 3 节。
```

下一轮代码修改建议按 ticket 边界处理：

- 先建立 Batch 2 的最小 ticket 边界，不要直接引入大功能；
- 将 Windows GPU 验证清单转成可执行 checklist；
- Batch 1 的 macOS 轻量依赖已完成，但真实 GPU 训练与 Merge 质量仍待补证。

本轮不要同时引入：

- Region / Boundary / Frequency Loss；
- Dataset Metadata 与 Sampling；
- Identity Geometry；
- Source Shape Template；
- Shape-aware Merge；
- UI 或服务化改造。

必须保持：

- 所有新增增强默认关闭；
- 旧模型和旧配置继续可加载；
- `eyes_mouth_prio=False` 时维持原三输出数据路径；
- macOS 只做轻量验证，真实 GPU 训练与 Merge 质量留到 Windows GPU；
- Python 版本最低为 3.9；
- 新配置缺失时不改变传统训练与 Merge 行为；
- Merger 内部 mode 等逻辑键保持英文；
- 代码状态、测试结果和未完成风险同步写入下一份 handoff。

维护规则：

- 每次重要阶段结束时新建一份带时间戳的 handoff；
- 更新本文件，使其始终指向最新 handoff；
- 不删除历史 handoff；
- handoff 内容结构继续参照 H-001，并明确实际文件、函数、测试和下一步。
