# B3-10 Landmark Geometry Loss MVP

- 前置：B3-05,B3-08；P0。
- 目标：实现归一化 landmark geometry loss，只约束身份稳定 landmark 子集；逐点 validity mask 后归约为 batch scalar。
- 默认权重 0；与 ratio loss 独立开关、独立日志、独立 effective 状态。
- 修改：复用 `geometry/losses.py` 公共归约函数；不得复制验证逻辑。
- 禁止外部 landmark 网络、Hybrid Landmark、逐帧 SRC/DST 对齐、Merge warp。
- 测试：已知点差、mask、退化样本、float32、梯度有限、权重零和独立开关。
- 完成：索引子集、公式、测试、Summary/Review/SHA。