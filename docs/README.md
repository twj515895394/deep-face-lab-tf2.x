# DeepFaceLab TF2.x 文档总索引

> 文档版本：v2.4  
> 更新日期：2026-07-30  
> 总体开发顺序以`implementation/enhanced-dfl-master-implementation-plan.md`为准；跨会话事实以`.handoff/current.md`为准。

## 1. 当前路线

```text
Batch 1 训练正确性与扩展骨架：COMPLETE
Batch 2 Metadata / Smart Sampling：COMPLETE
  Windows GPU Final Matrix：DEFERRED-BY-MAINTAINER / NOT EXECUTED
Batch 3 Minimal Loss Hook + Identity Geometry：READY-FOR-B3-01-ONLY
Batch 4 Source Shape Template：DESIGN-DRAFT-REVALIDATE-AFTER-B3
Batch 5 Hybrid Landmark + Piecewise Affine Warp：DESIGN-DRAFT-REVALIDATE-AFTER-B4
Batch 6 Shape-aware Soft Mask + Temporal：DESIGN-DRAFT-REVALIDATE-AFTER-B5
Batch 7 Appearance / Region / Boundary / Frequency：LATER
Batch 8 联调/A-B/默认值/GUI/兼容/文档：LATER
```

Batch 4–6已经详细拆票，但不是编码许可。每个前置批次完成后必须重新代码审计、修订和独立Review。

## 2. 唯一入口

- [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)
- [最新交接入口](../.handoff/current.md)
- [Batch 4–6滚动拆票策略](development/face-shape-batch4-6-rolling-ticket-plan.md)

## 3. 当前开发Frontier：Batch 3

按顺序读取：

1. [Batch 3正式施工设计](development/batch3-identity-geometry-tasks.md)
2. [训练增强实施计划](implementation/training-enhancement-implementation-plan.md)
3. [src脸型保持设计](optimization/src-face-shape-preservation-design.md)
4. [训练与Shape-aware Merge联合设计](optimization/src-face-shape-training-and-shape-aware-merge-design.md)
5. `../.scratch/batch3-identity-geometry/reviews/code-anchor-audit-20260730.md`
6. `../.scratch/batch3-identity-geometry/reviews/document-review-20260730.md`
7. `../.scratch/batch3-identity-geometry/issues/01-baseline-contracts-fixtures.md`

当前状态：代码锚点和文档Review完成，15票已升级为弱模型可执行规格，只签发B3-01；Batch 3代码、自动测试和GPU训练尚未开始。

关键设计：不新增landmark head；使用target-aligned landmark派生的Ratio/SDF监督与现有可微src predicted mask计算Geometry Loss。Geometry只进入src-src loss；默认关闭，不改checkpoint/optimizer/DFM/Merge。

## 4. 批次施工文档

### Batch 1

- [P0正确性与扩展安全骨架](development/batch1-correctness-and-extension-foundation-tasks.md)
- [训练正确性审计](optimization/training-correctness-audit.md)

### Batch 2

- [Metadata与Quality/Pose Sampling](development/batch2-training-data-and-sampling-tasks.md)
- [Faceset Metadata与智能采样用户指南](usage/faceset-metadata-and-sampling.md)
- [Faceset Analyzer完整说明](usage/faceset-analyzer-complete-guide.md)
- [options-json参考](implementation/options-json-training-configuration-reference.md)
- [Batch 2 GUI接入](implementation/batch2-gui-parameter-integration.md)

### Batch 3

- [Minimal Loss Hook + Identity Geometry详细施工](development/batch3-identity-geometry-tasks.md)
- 工作区：`../.scratch/batch3-identity-geometry/`
- Issue数：15
- 状态：`READY-FOR-B3-01-ONLY`

### Batch 4

- [Source Shape Template详细任务](development/batch4-source-shape-template-tasks.md)
- 工作区：`../.scratch/batch4-source-shape-template/`
- Issue数：13
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`
- 边界：`.srcshape` Geometry Bridge，不实现Warp。

### Batch 5

- [Hybrid Landmark + Piecewise Affine Warp详细任务](development/batch5-hybrid-landmark-piecewise-warp-tasks.md)
- 工作区：`../.scratch/batch5-hybrid-landmark-warp/`
- Issue数：14
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`
- 边界：Hybrid/Warp/Merge接入，不实现Mask/Temporal。

### Batch 6

- [Shape-aware Soft Mask + Temporal详细任务](development/batch6-shape-aware-soft-mask-temporal-tasks.md)
- 工作区：`../.scratch/batch6-shape-mask-temporal/`
- Issue数：14
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`
- 边界：Mask/Temporal，不实现Batch 7通用训练Loss。

## 5. 架构与代码地图

- [当前项目架构与升级分析](analysis/dfl-current-project-overview.md)
- [训练架构分析](analysis/training-architecture-analysis.md)
- [Merge架构分析](analysis/merging-architecture-analysis.md)
- [源码树分析](implementation/deepfacelab-tf2x-source-tree-analysis.md)
- [训练调用链](implementation/deepfacelab-training-call-chain-analysis.md)
- [Merger调用链](implementation/deepfacelab-merger-call-chain-analysis.md)
- [代码修改地图](implementation/deepfacelab-code-modification-map.md)
- [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)

## 6. 脸型与Merge专项

- [src脸型保持设计](optimization/src-face-shape-preservation-design.md)
- [src脸型训练与Shape-aware Merge联合设计](optimization/src-face-shape-training-and-shape-aware-merge-design.md)
- [Shape-aware Merge实现设计](optimization/shape-aware-merge-implementation-design.md)
- [Shape-aware Merge实施计划](implementation/merge-shape-aware-implementation-plan.md)

## 7. 验收与状态规则

分别记录：Code、Automated、Windows/Environment、Performance、Visual A/B。自动测试不等价GPU；短跑不等价长期视觉。未执行必须写`NOT EXECUTED/DEFERRED/PENDING`。视觉使用`PROMISING/NEUTRAL/REGRESSION/INCONCLUSIVE`并附素材和指标。

历史Batch 2 Windows GPU Matrix保持`DEFERRED-BY-MAINTAINER / NOT EXECUTED`，不得改写为PASS。

## 8. 弱模型执行规则

一次只执行一个Ticket。Ticket之外不得重构、改Schema、改默认值或提前实现后批次。每票必须：实现→指定测试→Summary→独立Review→修复P0/P1→更新Handoff→再进入下一票。
