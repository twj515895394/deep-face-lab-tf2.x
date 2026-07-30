# B6-10 Scene Cut、Tracking Lost、Gap、Config变化Reset与多脸隔离

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-08/09；阻塞B6-11/12。
- 目标：统一决定Temporal state何时更新、跳过或重置，防止拖影、跨场景和跨人物污染。

## Reset触发

- scene cut（优先使用上游信号；无信号时使用冻结的低成本frame/global histogram proxy）。
- frame index非连续或gap超过阈值。
- face tracking lost/ambiguous/reappeared。
- model/template/config hash改变。
- face scale/position/pose瞬变超过硬阈值。
- Warp/Shape Mask连续invalid超过阈值。
- worker/session/video生命周期变化。

## 输出

`TemporalUpdateDecision(update,reset,skip,reason,match_confidence)`，reason稳定。reset在应用新样本前执行；新state由当前有效样本初始化，不使用旧滤波值。

## 多脸

每脸独立key/state/filter。检测顺序交换不得交换state；两脸接近导致匹配歧义时双方Temporal关闭/重置，不猜identity。某脸invalid不影响其他脸。

## Scene Cut边界

不得依赖输出merge图造成反馈；应使用原dst frame或上游frame_info。阈值和proxy在B6-01/B6-13视频fixtures冻结。

## Forbidden

不保留上一场景mask；不跨视频任务复用；不把list index当track；不吞worker/OOM；不无限保存失踪face state。

## 测试

`test_batch6_temporal_reset.py`覆盖所有reset reason、frame gap、scene cut、config/hash、丢脸重现、多脸交换/交叉/歧义、单脸invalid隔离、state eviction和reset后无拖尾。

## 完成定义

update/skip/reset顺序唯一，多脸和scene边界安全；Summary、Review、SHA完整。
