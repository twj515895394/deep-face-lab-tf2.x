# Ticket 06：Lion v2 公式与 legacy state 保护总结

> 生成时间：2026-07-26 18:45:00 +0800
> 状态：done-macos-lightweight

## 变更结论

本轮已将 `core/leras/optimizers/Lion.py` 修正为标准 Lion v2 更新语义：

- `update_direction = sign(beta1 * momentum + (1-beta1) * grad)`
- `new_momentum = beta2 * momentum + (1-beta2) * grad`
- `new_weight = weight - lr * update_direction`

同时为 Lion optimizer state 增加 `lion_state_schema_version` 标记。旧 optimizer 文件缺少该标记时，不再静默加载旧 `c` slot；加载后会通过 `UserWarning` 明确提示，并重置 `iterations` 与 `c`，避免把 beta1 语义旧 state 当成 beta2 momentum 继续训练。

## 新增/修改接口与字段

- `Lion.get_weights()` 新增保存变量：`lion_state_schema_version`。
- `Lion.load_weights(filename)` 增加 legacy state 检测与重置逻辑。
- `core/leras/optimizer_roundtrip.py` 的 Lion NumPy 路径改为 v2 公式。
- `serialize_optimizer_state("lion", ...)` 新增 `lion_state_schema_version`。
- `deserialize_optimizer_state(..., reset_legacy_lion_state=True)` 对 legacy Lion payload 默认保留主权重、重置 optimizer slot；严格审计可传 `False` 并抛出 `ValueError`。

## 兼容性说明

- 旧模型主权重文件不受本 Ticket 修改影响，仍由模型各自的 `Saveable` 加载。
- 旧 Lion optimizer state 可以被识别为 legacy；主权重保留，optimizer slot 重置。
- 新保存的 Lion optimizer state 带 v2 schema marker，后续恢复不会被误判为 legacy。

## 技术验证结果

macOS 轻量验证通过：

```bash
python3 -m unittest tests.smoke.test_batch1_optimizer_roundtrip -v
python3 -m py_compile core/leras/optimizers/Lion.py core/leras/optimizer_roundtrip.py tests/smoke/test_batch1_optimizer_roundtrip.py
```

聚焦测试结果：10 passed。

覆盖要点：

- Lion roundtrip 在 v2 公式下连续训练与保存恢复后一致。
- beta2 改变 momentum state。
- update direction 使用 beta1 混合方向。
- legacy Lion state 默认重置，不静默续用。
- strict audit 模式可拒绝 legacy Lion state。
- v2 Lion state 可保留 momentum 并无误差恢复。
- AdaBelief / RMSprop roundtrip 不回归。

## 人工验证建议

Windows GPU 环境仍需补充：

- 真实 TensorFlow session 中旧 Lion optimizer 文件加载时 slot reset 行为。
- SAEHD 使用 Lion 训练 1-3 iteration 后保存恢复，确认新 v2 state 可连续恢复。
- 旧 Lion state 恢复后短训 loss / 参数有限性检查。

## 风险与注意事项

- 本 Ticket 改变 Lion optimizer 的训练轨迹，属于正确性修复而非兼容保持。
- legacy optimizer state 被重置后，恢复训练前几步可能和历史旧公式轨迹不同；这是避免语义污染的预期行为。
- Ticket 07 的 finite gradient gate 与 Loss Scaling 策略仍未实现，本轮未触碰训练 step 更新顺序。
