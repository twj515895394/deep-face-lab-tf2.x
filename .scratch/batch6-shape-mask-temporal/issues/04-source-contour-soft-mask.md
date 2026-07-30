# B6-04 Source Contour Soft Mask生成、Softness与边缘权重

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-03；阻塞B6-05。
- 目标：从ContourSupportMap生成表示src脸型轮廓的soft mask候选；不与现有predicted/dst/XSeg mask组合。

## 算法

- inside support为主体；根据normalized distance和`shape_mask_softness`生成单调soft edge。
- coverage-valid region作为上限，coverage缺失区权重为0。
- `shape_mask_power`只控制候选贡献，不改变几何support。
- 输出`SourceShapeMask(mask, edge_weight, valid, reason, metrics)`，float32 `[H,W,1]`、范围[0,1]。
- 0 power调用方不应执行；若执行用于测试，输出贡献为0而基础candidate仍可验证。

## 边界

- softness=0的离散行为需明确且不产生锯齿爆炸；建议最小epsilon或hard edge仅测试模式。
- contour太小/大、coverage低、nonfinite返回invalid。
- 不应用MergerConfig erode/blur；这些仍在现有下游顺序中。

## Forbidden

不读取predicted/dst/XSeg；不做颜色blend；不跨帧；不将mask写回Template或输出目录；不自动修复invalid support。

## 测试

`test_batch6_source_shape_mask.py`覆盖softness单调、power、coverage限制、range/finite、resolution、invalid support、edge width、input不变、determinism和golden masks。

## 完成定义

候选mask与现有mask解耦，softness/coverage/invalid语义有测试；Summary、Review、SHA完整。
