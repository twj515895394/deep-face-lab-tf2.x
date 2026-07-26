# 11 — 汇总 Batch 1 兼容矩阵与 handoff

Status: done-macos-lightweight
Type: AFK
Blocked by: 09 — 建立训练保存恢复 smoke; 10 — 建立 Merge 默认路径 smoke

**构建内容:** Batch 1 的实际代码状态、测试结果、Windows GPU 待验证项、兼容矩阵和下一步风险被写入文档与最新 handoff，后续开发者可以安全判断是否进入 Batch 2。

- [x] 更新 Batch 1 完成状态矩阵。
- [x] 记录 macOS 已执行的轻量检查及结果。
- [x] 记录 Windows GPU 已执行或待执行的真实训练、保存恢复、Merge 验证。
- [x] 明确所有未完成风险与是否阻断 Batch 2。
- [x] 新建时间戳 handoff，并更新 `.handoff/current.md` 指向最新 handoff。
- [x] 不删除历史 handoff。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/11-batch1-compatibility-matrix-and-handoff-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。（不适用：本 issue 更新 Batch 1 状态、验证边界与 handoff，可观测文档状态发生变化，已生成 summary。）

## Comments

- 2026-07-26 20:34:48 +0800：macOS 轻量复核与 Batch 1 兼容矩阵汇总完成。Summary: `.scratch/batch1-correctness-foundation/reports/11-batch1-compatibility-matrix-and-handoff-summary.md`。最新 handoff: `.handoff/handoff-20260726-203448.md`。Batch 1 可进入 Batch 2 设计和轻量开发准备；Windows GPU 真实训练、保存恢复、Merge 质量和 FP16/BF16 稳定性仍是后续验收门。
