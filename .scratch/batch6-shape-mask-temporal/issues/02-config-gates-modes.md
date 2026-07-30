# B6-02 Shape-aware Mask/Temporal配置Schema、Gate、模式与默认关闭

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-01；阻塞B6-05/07/09/11。
- 目标：定义Mask与Temporal两个独立可组合Gate和唯一默认值来源，兼容旧MergerConfig/session。

## Gate

沿用增强框架：`merge.enabled && merge.shape_aware_mask`与`merge.enabled && merge.temporal_stabilization`。Warp仍由Batch5独立Gate控制；Shape Mask requested但Warp unavailable时按冻结policy disabled/fallback。

## 参数草案

`shape_mask_mode='off|source_contour|hybrid'`、`shape_mask_power=0`、`shape_mask_softness`、`temporal_mode='off|ema|one_euro'`、`temporal_strength=0`、`temporal_reset_gap=1`、`one_euro_min_cutoff/beta/d_cutoff`。最终范围在B6-01后冻结。

## 规则

- 两项默认off/0，关闭时不创建state、不分配额外map。
- requested/effective/reason分别记录。
- 旧session缺字段默认关闭；`copy/get_config/eq/to_string`完整。
- Temporal不能自动因视频存在而启用；Mask不能自动因Template存在而启用。
- 配置改变导致state reset，由B6-10处理。

## Forbidden

不复制GUI默认；不创建第三套全局Gate；不将非法值clip成正强度；不让Temporal依赖wall clock；不混入Batch7 loss参数。

## 测试

`test_batch6_shape_mask_temporal_config.py`覆盖所有Gate组合、旧session、非法/unknown、zero strength、copy/eq/serialize、模式组合、默认唯一来源和reset-required flag。

## 完成定义

Schema、Gate、状态和兼容有测试/文档；Summary、Review、SHA完整。
