# B6-08 Per-face/Track Temporal State、Identity Key与生命周期契约

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-01；阻塞B6-09/10。
- 目标：定义可以安全保存上一帧几何/Mask测量的最小状态容器和face identity；不实现滤波。

## 关键风险

当前Merger可能只有每帧`landmarks_list`和处理顺序，没有稳定track id。检测顺序在多脸场景可变化，不能以list index跨帧绑定人物。

## 设计

`TemporalFaceKey`优先使用上游稳定track id；若不存在，采用严格的短期几何匹配器（bbox/landmark center/scale/IoU/embedding禁止）并只在唯一高置信匹配时建立state。匹配歧义或多候选时禁用该脸Temporal并重置，不猜最近index。

`TemporalFaceState`含last_frame_index、config/template/model hash、filtered landmarks/parameters/mask摘要、filter internal state、validity、reset reason；不保存完整原始帧或用户路径。

`TemporalStateStore`按key隔离、有容量上限、显式begin/end/reset/evict；worker/session所有权在B6-11冻结。状态不可在多个视频任务间复用。

## Forbidden

不使用face list index作为稳定identity；不引入外部人脸识别网络；不把不同模型/Template/config状态复用；不pickle完整图像；不在无可靠匹配时强行平滑。

## 测试

`test_batch6_temporal_state.py`覆盖稳定track、无track唯一匹配、检测顺序交换、两脸交叉、歧义禁用、容量/eviction、hash变化、视频任务结束、内存上限和无隐私数据。

## 完成定义

identity/state/lifecycle可独立测试，任何歧义安全关闭；供B6-09/10唯一使用；Summary、Review、SHA完整。
