# 07 — 收敛 finite gradient gate 与 Loss Scaling 策略

Status: done-macos-lightweight
Type: HITL
Blocked by: 04 — 建立 Precision Contract 与 dtype 审计; 05 — 建立 optimizer roundtrip 审计基础

**构建内容:** 训练 step 在梯度 finite 时才应用 optimizer update；FP32/FP16/BF16 的 Loss Scaling 与 runtime state 策略被明确实现或明确降级为 experimental 风险。

- [x] 训练图先检查 unscaled gradient finite，再决定是否执行 optimizer update。
- [x] 非 finite step 不污染参数。
- [x] FP32 不引入不必要的 Loss Scaling。
- [x] FP16/BF16 的 scaling 策略与 precision contract 一致。
- [x] Loss Scale runtime state 可保存恢复，或明确将对应低精度路径标记为 experimental。
- [x] 进入实现前需人工确认：本批次是否只收敛策略并保留低精度 experimental，还是继续推进更深的 FP32 master weight 改造。
- [x] macOS 侧只做 mock/小图数值测试；Windows GPU 侧必须补充真实训练验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/07-finite-gradient-gate-and-loss-scale-policy-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 19:47:34 +0800：已按用户确认的保守方案 A+ 完成 macOS 轻量实现。总结报告见 `.scratch/batch1-correctness-foundation/reports/07-finite-gradient-gate-and-loss-scale-policy-summary.md`。真实 TensorFlow GPU 短训、BF16 稳定性与保存恢复仍需 Windows GPU 验证。
