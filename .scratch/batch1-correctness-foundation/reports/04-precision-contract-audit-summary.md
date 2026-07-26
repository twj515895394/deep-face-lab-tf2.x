# 04 — Precision Contract 与 dtype 审计完成总结

> 生成时间：2026-07-26 17:47:06 +0800
> 状态：macOS 轻量验证通过；Windows GPU 真实 dtype / finite / roundtrip / 短训练证据仍缺失。

## 结论

已新增统一 Precision Contract 与 dtype 审计入口，并最小接入 SAEHD 初始化路径。

- 新增 `core/leras/precision_contract.py`。
- `SAEHDModel` 初始化时记录 requested/effective precision contract。
- `_get_training_precision()` 优先返回 effective precision，异常上下文不再只依赖 requested 值。
- FP32 作为 Batch 1 validated baseline；FP16/BF16 保持 experimental。

## 新增接口

- `normalize_precision_name(value)`
- `resolve_precision_contract(requested_precision, runtime_capabilities=...)`
- `audit_precision_dtypes(contract, weights=..., gradients=..., optimizer=...)`
- `build_default_saehd_contract(requested_precision, runtime_capabilities=...)`
- `summarize_precision_contract(contract)`

报告字段覆盖：

- `requested_precision`
- `effective_precision`
- `status`
- `compute_dtype`
- `master_weight_dtype`
- `gradient_dtype`
- `optimizer_slot_dtypes`
- `placeholder_dtype`
- `save_file_dtype`
- `load_variable_dtype`
- `loss_scale_mode`
- `fallback_reason`
- `observed`
- `mismatches`
- `evidence`

## 默认语义

- `fp32`：validated baseline。
- `fp16`：experimental，缺完整 dynamic loss scaling / finite gate / roundtrip / Windows GPU 证据。
- `bf16`：experimental，保留当前 legacy static loss scale 事实，不声明已验证。
- 无效 precision：回退 `fp32` 并记录 `invalid_requested_precision`。
- 能力不足：低精度请求回退 `fp32`，状态记录为 `blocked`。

## 技术验证

已通过：

```bash
python3 -m unittest tests.smoke.test_batch1_precision_contract tests.smoke.test_batch1_config_defaults
python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py'
python3 -m py_compile main.py models/Model_SAEHD/Model.py tools/smoke/batch1_mac_smoke.py tests/smoke/test_batch1_mac_smoke.py tests/smoke/test_batch1_eyes_mouth_masks.py tests/smoke/test_batch1_precision_contract.py tests/smoke/test_batch1_config_defaults.py core/leras/precision_contract.py core/enhancements/config.py core/enhancements/__init__.py
python3 -m tools.smoke.batch1_mac_smoke --print-json
```

结果：

```text
35 tests passed
py_compile passed
smoke status: pass
AST scan: 171 Python files, 0 syntax errors
```

## 风险与待验证

- macOS 当前无 TensorFlow / cv2 / colorama，未执行真实训练图。
- Windows GPU 仍需补充 CUDA/cuDNN、真实 dtype、finite gate、optimizer roundtrip、保存恢复与短训练证据。
- 本 ticket 不实现 FP32 master weight 改造，也不修复低精度 Loss Scaling 策略。
