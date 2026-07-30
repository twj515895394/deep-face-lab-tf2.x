# Batch 3 Ticket 设计状态

更新时间：2026-07-30

## 已完成

- 正式批次施工文档已按真实代码锚点修订。
- B3-01～B3-15 全部升级为弱模型可执行的详细 Issue。
- 完成代码锚点复核和独立文档 Review。
- 关闭 P0/P1设计Finding：重复Gate、伪可微Landmark Loss、landmark坐标系、Hook插入、loss通道、Anchor/Template边界、Curriculum兼容。
- Ticket DAG、Master Test Matrix、Windows GPU A/B规约和Review模板已建立。

## 当前状态

```text
Batch 3 code-anchor audit: COMPLETE
Batch 3 document review: PASS-AFTER-FIXES
Batch 3 ticket design: FROZEN-FOR-B3-01
Batch 3 coding: READY-FOR-B3-01-ONLY
Batch 3 implementation: NOT STARTED
Batch 3 automated/GPU validation: NOT EXECUTED
First executable ticket: B3-01
```

## 关键设计修订

- Gate固定为`training.enabled && training.loss_hooks && training.identity_geometry`，无`geometry.enabled`。
- Geometry监督来自target-aligned landmark派生的Ratio/SDF；prediction来自现有可微src predicted mask。
- 不新增landmark网络，不实现直接预测68点坐标Loss。
- Geometry只进入src-src loss；DST、Merge、checkpoint、optimizer、DFM不改。
- Curriculum由iter+config确定性恢复。

## 下一步

严格按B3-01开始，一次只执行一票。每票必须完成测试、Summary、独立Review、修复和状态同步后，才进入DAG下一票。

Batch 4–6可以保持详细滚动设计草案，但Batch 4必须在Batch 3真实完成后重新审计和冻结，不能直接编码。

## 事实保护

Batch 2 Windows GPU Final Matrix仍为`DEFERRED-BY-MAINTAINER / NOT EXECUTED`。本轮只完成设计与Review，没有修改训练代码，没有执行Batch 3自动测试或GPU训练。
