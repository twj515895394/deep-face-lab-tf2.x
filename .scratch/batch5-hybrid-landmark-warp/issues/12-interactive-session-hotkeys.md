# B5-12 InteractiveMerger配置、Session兼容、Hotkeys与预取一致性

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P1；前置B5-02/11；阻塞B5-13。
- 目标：将Shape Warp参数纳入现有MergerConfig复制、相等比较、session保存恢复、逐帧传播和快捷键；不改变底层Warp算法。

## 代码锚点

`MergerConfigMasked.__init__/copy/get_config/__eq__/to_string/ask_settings`，`InteractiveMergerSubprocessor.Frame/ProcessingFrame`，session pickle重建，`masked_keys_funcs`，prev/next/override config传播，prefetch结果接受条件`frame.cfg == pf_result.cfg`。

## 设计

- 增加power增减/开关的固定热键，避免与现有键冲突；内部英文key不改。
- `get_config`包含新字段，旧session缺字段使用默认0；新session恢复后Template identity/hash需重新验证，不信任pickle里的runtime context。
- config改变后当前帧及受传播帧标记未完成；prefetch旧cfg结果因不相等被丢弃。
- Template context是会话级，不序列化完整arrays到每Frame。
- 非interactive批处理使用同一config字段和Gate。

## Forbidden

不pickle loader/文件句柄；不在session中嵌入用户Template内容；不改变旧hotkey含义；不让旧prefetch结果覆盖新power；不做Temporal。

## 测试

`test_batch5_interactive_shape_warp.py`覆盖旧/new session、copy/eq、hotkey边界、逐帧传播、prefetch stale result、模型iter变化、Template hash变化、interactive/batch一致、中文说明和power0。

## 完成定义

旧session可恢复，配置传播和结果丢弃正确，runtime context不被不安全pickle；Summary、Review、SHA完整。
