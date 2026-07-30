# B6-05 Predicted/DST/XSeg与Source Shape Mask组合契约

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-02/04；阻塞B6-06/07。
- 目标：在local predicted space组合Shape candidate与现有mask语义，输出`wrk_shape_mask_candidate`；不接MergeMasked顺序。

## 输入

source shape mask、`prd_face_mask`、`prd_face_dst_mask`、可选XSeg-prd/XSeg-dst、当前`mask_mode`、shape power/mode。所有输入需同resolution/float32/[0,1]。

## 模式草案

- `source_contour`：以source mask限定/扩展predicted mask外轮廓，但不无条件覆盖内部置信。
- `hybrid`：source contour提供几何support，现有selected mask提供像素置信，XSeg仍作为语义/遮挡约束。
- 组合公式必须逐mask_mode冻结；避免简单`max`扩大到背景或`min`裁回dst轮廓。

建议输出：`mask = selected_existing * inner_confidence + source_mask * contour_weight`并由support/coverage限制；精确公式在B6-01/B6-13 A/B后冻结。

## 规则

- shape power=0输出selected existing mask逐像素等价。
- source invalid时回selected existing。
- XSeg模式仍保留原有语义，不能被source mask绕过。
- 不在此erode/blur/inverse warp。
- 输出metrics含新增/移除面积、overlap和coverage。

## Forbidden

不改变`mask_mode_dict`旧值；不把XSeg缺失吞成全1；不跨分辨率隐式resize；不做Temporal；不对RGB操作。

## 测试

`test_batch6_mask_composition.py`覆盖mask modes0..9代表/全矩阵、power0、invalid source、XSeg约束、背景泄露、面积指标、range/finite、shape mismatch和golden outputs。

## 完成定义

每种existing mask语义与Shape贡献明确，power0等价；Summary、Review、SHA完整。
