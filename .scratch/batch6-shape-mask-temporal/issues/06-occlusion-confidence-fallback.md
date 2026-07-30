# B6-06 Occlusion、Coverage、Confidence与Shape Mask Fallback

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-05；阻塞B6-07/12。
- 目标：决定当前脸/帧Shape Mask是否可用以及effective power；不做Temporal或最终Merge。

## 输入

Batch5 WarpQuality/decision、Template confidence、source support coverage、existing mask/XSeg overlap、occlusion proxy、area change、用户power。

## 输出

`ShapeMaskDecision(requested,effective,effective_power,reason,metrics,warnings)`。reason固定如`disabled`, `warp_invalid`, `coverage_low`, `template_low_confidence`, `occlusion_high`, `mask_overlap_low`, `area_change_excessive`, `ready`。

## 策略

- session级Template invalid关闭Shape Mask；frame级风险只回退该脸existing mask。
- threshold附近允许连续衰减power，超过硬阈值为0；公式由B6-01 fixtures冻结。
- XSeg/occlusion优先保护真实遮挡，source contour不得覆盖手、头发、物体。
- 不使用上一帧决定；B6-10负责state/reset。
- OOM、worker、I/O不是fallback，必须传播。

## Forbidden

不吞异常；不把coverage hole自动填满；不因source confidence高绕过XSeg；不删除/修改Template；不缓存本帧decision到其他脸。

## 测试

`test_batch6_shape_mask_decision.py`覆盖全部reason、阈值边界、连续衰减、occlusion/XSeg、area变化、multi-face隔离、session/frame错误、power0、warning key和nonfinite。

## 完成定义

安全决策与mask公式解耦，回退语义可复现；Summary、Review、SHA完整。
