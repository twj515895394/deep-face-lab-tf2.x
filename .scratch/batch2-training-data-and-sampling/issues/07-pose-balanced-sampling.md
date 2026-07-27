# 07 — 实现可解释、保守且可回退的 Pose-balanced Sampling

Status: open
Type: AFK
Blocked by: `06-sampling-policy-and-legacy-adapters.md`

**构建内容：** 基于 Metadata yaw bucket 构建保守的姿态权重，提高稀缺侧脸覆盖，同时通过强度、上下限、unknown 处理和统计报告避免极少数样本被无限重复。

## 目标

- 不追求所有姿态绝对均匀，而是可控地缓解分布失衡。
- 使用 7 个可解释 yaw bucket，不替换 legacy uniform_yaw。
- 空 bucket、unknown、极小 faceset 和错误 Metadata 都能安全处理。
- 权重公式是纯函数，可被独立统计验证。
- 每张可用样本保持非零概率。

## 详细任务

### Bucket 数据

- [ ] 消费 Metadata Loader 输出的 yaw_bucket_ids / pose_valid。
- [ ] 统计每个非空 bucket count。
- [ ] unknown 单独统计，不混入左右 bucket。
- [ ] 记录 src / dst 独立分布。

### 权重公式

建议：

```text
reference = median(non_empty_counts)
raw = (reference / max(count_b, 1)) ** balance_strength
bucket_weight = clip(raw, 0.5, 2.0)
```

- [ ] 默认 `balance_strength=0.5`。
- [ ] strength=0 时所有有效 bucket 权重 1。
- [ ] unknown 默认 0.75，但可配置且不得为 0。
- [ ] 空 bucket 不参与 median 和除法。
- [ ] 全部 unknown 时返回中性权重并告警。
- [ ] 权重最终按样本数组展开。
- [ ] 最终 finite、正数、均值归一化。

### Policy

- [ ] 新增 `PoseBalancedPolicy`。
- [ ] Metadata pose 不可用时返回 fallback，不自行猜测 yaw。
- [ ] `describe()` 输出 bucket counts、weights、strength、limits。
- [ ] 不在 policy 内读取图片。

### 分布测试

- [ ] 平衡 faceset：分布不应被大幅改变。
- [ ] 正脸 90%、侧脸 10%：侧脸抽样比例应明显提高但不占满。
- [ ] 只有一个非空 bucket：等价随机。
- [ ] 一个 bucket 只有一张：权重受 max 限制。
- [ ] 全部 unknown：中性/fallback。
- [ ] bucket boundary fixture。
- [ ] 固定 seed 大样本抽取，频率在理论容差内。

### 报告字段

- [ ] original bucket distribution。
- [ ] bucket weight。
- [ ] expected sampling distribution。
- [ ] 实际抽样分布由后续 Host 统计。
- [ ] unknown ratio 与建议。

## 建议文件

- `samplelib/sampling/weights.py`
- `samplelib/sampling/policies.py`
- `tests/smoke/test_batch2_pose_weights.py`

## 验收标准

- [ ] 稀缺 bucket 得到有限增强。
- [ ] 任意 bucket 不会因公式得到 Inf/NaN。
- [ ] 样本权重不为零。
- [ ] `balance_strength=0` 为中性行为。
- [ ] 关闭 Metadata Sampling 不调用此逻辑。
- [ ] legacy_uniform_yaw 仍可单独选择。

## 回退

pose 数据缺失、匹配率不足或权重无效时，由 Resolver 使用 fallback_mode。

## 不在本 ticket

- 不使用 pitch 做二维主采样。
- 不加入质量权重。
- 不实现多进程 Host。
- 不根据 Loss 动态调整。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/07-pose-balanced-sampling-summary.md`，记录公式、边界、分布模拟、默认值和 fallback。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；可与 Ticket 08 在 Ticket 06 后并行。
