# 08 — 实现 Quality-aware 权重与 Quality + Pose 组合规则

Status: open
Type: AFK
Blocked by: `06-sampling-policy-and-legacy-adapters.md`

**构建内容：** 将 Analyzer 的静态 quality score 转换为保守采样权重，并与 Pose 权重组合、归一化、裁剪和混合均匀探索；降低明显低价值样本的重复频率，但不删除样本、不修改 Loss、不让任何可读样本永久失去训练机会。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 03 summary，确认 `quality_score` 定义、范围和 valid 语义
3. Ticket 05 summary，确认 runtime quality 数组和缺失记录中性值
4. Ticket 06 summary，确认 Policy/Factory 接口
5. Ticket 07 当前接口或 summary；若并行开发，只依赖双方已约定的纯权重结果，不直接互相改文件

## 当前前置接口必须先确认

- `quality_scores` dtype/shape；
- `quality_valid=False` 和 `metadata_valid=False` 的区别；
- `quality_score` 是否已经保证 `[0,1]`；
- Ticket 07 权重结果的正式字段和归一化约定；
- min/max weight 的安全范围由 Config 还是本函数负责最终校验；
- Factory 在 Policy 尚未具备 Host 时如何保持不可启用。

## 目标

- quality 只改变抽样概率，不乘训练 Loss。
- unknown / missing Metadata 使用中性权重。
- 默认范围保守，不能只剩高清正脸。
- pose 与 quality 冲突时有明确、可观测的组合规则。
- 所有公式纯函数、finite、可复现。

## 推荐纯函数接口

```python
@dataclass
class QualityWeightResult:
    sample_weights: np.ndarray
    raw_min: float
    raw_mean: float
    raw_max: float
    clip_low_count: int
    clip_high_count: int
    invalid_count: int
    warnings: list


def compute_quality_weights(
    quality_scores: np.ndarray,
    quality_valid: np.ndarray,
    quality_strength: float = 0.5,
) -> QualityWeightResult:
    ...


def combine_sampling_weights(
    pose_weights: np.ndarray,
    quality_weights: np.ndarray,
    min_weight: float,
    max_weight: float,
) -> np.ndarray:
    ...


def weights_to_probabilities(
    weights: np.ndarray,
    uniform_mix: float = 0.1,
) -> np.ndarray:
    ...
```

三个阶段必须分开测试，不要塞进一个函数。

## 建议施工顺序

### Step 1：实现 Quality Weight

```text
q = clip(q, 0, 1)
smooth_q = q*q*(3-2*q)
weight = 1 + strength*(2*smooth_q-1)
```

规则：

- invalid/missing → 1.0；
- NaN/Inf → 1.0 + warning count；
- strength=0 → 全 1；
- 不在此步骤做最终概率归一化。

### Step 2：实现安全 normalize/clip helper

推荐固定顺序并写测试：

```text
检查 finite/positive
→ clip(min,max)
→ 除以 mean
→ 再 clip(min,max)
→ 再检查 finite/positive
```

如果 mean 非法、数组为空或全零，返回结构化错误，由上层 fallback；测试 helper 可显式返回 uniform，但生产 Resolver 必须保留 reason。

### Step 3：实现 Pose + Quality 组合

```text
combined = pose * quality
→ normalize/clip helper
```

不要对 pose 和 quality 各自反复归一化后再隐藏性改变上限；summary 中必须写最终顺序。

### Step 4：实现 uniform exploration

先把正权重转成加和为 1 的 `p_weighted`，再：

```text
p_final = (1-mix)*p_weighted + mix*(1/N)
```

最后再做一次加和归一化以吸收浮点误差，断言所有概率 > 0。

### Step 5：实现 Policy 描述

`QualityPoseBalancedPolicy.describe()` 至少输出：

- quality strength；
- pose strength；
- weight min/mean/max；
- probability min/max；
- uniform mix；
- invalid quality count；
- clip low/high count；
- expected pose distribution。

## 详细任务

### Quality Weight

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
- [ ] mean 非法或全零时回到结构化失败，由 Resolver 选择 uniform/legacy。
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
- [ ] `describe()` 输出完整统计。

## 必须实现的数值测试

```text
q = [0, 0.25, 0.5, 0.75, 1]
invalid mask 混合
q 全相同
q 含 NaN/Inf
pose 稀缺样本 quality 较低
N=1 / N=2 / N=100000
uniform_mix = 0 / 0.1 / 0.3
非法 min/max/strength
```

断言：

- weight/probability finite；
- probability 全正且 sum≈1；
- missing quality 为中性；
- uniform mix 后任何样本概率至少包含 `mix/N` 分量；
- 稀缺侧脸不因 quality 低被完全消除。

## 最小测试命令

```bash
python -m compileall samplelib/sampling
python -m unittest \
  tests.smoke.test_batch2_quality_weights \
  tests.smoke.test_batch2_combined_weights
```

## 禁止捷径与常见错误

- 不允许把 quality weight 乘到训练 loss。
- 不允许 `issues` 中出现 blur 就直接 weight=0。
- 不允许 missing Metadata 使用 quality=0。
- 不允许先转概率、乘 pose 后忘记重新归一化。
- 不允许 uniform mix 前后出现负数或零概率。
- 不允许使用 softmax 放大极端权重；本批次坚持保守线性/乘法设计。
- 不允许在 Policy 中读取图片或单样本训练 Loss。
- 不允许为了测试通过把 NaN 静默替换为高质量权重。

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
- [ ] Ticket 09 可以直接消费最终 probabilities 和 describe 数据。

## 回退

quality 数据不可用时退化为 pose-only；组合权重整体异常时由 Resolver/Host 回退 legacy。

## 不在本 ticket

- 不读取单样本训练 Loss。
- 不识别长期学不动样本。
- 不自动执行任何图片文件操作。
- 不实现多进程索引 Host。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/08-quality-aware-weighting-summary.md`，记录公式、默认参数、分布模拟、clip/fallback 和人工抽查结论。
- [ ] 给 Ticket 09 明确最终 probabilities dtype、shape、正数和归一化契约。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；可与 Ticket 07 在 Ticket 06 后并行。
- 2026-07-27：补充弱模型分层纯函数、数值测试、uniform exploration 断言和禁止捷径。