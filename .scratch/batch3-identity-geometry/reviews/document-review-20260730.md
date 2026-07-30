# Batch 3 独立文档一致性 Review（2026-07-30）

## 1. Review范围

- 正式批次设计 `docs/development/batch3-identity-geometry-tasks.md`
- `.scratch/batch3-identity-geometry/issues/01..15`
- Master Test Matrix、Windows GPU A/B、Review模板、Handoff
- 权威Geometry路线与真实代码锚点

## 2. Review方法

逐票检查：目标单一、输入输出、文件/函数、Scope/Forbidden、默认值、错误/Fallback、兼容、测试命令、完成定义、前后依赖，以及弱模型是否仍需自行做重大设计决定。

## 3. 总结

```text
初审：REQUEST-CHANGES
修订：COMPLETE
复审：PASS
签发范围：B3-01 ONLY
实现/GPU事实：NOT STARTED / NOT EXECUTED
```

## 4. 初审问题

- P0：直接Landmark Loss没有可微prediction。
- P0：重复`geometry.enabled`。
- P1：legacy landmarks坐标系不匹配。
- P1：Hook返回/reduction和插入点不完整。
- P1：loss history通道/热切换未约束。
- P1：Anchor与`.srcshape`职责重叠。
- P1：Curriculum保存状态可能破坏兼容。
- P1：SRC/DST隔离缺少图级禁止项。
- P1：Issue短草案不足以交给弱模型。

## 5. 修订结果

15票全部扩展为完整施工规格。关键固定决策：

1. 参数`geometry` section无独立enabled。
2. Hook返回per-sample `[batch]` addition。
3. disabled不构建Noop生产图。
4. ShapeAnchorV1是训练内部资产，不是Batch 4 `.srcshape`。
5. 新aligned supervision与target affine/flip一致，不应用non-rigid warp。
6. Ratio/Contour从可微predicted src mask计算。
7. Geometry只加入src-src loss。
8. Curriculum由iter+config确定性重建。
9. 权重/optimizer/DFM/Merge格式不改。
10. 自动/GPU/视觉验收分别记录。

## 6. DAG Review

- 无循环依赖。
- 配置、Hook、Anchor可并行。
- Supervision晚于Anchor loader。
- Ratio/Contour晚于Hook、错误边界和Supervision。
- SAEHD接入晚于所有模块。
- 控制流/GPU晚于主接入。
- 文档收口最后执行。

结论：`PASS`

## 7. 越界检查

未混入：Batch 4正式Template、Batch 5 Hybrid/Warp、Batch 6 Mask/Temporal、Batch 7通用Loss、GUI页面、新Backbone/外部大模型。

结论：`PASS`

## 8. 弱模型执行适配

每票均明确：

- 允许/禁止文件和函数；
- 输入shape/dtype/layout；
- 固定字段/公式/常量；
- 失败语义；
- 测试文件、场景、命令；
- Summary/Review/Commit证据；
- 不允许临时重大设计。

结论：`PASS-WITH-TICKET-SEQUENCING`。弱模型必须一次只执行一票，不得并票实现。

## 9. 签发

```text
Batch 3 document design: APPROVED
First executable ticket: B3-01
Later tickets: BLOCKED-BY-DAG
Batch 3 code status: NOT STARTED
```
