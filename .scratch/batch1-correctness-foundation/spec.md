# Batch 1 Correctness Foundation

Status: done-macos-lightweight

## 背景

本批次承接 `.handoff/current.md` 与 `docs/development/batch1-correctness-and-extension-foundation-tasks.md`。

当前状态：

- Batch 1 详细设计已完成。
- Ticket 01 / 02 / 03 / 04 / 05 / 06 / 07 / 08 / 09 / 10 / 11 已完成 macOS 轻量实现、验证与复核。
- 下一步进入 Batch 2 前置设计 / 任务拆分；Windows GPU 真实训练、保存恢复与 Merge 质量仍待补证。

## 执行边界

本批次只做 P0 正确性修复、观测能力、兼容配置骨架和可重复 smoke。不得在本批次引入 Region Loss、Boundary Loss、Frequency Loss、Dataset Metadata、Identity Geometry、Source Shape Template、Shape-aware Merge、UI 或服务化改造。

## 平台验证约定

本项目在 macOS 上开发时默认没有可用 GPU，因此 macOS 侧只要求完成轻量级工程验证：

- Python 版本最低为 3.9，推荐使用 3.11 或 3.12。
- Python 语法编译检查。
- 可在 CPU 环境完成的单元测试或纯函数测试。
- 不依赖真实 GPU 的导入、配置读取、fixture 和 smoke harness 结构检查。
- 不能把 macOS 上无法执行的 GPU 训练或真实视觉质量验证写成已完成。

真实训练、GPU 行为、CUDA/cuDNN、Windows 启动脚本、实际模型保存恢复与 Merge 质量验证，需要在 Windows GPU 环境执行，并在对应 issue 的完成总结中记录结果或明确标记为待 Windows 验证。

## Ticket Frontier

优先领取所有阻塞依赖均已完成的 issue。当前 frontier：

- Batch 2 前置设计 / 任务拆分（待新建 ticket）

已完成：

- `01-baseline-and-mac-smoke-harness.md`
- `02-eyes-mouth-mask-priority-feed.md`
- `03-training-exception-semantics.md`
- `04-precision-contract-audit.md`
- `05-optimizer-roundtrip-audit.md`
- `06-lion-v2-and-legacy-state.md`
- `07-finite-gradient-gate-and-loss-scale-policy.md`
- `08-enhancement-feature-flags.md`
- `09-training-save-resume-smoke.md`
- `10-merge-default-path-smoke.md`
- `11-batch1-compatibility-matrix-and-handoff.md`

## 参考文档

- `.handoff/current.md`
- `.handoff/handoff-20260726-batch1-detailed-design.md`
- `docs/development/batch1-correctness-and-extension-foundation-tasks.md`
- `docs/implementation/manual-quality-acceptance-and-development-validation-standard.md`
