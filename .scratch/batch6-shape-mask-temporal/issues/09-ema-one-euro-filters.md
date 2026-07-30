# B6-09 EMA与One Euro Filter实现、参数语义与确定性

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-02/08；阻塞B6-10/11。
- 目标：实现不依赖Merger的纯Temporal filters，用于landmark/shape power/mask diagnostics等低维量；不直接处理视频帧图像。

## EMA

`y_t = alpha*x_t + (1-alpha)*y_{t-1}`；`temporal_strength`到alpha的映射固定、单调、0表示无平滑。首个有效样本直接初始化；invalid样本不更新或触发reset由调用策略明确。

## One Euro

实现标准低通和导数自适应：`min_cutoff/beta/d_cutoff`、基于帧时间间隔或冻结fps。若无可靠timestamp，使用frame index和明确fps参数；禁止wall-clock。dt<=0、gap过大返回reset-required。

## API

纯状态dataclass和`update(value, frame_index/timestamp)->FilterUpdateResult(value,state,valid,reason)`；支持标量和固定shape float32数组，shape变化拒绝。输入/输出finite，不原地修改。

## 过滤对象

优先landmark坐标/Hybrid displacement/effective powers/softness等参数，不建议直接对整张mask逐像素One Euro；是否平滑低分辨mask摘要在B6-01后冻结。

## Forbidden

不访问global state；不按处理线程时间；不跨face共享；不自动修复NaN；不把filter state写入模型checkpoint；不做scene reset判断。

## 测试

`test_batch6_temporal_filters.py`覆盖EMA公式、strength边界、OneEuro标准序列、dt/fps、静止噪声与快速运动、shape/nonfinite、determinism、state copy、无输入修改和golden values。

## 完成定义

两种filter为独立可复用纯模块，数学/参数/边界有测试；Summary、Review、SHA完整。
