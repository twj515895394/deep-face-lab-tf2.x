# Ticket 09 — 训练保存恢复 smoke 总结

> 状态：macOS 轻量验证通过；Windows GPU 真实 SAEHD 保存恢复仍待补证。  
> 生成时间：2026-07-26 20:10:10 +0800

## 本次结论

已建立 Batch 1 训练保存恢复 smoke 的 macOS 轻量路径。该路径不依赖 TensorFlow、cv2 或 GPU，使用与现有 optimizer roundtrip helper 对齐的 NumPy 小向量训练轨迹，验证训练 step、保存、销毁、重载和继续 step 的基本一致性。

## 新增与修改

代码：

- `core/leras/training_save_resume_smoke.py`
- `tools/smoke/batch1_mac_smoke.py`

测试：

- `tests/smoke/test_batch1_training_save_resume_smoke.py`
- `tests/smoke/test_batch1_mac_smoke.py`

模型路由审计：

- `.scratch/batch1-correctness-foundation/reports/route-plan-ticket09-20260726.json`
- `.scratch/batch1-correctness-foundation/reports/model-routing-ledger-ticket09-20260726.json`

## 覆盖点

1. AdaBelief 保存恢复后下一步与连续训练一致。
2. RMSprop 保存恢复后下一步与连续训练一致。
3. Lion v2 momentum slot 带 schema marker 保存恢复。
4. 主权重保存文件存在且非空。
5. 保存前主权重发生变化。
6. 恢复后继续 step 主权重继续变化。
7. model iteration 保存、加载、恢复后连续。
8. optimizer iteration 保存、加载、恢复后连续。
9. optimizer slot reload error 为 0。
10. optimizer slot next-step update error 为 0。
11. 缺失 `enhancements` 的 legacy options 默认关闭全部增强。
12. macOS 缺 TensorFlow/GPU 时 FP16/BF16 不标记为 validated。

## 接口与可观测输出

新增 helper：

- `normalize_legacy_training_options(options)`
- `save_training_checkpoint(checkpoint_path, ...)`
- `load_training_checkpoint(checkpoint_path)`
- `run_training_save_resume_smoke(...)`
- `run_all_training_save_resume_smokes()`

`tools.smoke.batch1_mac_smoke` 的 summary 新增：

```text
checks.training_save_resume.status
checks.training_save_resume.optimizers
checks.training_save_resume.max_abs_reload_error
checks.training_save_resume.max_abs_update_error
checks.training_save_resume.macos_lightweight_only
checks.training_save_resume.windows_gpu_validation_required
```

默认行为不变：新增 helper 不接入真实训练主流程，不改变 SAEHD 初始化、训练、保存或 Merge 逻辑。

## 验证结果

已通过：

```bash
python3 -m unittest tests.smoke.test_batch1_training_save_resume_smoke -v
python3 -m unittest tests.smoke.test_batch1_training_save_resume_smoke tests.smoke.test_batch1_mac_smoke -v
python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py' -v
python3 -m py_compile core/leras/training_save_resume_smoke.py tools/smoke/batch1_mac_smoke.py tests/smoke/test_batch1_training_save_resume_smoke.py tests/smoke/test_batch1_mac_smoke.py
python3 -m tools.smoke.batch1_mac_smoke --print-json
```

结果摘要：

```text
Batch 1 smoke: 73 tests passed
training_save_resume optimizers: adabelief, rmsprop, lion
max_abs_reload_error: 0.0
max_abs_update_error: 0.0
Python: 3.12.8
Platform: Darwin arm64
TensorFlow: missing
cv2: missing
```

## Windows GPU 人工验证建议

1. 准备 8-16 张 src/dst aligned faces。
2. SAEHD fp32，resolution 64 或 96，batch size 2。
3. AdaBelief 主基线，GAN / TrueFace 关闭。
4. 初始化后训练 2-5 iter，确认 loss finite。
5. 保存模型，确认所有模型与 optimizer 文件存在且非空。
6. 关闭进程或重置 TensorFlow session。
7. 不新增 `enhancements` 字段，重新加载旧配置路径。
8. 确认 model iteration 连续。
9. 确认 optimizer iteration 与 slot 恢复。
10. 继续训练 2-5 iter，记录 loss absolute difference、weight max/mean absolute difference、optimizer slot max absolute difference。

## 风险与注意事项

- 本轮未验证真实 TensorFlow `nn.Saveable` / session / GPU optimizer state。
- 本轮未验证真实 SAEHD faceset、CUDA/cuDNN、Windows 启动脚本或训练质量。
- FP16/BF16 仍不能标记为 validated；BF16 仍是 legacy static experimental scale。
- Ticket 11 现在可继续，用于汇总 Batch 1 兼容矩阵与最终 handoff。
