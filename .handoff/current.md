# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-26  
> 当前交接编号：H-005

请先阅读最新交接文档：

- [Ticket 04/08 Precision 与 Feature Flag：handoff-20260726-174706.md](handoff-20260726-174706.md)

然后继续阅读：

1. [Ticket 03 训练异常语义](handoff-20260726-165523.md)
2. [Batch 1 首轮实现与 Ticket 化](handoff-20260726-161235.md)
3. [Batch 1 详细设计补齐](handoff-20260726-batch1-detailed-design.md)
4. [首次完整项目交接](handoff-20260726-initial-project-state.md)
5. [Batch 1 ticket 总入口](../.scratch/batch1-correctness-foundation/spec.md)
6. [Batch 1：P0 正确性与扩展安全骨架详细设计](../docs/development/batch1-correctness-and-extension-foundation-tasks.md)
7. [文档总索引](../docs/README.md)
8. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
9. [训练正确性审计规范](../docs/optimization/training-correctness-audit.md)
10. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)

当前状态：

```text
Batch 1 详细设计：已完成
Batch 1 ticket 拆分：已完成
Ticket 01 macOS 轻量 smoke harness：已完成
Ticket 02 Eyes / Mouth Priority 真实 mask 修复：已完成
Ticket 03 统一训练异常处理与失败语义：macOS 轻量验证已完成
Ticket 04 Precision Contract 与 dtype 审计：macOS 轻量验证已完成
Ticket 08 Enhancement Feature Flag 骨架：macOS 轻量验证已完成
Python 基线：最低 3.9，推荐 3.11 / 3.12
下一步：从 Ticket 05 / 10 frontier 继续
```

当前下一步：

```text
Ticket 05：建立 optimizer roundtrip 审计基础
Ticket 10：建立 Merge 默认路径 smoke
```

下一轮代码修改建议按 ticket 边界处理：

- Ticket 05 优先记录 optimizer slot dtype 与保存恢复数值误差，不在本 ticket 修 Lion 公式；
- Ticket 10 验证缺失 Enhancement Config 时 Merge 默认路径不变，不实现 Shape-aware Merge。

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
- 代码状态、测试结果和未完成风险同步写入下一份 handoff。

维护规则：

- 每次重要阶段结束时新建一份带时间戳的 handoff；
- 更新本文件，使其始终指向最新 handoff；
- 不删除历史 handoff；
- handoff 内容结构继续参照 H-001，并明确实际文件、函数、测试和下一步。
