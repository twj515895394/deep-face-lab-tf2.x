# B6-13 Regression、Performance、Temporal/Visual A/B与Windows矩阵

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-11/12；阻塞B6-14。
- 目标：分层验证Shape Mask和Temporal在真实视频中的轮廓、遮挡、抖动、重置、多脸、性能与兼容；自动测试不等价视觉结果。

## 自动Gate

全部B6 tests + Batch1–5回归；Mask/Temporal分别关闭和组合；power/strength0输出等价；mask modes/XSeg/raw/superres/color；multi-face identity；scene cut/gap/lost/reset；worker/session/rewind；异常和资源清理。

## Visual A/B

固定模型、Template、Warp power和视频，比较：A传统/B Batch5 Warp/C +Shape Mask/D +EMA/E +OneEuro。素材含正侧脸、快速转头、张嘴闭眼、头发/手遮挡、scene cut、镜头闪切、检测丢失、多脸交叉。指标：src contour retention、mask edge/background leak、occlusion preservation、landmark/mask jitter、motion lag/ghosting、reset恢复时间、expression、artifact。

## Performance

每脸support/mask/filter/state/diagnostic耗时；整体fps/RSS/worker；state数量与eviction；debug关闭开销。Gate关和strength0不得有显著额外成本。预算B6-01后冻结。

## Windows/长视频

真实predictor + Merger短/长视频，interactive/batch、session/rewind、scene cut、多脸。记录CPU/GPU、process_count、输出帧完整性、crash/OOM、state cleanup。未执行写`NOT EXECUTED`。

## 状态

`CODE/AUTOMATED/WINDOWS/PERFORMANCE/VISUAL/TEMPORAL-STABILITY`分别记录。视觉用`PROMISING/NEUTRAL/REGRESSION/INCONCLUSIVE`并附metrics/片段约束。

## 完成定义

矩阵、命令、报告模板和真实结果完整；无跨脸/跨场景污染；zero path、遮挡和旧模式无回归；Summary、Review、SHA完整。
