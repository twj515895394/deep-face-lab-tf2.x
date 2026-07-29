# Handoff: Batch 2 Ticket 06 — Sampling Policy API & Legacy Adapters 落地交接

> 时间: 2026-07-29  
> 编号: H-020 (Batch 2 Ticket 06 Completion)

## 1. 本次完成的变更说明

我们成功落地方案并实现了 **Batch 2 Ticket 06**：

- **`samplelib/sampling/config.py`**:
  - 提供 `SamplingMode` (Enum) 和不可变的 `SamplingConfig` (dataclass `frozen=True`)，包含强大的 `from_mapping` 安全解析与数值边界防崩溃。
- **`samplelib/sampling/policies.py`**:
  - 提供 `SamplingPolicy` 抽象基类；
  - 实现 `LegacyRandomPolicy`（绑定 `mplib.IndexHost`）；
  - 实现 `LegacyUniformYawPolicy`（完美继承 128 yaw 线性空间分桶与 `mplib.Index2DHost`）。
- **`samplelib/sampling/factory.py`**:
  - 提供 `SamplingResolution` 与 `SamplingPolicyFactory.resolve`，实现 8 种场景决策矩阵表，以及 Ticket 07/08 的动态 Policy 注册点 `register_policy`。
- **测试套件**:
  - [`tests/smoke/test_batch2_sampling_config.py`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_sampling_config.py)
  - [`tests/smoke/test_batch2_legacy_sampling_adapters.py`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_legacy_sampling_adapters.py)
  - [`tests/smoke/test_batch2_sampling_factory.py`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_sampling_factory.py)
- **总结报告**:
  - [`06-sampling-policy-and-legacy-adapters-summary.md`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/06-sampling-policy-and-legacy-adapters-summary.md)

## 2. 验证结果

- **测试用例**: `./.venv/bin/python -m unittest discover -s tests/smoke -p "test_*.py"`: 130/130 **PASS** (100% 通过)。

## 3. 下一步计划

准备推进 **Batch 2 Ticket 07**:  
[`.scratch/batch2-training-data-and-sampling/issues/07-pose-balanced-sampling.md`](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/issues/07-pose-balanced-sampling.md)
