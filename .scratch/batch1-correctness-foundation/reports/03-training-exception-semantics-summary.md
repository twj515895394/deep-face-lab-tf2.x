# Ticket 03 Summary — 统一训练异常处理与失败语义

> 生成时间：2026-07-26 16:55:23 +0800
> 状态：macOS 轻量验证通过，Windows GPU 真实训练启动验证待补充。

## 结论

Ticket 03 已完成 macOS 侧实现与验证。

`SAEHDModel.onTrainOneIter()` 现在会在样本生成、样本协议校验或 `unified_train()` 失败时记录训练上下文并重新抛出原异常。非 OOM 异常不再落入后续 loss 返回路径；OOM 类异常也保留原始异常对象和 traceback 语义，不做自动降 batch size 或 fallback。

## 修改范围

- `models/Model_SAEHD/Model.py`
  - 新增训练异常上下文 helper。
  - 新增 OOM 分类 helper，避免把 `non-oom` 等否定表述误判成 OOM。
  - `onTrainOneIter()` 将 `generate_next_samples()`、样本解包和 `unified_train()` 纳入统一异常处理。
  - 异常发生时记录 `iter`、`batch_size`、`resolution`、`precision`、`has_eyes_mouth`、src/dst sample shapes 和 traceback，然后 `raise` 原异常。
- `tests/smoke/test_batch1_eyes_mouth_masks.py`
  - 覆盖正常返回结构不变。
  - 覆盖非 OOM 异常记录上下文后重新抛出。
  - 覆盖 OOM 异常记录上下文后重新抛出原异常。
  - 覆盖样本协议错误不会调用 `unified_train()`，并按非 OOM 失败记录上下文。
  - 覆盖 OOM 分类边界，包括 `non-oom` 反例。

## 接口与默认行为

- 无新增用户配置项。
- 无新增训练返回字段。
- 正常训练 step 返回结构保持：

```python
(('src_loss', np.mean(src_loss)), ('dst_loss', np.mean(dst_loss)))
```

- 异常路径的可观测行为发生变化：原先可能被吞掉的非 OOM 异常现在会记录上下文并重新抛出。

## 技术验证

macOS 本机验证通过：

```bash
python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py'
python3 -m py_compile main.py models/Model_SAEHD/Model.py tools/smoke/batch1_mac_smoke.py tests/smoke/test_batch1_mac_smoke.py tests/smoke/test_batch1_eyes_mouth_masks.py
python3 -m tools.smoke.batch1_mac_smoke --print-json
```

结果：

```text
17 tests passed
py_compile passed
smoke status: pass
AST scan: 166 Python files, 0 syntax errors
```

## 人工验证建议

Windows GPU 环境仍需补充：

- SAEHD FP32 真实训练启动。
- 人工触发或模拟一次 OOM，确认日志包含 batch、resolution、precision 等上下文，并且训练进程按原异常失败。
- 人工触发一次非 OOM 训练异常，确认不会继续返回 loss。

## 风险与注意事项

- macOS 当前没有 TensorFlow / CUDA / cv2 完整环境，不能声明真实 GPU 训练已验证。
- 数值异常的“更新前 finite gradient gate”不属于本 ticket，仍由后续 Ticket 07 处理。
- 本 ticket 不实现自动降 batch size、自动 fallback 或低精度策略调整。
