# 10 — 建立 Merge 默认路径 smoke

Status: done-macos-lightweight
Type: AFK
Blocked by: 08 — 建立向后兼容的 Enhancement Feature Flag 骨架

**构建内容:** 所有增强关闭时，默认 Merge 路径仍可通过 dummy predictor 或最小 fixture 执行，不因 Batch 1 配置骨架产生未解释行为变化。

- [x] Merge smoke 使用默认关闭的增强配置。
- [x] dummy predictor 或最小 fixture 能覆盖 MergeMasked 默认路径。
- [x] 缺失 Enhancement Config 时 Merge 行为保持传统路径。
- [x] 不在本 issue 中实现 Shape-aware Merge。
- [x] macOS 侧完成 dummy/CPU smoke；Windows GPU 侧补充真实模型 Merge 验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/10-merge-default-path-smoke-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 18:19:47 Asia/Shanghai：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/10-merge-default-path-smoke-summary.md`。新增 dummy predictor + fixture 的 MergeMaskedFace 默认路径 smoke；缺失 / 全关 Enhancement Config 时传统路径保持一致；未实现 Shape-aware Merge，Windows GPU 真实模型 Merge 仍待补证。
