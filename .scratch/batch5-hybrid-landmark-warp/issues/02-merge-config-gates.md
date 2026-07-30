# B5-02 Merge配置Schema、Gate、`source_shape_power`与默认关闭

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-01；阻塞B5-11/12。
- 目标：在增强配置和MergerConfig中定义唯一Shape Warp参数来源；默认关闭且0严格走传统路径。

## 字段草案

核心增强Gate沿用`merge.enabled && merge.source_shape_template && merge.shape_aware_warp`。Merger运行参数：`source_shape_power=0.0`、`shape_warp_mode='off'`、`shape_confidence_threshold`、`shape_fallback='traditional'`。最终字段在B5-01后冻结；默认值只在核心配置/构造器一处定义，GUI只传用户修改项。

## 规则

- power范围[0,1]；0时不加载Template、不构造Hybrid、不Warp。
- mode第一版`off|piecewise_affine`；unknown回off并告警。
- 配置requested与runtime effective分开，reason稳定。
- `get_config/__eq__/to_string/copy`和旧session reconstruction兼容。
- hotkey改变power只影响当前/后续frame配置，不改变Template身份。

## Forbidden

不新增第二个同义power；不把默认设非0；不改旧mask/mode键；不因Template存在自动启用；不在B5实现GUI页面。

## 测试

`test_batch5_shape_warp_config.py`覆盖旧config/session、缺字段、非法数值、Gate组合、power=0、copy/eq/serialize、unknown、中文显示不改内部英文值和默认值单一来源。

## 完成定义

Schema、requested/effective/reason、旧session兼容和zero gate有测试、文档、Summary、Review、SHA。
