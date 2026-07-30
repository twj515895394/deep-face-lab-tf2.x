# B5-13 Unit/Integration、Visual A/B、Performance与Windows GPU矩阵

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-11/12；阻塞B5-14。
- 目标：分层证明Hybrid/Warp正确、兼容、可回退且有可接受视觉/性能；自动测试不等价视觉或GPU。

## 自动Gate

覆盖全部B5 tests、Batch1–4回归、power0像素等价、Template invalid fallback、多脸、session、mask/raw/superres/color代表矩阵、异常传播、determinism和资源清理。记录OS/Python/test count/EXIT/SHA。

## Visual A/B

固定模型/Template/dst视频/Merge参数，比较power 0、0.25、0.5、1.0。帧集必须含正脸、侧脸、转头、张嘴、闭眼、遮挡、快速运动、多脸。指标：脸宽/jaw/chin retention、eyes/mouth expression、triangle artifact、mask错位、边缘、身份自然度；保存逐帧diagnostics和盲评说明。

## Performance

记录每脸Hybrid、Warp、Validator耗时，整体fps、RSS、临时buffer和多worker扩展。power0不得产生显著额外成本；预算在B5-01后冻结。

## Windows/GPU

Warp本身CPU，但真实SAEHD predictor + Merger需执行Windows短片和长片，记录GPU/CPU、worker、crash/OOM、session resume、输出文件完整性。失败保留日志；未执行写`NOT EXECUTED`。

## 结果状态

`CODE/AUTOMATED/WINDOWS/PERFORMANCE/VISUAL`分别记录。视觉使用`PROMISING/NEUTRAL/REGRESSION/INCONCLUSIVE`，不能只写PASS。

## 完成定义

矩阵、命令、素材约束、指标、报告模板和真实状态完整；所有P0/P1回归关闭；Summary、Review、SHA完整。
