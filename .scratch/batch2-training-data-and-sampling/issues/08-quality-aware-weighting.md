# 08 — 实现 Quality-aware 权重与 Quality + Pose 组合规则

Status: open
Type: AFK
Blocked by: `06-sampling-policy-and-legacy-adapters.md`

**构建内容：** 将 Analyzer 的静态 quality score 转换为保守采样权重，并与 Pose 权重组合、归一化、裁剪和混合均匀探索；降低明显低价值样本的重复频率，但不删除样本、不修改 Loss、不让任何可读样本永久失去训练机会。

## 目标

- quality 只改变抽样概率，不乘训练 Loss。
- unknown / missing Metadata 使用中性权重。
- 默认范围保守，不能只剩高清正脸。
- pose 与 quality 冲突时有明确、可观测的组合规则。
- 所有公式纯函数、finite、可复现。

## 详细任务

### Quality Weight

建议：

```text
smooth_q = q*q*(3-2*q)
quality_weight = 1 + quality_strength*(2*smooth_q-1)
```

- [ ] q 安全裁剪到 `[0,1]`。
- [ ] 默认 `quality_strength=0.5`，大致产生 `[0.5,1.5]`。
- [ ] strength=0 返回中性权重。
- [ ] quality_valid=False / metadata missing 返回 1.0。
- [ ] NaN/Inf 返回中性并记录 warning count。
- [ ] 不根据 `issues` 直接置零。

### Weight Bounds / Normalize

- [ ] 默认 min=0.5、max=2.0。
- [ ] 配置硬安全范围 min>=0.25、max<=3.0。
- [ ] clip → mean normalize → 再 clip。
- [ ] mean 非法或全零时回到 uniform weights。
- [ ] 记录 clip low/high counts。

### Pose + Quality

```text
combined_i = pose_weight_i * quality_weight_i
```

- [ ] 组合后统一归一化和裁剪。
- [ ] 稀缺 bucket 低质量样本不能被全部清除。
- [ ] 输出每个 pose bucket 的 quality 分位数和期望抽样分布。
- [ ] src / dst 分别计算。

### Uniform Exploration

```text
p_final = (1-uniform_mix)*p_weighted + uniform_mix*(1/N)
```

- [ ] 默认 uniform_mix=0.10。
- [ ] 安全范围建议 0.05-0.30；0 仅允许显式高级配置。
- [ ] 最终概率和为 1、全部正数、finite。
- [ ] 极小样本集正常。

### Policy

- [ ] 新增/完成 `QualityPoseBalancedPolicy`。
- [ ] Metadata 只有 pose、quality 部分缺失时：缺失 quality 中性，不整体失败。
- [ ] pose 数据整体不可用时按 resolver fallback。
- [ ] `describe()` 输出 quality strength、weight min/mean/max、uniform mix、clip counts。

## 测试场景

- [ ] q=0/0.5/1 和边界外值。
- [ ] quality 全相同：分布中性。
- [ ] 少量低质量图：仍有非零概率。
- [ ] 所有 quality invalid：等价 pose-only 或 uniform。
- [ ] 稀缺侧脸质量较低：姿态仍获得有限覆盖。
- [ ] NaN/Inf/负配置。
- [ ] 大数组概率和、finite、内存 dtype。
- [ ] 固定 seed 统计分布。

## 建议文件

- `samplelib/sampling/weights.py`
- `samplelib/sampling/policies.py`
- `tests/smoke/test_batch2_quality_weights.py`
- `tests/smoke/test_batch2_combined_weights.py`

## 验收标准

- [ ] 不修改任何训练 loss tensor。
- [ ] 不产生零概率。
- [ ] missing Metadata 不被当成坏图。
- [ ] 组合权重 finite 且在安全范围。
- [ ] 默认参数对分布的改变保守且可解释。
- [ ] uniform exploration 在统计测试中可观察。

## 回退

quality 数据不可用时退化为 pose-only；组合权重整体异常时由 Resolver/Host 回退 legacy。

## 不在本 ticket

- 不读取单样本训练 Loss。
- 不识别长期学不动样本。
- 不自动生成清理列表之外的文件操作。
- 不实现多进程索引 Host。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/08-quality-aware-weighting-summary.md`，记录公式、默认参数、分布模拟、clip/fallback 和人工抽查结论。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；可与 Ticket 07 在 Ticket 06 后并行。
