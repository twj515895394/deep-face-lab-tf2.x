# B5-06 DST Expression Offset提取与Hybrid Landmark Composition

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-04/05；阻塞B5-07/09。
- 目标：把posed src stable geometry与dst当前expression offsets合成为Hybrid Landmark；不Warp像素。

## 输入输出

输入：`posed_src_landmarks[68,2]`、`dst_landmarks[68,2]`、dst neutral/reference proxy、RegionSpec、`source_shape_power`、confidence。输出：hybrid landmarks、per-region weights、composition diagnostics、valid/reason。

## Composition

- 先在同一pose/canvas中计算dst相对稳定reference的局部offset。
- stable points主要取posed src；dynamic points保留dst offset；mixed points按冻结权重blend。
- power作为src identity贡献全局乘子，不直接缩放dst expression幅度。
- power=0输出必须与dst landmarks在容差内一致。
- power=1也不得把eyes/mouth/brows变成src静态形状。
- 左右对称和face side语义按68点表固定。

## 无Neutral Frame策略

第一版不得假设视频有neutral frame。reference proxy只能由当前dst landmarks的stable/mixed点和canonical pose构造；不得跨帧状态（Temporal属于B6）。具体纯函数在B5-01后冻结。

## Forbidden

不按batch/frame索引配src素材；不使用前后帧；不重新检测landmark；不改变Template；不clip掩盖拓扑翻转；不做Mask。

## 测试

`test_batch5_hybrid_landmarks.py`覆盖power 0/0.5/1、mouth/eyes/brows动作保持、jaw/face width迁移、pose不重复应用、左右对称、极端expression、nonfinite、点数错误、determinism和golden fixtures。

## 完成定义

Hybrid公式和region权重唯一；zero power等价；动态表情有量化测试；Summary、Review、SHA完整。
