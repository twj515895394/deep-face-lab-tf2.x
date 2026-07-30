# B3-02 配置 Schema、默认值、Feature Flags 与 options-json

## 1. 基本信息

- Ticket ID：`B3-02`
- 状态：`BLOCKED-BY-B3-01`
- 优先级：P0
- 前置 Ticket：B3-01
- 阻塞 Ticket：B3-04、B3-07、B3-12、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`
- 建议提交粒度：配置实现/测试一个提交，文档/Review 一个提交

## 2. 背景与问题

`core/enhancements/config.py` 已有唯一增强配置入口和以下训练门：

```text
training.enabled
training.loss_hooks
training.identity_geometry
training.curriculum
```

当前短草案曾提出额外的 `geometry.enabled`。独立 Review 判定这会形成两个控制同一能力的开关并增加 requested/effective 歧义，因此本 Ticket 明确取消 `geometry.enabled`。

Batch 3 需要新增的是“参数 section”，不是第二套 feature gate。

## 3. Scope

### 3.1 In Scope

- 扩展 `DEFAULT_ENHANCEMENT_CONFIG`，增加只保存参数的 `geometry` section。
- 保留现有 `training.*` 布尔门作为唯一启停来源。
- 定义数值、字符串、路径和 curriculum 参数解析器。
- 定义 requested/effective/reason 状态解析接口。
- 支持 persisted options 与 `--options-json` 嵌套对象 roundtrip。
- 对旧 options、未知字段、非法类型和未来 schema 提供明确行为。

### 3.2 Out of Scope

- 不实现 Geometry Loss。
- 不增加 GUI 页面。
- 不修改 SamplingConfig。
- 不自动迁移用户根级字段。
- 不提高 `SUPPORTED_SCHEMA_VERSION`，除非兼容测试证明必须。

### 3.3 Forbidden Changes

- 禁止新增 `geometry.enabled`。
- 禁止在 GUI、CLI 或 SAEHD 中复制默认值。
- 禁止解析失败后隐式启用。
- 禁止把非法正权重裁剪成某个可运行正值；安全结果必须是该项 effective=false。
- 禁止吞掉 OOM、checkpoint 或核心 tensor 错误；配置 fallback 只处理配置自身。

## 4. 当前代码锚点

- `core/enhancements/config.py::DEFAULT_ENHANCEMENT_CONFIG`
- `core/enhancements/config.py::EnhancementConfig.__init__`
- `core/enhancements/config.py::EnhancementConfig.from_mapping`
- `core/enhancements/config.py::EnhancementConfig.is_enabled`
- `core/enhancements/config.py::EnhancementConfig.to_dict`
- `core/enhancements/config.py::normalize_enhancement_config`
- `models/ModelBase.py::ModelBase.load_train_step_config`
- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize_options`

## 5. 冻结 Schema

```json
{
  "schema_version": 1,
  "training": {
    "enabled": false,
    "metadata_sampling": false,
    "loss_hooks": false,
    "identity_geometry": false,
    "curriculum": false
  },
  "geometry": {
    "ratio_weight": 0.0,
    "contour_weight": 0.0,
    "anchor_path": null,
    "min_anchor_confidence": 0.70,
    "min_sample_confidence": 0.50,
    "frontal_yaw_limit_deg": 20.0,
    "warmup_iters": 0,
    "ramp_iters": 0,
    "invalid_sample_policy": "skip"
  }
}
```

说明：

- 字段名在本 Ticket Review 后冻结。
- `ratio_weight` 和 `contour_weight` 默认必须为 `0.0`。
- `invalid_sample_policy` 第一版只接受 `skip`；不实现静默填充或使用上一批值。
- `anchor_path=null` 表示使用默认发现规则，不表示自动启用 Geometry。
- 不提供可配置 feature 列表，避免不同 checkpoint/session 使用不同 R 维。

## 6. Gate 与状态模型

Geometry requested：

```text
training.enabled
AND training.loss_hooks
AND training.identity_geometry
```

Geometry effective 还必须满足：

