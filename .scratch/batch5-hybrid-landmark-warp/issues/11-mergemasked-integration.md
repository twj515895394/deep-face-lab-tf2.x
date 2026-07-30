# B5-11 MergeMasked接入顺序、逐脸Fallback与零强度等价

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-02/03/10；阻塞B5-12/13。
- 目标：把已验证Warp最小接入`MergeMaskedFace`，保持传统mask/color/blend顺序和多脸行为；power=0像素等价。

## 插入顺序草案

```text
dst aligned face -> predictor -> predicted face/masks
-> [optional validated shape warp on predicted face and corresponding predicted mask]
-> existing mask mode/XSeg/erode/blur
-> inverse face_output_mat
-> existing color/seamless/blend
```

B5-01后以真实代码冻结。若warp image，相关predicted mask必须采用同一geometry mapping或明确保持语义；不得只warp RGB造成mask错位。

## 规则

- 每个检测脸独立decision/Hybrid/Warp/fallback，不影响同帧其他脸。
- invalid frame/face回到该脸传统路径。
- power=0/Gate关不加载Template、不分配warp buffers、不改变输出。
- 原有super-resolution、mask modes、XSeg、color transfer、raw modes分别建立兼容矩阵；raw-predict语义需明确。
- 失败日志限频并含frame/face index、reason，不含完整路径/数组。

## Forbidden

不改predictor输出接口；不把warp放在错误坐标空间；不改变face_mat/face_output_mat含义；不吞OOM；不实现Shape-aware Mask/Temporal。

## 测试

`test_batch5_mergemasked_shape_warp.py`覆盖power0像素/hash等价、单/多脸、每种mask/raw/superres/color组合的核心代表、fallback、RGB/mask对齐、异常传播、input不变和执行顺序spy。

## 完成定义

Warp真实进入Merge且零强度等价；逐脸fallback、旧模式兼容和顺序有证据；Summary、Review、SHA完整。
