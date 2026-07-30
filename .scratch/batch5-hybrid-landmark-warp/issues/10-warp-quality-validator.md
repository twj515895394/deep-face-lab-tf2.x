# B5-10 Triangle Flip/Degenerate、Hole、越界与Warp质量Validator

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-07/09；阻塞B5-11。
- 目标：在像素结果进入Merge前验证几何和coverage，决定整帧接受或回退；禁止输出部分坏warp。

## 检查

- source/target triangle finite、面积、方向、area ratio、condition number。
- flipped/degenerate triangle数量和关键region分布。
- point displacement max/percentile。
- coverage比例、内部holes、重叠异常、out-of-bounds比例。
- output finite/range/channel。
- B5-07 decision effective与Template/landmark状态。

## 输出

`WarpQualityResult(valid,reason,metrics,failed_triangles,warnings)`；reason固定如`triangle_flipped`, `triangle_degenerate`, `displacement_excessive`, `coverage_low`, `hole_detected`, `out_of_bounds`, `non_finite`, `ready`。

第一版策略是整帧fallback传统Merge，不做局部三角修补。阈值由B5-01 fixtures和B5-13 A/B冻结；实现不得凭感觉调整。

## Forbidden

不clip坐标掩盖翻转；不补洞后声称几何valid；不按异常文本匹配；不吞OOM/OpenCV错误；不保留上一帧warp（B6才有Temporal）。

## 测试

`test_batch5_warp_quality.py`覆盖每个reason、阈值边界、关键jaw翻转、非关键小面积、holes、coverage、越界、nonfinite、整帧fallback和metrics determinism。

## 完成定义

validator与warp core解耦，所有accept/fallback由结构化结果决定；Summary、Review、SHA完整。
