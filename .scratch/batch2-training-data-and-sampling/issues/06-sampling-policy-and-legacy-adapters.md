# 06 — 建立 Sampling Policy API、配置对象与 legacy 适配层

Status: open
Type: AFK
Blocked by: `05-metadata-loader-folder-packed-compat.md`

**构建内容：** 在不改变当前 `IndexHost` / `Index2DHost` 默认行为的前提下，建立统一 Sampling Policy、requested/effective mode 解析、配置校验和 legacy adapter，为 Pose、Quality 和后续扩展提供稳定接入点。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 05 summary，确认 `RuntimeMetadata` 状态与紧凑数组
3. `samplelib/SampleGeneratorFace.py` 当前 `uniform_yaw_distribution` 分支
4. `core/mplib/__init__.py::IndexHost/Index2DHost`
5. `core/enhancements/config.py` 当前安全配置解析方式
6. 正式详细设计中的模式优先级和 fallback 表

## 当前源码事实必须先确认

- legacy random 是否调用 `IndexHost(self.samples_len)`；
- uniform yaw 如何构建 128 bucket、yaw 符号如何处理；
- `Index2DHost` 是否没有 seed 参数；
- `SampleGeneratorFace` 的 ct_index_host 是否独立；
- `EnhancementConfig` 是否忽略 section 内未知字段；
- Ticket 05 `RuntimeMetadata.status` 的正式枚举值。

## 目标

- 新模式不直接堆进 `SampleGeneratorFace.__init__` 条件分支。
- legacy_random 和 legacy_uniform_yaw 有明确适配器。
- requested mode、effective mode、fallback reason 可观测。
- 所有新参数有安全默认和边界裁剪。
- policy 构建不依赖 TensorFlow。

## 建议对象模型

```python
class SamplingMode(Enum):
    LEGACY = "legacy"
    LEGACY_RANDOM = "legacy_random"
    LEGACY_UNIFORM_YAW = "legacy_uniform_yaw"
    POSE_BALANCED = "pose_balanced"
    QUALITY_POSE_BALANCED = "quality_pose_balanced"

@dataclass(frozen=True)
class SamplingConfig:
    mode: SamplingMode = SamplingMode.LEGACY
    fallback_mode: SamplingMode = SamplingMode.LEGACY_RANDOM
    pose_balance_strength: float = 0.5
    quality_strength: float = 0.5
    uniform_mix: float = 0.1
    min_sample_weight: float = 0.5
    max_sample_weight: float = 2.0
    min_metadata_match_ratio: float = 0.9
    seed: Optional[int] = None
    log_interval_draws: int = 10000

@dataclass
class SamplingResolution:
    requested_mode: str
    effective_mode: str
    fallback_reason: Optional[str]
    policy: "SamplingPolicy"
```

Python 3.9 使用 `Optional`，不要使用 `|` union。

## 建议施工顺序

### Step 1：先实现 SamplingConfig

- 独立于 `EnhancementConfig`；
- `from_mapping()` 安全解析；
- 所有浮点先 finite check；
- fallback_mode 只允许两个 legacy 模式；
- min/max 关系非法时回安全默认，不交换用户值后静默继续；
- roundtrip 测试。

### Step 2：实现 Policy 抽象和 legacy adapters

建议最小接口：

```python
class SamplingPolicy:
    mode: str

    def validate(self): ...
    def build_index_host(self, samples, role=None): ...
    def describe(self) -> dict: ...
```

`LegacyRandomPolicy` 必须直接复用现有 `IndexHost`。`LegacyUniformYawPolicy` 应提取或调用当前分桶逻辑，不能重新设计 7 bucket 版本来冒充 legacy。

### Step 3：先做 legacy contract 测试

在任何新 mode resolver 前，证明：

```text
metadata_sampling=False + uniform_yaw=False
→ LegacyRandomPolicy

metadata_sampling=False + uniform_yaw=True
→ LegacyUniformYawPolicy
```

对 IndexHost 固定 seed 情况比较序列；对 Index2DHost 至少比较 bucket 构造和输出 contract。

### Step 4：实现 Resolver 决策表

Resolver 只做模式选择，不计算 pose/quality 权重。建议伪代码：

```python
if not metadata_sampling:
    return resolve_legacy(uniform_yaw)
if config.mode == LEGACY:
    return resolve_legacy(uniform_yaw)
if config.mode in explicit_legacy:
    return explicit_legacy_policy
if runtime_metadata is not usable:
    return fallback(config.fallback_mode, reason=runtime_metadata.status)
if requested_new_policy_not_registered:
    return fallback(..., reason="policy_unavailable")
return requested_policy
```

