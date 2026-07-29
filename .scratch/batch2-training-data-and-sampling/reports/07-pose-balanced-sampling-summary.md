# Batch 2 Ticket 07 — Pose-balanced Sampling 研发总结

> 完成时间：2026-07-29  
> 状态：PASS (macOS / venv 验证通过)

## 1. 概述与核心变更

本 Ticket 实现了基于 Metadata 姿态分桶 (Yaw Bucket) 的保守、可解释且无 NaN/Inf 的姿态采样权重计算与策略包扩展：

1. **`samplelib/sampling/weights.py`**:
   - `PoseWeightResult`: 包含 `sample_weights`, `bucket_counts`, `bucket_weights`, `expected_distribution`, `warnings`。
   - `compute_pose_weights(...)`: 纯函数实现，使用 `median(non_empty_counts)` 与 `(reference / count) ** balance_strength` 公式，剪裁在 `[min_bucket_weight, max_bucket_weight]` 之间。
   - 具备完整边界防御：`N=0`、全 unknown/invalid、单 Bucket、极端失衡及非有限值处理，均值归一化恢复为 1.0，保证每张可用样本权重正值且有限。

2. **`samplelib/sampling/policies.py`**:
   - `PoseBalancedPolicy`: 继承 `SamplingPolicy`，封装 `RuntimeMetadata` 的 `yaw_bucket_ids` 与 `pose_valid`。
   - `build_index_host()` 明确抛出 `NotImplementedError` (等待 Ticket 09 生产 Host 接入)。
   - `describe()` 输出完整的配置、桶计数、桶权重、期望理论抽样分布及告警。

3. **`samplelib/sampling/factory.py`**:
   - 注册 `SamplingMode.POSE_BALANCED` 到 `SamplingPolicyFactory` 工厂决断列表。

---

## 2. 自动化测试验证

### 2.1 单元测试套件
```bash
./.venv/bin/python -m compileall samplelib/sampling tests/smoke/test_batch2_pose_weights.py
./.venv/bin/python -m unittest tests/smoke/test_batch2_pose_weights.py
```
- 测试结果：**11/11 PASS (100% 通过)**。
- 覆盖了 A (完全平衡)、B (强失衡)、C (单 Bucket)、D (极稀缺单张)、E (全 Unknown/Invalid)、F (部分 Invalid 混合)、strength=0 退化、N=0 空数据集、Monte Carlo 抽样模拟验证（50,000 次随机抽样模拟与理论期望分布误差 < 1.5%）。

---

## 3. `--options-json` 训练配置同步状态

```text
--options-json 文档同步：NA
文档版本：v1.0
修改章节：无（本 Ticket 仅实现姿态采样权重计算与 Policy，未改动 SAEHD CLI 训练参数）
```

---

## 4. 给 Ticket 09 (WeightedIndexHost) 的契约与参数

- **`PoseWeightResult` 约定**：
  - `sample_weights`: `float32[N]` 数组，严格满足 `sample_weights > 0` 且 `np.mean(sample_weights) == 1.0`。
  - Ticket 09 接入 `WeightedIndexHost` 时，直接消费 `sample_weights` 作为抽样概率依据，无需关心内部姿态算法细节。

---

## 5. Windows / GPU 待办

- **Windows 验收**：`PENDING-WINDOWS-GPU`
