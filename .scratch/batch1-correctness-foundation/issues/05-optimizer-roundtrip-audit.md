# 05 — 建立 optimizer roundtrip 审计基础

Status: ready-for-agent
Type: AFK
Blocked by: 04 — 建立 Precision Contract 与 dtype 审计

**构建内容:** 开发者可以用小图或 fixture 验证 optimizer state 的保存、加载和下一步更新行为，为后续 Lion 修复和低精度策略提供可比较基线。

- [ ] AdaBelief、RMSprop、Lion 至少有小规模 roundtrip 覆盖。
- [ ] 测试能比较连续训练与保存恢复后下一步更新是否一致。
- [ ] 记录 optimizer slot dtype 与数值误差。
- [ ] macOS 侧优先使用 CPU 可运行的小图测试；Windows GPU 侧补充真实模型恢复验证。
- [ ] 不在本 issue 中修改 Lion 公式，只建立可观测性。

## 完成总结报告

- [ ] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/05-optimizer-roundtrip-audit-summary.md` 生成 summary 报告。
- [ ] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [ ] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