### Step 5：为 Ticket 07/08 预留注册点

不要提前实现权重，只提供显式注册或 factory 分支。新 policy 尚未实现时必须 fallback，不能返回空 policy。

## 详细任务

### SamplingConfig

- [ ] 新增 `samplelib/sampling/config.py`。
- [ ] 字段：mode、metadata_path、fallback_mode、pose_balance_strength、quality_strength、uniform_mix、min/max weight、min_match_ratio、seed、log interval。
- [ ] mode 严格枚举。
- [ ] fallback_mode 只允许 legacy_random 或 legacy_uniform_yaw。
- [ ] 数值安全解析、finite 检查和范围裁剪。
- [ ] 缺失 mapping 使用默认；未知字段不启用功能。
- [ ] `to_dict()` roundtrip。

### Policy Interface

- [ ] 新增 `samplelib/sampling/policies.py`。
- [ ] 定义 `SamplingPolicy.build_index_host()`、`describe()`、`validate()`。
- [ ] 定义 `LegacyRandomPolicy`，使用现有 `mplib.IndexHost`。
- [ ] 定义 `LegacyUniformYawPolicy`，复用当前 128 yaw 分组逻辑或提取为兼容 helper。
- [ ] legacy adapter 的默认随机语义不得无意改变。
- [ ] 新 policy 支持显式 seed；legacy 路径不强制改变历史默认。

### Factory / Resolver

- [ ] 新增 `samplelib/sampling/factory.py`。
- [ ] 输入：SamplingConfig、metadata runtime、legacy uniform_yaw、role。
- [ ] 输出：policy、requested/effective mode、fallback reason。
- [ ] `metadata_sampling=False` 时直接 legacy。
- [ ] mode=legacy 时映射旧 uniform_yaw。
- [ ] 新模式依赖不满足时按 fallback_mode。
- [ ] src / dst 分别解析。
- [ ] 解析失败不得吞掉训练数据为空等核心错误。

## 模式决策表必须写入测试

| master flag | requested mode | legacy uniform_yaw | Metadata | expected effective |
|---|---|---:|---|---|
| false | any | false | any | legacy_random |
| false | any | true | any | legacy_uniform_yaw |
| true | legacy | false | any | legacy_random |
| true | legacy | true | any | legacy_uniform_yaw |
| true | legacy_random | any | any | legacy_random |
| true | legacy_uniform_yaw | any | any | legacy_uniform_yaw |
| true | pose_balanced | any | unavailable | fallback_mode |
| true | quality_pose_balanced | any | usable | registered new policy |

## 最小测试命令

```bash
python -m compileall samplelib/sampling
python -m unittest \
  tests.smoke.test_batch2_sampling_config \
  tests.smoke.test_batch2_sampling_factory \
  tests.smoke.test_batch2_legacy_sampling_adapters
```

## 禁止捷径与常见错误

- 不允许把所有模式判断直接写回 `SampleGeneratorFace.__init__`。
- 不允许用新的 7 bucket 算法替代 legacy 128 yaw 分组。
- 不允许 invalid mode 自动选择最接近的字符串。
- 不允许 resolver catch `ValueError("No training data")` 并 fallback。
- 不允许 policy 读取 JSON 或图片；只消费构造时提供的数据。
- 不允许 new mode 未实现时返回 `None` 让下游崩溃。
- 不允许显式 seed 污染 NumPy 全局 RNG。

## 验收标准

- [ ] 现有 legacy 两种行为可以通过统一 policy 调用。
- [ ] new mode 未实现完成前不会被错误启用。
- [ ] requested/effective/fallback 字段完整。
- [ ] 配置异常回到安全默认。
- [ ] policy 模块不读取图片、不导入模型。
- [ ] 为 Ticket 07/08 提供稳定接口。
- [ ] legacy master flag 关闭路径有明确回归证据。

## 回退

Factory 可以直接返回 legacy adapter；删除新 policy 文件后，Generator 仍可恢复当前旧分支。

## 不在本 ticket

- 不计算 pose 或 quality 权重。
- 不实现 WeightedIndexHost。
- 不修改 SAEHD 用户选项。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/06-sampling-policy-and-legacy-adapters-summary.md`，记录最终配置、模式解析表、legacy 一致性证据和 fallback 测试。
- [ ] 给 Ticket 07/08 明确最终注册接口和 `SamplingResolution` 字段。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 05 完成。
- 2026-07-27：补充弱模型对象模型、Resolver 伪代码、模式决策表和 legacy 防回归要求。