# B4-13 用户/GUI Schema、独立Review、Batch 5 Consumer Handoff与收口

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-12；阻塞Batch4签发和Batch5 Revalidation。
- 目标：使代码、Schema、来源优先级、CLI、状态和证据一致，并留下Batch5可执行的唯一consumer入口。

## 必须完成

- 13票Summary、独立Review、P0/P1修复和Commit SHA。
- 更新正式B4文档、docs索引、master plan、根handoff。
- 用户说明：生成、validate、inspect、显式路径、冲突、fallback、删除/重建。
- GUI未来Schema只定义字段和显示状态，不复制核心默认值。
- 发布`.srcshape` consumer contract：公开字段、immutable runtime object、loader API、reason codes、示例fixture。
- 记录自动/Windows/performance/consumer各Gate真实状态。

## Batch 5 Revalidation输入

- 最终Schema和版本。
- 模型/来源/fingerprint匹配结果。
- 默认路径和discovery API。
- confidence component和安全阈值。
- loader/cache/fallback行为。
- 实际性能、Windows问题、未执行项。

Batch5所有Issue必须据此复核，尤其MergerConfig字段、Template加载位置、坐标系和fallback；不得直接用当前草案编码。

## Forbidden

- 不把Schema/自动测试写成Warp效果PASS。
- 不在B4混入Hybrid/Warp实现。
- 不遗漏invalid/legacy行为。
- 不签发Batch5编码，除非完成Batch5独立Revalidation Review。

## 完成定义

文档/代码/测试一致，P0/P1关闭，状态分层准确，Batch5 consumer入口唯一，根handoff明确下一Frontier。交付用户文档、GUI字段表、Review、Handoff和最终SHA。
