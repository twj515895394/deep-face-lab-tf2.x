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

## Agent 执行入口

任何 Agent、Codex、Claude 或能力偏弱的编码模型领取 Ticket 前，必须依次阅读：

1. `.handoff/current.md`
2. 本 `spec.md`
3. `docs/development/batch2-training-data-and-sampling-tasks.md`
4. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
5. 当前 Ticket
6. 当前 Ticket 所有 `Blocked by` 对应 summary
7. 当前 Ticket “Agent 开工前必读”中列出的源码

不得只把当前 Ticket 标题和 checklist 发送给执行模型。任务上下文至少必须包含：

```text
当前 Ticket
+
AGENT_IMPLEMENTATION_GUIDE.md
+
前置 Ticket summary
+
相关源码文件
```

若前置 summary 缺失、接口不一致或当前源码与 Ticket 假设冲突，Agent 必须标记 blocked，不得自行扩大重构范围。

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
- 在同一 ticket 中顺带开发 Batch 3 / 4 / 5 / 6 功能；
- 为通过测试吞掉核心训练、SampleProcessor、TensorFlow、save/load 错误；
- 只做导入或语法检查就把功能标记 resolved。

## Ticket 质量标准

每个 Ticket 已按弱模型执行要求包含：

- 开工前必读文档和源码；
- 当前源码事实检查；
- 推荐对象/API 骨架；
- 分步骤施工顺序；
- 边界、fallback 和禁止捷径；
- 可复制或可调整的测试命令；
- 验收证据和 summary 交接要求。

执行模型必须按 Ticket 顺序完成，不得跳过前置纯函数/基线任务，直接进入高风险运行时改造。

## 通用完成定义

单个 Ticket 只有同时满足以下条件才可从 open 改为 resolved：

```text
前置依赖已完成
+
源码事实复核有记录
+
实现严格在 Ticket 范围内
+
对应自动测试实际通过
+
legacy/关闭路径回归有证据
+
summary 已生成
+
Windows/GPU 未执行项明确标记
```

以下不算完成：

- 只创建文件或接口；
- 只通过 `compileall`；
- 测试被全部 skip；
- 只有 synthetic 测试但 Ticket 要求 Windows spawn/GPU；
- 未生成 summary；
- 通过 fallback 掩盖核心错误；
- 文档声称完成但没有 commit、命令或日志依据。

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

禁止跳过 01-08，直接让弱模型修改 Ticket 09/10 的 Generator 或 SAEHD 接线。

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
- 自动测试命令与 PASS / SKIP / PENDING / FAIL；
- 人工验证步骤；
- 未完成的 Windows / GPU 项；
- 兼容和回退证据；
- 风险与下一 ticket 建议；
- 下一 Ticket 可依赖的公共接口；
- 下一 Ticket 不应依赖的内部实现。

summary 模板以：

```text
.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md
```

为准。

## 弱模型执行建议

给能力较弱的模型分配任务时：

- 一次只分配一个 Ticket；
- 不同时分配并行 Ticket 07 和 08 给同一个弱模型；
- Ticket 09、10 应要求模型先输出源码事实复核，再允许编码；
- 要求每完成一个小步骤立即运行对应测试；
- 不把完整 Batch 2 一次性作为单个 prompt；
- 使用前置 summary 作为稳定接口，而不是让后续模型重新阅读全部历史提交；
- 高风险 Ticket 完成后应由更强模型或人工进行 code review。

## 参考文档

- `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
- `docs/development/batch2-training-data-and-sampling-tasks.md`
- `docs/development/batch1-correctness-and-extension-foundation-tasks.md`
- `docs/implementation/enhanced-dfl-master-implementation-plan.md`
- `docs/implementation/training-enhancement-implementation-plan.md`
- `docs/optimization/training-quality-algorithm-roadmap.md`
- `docs/optimization/src-dst-training-quality-optimization-design.md`
- `docs/implementation/deepfacelab-config-and-extension-architecture.md`
- `docs/implementation/deepfacelab-code-modification-map.md`
- `docs/implementation/manual-quality-acceptance-and-development-validation-standard.md`