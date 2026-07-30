# Batch 6 Shape-aware Soft Mask + Temporal 执行计划

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`，当前禁止编码。

规则：Batch5完成后先B6-01审计最终WarpResult/Quality/coverage、Merge顺序、多脸和session；Mask与Temporal分别可开关；默认关闭；无可靠track不得跨帧复用；任何异常回退Batch5/传统路径；不做Batch7训练Loss；一次一票并完成测试/Review闭环。

Waves：0审计；1配置/contour/temporal identity；2soft mask/composition/fallback；3Merge接入；4filter/reset；5lifecycle/diagnostics；6矩阵；7收口。
