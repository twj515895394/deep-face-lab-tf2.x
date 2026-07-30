# B5-05 Canonical Source Template到当前DST Pose/Canvas变换

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-03/04；阻塞B5-06。
- 目标：把canonical src geometry放入当前dst aligned face pose与尺度，输出`posed_src_landmarks[68,2]`；不加入expression、不Warp图像。

## 算法边界

使用当前dst landmarks和B5-01冻结的稳定参考点估计相似/仿射pose transform。输入canonical template、dst landmarks、face type/output size、confidence；输出posed landmarks、transform matrix、fit residual、valid/reason。

## 规则

- 只用不易受表情影响的参考点；禁止mouth/eyelid主导pose。
- transform方向、坐标空间和invert语义固定。
- 极端yaw/pitch、参考点退化、非有限、残差超阈值返回invalid，不输出部分结果。
- power=0调用方不应执行本函数。
- 输出float32有限，轻微越界可保留给后续validator，不在此无条件clip。

## Forbidden

不做expression offset、不修改dst landmarks、不调用3D模型、不通过图像重新检测点、不Warp像素。

## 测试

`test_batch5_template_pose_transform.py`覆盖identity/translation/scale/rotation、正反矩阵、stable参考点、mouth变化不影响pose、degenerate、极端pose、NH坐标转换、golden fixtures和determinism。

## 完成定义

pose transform API、参考点、残差阈值和失败reason有测试；供B5-06唯一消费；Summary、Review、SHA完整。
