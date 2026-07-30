# B6-07 MergeMasked Mask顺序接入、RGB/Mask一致与零影响

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-05/06；阻塞B6-11/12/13。
- 目标：把validated Shape Mask最小接入现有local mask流程，保持erode/blur/inverse affine/color/blend语义；Gate关/power0逐像素等价。

## 插入点

在B6-01基于真实代码冻结：现有mask mode/XSeg生成`wrk_face_mask_a_0`后、noise threshold和subres/local erode/blur前，以Shape candidate替换或组合；不得在frame-space inverse warp后再混local mask。

## 规则

- Batch5若Warp RGB和predicted mask，Shape support必须同一几何空间。
- Shape invalid时使用原`wrk_face_mask_a_0`。
- Gate关/power0不生成support、不分配额外大buffer、不改mask。
- raw modes、original、seamless、hist-match、superres分别明确行为。
- 多脸每脸独立mask/decision；最终合成顺序保持现有实现。
- OOM/OpenCV错误传播并含上下文。

## Forbidden

不改变旧mask mode编号/含义；不重复erode/blur；不修改颜色迁移；不做Temporal；不让source mask覆盖整帧背景。

## 测试

`test_batch6_mergemasked_shape_mask.py`覆盖power0 hash、mask modes、XSeg、raw/original/seamless/superres、invalid fallback、多脸、RGB-mask空间、执行顺序spy、buffer/输入不变和异常传播。

## 完成定义

Shape Mask真实进入正确位置，zero path等价，所有旧模式有兼容证据；Summary、Review、SHA完整。
