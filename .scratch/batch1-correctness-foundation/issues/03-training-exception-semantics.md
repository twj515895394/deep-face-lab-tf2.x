# 03 — 统一训练异常处理与失败语义

Status: done-macos-lightweight
Type: AFK
Blocked by: 02 — 修复 Eyes / Mouth Priority 真实 mask 传递

**构建内容:** 训练过程中的非 OOM 异常会带上下文重新抛出，不再被静默吞掉；OOM 异常仍保留原始失败语义，方便开发者准确定位失败原因。

- [x] 非 OOM 训练异常记录关键上下文后重新抛出。
- [x] OOM 类异常记录 batch、resolution、precision 等上下文后重新抛出原异常。
- [x] 不在本 issue 中实现自动降 batch size 或自动 fallback。
- [x] 不改变正常训练 step 的返回结构。
- [x] macOS 侧用 mock 异常覆盖失败语义；Windows GPU 侧补充真实训练启动验证。

## 完成总结报告

- [x] 若本 issue 涉及接口、参数、响应字段、校验规则或默认行为变化，完成后已在 `.scratch/batch1-correctness-foundation/reports/03-training-exception-semantics-summary.md` 生成 summary 报告。
- [x] summary 报告已包含新增/修改接口、输入参数变更、输出字段变更、人工验证建议、技术验证结果、风险与注意事项。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。
- [x] 若本 issue 无接口或可观测行为变化，已在 `## Comments` 中说明无需 summary 报告的原因。（不适用：本 issue 改变异常路径可观测行为，已生成 summary。）

## Comments

- 2026-07-26 16:55:23 +0800：macOS 轻量实现与验证完成。Summary: `.scratch/batch1-correctness-foundation/reports/03-training-exception-semantics-summary.md`。Windows GPU 真实训练启动验证仍待补充。
