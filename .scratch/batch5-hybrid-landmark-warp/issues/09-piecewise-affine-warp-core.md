# B5-09 Piecewise Affine Warp核心、Interpolation与Coverage Map

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-06/08；阻塞B5-10。
- 目标：把预测脸从dst landmark geometry局部变形到Hybrid geometry，输出warped image及coverage；不接MergeMasked。

## API

`piecewise_affine_warp(image, source_points, target_points, topology, output_shape, interpolation, border_mode) -> WarpResult`。明确方向：source为预测脸当前dst几何，target为Hybrid几何；禁止调用方猜invert。

`WarpResult`含image float32、coverage mask、triangle status、valid/reason、timing。输入image通道1/3均支持，shape/dtype/range按B5-01冻结。

## 实现规则

- 每三角计算局部affine，使用固定拓扑和确定性绘制顺序。
- 三角边界避免裂缝：固定rasterization/overlap策略和coverage union。
- interpolation第一版image用cubic/linear之一、mask用linear；具体由A/B与测试冻结，不能按调用方任意混用。
- border默认constant 0或replicate按坐标空间冻结；coverage区分真实warp和填充。
- 先纯NumPy/OpenCV CPU路径；不引入GPU custom op。

## Forbidden

不做Delaunay/TPS/neural warp；不自动修复翻转三角；不融合原图；不计算Shape mask；不吞OpenCV错误；不原地修改输入。

## 测试

`test_batch5_piecewise_affine_warp.py`覆盖identity像素等价、translation/scale/local jaw、1/3通道、coverage无洞、边界连续、determinism、input不变、错误point/topology/output、性能基线和golden images。

## 完成定义

方向、rasterization、interpolation、coverage和失败reason固定；所有triangle质量判断留给B5-10；Summary、Review、SHA完整。
