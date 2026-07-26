# 08 — 建立向后兼容的 Enhancement Feature Flag 骨架

Status: ready-for-agent
Type: AFK
Blocked by: 02 — 修复 Eyes / Mouth Priority 真实 mask 传递

**构建内容:** 新增强能力拥有默认关闭、缺失安全、未知字段不改变旧行为的配置骨架，旧模型和旧配置仍可加载并保持传统训练与 Merge 行为。

- [ ] 新 Enhancement Config 缺失时所有增强默认关闭。
- [ ] 未知字段不改变旧训练和 Merge 行为。
- [ ] 旧模型无新字段时可加载。
- [ ] Eyes / Mouth Priority 作为已有功能修复，不额外套增强总开关。
- [ ] 不在本 issue 中实现任何新训练 loss 或 shape-aware merge 算法。
- [ ] macOS 侧完成配置读取和默认值测试；Windows GPU 侧补充旧模型加载验证。

## 完成总结报告

- [ ] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/08-enhancement-feature-flags-summary.md` 生成 summary 报告。
- [ ] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [ ] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

