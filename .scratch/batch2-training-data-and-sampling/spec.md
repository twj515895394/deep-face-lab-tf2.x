# Batch 2 Training Data Metadata and Sampling

Status: ready-for-implementation

## 背景

本批次承接：

- `.handoff/current.md`
- `docs/development/batch2-training-data-and-sampling-tasks.md`
- `docs/implementation/enhanced-dfl-master-implementation-plan.md`
- `docs/implementation/training-enhancement-implementation-plan.md`

本批次交付一套可独立长期使用的完整能力：

```text
Faceset Analyzer
+
Metadata Schema v1 / Sidecar
+
Pose-balanced Sampling
+
Quality + Pose Sampling
+
日志、报告和安全回退
```

## 已确定决策

- 正式训练基线固定为 FP32 + AdaBelief。
- Lion 后续开发与验收暂停。
- FP16 / BF16 不进入 Batch 2。
- 动态单样本 Loss 感知采样延期到未来独立批次。
- Identity Geometry、脸型 Loss、Source Shape Template 和 Shape-aware Merge 不进入 Batch 2。
- 所有新增功能默认关闭。
- Batch 2 完成后必须能作为正式功能继续使用，不允许只交付 Schema、接口或 TODO。

## 执行边界

本批次允许修改：

- `samplelib/metadata/*`
- `samplelib/sampling/*`
- `samplelib/SampleLoader.py`
- `samplelib/SampleGeneratorFace.py`
- `mainscripts/FacesetAnalyzer.py`
- `core/enhancements/config.py`
- `models/Model_SAEHD/Model.py`
- `main.py`
- `tests/*`
- `docs/*`
- `.handoff/*`

本批次不得：

- 修改 SAEHD 网络和 Loss 公式；
- 修改模型权重、optimizer、DFM 或 Merge 格式；
- 自动删除或覆盖 aligned 图片；
- 修改 `faceset.pak` 格式；
- 把动态 Loss 状态写入 Metadata；
- 引入大型外部质量模型；
- 在同一 ticket 中顺带开发 Batch 3 / 4 / 5 / 6 功能。

## 平台验证约定

### macOS / CPU 轻量验证

可完成：

- Python 3.9+ 语法和导入；
- Schema、identity、fingerprint、pose、quality 纯函数；
- synthetic image Analyzer；
- JSON 原子写入和增量更新；
- policy / weights / deterministic host；
- 普通和小型 Packed fixture；
- 不依赖真实 GPU 的 Generator 结构测试。

不得把以下内容写成已完成：

- Windows 多进程 spawn 全链路；
- 真实 FP32 SAEHD GPU 训练；
- 保存退出恢复；
- 真实训练速度和显存；
- 最终采样效果人工判断。

### Windows GPU 验收

必须使用 FP32 + AdaBelief，完成：

- legacy_random；
- legacy_uniform_yaw；
- pose_balanced；
- quality_pose_balanced；
- 普通与 Packed Faceset；
- Metadata 部分缺失、损坏和 fallback；
- 多进程 generator；
- 保存、退出、恢复；
- 实际采样分布和 iter time 记录。

## Ticket Frontier

优先领取所有前置依赖已完成的 issue。

当前 frontier：

- `01-baseline-and-fixtures.md`

后续依赖顺序：

```text
01
↓
02
↓
03
↓
04
↓
05
↓
06
├─→ 07
└─→ 08
     ↓
     09
     ↓
     10
     ↓
     11
     ↓
     12
```

## Issues

- `01-baseline-and-fixtures.md`
- `02-sample-identity-and-metadata-schema.md`
- `03-lightweight-faceset-analyzer-core.md`
- `04-analyzer-cli-atomic-store-and-incremental.md`
- `05-metadata-loader-folder-packed-compat.md`
- `06-sampling-policy-and-legacy-adapters.md`
- `07-pose-balanced-sampling.md`
- `08-quality-aware-weighting.md`
- `09-weighted-index-host-and-generator-integration.md`
- `10-config-saehd-logging-and-fallback.md`
- `11-batch2-test-matrix-and-windows-acceptance.md`
- `12-compatibility-docs-and-handoff.md`

## 完成总结报告约定

每个 issue 完成后必须在：

```text
.scratch/batch2-training-data-and-sampling/reports/
```

生成同名 summary，至少记录：

- 实际修改文件和函数；
- 新增/修改接口；
- 参数、默认值和输出字段；
- 自动测试结果；
- 人工验证步骤；
- 未完成的 Windows / GPU 项；
- 兼容和回退证据；
- 风险与下一 ticket 建议。

## 参考文档

- `docs/development/batch2-training-data-and-sampling-tasks.md`
- `docs/development/batch1-correctness-and-extension-foundation-tasks.md`
- `docs/implementation/enhanced-dfl-master-implementation-plan.md`
- `docs/implementation/training-enhancement-implementation-plan.md`
- `docs/optimization/training-quality-algorithm-roadmap.md`
- `docs/optimization/src-dst-training-quality-optimization-design.md`
- `docs/implementation/deepfacelab-config-and-extension-architecture.md`
- `docs/implementation/deepfacelab-code-modification-map.md`
- `docs/implementation/manual-quality-acceptance-and-development-validation-standard.md`
