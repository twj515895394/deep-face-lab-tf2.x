# Batch 2 Ticket 08 — Quality-aware 权重与 Quality + Pose 组合规则 研发总结

> 完成时间：2026-07-29  
> 状态：PASS (macOS / venv 验证通过)

## 1. 概述与核心变更

本 Ticket 实现了基于静态 `quality_score` 的保守质量权重计算、Pose + Quality 乘积组合归一化、以及统一混合 `uniform_mix` 均匀探索的概率转换：

1. **`samplelib/sampling/weights.py`**:
   - `QualityWeightResult`: 包含 `sample_weights`, `raw_min`, `raw_mean`, `raw_max`, `invalid_count`, `warnings`。
   - `compute_quality_weights(...)`: 纯函数实现，使用 3 阶 Cubic smoothstep 曲线 `q*q*(3 - 2*q)` 计算 `1 + strength*(2*smooth_q - 1)` (默认强度 0.5，对应权重 `[0.5, 1.5]`)。缺失或非有限得分赋中性权重 `1.0`。
   - `combine_sampling_weights(...)`: 计算 `pose * quality` 乘积后，按顺序执行 `clip -> mean_normalize -> re-clip -> re-normalize`，确保平均权重恢复为 1.0 且落在有限相对区间。
   - `weights_to_probabilities(...)`: 将样本权重转为加和为 1.0 的绝对概率分布，混合 `(1 - mix) * p_weighted + mix * (1/N)`，确保保底探索分量大于 0。

2. **`samplelib/sampling/policies.py`**:
   - `QualityPoseBalancedPolicy`: 继承 `SamplingPolicy`，调用 `compute_pose_weights`、`compute_quality_weights`、`combine_sampling_weights` 及 `weights_to_probabilities` 导出完整概率分布。
   - `build_index_host()` 抛出 `NotImplementedError` (留待 Ticket 09 生产 Host 接入)。
   - `describe()` 输出完整的配置、质量统计、期望姿态分布、最小/最大权重与概率及告警。

3. **`samplelib/sampling/factory.py`**:
   - 在 `SamplingPolicyFactory` 中默认注册 `SamplingMode.QUALITY_POSE_BALANCED`。

---

## 2. 自动化测试验证

### 2.1 单元测试套件
```bash
./.venv/bin/python -m compileall samplelib/sampling tests/smoke/test_batch2_quality_weights.py tests/smoke/test_batch2_combined_weights.py
./.venv/bin/python -m unittest tests/smoke/test_batch2_quality_weights.py tests/smoke/test_batch2_combined_weights.py
```
- 测试结果：**10/10 PASS (100% 通过)**。
- 包含了 Smoothstep 曲线数值单调性、strength=0 退化、NaN/Inf/Invalid 质量中性分配、稀缺姿态低质量样本保留断言（稀缺侧脸权重不被抹杀）、`uniform_mix` 保底概率分配及 Policy/Factory 决断逻辑。

---

## 3. `--options-json` 训练配置同步状态

```text
--options-json 文档同步：NA
文档版本：v1.0
修改章节：无（本 Ticket 仅实现质量权重计算与组合 Policy，未改动 SAEHD CLI 训练参数）
```

---

## 4. 给 Ticket 09 (WeightedIndexHost) 的契约与参数

- **`probabilities` 约定**：
  - `probabilities`: `float32[N]` 数组，严格满足 `probabilities > 0` 且 `np.sum(probabilities) == 1.0`。
  - 每个样本保底具备至少 `uniform_mix * (1 / N)` 的概率分量。
  - Ticket 09 `WeightedIndexHost` 在构建多进程采样池时，直接消费该 `probabilities` 数组。

---

## 5. Windows / GPU 待办

- **Windows 验收**：`PENDING-WINDOWS-GPU`
