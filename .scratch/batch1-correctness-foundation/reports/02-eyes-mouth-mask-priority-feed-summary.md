# 02 — 修复 Eyes / Mouth Priority 真实 mask 传递完成总结

生成时间：2026-07-26 15:52:43 +0800

## 结论

已修复 SAEHD 训练中 Eyes / Mouth Priority 的真实 mask 传递问题。`eyes_mouth_prio=True` 时不再向 priority loss 喂全零 mask，而是要求样本生成器返回真实 EYES_MOUTH mask，并将其传入训练 feed。

同时修复了 `_has_eyes_mouth` 初始化过晚的问题：该 flag 现在会在训练图构建前设置，使 priority loss 分支能够进入图构建。

## 新增或修改接口

- `SAEHDModel.unified_train(...)` 增加可选关键字参数：
  - `target_srcm_em`
  - `target_dstm_em`
- 新增内部 helper：
  - `_unpack_training_samples(...)`
  - `_add_eyes_mouth_masks_to_feed(...)`
  - `_validate_eyes_mouth_mask(...)`

这些 helper 是运行时内部实现细节，不作为外部 API 承诺。

## 输入参数变更

- `eyes_mouth_prio=False`：src/dst 仍各接受 3 个样本输出，保持旧路径。
- `eyes_mouth_prio=True`：src/dst 必须各提供 4 个样本输出，第 4 个输出为 EYES_MOUTH mask。
- 开启 priority 但缺少 EM mask、EM mask shape 与 full mask 不一致、EM mask 包含 inf/nan 时会立即抛出 `ValueError`。

## 输出字段变更

无外部响应字段变更。

训练行为变化：

- 修复前：priority loss placeholder 被 `np.zeros_like(full_mask)` 填充，priority loss 无有效监督。
- 修复后：priority loss 使用真实 EM mask。开启该选项后 loss 轨迹可能变化，这是正确性修复的预期结果。

## 技术验证结果

- `python3 -m unittest tests.smoke.test_batch1_eyes_mouth_masks tests.smoke.test_batch1_mac_smoke`：通过，13 个测试。
- `python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py'`：通过，13 个测试。
- `python3 -m py_compile models/Model_SAEHD/Model.py tests/smoke/test_batch1_eyes_mouth_masks.py tools/smoke/batch1_mac_smoke.py tests/smoke/test_batch1_mac_smoke.py`：通过。
- `python3 -m tools.smoke.batch1_mac_smoke --print-json`：通过，最低 Python 版本记录为 3.9，Git metadata 已采集，AST 扫描 166 个 Python 文件，0 个语法错误，并记录轻量导入失败原因。

## 人工验证建议

Windows GPU 环境仍需补充：

- `eyes_mouth_prio=False` 的真实 SAEHD 训练启动，确认三输出路径不回归。
- `eyes_mouth_prio=True` 的真实 SAEHD 训练启动，确认生成器返回第 4 个 mask 且训练 step 不报错。
- 对比开启 priority 前后的 loss 与 preview，不把 loss 变化简单视为回归。

## 风险与注意事项

- 本次 macOS 验证为 mock/纯函数级验证，没有执行真实 TensorFlow 训练图。
- 开启 priority 后如数据集缺少可生成 EYES_MOUTH mask 的必要信息，现在会显式失败，而不是静默训练无效 loss。
- 本 issue 不处理非 OOM 异常重抛、finite gradient gate、Loss Scaling 或 optimizer state；这些仍由后续 ticket 承接。
