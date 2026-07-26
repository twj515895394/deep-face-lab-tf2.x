# 05 — 建立 optimizer roundtrip 审计基础

Status: done-macos-lightweight
Type: AFK
Blocked by: 04 — 建立 Precision Contract 与 dtype 审计

**构建内容:** 开发者可以用小图或 fixture 验证 optimizer state 的保存、加载和下一步更新行为，为后续 Lion 修复和低精度策略提供可比较基线。

- [x] AdaBelief、RMSprop、Lion 至少有小规模 roundtrip 覆盖。
- [x] 测试能比较连续训练与保存恢复后下一步更新是否一致。
- [x] 记录 optimizer slot dtype 与数值误差。
- [x] macOS 侧优先使用 CPU 可运行的小图测试；Windows GPU 侧补充真实模型恢复验证。
- [x] 不在本 issue 中修改 Lion 公式，只建立可观测性。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/05-optimizer-roundtrip-audit-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 18:19:47 Asia/Shanghai：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/05-optimizer-roundtrip-audit-summary.md`。新增 NumPy optimizer roundtrip harness；AdaBelief / RMSprop / Lion 均覆盖 reload/update error 与 slot dtype；未修改 Lion 公式，Windows GPU 真实 session 保存恢复仍待补证。
