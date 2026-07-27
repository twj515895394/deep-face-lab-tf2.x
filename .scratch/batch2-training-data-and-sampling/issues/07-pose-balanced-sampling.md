# 07 — 实现可解释、保守且可回退的 Pose-balanced Sampling

Status: open
Type: AFK
Blocked by: `06-sampling-policy-and-legacy-adapters.md`

**构建内容：** 基于 Metadata yaw bucket 构建保守的姿态权重，提高稀缺侧脸覆盖，同时通过强度、上下限、unknown 处理和统计报告避免极少数样本被无限重复。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 03 summary，确认 yaw bucket ID、unknown ID 和左右方向
3. Ticket 05 summary，确认 `RuntimeMetadata.yaw_bucket_ids/pose_valid`
4. Ticket 06 summary，确认 Policy/Factory 注册接口
5. `SampleGeneratorFace` 当前 legacy uniform yaw 分组，只用于对照，不可替换

## 当前源码和前置接口必须先确认

- yaw bucket 总数和 ID 顺序；
- unknown 是否使用负值或固定最后一类；
- `pose_valid=False` 与 unknown bucket 的关系；
- src/dst runtime metadata 是否各自独立；
- Ticket 06 `SamplingPolicy` 的正式构造和 `describe()` 约定；
- `min_sample_weight/max_sample_weight` 是此 Ticket 使用还是留到组合 Ticket 08。

## 目标

- 不追求所有姿态绝对均匀，而是可控地缓解分布失衡。
- 使用 7 个可解释 yaw bucket，不替换 legacy uniform_yaw。
- 空 bucket、unknown、极小 faceset和错误 Metadata 都能安全处理。
- 权重公式是纯函数，可被独立统计验证。
- 每张可用样本保持非零概率。

## 推荐纯函数接口

```python
@dataclass
class PoseWeightResult:
    sample_weights: np.ndarray
    bucket_counts: np.ndarray
    bucket_weights: np.ndarray
    expected_distribution: np.ndarray
    warnings: list


def compute_pose_weights(
    yaw_bucket_ids: np.ndarray,
    pose_valid: np.ndarray,
    balance_strength: float = 0.5,
    unknown_weight: float = 0.75,
    min_bucket_weight: float = 0.5,
    max_bucket_weight: float = 2.0,
) -> PoseWeightResult:
    ...
```

函数不得读取 Metadata JSON、图片或全局配置。

## 建议施工顺序

### Step 1：输入校验

- 两个数组长度相同；
- bucket ID 在允许集合或 unknown；
- strength 和权重 finite；
- N=0 返回结构化错误，不生成空“成功”权重；
- bool mask 转为明确 dtype。

### Step 2：统计非空有效 bucket

只使用 `pose_valid=True` 的已知 bucket 计算 `non_empty_counts`。unknown 单独统计，不参与 median。

### Step 3：计算 bucket 权重

```text
reference = median(non_empty_counts)
raw_b = (reference / max(count_b, 1)) ** balance_strength
bucket_weight_b = clip(raw_b, 0.5, 2.0)
```

退化规则：

- strength=0：所有样本 1；
- 只有一个有效 bucket：所有样本 1；
- 全部 unknown：中性 1 并 warning；
- unknown：默认 0.75，但最终不得为 0；
- 空 bucket 不生成样本权重，也不除零。

### Step 4：展开到 sample 权重并归一化

先按 bucket 展开，再验证 finite/positive，最后均值归一化为约 1。若均值非法，返回错误交由 resolver fallback，不能在函数内静默随机。

### Step 5：实现 `PoseBalancedPolicy`

Policy 只封装已有 runtime arrays 和配置：

```python
class PoseBalancedPolicy(SamplingPolicy):
    def validate(self): ...
    def build_weights(self) -> PoseWeightResult: ...
    def describe(self) -> dict: ...
```

此 Ticket 不实现 WeightedIndexHost；`build_index_host()` 可明确抛 `NotImplementedError` 或由 Ticket 09 接入，但 factory 不得提前启用不可运行路径。推荐先让 factory 只在测试环境取得 weight result，Ticket 09 完成后才正式启用。

### Step 6：做分布模拟

使用纯 NumPy 理论概率或临时测试 sampler 验证方向，不要在本 Ticket 修改生产 Host。

## 详细任务

### Bucket 数据

- [ ] 消费 Metadata Loader 输出的 yaw_bucket_ids / pose_valid。
- [ ] 统计每个非空 bucket count。
- [ ] unknown 单独统计，不混入左右 bucket。
- [ ] 记录 src / dst 独立分布。

### 权重公式

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

## 必须实现的测试数据

至少构造以下数组，不依赖真实图片：

```text
A: [10,10,10,10,10,10,10] 平衡
B: [900,20,20,15,15,15,15] 强失衡
C: [100,0,0,0,0,0,0] 单 bucket
D: [0,0,0,0,0,0,1] 极稀缺
E: 全 unknown
F: 部分 invalid + unknown
```

每个案例断言：finite、positive、均值、权重上下限、预期方向。

## 最小测试命令

```bash
python -m compileall samplelib/sampling
python -m unittest tests.smoke.test_batch2_pose_weights
```

## 禁止捷径与常见错误

- 不允许直接使用 `1/count`，这会过度强化单张稀缺样本。
- 不允许把空 bucket count=0 放进 median 或除法。
- 不允许 unknown 权重为 0。
- 不允许重新从 landmarks 或图片计算 yaw。
- 不允许修改 legacy `Index2DHost` 或 uniform_yaw。
- 不允许在权重函数里抽样，纯权重与 Host 必须分层。
- 不允许只验证“侧脸权重大”，还必须验证平衡数据不会被明显扰动。

## 分布测试

- [ ] 平衡 faceset：分布不应被大幅改变。
- [ ] 正脸 90%、侧脸 10%：侧脸抽样比例应明显提高但不占满。
- [ ] 只有一个非空 bucket：等价随机。
- [ ] 一个 bucket 只有一张：权重受 max 限制。
- [ ] 全部 unknown：中性/fallback。
- [ ] bucket boundary fixture。
- [ ] 固定 seed 大样本抽取，频率在理论容差内；生产 Host 测试留给 Ticket 09。

## 报告字段

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
- [ ] Ticket 09 可以直接消费 `sample_weights`，无需理解姿态公式。

## 回退

pose 数据缺失、匹配率不足或权重无效时，由 Resolver 使用 fallback_mode。

## 不在本 ticket

- 不使用 pitch 做二维主采样。
- 不加入质量权重。
- 不实现多进程 Host。
- 不根据 Loss 动态调整。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/07-pose-balanced-sampling-summary.md`，记录公式、边界、分布模拟、默认值和 fallback。
- [ ] 给 Ticket 09 明确 `PoseWeightResult` dtype、shape、取值范围。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；可与 Ticket 08 在 Ticket 06 后并行。
- 2026-07-27：补充弱模型纯函数接口、退化规则、固定测试数组和禁止捷径。