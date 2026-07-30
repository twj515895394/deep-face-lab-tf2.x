# B3-08 Landmark/Ratio 特征与有效性

- 前置：B3-07；P0。
- 目标：定义平移/尺度归一化 landmark 与稳定比例特征，输出 feature tensor 和 validity mask。
- 比例仅覆盖身份稳定区域：脸宽、下颌、下巴、颧骨；眼口开合等表情量不得进入 identity target。
- 修改建议：`core/enhancements/geometry/features.py`；纯 NumPy 参考实现先行。
- 测试：平移/尺度不变性、镜像规则、退化点、缺点、NaN、batch 与 float32。
- 禁止姿态网络、Hybrid Landmark、外部模型。
- 完成：公式/索引表、测试、Summary/Review/SHA。