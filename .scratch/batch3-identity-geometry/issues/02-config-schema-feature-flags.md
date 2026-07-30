# B3-02 配置 Schema、默认值与 Feature Flags

- 状态：BLOCKED-BY-B3-01；P0；阻塞 B3-04/B3-07/B3-13。
- 目标：在 `core/enhancements/config.py` 扩展 geometry 配置，保持默认关闭和单一默认值来源。
- 字段：`geometry.enabled=false`、`ratio_weight=0.0`、`landmark_weight=0.0`、`anchor_path=null`、`curriculum={warmup_iters,ramp_iters}`；字段名在实现前由本票最终 Review 冻结。
- Gate：`training.enabled && training.loss_hooks && training.identity_geometry && geometry.enabled`。
- 输出 requested/effective/reason；未知字段忽略并告警；非法数值回默认关闭。
- 禁止：根级平行配置、GUI 默认值、隐式启用、改 schema 兼容语义。
- 测试：`test_batch3_geometry_config.py` 覆盖缺字段、旧 JSON、unknown、负权重、NaN、双门/四门状态。
- 完成：options-json 示例、配置迁移说明、测试/Review/SHA。