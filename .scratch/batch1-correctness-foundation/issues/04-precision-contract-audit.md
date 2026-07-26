# 04 — 建立 Precision Contract 与 dtype 审计

Status: done-macos-lightweight
Type: AFK
Blocked by: 01 — 建立 Batch 1 基线与 macOS 轻量 smoke harness

**构建内容:** 开发者可以生成 FP32 / FP16 / BF16 的 dtype 审计信息，明确权重、梯度、optimizer slot 和恢复后的真实 dtype，避免把未验证低精度路径误标为 validated。

- [x] 提供统一的 requested/effective precision 解析或审计入口。
- [x] 审计报告能覆盖 weight、gradient、optimizer slot、保存文件和加载后 dtype。
- [x] FP32 路径作为 validated 基线。
- [x] FP16/BF16 如未通过完整证据，必须保留 experimental 标记或风险说明。
- [x] macOS 侧可完成 CPU/导入/结构级审计；Windows GPU 侧补充真实 CUDA/cuDNN 行为。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/04-precision-contract-audit-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。（不适用：本 issue 新增 precision contract 可观测报告字段，已生成 summary。）

## Comments

- 2026-07-26 17:47:06 +0800：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/04-precision-contract-audit-summary.md`。Windows GPU 真实 dtype / finite / roundtrip / 短训练证据仍待补充；FP16/BF16 保持 experimental。
