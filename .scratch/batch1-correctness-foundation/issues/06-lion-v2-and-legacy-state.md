# 06 — 修复 Lion v2 公式并保护 legacy state

Status: done-macos-lightweight
Type: AFK
Blocked by: 05 — 建立 optimizer roundtrip 审计基础

**构建内容:** Lion optimizer 使用标准 beta1/beta2 更新语义；旧 Lion optimizer state 不会被静默按新公式恢复，避免训练轨迹被不兼容状态污染。

- [x] Lion update direction 使用 beta1 混合梯度方向。
- [x] Lion momentum state 使用 beta2 更新。
- [x] 新 Lion state 具备可识别的 v2 语义或迁移保护。
- [x] legacy Lion 主权重可以继续加载。
- [x] legacy Lion optimizer state 不静默恢复为新公式 state，需重置或明确告警。
- [x] macOS 侧通过手工数值测试；Windows GPU 侧补充真实训练恢复验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/06-lion-v2-and-legacy-state-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。（不适用：Lion 公式与 optimizer state 恢复行为发生可观测变化，已生成 summary。）

## Comments

- 2026-07-26 18:45:00 +0800：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/06-lion-v2-and-legacy-state-summary.md`。Windows GPU 真实 TensorFlow session 保存恢复与短训轨迹仍待补充。