```text
requested
AND 至少一个权重 > 0
AND 配置合法
AND Anchor/监督输入满足对应 Ticket 的有效性条件
```

建议新增纯函数：

```python
def resolve_geometry_config_state(config: EnhancementConfig) -> dict:
    # 返回稳定键：requested, effective, reason, ratio_weight,
    # contour_weight, curriculum_requested, warnings
```

`reason` 必须是稳定枚举字符串，例如：

```text
disabled_training
disabled_loss_hooks
disabled_identity_geometry
zero_weights
invalid_geometry_config
requested_waiting_for_anchor
ready
```

配置层不得声称 runtime anchor 已加载成功；`requested_waiting_for_anchor` 由配置层输出，B3-07 再得到最终 runtime effective。

## 7. 解析规则

- bool 继续复用 `_safe_bool`。
- float 必须拒绝 bool、NaN、Inf、负数。
- iteration 字段必须是 `int >= 0`，拒绝 float 字符串的隐式截断。
- 路径接受 `None` 或非空字符串；空白字符串归一化为 `None` 并告警。
- 未知 `geometry` 字段保留 roundtrip 或忽略的策略必须统一：建议保存到 `_extra_geometry_fields` 仅用于 roundtrip，但任何 unknown 不得影响运行。
- 未来更高 schema version 继续使全部增强关闭。

## 8. 实施步骤

1. 在 `DEFAULT_ENHANCEMENT_CONFIG` 增加 `geometry`。
2. 在 `EnhancementConfig.__init__` 增加 `_geometry` 与 geometry warning 容器。
3. 新增 `_safe_non_negative_float`、`_safe_non_negative_int`、`_safe_optional_path`。
4. 在 `from_mapping` 的 known 集合加入 `geometry`。
5. 在 `to_dict` 原样输出规范化 geometry。
6. 新增只读 properties 或 `geometry_config` 快照，禁止调用方直接改 `_geometry`。
7. 新增 `geometry_gate_state()` 或 `resolve_geometry_config_state()`。
8. 验证 `ModelBase.load_train_step_config` 对 nested enhancements 不做错误字符串化。
9. 更新 options-json 示例；不增加交互询问。

## 9. 测试要求

测试文件：`tests/smoke/test_batch3_geometry_config.py`

必须覆盖：

- 完全缺字段的旧模型：所有新值为默认，Geometry 未 requested。
- 只有 `training.identity_geometry=true`：因其他门关闭而未 requested。
- 三门全开但权重全 0：requested=true、effective=false、reason=`zero_weights`。
- 三门全开且单项正权重：配置 effective=true，但 runtime 仍等待 Anchor。
- 负数、NaN、Inf、bool-as-number、空路径、非法 policy。
- unknown geometry 字段不启用任何功能。
- `to_dict -> from_mapping -> to_dict` 稳定。
- `--options-json` 嵌套对象注入后不丢 src/dst sampling override。
- 高 schema version 全部增强关闭。
- 不存在 `geometry.enabled`，提供该 unknown 字段时不得成为 gate。

命令：

```bash
python -m unittest tests.smoke.test_batch3_geometry_config -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 10. 完成定义

- 默认值唯一位于 `core/enhancements/config.py`。
- Gate 只有现有三个 training 布尔门。
- 所有权重默认 0，非法输入安全关闭并产生 warning/reason。
- 旧 options 和 Batch 2 sampling roundtrip 不变。
- options-json 文档与代码一致。
- Summary、Review、测试结果和 Commit SHA 齐全。

## 11. Review 检查表

- 是否重复创建 gate？
- 是否让未知字段影响 effective？
- 是否把 config effective 与 runtime anchor ready 混为一谈？
- 是否破坏 sampling src/dst override？
- 是否存在 GUI/Model.py 中的重复默认值？
- 是否把非法值裁剪成正权重？

## 12. 交付物

- `core/enhancements/config.py`
- `tests/smoke/test_batch3_geometry_config.py`
- options-json 示例更新
- 配置迁移/兼容说明
- Summary、Review、Commit SHA
