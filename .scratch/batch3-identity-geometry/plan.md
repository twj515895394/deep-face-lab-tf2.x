# Batch 3 执行计划

## Wave 0：设计门

- 完成 B3-01～B3-15 Issue 文档。
- 完成 Master Test Matrix、Windows GPU A/B 规约、Summary/Review 模板。
- 做文档一致性 Review；修复后才允许编码。

## Wave 1：基础设施

`B3-01 -> {B3-02, B3-03, B3-06} -> B3-04 -> B3-05`

目标：冻结契约，稳定配置、Loss Hook、结果模型与错误边界。

## Wave 2：Geometry Core

`B3-06 -> B3-07 -> B3-08 -> {B3-09, B3-10} -> B3-11`

目标：建立 Anchor、ratio/landmark 特征和 SRC 身份几何约束，不接 SAEHD 主链路。

## Wave 3：Curriculum 与集成

`B3-12 -> B3-13`

目标：最小阶段调度、主链路接入、旧 checkpoint/optimizer 兼容。

## Wave 4：验收与收口

`B3-14 -> B3-15`

目标：控制流回归、自动矩阵、GPU A/B 规约、文档与 handoff。

## 强制质量门

- 每票独立 commit；禁止混票。
- tests 失败不得进入下一票。
- Review 必须检查 Scope 扩张、默认启用、异常吞噬、shape/dtype、SRC/DST 混淆、保存恢复遗漏。
- GPU 未执行必须明确写 `NOT EXECUTED`。