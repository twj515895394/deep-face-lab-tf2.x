# Batch 2 Reports

本目录保存 `.scratch/batch2-training-data-and-sampling/issues/` 每个 ticket 的完成总结和 Windows GPU 验收记录。

## 命名

```text
<ticket-file-stem>-summary.md
```

例如：

```text
02-sample-identity-and-metadata-schema-summary.md
```

## 每份 summary 必须包含

1. Ticket、完成时间、commit 和状态。
2. 实际新增/修改文件。
3. 实际新增/修改的类、函数和接口。
4. 配置字段、参数、默认值和兼容规则。
5. 输出文件、Schema 字段或日志变化。
6. 自动测试命令和结果。
7. 人工验证步骤和结果。
8. macOS/CPU 与 Windows GPU 验证边界。
9. Fallback、回退和旧行为一致性证据。
10. 性能数据或尚未测量的明确说明。
11. 风险、限制、未完成项和下一 ticket。

## 状态用语

- `done`：代码、自动测试、目标平台真实验收和文档全部完成。
- `done-macos-lightweight-pending-windows`：只完成 CPU/macOS 轻量验证，不能代表真实训练完成。
- `blocked`：存在明确阻断，必须记录原因和复现步骤。
- `deferred`：经决策延期，不作为本批次阻断项。

## Windows 记录

统一使用：

```text
windows-gpu-acceptance.md
```

记录硬件、驱动、CUDA、TensorFlow、容器/宿主环境、faceset、模型配置、命令、日志摘要、采样分布、性能、保存恢复和失败项。

## 禁止

- 不得只写“测试通过”而没有命令和范围。
- 不得把 synthetic / mock 结果写成真实 SAEHD GPU 训练。
- 不得把 quality score 主观合理写成最终换脸质量提升。
- 不得把 Dynamic Loss-aware Sampling、Identity Geometry、Lion 或低精度写成 Batch 2 已完成能力。
