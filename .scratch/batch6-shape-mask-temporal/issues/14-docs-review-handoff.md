# B6-14 用户/GUI Schema、独立Review、批次收口与后续路线Handoff

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-13；阻塞Batch6签发和后续Batch7/8复核。
- 目标：使Mask、Temporal、配置、视觉/性能证据和状态一致；不把脸型视频闭环的阶段结果夸大为生产完成。

## 必须完成

- 14票Summary、独立Review、P0/P1修复和SHA。
- 更新正式B6文档、docs索引、master plan、根handoff。
- 用户说明：Template/Warp前置、Shape Mask模式、Temporal模式/强度、遮挡/scene cut/多脸限制、Interactive/session、排错和关闭回退。
- GUI未来字段、范围、状态/metrics显示；默认值仍由核心唯一提供。
- 分层记录Code/Automated/Windows/Performance/Visual/Temporal状态和未执行项。
- 输出后续Batch7/8输入：实际mask/temporal artifact、性能瓶颈、是否需要训练Boundary/Appearance Loss、默认值候选和兼容问题。

## Review重点

Mask插入顺序、XSeg/遮挡、zero path、Temporal identity、scene reset、多脸隔离、乱序worker、session rewind、隐私/日志、错误传播、是否混入Batch7 Loss。

## Forbidden

不把PROMISING写成生产PASS；不遗漏长视频/多脸/scene cut未执行项；不修改历史Batch状态；不在B6临时实现Batch7训练Loss或完整UI；不自动签发后续编码。

## 完成定义

文档/代码/测试/metrics一致，P0/P1关闭，真实状态准确，根handoff明确项目Frontier和后续Review输入。交付用户文档、GUI字段表、Review、Handoff、最终SHA。
