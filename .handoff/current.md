# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-26  
> 当前交接编号：H-002

请先阅读最新交接文档：

- [Batch 1 详细设计补齐：handoff-20260726-batch1-detailed-design.md](handoff-20260726-batch1-detailed-design.md)

然后继续阅读：

1. [首次完整项目交接](handoff-20260726-initial-project-state.md)
2. [Batch 1：P0 正确性与扩展安全骨架详细设计](../docs/development/batch1-correctness-and-extension-foundation-tasks.md)
3. [文档总索引](../docs/README.md)
4. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
5. [训练正确性审计规范](../docs/optimization/training-correctness-audit.md)
6. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)

当前状态：

```text
Batch 1 详细设计：已完成
Batch 1 运行时代码：尚未修改
下一步：建立最小 smoke harness，并修复 Eyes / Mouth Priority 真实 mask 传递
```

当前下一步：

```text
B1-00：冻结基线与建立最小 smoke harness
        ↓
B1-01：修复 Eyes / Mouth Priority 真实 mask
        ↓
对应单元测试与默认路径回归
```

第一轮代码修改建议只处理：

- `models/Model_SAEHD/Model.py` 中训练样本解包与 `unified_train()` feed；
- `tests/smoke/test_batch1_eyes_mouth_masks.py`；
- 必要的最小测试公共代码。

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
- 新配置缺失时不改变传统训练与 Merge 行为；
- 代码状态、测试结果和未完成风险同步写入下一份 handoff。

维护规则：

- 每次重要阶段结束时新建一份带时间戳的 handoff；
- 更新本文件，使其始终指向最新 handoff；
- 不删除历史 handoff；
- handoff 内容结构继续参照 H-001，并明确实际文件、函数、测试和下一步。
