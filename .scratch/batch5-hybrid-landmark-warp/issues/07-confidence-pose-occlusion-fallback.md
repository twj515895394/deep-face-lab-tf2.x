# B5-07 Template/Landmark Confidence、极端姿态、遮挡与逐帧Fallback

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-03/06；阻塞B5-10/11。
- 目标：在Warp前决定当前帧是否安全使用Hybrid，输出effective power和稳定reason；不自行Warp或日志刷屏。

## 输入

Template confidence/identity check、pose fit residual、dst landmark validity、yaw/pitch proxy、occlusion/face bounds、Hybrid displacement statistics、用户power。

## 输出

`ShapeWarpDecision(requested,effective,effective_power,reason,warnings,metrics)`。reason固定如`disabled`, `template_invalid`, `low_confidence`, `pose_extreme`, `occluded`, `landmark_invalid`, `displacement_excessive`, `ready`。

## 策略

- 全局身份/Template invalid：本会话Shape disabled。
- frame-level风险：仅当前帧回退传统Merge。
- 接近阈值可连续衰减effective power，公式和范围在fixtures固定；超过硬阈值直接0。
- 不使用前帧状态，不做EMA；Batch6负责Temporal。
- OOM、I/O、worker错误不是frame fallback，必须传播。

## Forbidden

不吞异常；不因低confidence删除Template；不自动提高power；不按视觉像素黑盒判断；不把遮挡帧结果缓存给后续帧。

## 测试

`test_batch5_shape_warp_decision.py`覆盖所有reason、阈值边界、衰减单调性、身份fatal/帧fallback、extreme yaw、遮挡、异常displacement、power0、无跨帧state和warning限频key。

## 完成定义

session/frame错误边界和effective power可复现；供B5-10/11唯一使用；Summary、Review、SHA完整。
