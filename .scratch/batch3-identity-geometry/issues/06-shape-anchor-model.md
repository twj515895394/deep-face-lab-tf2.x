# B3-06 Shape Anchor 数据模型与身份绑定

- 前置：B3-01；P0。
- 目标：定义 Batch 3 Anchor 内存/文件契约，复用 Batch 2 stable sample identity 与 dataset fingerprint。
- 字段：schema_version、role=src、dataset_fingerprint、feature_version、landmark_layout、normalized_anchor、validity、created_by；精确 shape 在 B3-01 后冻结。
- 禁止实现 Batch 4 `model.srcshape`、Merge template、逐帧 SRC/DST 配对或新样本 ID。
- 修改建议：`core/enhancements/geometry/anchor.py` 与纯函数测试。
- 测试：round-trip、identity mismatch、wrong role/version/layout、float64 拒绝或显式转 float32。
- 完成：Schema、测试、Summary、Review、SHA。