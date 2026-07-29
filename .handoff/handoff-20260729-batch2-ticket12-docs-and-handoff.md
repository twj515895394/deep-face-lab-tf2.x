# Batch 2 Ticket 12 Compatibility Docs, Usage Guide & Handoff 落地交接

> 更新时间：2026-07-29  
> 对应目标：Batch 2 Ticket 12 (Compatibility Docs, Usage Guide & Handoff)  
> 当前状态：已完成 (macOS 轻量验证 PASS, 169/169 测试通过)  
> 关联批次：Batch 2 最终收口交接 (H-026)

---

## 1. 交付改动清单

1. **[docs/usage/faceset-metadata-and-sampling.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/docs/usage/faceset-metadata-and-sampling.md)** (新增):
   - 编写面向 DeepFaceLab 最终用户的完整使用指南。
   - 涵盖 Faceset Analyzer CLI (`faceset-analyze`) 全量 8 个参数说明与可复制场景示例。
   - 包含机器报告 JSON (`faceset_metadata_report.v1.json`) 关键指标说明。
   - 包含 `--options-json` 参数配置语法、4 种采样模式 (`legacy_random`, `legacy_uniform_yaw`, `pose_balanced`, `quality_pose_balanced`) 详解与权重微调范围。
   - 结构化排查表与常见 Fallback (`missing`, `invalid_file`, `unsupported_schema`, `partial_match`) 应对动作。

2. **[docs/README.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/docs/README.md)** (修改):
   - 更新文档版本至 `v2.2`。
   - 更新 Phase 3 / Batch 2 当前代码状态索引与最新交接入口。
   - 补充 Batch 2 详细设计与用户指南跳转链接。

3. **[docs/implementation/enhanced-dfl-master-implementation-plan.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/docs/implementation/enhanced-dfl-master-implementation-plan.md)** (修改):
   - 同步更新 Phase 3 数据与采样增强的实际实施状态为 `done-macos-lightweight-pending-windows`。

4. **[.scratch/batch2-training-data-and-sampling/spec.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/spec.md)** (修改):
   - 状态更新为 `done-macos-lightweight-pending-windows`。

5. **[.scratch/batch2-training-data-and-sampling/reports/12-compatibility-docs-and-handoff-summary.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/12-compatibility-docs-and-handoff-summary.md)** (新增):
   - 整理包含 9 项实现事实比对表与 14 场景证据化兼容性矩阵表。

6. **[.handoff/current.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.handoff/current.md)** (修改):
   - 更新全局交接入口至 `H-026 + Batch 2 Ticket 12 Completion`。

---

## 2. 稳定公共 API 承诺

后续 Batch 3 及以后功能可安全依赖以下 Batch 2 交付接口：

1. **Metadata Store & Schema**:
   - `samplelib.metadata.schema.SampleMetadata`: v1 结构。
   - `samplelib.metadata.atomic_store.read_metadata()` / `atomic_write_metadata()`: 原子 JSON 文件读写。
2. **Analyzer**:
   - `samplelib.metadata.analyzer.FacesetAnalyzer`: 支持 ordinary 文件夹与 packed `faceset.pak` 的分析器。
3. **Runtime Metadata Loader**:
   - `samplelib.metadata.loader.RuntimeMetadataLoader`: 内存索引、多侧边栏与 usable 匹配率校验。
4. **Sampling API & Host**:
   - `samplelib.sampling.config.SamplingConfig`: 支持字典解析与 4 种采样模式。
   - `samplelib.sampling.policy.SamplingPolicy`: 统一分配抽象。
   - `samplelib.sampling.weighted_host.WeightedIndexHost`: 多进程安全的概率权重采样宿主。
5. **SAEHD Integration**:
   - `models.Model_SAEHD.Model.build_sampling_runtime`: 解析 `--options-json` 构造底层采样逻辑。

---

## 3. 验证命令与结果

```bash
# 1. 编译与语法检查
./.venv/bin/python -m compileall samplelib/metadata samplelib/sampling mainscripts/FacesetAnalyzer.py models/Model_SAEHD/Model.py tests/smoke/

# 2. CLI Help 命令检查
./.venv/bin/python main.py faceset-analyze --help
./.venv/bin/python main.py train --help

# 3. 完整单元测试套件 (169 测试全量 PASS)
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

**运行结果**：
- **编译检查**：`PASS`
- **CLI 命令**：`PASS`
- **单元测试**：`PASS (169/169 PASS, 0 FAIL)`
- **Windows FP32 GPU 验收**：`PENDING-WINDOWS-GPU`

---

## 4. 明确延期的能力清单

以下功能已在用户文档与规划中明确列出为延期或未来批次任务：

- Dynamic Loss-aware Sampling（暂未开发）
- Identity Geometry / 脸型 Loss（Batch 4）
- Source Shape Template（Batch 5）
- Shape-aware Merge（Batch 6）
- Lion 算法深度拓展与 FP16/BF16 验收（Paused）

---

## 5. 下一步规划

1. **待办事件**：如具备 Windows GPU 环境，可按照 [.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md) 规程进行实机运行打卡。
2. **下一个批次**：开启 **Batch 3 (Multi-objective Loss Hook & Identity Appearance)** 前置需求研讨与方案设计。
