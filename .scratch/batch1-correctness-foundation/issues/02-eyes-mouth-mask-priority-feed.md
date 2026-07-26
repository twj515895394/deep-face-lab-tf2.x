# 02 — 修复 Eyes / Mouth Priority 真实 mask 传递

Status: resolved
Type: AFK
Blocked by: 01 — 建立 Batch 1 基线与 macOS 轻量 smoke harness

**构建内容:** 当 `eyes_mouth_prio=True` 时，训练 step 使用样本生成器返回的真实 eyes/mouth mask 参与 priority loss；当该选项关闭时，旧的三输出训练路径保持不变。

- [x] `eyes_mouth_prio=False` 时继续接受 src/dst 各 3 个样本输出。
- [x] `eyes_mouth_prio=True` 时要求 src/dst 各 4 个样本输出，并读取第 4 个 EM mask。
- [x] 开启 priority 但缺少 EM mask 时立即失败，不再静默使用全零 mask。
- [x] EM mask shape 与 full mask 不一致时立即失败。
- [x] 单元测试证明 feed 中 EM mask 内容来自输入样本，不是 `zeros_like` 替代物。
- [x] macOS 可执行纯函数或 mock 级测试；Windows GPU 环境补充真实训练启动验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/02-eyes-mouth-mask-priority-feed-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。

## Comments

- 2026-07-26 15:52:43 +0800：已完成 Ticket 02。完成总结报告见 `.scratch/batch1-correctness-foundation/reports/02-eyes-mouth-mask-priority-feed-summary.md`。
