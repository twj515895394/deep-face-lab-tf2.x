# 09 — 建立训练保存恢复 smoke

Status: done-macos-lightweight
Type: AFK
Blocked by: 03 — 统一训练异常处理与失败语义; 06 — 修复 Lion v2 公式并保护 legacy state; 07 — 收敛 finite gradient gate 与 Loss Scaling 策略; 08 — 建立向后兼容的 Enhancement Feature Flag 骨架

**构建内容:** 开发者可以用最小模型或 fixture 验证训练保存、销毁、重载和继续 step 的基本一致性，并明确 macOS 与 Windows GPU 验证边界。

- [x] 保存恢复 smoke 覆盖主权重与 optimizer state。
- [x] 兼容缺失新配置字段的旧模型加载路径。
- [x] 对低精度路径记录 validated 或 experimental 状态。
- [x] macOS 侧只要求 CPU 可运行的最小 smoke 或语法/导入检查。
- [x] 已记录 Windows GPU 侧需补充真实 SAEHD 初始化、训练 step、保存恢复验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/09-training-save-resume-smoke-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [ ] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 20:10:10 +0800：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/09-training-save-resume-smoke-summary.md`。新增 NumPy training save/resume smoke，覆盖 AdaBelief / RMSprop / Lion 主权重、optimizer state、保存文件非空、销毁/重载后下一步轨迹一致；已记录真实 SAEHD / TensorFlow / Windows GPU 保存恢复待人工补证。
