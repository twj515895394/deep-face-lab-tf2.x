# B5-01 Batch 4产物与Merge真实锚点复核、坐标/拓扑/Fixtures

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；阻塞B5-02/03/04/08。
- 目标：Batch4完成后读取最终`.srcshape`和当前Merge代码，冻结所有坐标空间、调用顺序、默认值和测试fixtures。本票不实现Hybrid/Warp。

## 审计

`MergeMaskedFace`中的dst landmark、`face_mat/face_output_mat`、predictor input/output、mask resize/inverse warp；`MergerConfigMasked`构造/eq/get_config/to_string；Interactive session重建与frame config传播；最终Template loader/runtime object。

## 冻结坐标

区分frame pixel、aligned predictor canvas、canonical template normalized、hybrid canvas、output/super-resolution canvas；每个API写清shape/dtype/方向和变换矩阵。冻结68点索引、mirror map、triangle topology版本和测试golden data。

## In Scope

- 差异表`CONFIRMED/CHANGED/REMOVED/NEW`。
- 单脸/多脸、正脸/侧脸/表情/遮挡/极端点fixtures。
- `source_shape_power=0`基线图像hash/数值容差。
- 当前Merge顺序和允许插入点。

## Forbidden

不改Merge代码、不猜最终Template字段、不复制第二套landmark schema、不伪写视觉/GPU结果。

## 测试/完成

`test_batch5_contracts.py`验证坐标roundtrip、矩阵方向、point count、baseline fixtures、MergerConfig/session构造。修订所有受影响票并独立Review后才能签发后续基础票。
