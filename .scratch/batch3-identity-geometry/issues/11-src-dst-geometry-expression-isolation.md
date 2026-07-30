# B3-11 SRC/DST 职责与 Geometry/Expression 隔离

- 前置：B3-09,B3-10；P0。
- 目标：组合 ratio/landmark loss 时固定 SRC 身份几何、DST 姿态表情的非对称职责。
- 设计：Anchor 只绑定 SRC；DST 只提供当前训练条件，不作为 identity anchor；禁止逐帧配对。
- 输出：组合策略、有效项统计、expression-sensitive landmark 排除表。
- 修改：geometry orchestrator 与测试；不得接 SAEHD 主图。
- 测试：DST 眼口变化不改变 identity target、SRC 几何变化可检测、左右角色不可互换。
- 完成：职责表、测试、Summary/Review/SHA。