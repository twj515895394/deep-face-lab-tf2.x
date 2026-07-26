# 01 — 建立 Batch 1 基线与 macOS 轻量 smoke harness

Status: resolved
Type: AFK
Blocked by: None — 可以立即开始

**构建内容:** 开发者可以在 macOS 无 GPU 环境下运行一组轻量检查，确认当前 commit、Python 环境、基础导入和 smoke harness 结构可用，并把真实 GPU 验证留给 Windows 环境记录。

- [x] 记录当前 Git commit、Python 版本、平台信息和关键依赖可用性。
- [x] 建立 Batch 1 smoke 执行入口，能够只运行 CPU/纯函数级检查。
- [x] macOS 验证不要求真实 SAEHD GPU 训练，不把 GPU 缺失视为失败。
- [x] 输出或说明 Windows GPU 环境需要补充验证的项目。
- [x] 轻量检查失败时能定位到具体导入、语法或配置问题。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/01-baseline-and-mac-smoke-harness-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 15:48:40 +0800：已完成 Ticket 01。完成总结报告见 `.scratch/batch1-correctness-foundation/reports/01-baseline-and-mac-smoke-harness-summary.md`。
