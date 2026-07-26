# 01 — 建立 Batch 1 基线与 macOS 轻量 smoke harness 完成总结

生成时间：2026-07-26 15:48:40 +0800

## 结论

已建立 Batch 1 的 macOS 轻量 smoke harness。该 harness 用于记录当前 commit、Python/平台信息、关键依赖可用性、基础仓库结构与模块发现状态，并明确列出必须留到 Windows GPU 环境验证的项目。

本 issue 不验证真实 GPU 训练，也不把 macOS 缺少 `cv2` 或 `tensorflow` 视为 Batch 1 失败。

## 新增或修改接口

- 新增命令入口：`python3 -m tools.smoke.batch1_mac_smoke`
- 可选参数：
  - `--output-dir`：指定 `environment.json` 与 `smoke-summary.json` 输出目录。
  - `--print-json`：运行后将环境与摘要 JSON 打印到 stdout。

## 输入参数变更

无既有业务入口参数变更。

## 输出字段变更

新增 smoke 输出文件：

- `environment.json`
  - `generated_at`
  - `repo_root`
  - `git.commit`
  - `git.branch`
  - `python`
  - `platform`
  - `dependencies`
  - `windows_gpu_validation_required`
- `smoke-summary.json`
  - `status`
  - `checks.python_version_supported`
  - `checks.required_files`
  - `checks.repo_modules`
  - `checks.gpu_training_skipped_by_design`
  - `notes`

默认输出位置位于 `workspace/validation/batch1/<timestamp>/`，该目录已由 `.gitignore` 排除。

## 技术验证结果

- `python3 -m unittest tests.smoke.test_batch1_mac_smoke`：通过，3 个测试。
- `python3 -m py_compile tools/smoke/batch1_mac_smoke.py tests/smoke/test_batch1_mac_smoke.py`：通过。
- `python3 -m tools.smoke.batch1_mac_smoke --print-json`：通过，Git metadata 已采集，AST 扫描 166 个 Python 文件，0 个语法错误，并记录轻量导入失败原因。

本机记录：

- commit：`1d24a54f0b5b29852b0f725b2e2e1e92414cf9a2`
- branch：`main`
- Python：`3.12.8`
- 平台：`Darwin arm64`
- `numpy`：可用
- `cv2`：不可用
- `tensorflow`：不可用
- `core.leras.nn`：不可用，缺少 `colorama`
- `models` / `merger.MergeMasked`：不可用，缺少 `cv2`

## 人工验证建议

Windows GPU 环境仍需补充：

- Windows 启动脚本与环境激活。
- CUDA / cuDNN / TensorFlow GPU discovery。
- SAEHD FP32 初始化。
- 最小真实训练 step。
- 模型保存、重启、加载与下一步恢复。
- 默认 Merge 路径验证。

## 风险与注意事项

- 该 harness 是 Batch 1 的开发基线，不是完整训练验收。
- macOS 依赖缺失只作为环境事实记录；不得据此宣称 Windows GPU 路径通过或失败。
- 后续 Ticket 02 / 04 可依赖该入口作为轻量回归的一部分。
