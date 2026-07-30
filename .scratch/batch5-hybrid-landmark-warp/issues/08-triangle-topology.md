# B5-08 Fixed 68-point Triangle Topology、版本与Coverage契约

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-01/04；阻塞B5-09。
- 目标：定义唯一、固定、可版本化的三角网格连接；不计算Hybrid或Warp图像。

## 设计

- `TRIANGLE_TOPOLOGY_DLIB68_V1`为有序三元组tuple，点索引0..67，无重复点/重复三角。
- 覆盖jaw/cheek/chin、nose、eyes周边、mouth周边和内部face region；不得跨越不合理语义边界。
- 可增加固定边界辅助点，但若使用必须作为独立schema扩展并由src/dst同构生成，不能临时添加。
- topology version写入diagnostics，不写回`.srcshape`除非B4 consumer contract允许扩展。

## Validation

纯函数检查索引、重复、canonical triangle area、方向一致性、edge manifold/覆盖、未覆盖关键region。运行时每帧另由B5-10检查变形后质量。

## Forbidden

不在每帧Delaunay导致拓扑漂移；不根据landmark顺序动态排序；不使用随机或图像内容；不悄悄修改68点定义；不实现Warp。

## 测试

`test_batch5_triangle_topology.py`覆盖固定hash、索引/重复、canonical面积、左右对称、所有关键region覆盖、序列化稳定、非法拓扑和辅助点策略。

## 完成定义

Topology常量和版本唯一、hash固定、coverage有证据；B5-09/10只引用不复制；Summary、Review、SHA完整。
