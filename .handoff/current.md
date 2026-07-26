# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-26  
> 当前交接编号：H-001

请先阅读最新交接文档：

- [首次完整项目交接：handoff-20260726-initial-project-state.md](handoff-20260726-initial-project-state.md)

然后继续阅读：

1. [文档总索引](../docs/README.md)
2. [Enhanced DFL 统一实施总计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
3. [训练增强实施计划](../docs/implementation/training-enhancement-implementation-plan.md)
4. [Shape-aware Merge 实施计划](../docs/implementation/merge-shape-aware-implementation-plan.md)
5. [开发验证与人工质量验收标准](../docs/implementation/manual-quality-acceptance-and-development-validation-standard.md)

当前下一步：

```text
进入 Batch 1：P0 正确性与扩展骨架
```

重点包括：

- 重新核对 Eyes / Mouth Priority 的真实 mask 输入；
- 检查混合精度、Loss Scaling、Optimizer state 和恢复；
- 建立兼容的 Feature Flag / 配置入口；
- 建立训练与 Merge smoke test；
- 保证所有增强关闭时维持原始行为。

维护规则：

- 每次重要阶段结束时新建一份带时间戳的 handoff；
- 更新本文件，使其始终指向最新 handoff；
- 不删除历史 handoff；
- handoff 内容结构以 H-001 为模板。