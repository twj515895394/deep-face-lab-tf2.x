# Batch 5 Hybrid Landmark + Piecewise Warp 执行计划

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`，当前禁止编码。

规则：先B5-01读取最终`.srcshape`、MergeMasked/MergerConfig/session真实代码；一次一票；默认关闭；`source_shape_power=0`零影响；任何frame-level异常回退传统几何；不做Mask/Temporal；每票实现→测试→Summary→Review→修复。

Waves：0审计；1配置/Template Context/Region；2Pose/Expression/Confidence；3Topology/Warp/Validator；4Merge/Interactive；5矩阵；6收口。Batch6启动前必须重新审计最终Hybrid/Warp输出与quality flags。
