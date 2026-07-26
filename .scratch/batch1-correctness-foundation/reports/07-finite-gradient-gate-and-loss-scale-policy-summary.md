# Ticket 07：Finite Gradient Gate 与 Loss Scaling 策略总结

> 生成时间：2026-07-26 19:47:34 +0800
> 状态：done-macos-lightweight

## 变更结论

本轮按用户确认的保守方案 A+ 完成 Ticket 07：

- 训练图在 optimizer update 前检查 averaged 且 unscaled 后的 gradients 是否全部 finite。
- 任一参与本 step 的 optimizer 发现 non-finite gradient 时，整步 update 跳过，避免参数先被污染再由 Python 端发现。
- FP32 继续保持无 Loss Scaling，不引入新的 scale state。
- BF16 保留当前 legacy static loss scale 路径，但在 precision contract 中标为 `legacy_static_experimental`，不写成已验证稳定路径。
- 本轮不推进 FP32 master weight 改造，不强制 BF16 回退到 FP32。

## 新增/修改接口与字段

训练内部返回值有可观测语义变化：

- `unified_train(...)` 内部返回从 `(src_loss, dst_loss)` 扩展为 `(src_loss, dst_loss, gradients_finite, step_applied)`。
- `onTrainOneIter()` 会在 `step_applied=False` 时返回 `src_loss=0.0` 与 `dst_loss=0.0`，并跳过本次参数更新。
- `core/leras/precision_contract.py` 中 BF16 `loss_scale_mode` 从 `legacy_static` 调整为 `legacy_static_experimental`。

外部用户配置未新增参数，默认 precision 仍为 `fp32`。

## 技术验证结果

macOS 轻量验证通过：

```bash
python3 -m unittest tests.smoke.test_batch1_finite_gradient_gate -v
python3 -m unittest tests.smoke.test_batch1_precision_contract -v
python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py' -v
python3 -m py_compile models/Model_SAEHD/Model.py core/leras/precision_contract.py tests/smoke/test_batch1_precision_contract.py tests/smoke/test_batch1_finite_gradient_gate.py
python3 -m unittest discover -s tests -v
python3 -m tools.smoke.batch1_mac_smoke --print-json
```

覆盖要点：

- 旧 two-value train result 仍可被解析。
- gradient finite / step applied flag 可正确解析。
- FP32 `loss_scale_var=None` 时不会触碰 Loss Scale。
- non-finite gradient 会将低精度 loss scale 减半并重置恢复计数。
- finite gradient 会推进恢复计数，并在稳定区间后按上限恢复 scale。
- 模型训练图保留 `tf.cond` 作为 optimizer gate。
- `step_applied` 由 gated update 结果导出。
- BF16 contract 标记为 legacy static experimental。

## 人工验证建议

Windows GPU 环境仍需补充：

- SAEHD FP32 短训 1-3 iteration，确认 finite gradient gate 不改变正常 step。
- BF16 短训，确认 legacy static scale 路径仍能启动，并观察是否存在用户反馈的稳定性问题。
- 人工注入 NaN / Inf gradient 或构造极端 batch，确认参数文件在 skipped step 前后不变。
- 保存恢复后继续训练，确认 loss scale runtime state 与 optimizer state 没有新回归。

## 风险与注意事项

- macOS 当前缺 TensorFlow 与 GPU，本轮无法真实执行 TF1 session 训练图，只完成纯函数、静态结构与 smoke harness 级验证。
- BF16 仍是 experimental；本轮只保留现有路径并收敛风险声明，没有声称其 Windows GPU 训练已稳定。
- FP32 master weights 属于更大范围改造，涉及 optimizer slot dtype、保存恢复和真实训练验证，未纳入本 Ticket。
