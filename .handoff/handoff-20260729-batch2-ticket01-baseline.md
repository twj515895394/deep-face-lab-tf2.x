# Handoff: Batch 2 Ticket 01 — 基线、测试工作区与 Legacy 采样证据冻结落地

> 时间: 2026-07-29  
> 编号: H-015 (Batch 2 Ticket 01 Completion)

## 1. 本次完成的变更说明

我们成功落地方案并完成了 **Batch 2 Ticket 01** 的开发与基线证据冻结：

- **Synthetic Fixtures 生成器**:
  - 新增 [`tests/fixtures/batch2/build_synthetic_fixture.py`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/fixtures/batch2/build_synthetic_fixture.py)，自动生成不含真实人脸的合成 Aligned DFLIMG 样本（支持清晰、模糊、过暗/过亮及损毁文件），并支持生成 Ordinary 和 Packed (`faceset.pak`) 格式。
- **配置与环境描述契约**:
  - 新增 [`tests/fixtures/batch2/manifest.example.json`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/fixtures/batch2/manifest.example.json)。
- **基线与遗留算法证据冻结测试套件**:
  - 新增 [`tests/smoke/test_batch2_baseline.py`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_baseline.py)：
    - `collect_batch2_environment()` 环境收集与描述；
    - `SampleLoader` 对 Ordinary 和 Packed 人脸集样本加载及 `load_bgr`/`read_raw_file` 验证；
    - `IndexHost` 固定 seed 抽样序列、全 epoch 覆盖率证据冻结；
    - `Index2DHost` 多 Bucket 随机抽样冻结；
    - `SampleGeneratorFace` 的 Output Tensor contract (输出 shape, dtype, 数量) 证据冻结。
- **报告与模板文件**:
  - [`.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md)
  - [`.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md)

## 2. 验证结果与环境说明

- **验证模式**: macOS CPU / 无 GPU 环境（零语法/逻辑错误，未依赖物理 GPU）。
- **自动化测试状态**:
  - `python -m unittest tests.smoke.test_batch2_baseline`: 5/5 **PASS**
  - `python -m unittest discover -s tests/smoke -p "test_*.py"`: 85/85 **PASS**
- **Windows GPU 状态**: `PENDING-WINDOWS-GPU`（留存完整验收模板，待 Windows GPU 环境实测）。

## 3. 下一步计划

准备推进 **Batch 2 Ticket 02**:  
[`.scratch/batch2-training-data-and-sampling/issues/02-metadata-schema-and-identity.md`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/issues/02-metadata-schema-and-identity.md)
