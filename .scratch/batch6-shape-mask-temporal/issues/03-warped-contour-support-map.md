# B6-03 Warped Contour Support、Coverage与Distance Map

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-01；阻塞B6-04。
- 目标：把Batch5有效Warp的coverage/Hybrid contour转换为Shape Mask可用的有限、确定性support maps；不做最终mask组合。

## 输入输出

输入：Hybrid landmarks、Warp coverage、WarpQuality、output size。输出：`ContourSupportMap`，含outer contour raster、inside support、normalized distance、coverage-valid region、valid/reason。

## 规则

- 只在WarpQuality valid且坐标同空间时生成。
- outer contour主要使用jaw/cheek/chin和必要额头闭合策略；闭合点/曲线在B6-01 fixtures冻结。
- distance范围固定[0,1]或[-1,1]，与B3 SDF概念区分并文档化。
- coverage=0区不得成为可靠source contour。
- 生成CPU/OpenCV确定性、float32、1通道；输入不原地修改。
- 多脸各自独立map。

## Forbidden

不使用predicted/dst/XSeg mask决定几何support；不补Batch5 holes后声称valid；不跨帧平滑；不调用外部segmentation；不输出NaN。

## 测试

`test_batch6_contour_support.py`覆盖identity/warped jaw、coverage holes、闭合策略、不同resolution、越界、invalid quality、多脸、determinism、finite/range和golden maps。

## 完成定义

support map的坐标、闭合、coverage和reason唯一；供B6-04消费；Summary、Review、SHA完整。
