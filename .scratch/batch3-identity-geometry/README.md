# Batch 3 Identity Geometry 工作区

状态：`TICKET-DESIGN-DRAFT`

## 入口

- 正式批次设计：`docs/development/batch3-identity-geometry-tasks.md`
- 执行计划：`plan.md`
- 独立任务：`issues/`
- 测试与验收：`reports/`
- Review：`reviews/`
- 动态交接：`handoff/`

## 执行规则

1. 一次只执行一个 Ticket。
2. 每票先测试后接主链路。
3. 每票结束必须提交 Summary、Review、测试命令、结果、SHA 和未执行项。
4. B3-13 前不得修改 SAEHD 主训练链路。
5. 新能力默认关闭；关闭时必须与基线等价。
6. 不进入 Batch 4—7，不修改 Merge 或 checkpoint 核心格式。

## 第一可执行 Ticket

文档 Review 通过后从 `B3-01` 开始。