# B3-09 Ratio Geometry Loss MVP

- 前置：B3-05,B3-08；P0。
- 目标：实现可独立开关的 ratio loss，对有效 SRC 身份比例与 Anchor 比较；输出 batch scalar 与有效样本统计。
- 默认权重 0；无有效样本时 effective=false，不得制造零除或伪 loss。
- 修改建议：`core/enhancements/geometry/losses.py`；先 NumPy reference，再 TensorFlow 对齐测试。
- 禁止接 optimizer、混入 appearance/region/boundary/frequency、约束 DST 表情比例。
- 测试：零差、已知差、mask、梯度有限、权重零等价、determinism。
- 完成：公式、实现、测试、Summary/Review/SHA。