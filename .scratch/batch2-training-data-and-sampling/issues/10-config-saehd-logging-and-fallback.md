# 10 — 接入 Enhancement Config、SAEHD 用户选项、启动日志与安全回退

Status: open
Type: AFK
Blocked by: `09-weighted-index-host-and-generator-integration.md`

**构建内容：** 把 Analyzer sidecar 和 Sampling Policy 正式接入 `FP32 + AdaBelief` SAEHD 训练入口；解析向后兼容配置，分别处理 src/dst，输出 requested/effective/fallback 日志，并保证 Metadata 失败时传统训练继续、核心训练错误仍然抛出。

## 风险级别

High。该 ticket 修改 SAEHD options 和 Generator 构造，但不得修改网络、Loss、optimizer、checkpoint 核心字段或 Merge/DFM 格式。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 05、06、09 summary，确认 Loader、Resolver、Generator 参数和 stats API
3. `core/enhancements/config.py` 全文件及 Batch 1 config 测试
4. `models/Model_SAEHD/Model.py::on_initialize_options/on_initialize`
5. `models/ModelBase.py` options 读取、first run、override、save 语义
6. `SampleGeneratorFace` 当前 src/dst 构造位置
7. Batch 1 save/resume smoke，避免破坏旧模型配置

## 当前源码事实必须先确认

- `EnhancementConfig` 当前只接受已知 bool section 字段，top-level extra 如何保留；
- SAEHD first run 与 override 的判断顺序；
- `self.options` 何时写回 `data.dat`；
- 当前 `uniform_yaw` 的询问、保存和使用位置；
- src/dst Generator 的参数是否完全对称；
- pretrain 是否复写 uniform_yaw/random warp；
- Ticket 09 `sampling_policy` 和 stats 的正式 API；
- 当前日志输出位置是否会在每个 worker 重复打印。

## 目标

- 配置向后兼容，旧模型无新字段仍正常加载。
- 用户只看到少量必要选项，高级参数不逐项轰炸交互。
- src/dst 分别解析 Metadata 与 effective policy。
- requested、effective、fallback 均可观测。
- optional sampling 错误可回退，核心训练错误继续抛出。
- 新功能关闭时旧 `uniform_yaw`、Generator 和保存恢复行为不变。

## 配置分层建议

不要把 sampling 全部塞入 `training` bool section。建议：

```python
@dataclass(frozen=True)
class SamplingConfig:
    mode: str = "legacy"
    metadata_path: Optional[str] = None
    fallback_mode: str = "legacy_random"
    pose_balance_strength: float = 0.5
    quality_strength: float = 0.5
    uniform_mix: float = 0.1
    min_sample_weight: float = 0.5
    max_sample_weight: float = 2.0
    min_metadata_match_ratio: float = 0.9
    seed: Optional[int] = None
    log_interval_draws: int = 10000
```

`EnhancementConfig` 负责 master flag 和持有/解析 sampling mapping，但 SamplingConfig 的数值校验复用 Ticket 06，不能复制两套逻辑。

## 默认配置

```json
{
  "training": {
    "enabled": false,
    "metadata_sampling": false
  },
  "sampling": {
    "mode": "legacy",
    "metadata_path": null,
    "fallback_mode": "legacy_random",
    "pose_balance_strength": 0.5,
    "quality_strength": 0.5,
    "uniform_mix": 0.1,
    "min_sample_weight": 0.5,
    "max_sample_weight": 2.0,
    "min_metadata_match_ratio": 0.9,
    "seed": null,
    "log_interval_draws": 10000
  }
}
```

## 建议施工顺序

### Step 1：只扩展 Config 和测试

先实现：

- `EnhancementConfig.from_mapping()` 读取 sampling；
- `sampling_config` property；
- `to_dict()` roundtrip；
- 未知/错误类型安全默认；
- 高 schema 关闭增强；
- 旧配置不重写。

此阶段不改 SAEHD。

### Step 2：实现纯函数模式优先级

建议：

```python
def resolve_sampling_request(metadata_sampling_enabled, sampling_config, legacy_uniform_yaw):
    ...
```

先用单元测试固定：

```text
master=False → 完全按旧 uniform_yaw
master=True + mode=legacy → 完全按旧 uniform_yaw
explicit legacy_* → 显式模式
new mode → 进入 Metadata Loader/Factory
```

### Step 3：实现自动 Metadata 路径解析

默认只尝试 Ticket 04 规定路径：

```text
<faceset>/faceset_metadata.v1.json
```

显式路径优先。不得扫描目录猜多个 JSON，也不得训练启动时自动运行 Analyzer。

建议返回：

```python
@dataclass
class MetadataPathResolution:
    requested_path: Optional[Path]
    effective_path: Optional[Path]
    source: str  # explicit/auto/missing
    warning: Optional[str]
```

### Step 4：接入 SAEHD options，但保持交互最小化

只在 first run 或 override 询问：

```text
Enable metadata sampling? [y/N]
Sampling mode [legacy/pose_balanced/quality_pose_balanced]
```

高级参数继续使用默认或配置 mapping。不要新增十几个 input prompt。

旧模型正常启动时：

- 不询问新选项，除非用户 override；
- 不强制写 `enhancements`/`sampling`；
- 不改旧 `uniform_yaw`。

### Step 5：在 `on_initialize` 分别构建 src/dst runtime

推荐 helper，避免在大函数堆代码：

```python
def build_sampling_runtime(role, samples_path, samples, enhancement_config, legacy_uniform_yaw, seed):
    """Load metadata, resolve policy and return structured runtime."""
```

返回：

```python
@dataclass
class SamplingRuntime:
    role: str
    metadata_runtime: Optional[RuntimeMetadata]
    resolution: SamplingResolution
    startup_log: dict
```

src/dst 独立调用；任何一侧 fallback 不影响另一侧。

### Step 6：接入 Generator

只把 Ticket 09 已定义参数传入。不要修改 `batch_func`、训练 tensor 或 `unified_train()`。

### Step 7：实现启动日志

启动日志每侧一次，示例：

```text
[Sampling][src]
  requested: quality_pose_balanced
  effective: quality_pose_balanced
  faceset: packed, samples=18420
  metadata: loaded, matched=18420/18420 (100.0%)
  pose buckets: ...
  quality p05/median/p95: ...
  weights min/mean/max: ...
  uniform mix: 0.10
  fallback: none
```

fallback 示例必须显示 reason，不允许只写“using legacy”。

### Step 8：实现周期 Stats 日志

只读取 `snapshot_stats()`，失败只影响观测。周期日志不得在每 iter 构建大数组或刷屏。

### Step 9：验证保存恢复

保存的是配置，不保存静态 Host cycle/抽样位置。恢复后：

```text
重新加载 Metadata
→ 重新 Resolver
→ requested/effective 重新日志
→ 模型/optimizer iteration 连续
```

如果 seed 固定，恢复后不要求继续原随机 cycle 的精确位置；文档必须说明静态采样器不保存 draw state。

## Enhancement Config 详细任务

- [ ] 扩展 `core/enhancements/config.py`，保留兼容 schema 策略。
- [ ] 保持 `training.metadata_sampling` 为 bool master flag。
- [ ] 新增可选 top-level `sampling` mapping。
- [ ] 复用 Ticket 06 `SamplingConfig` 安全解析和 `to_dict()`。
- [ ] 旧配置无 sampling 时只构造运行时默认，不强制改写旧 `data.dat`。
- [ ] 只有新模型或用户明确 override 时保存新配置。
- [ ] 未知字段、错误类型、高版本 schema 按现有安全策略处理。

## SAEHD Options

- [ ] 在 `on_initialize_options()` 读取/归一化增强配置。
- [ ] 新模型或 override 可询问 `Enable metadata sampling?`。
- [ ] 开启后询问简化 mode。
- [ ] metadata_path 默认 auto，不要求用户每次输入绝对路径。
- [ ] 高级参数不在普通交互逐项询问。
- [ ] 旧 `uniform_yaw` 保留，不静默改写。

## Legacy 优先级

- [ ] metadata_sampling=False：按旧 uniform_yaw。
- [ ] metadata_sampling=True + mode=legacy：按旧 uniform_yaw。
- [ ] explicit legacy_random / legacy_uniform_yaw：显式模式生效。
- [ ] 新 mode：使用 Metadata policy。
- [ ] 所有映射都有单元测试。

## Runtime Wiring

- [ ] src、dst 分别加载 Sample 和 Metadata。
- [ ] src、dst 分别 Resolver policy。
- [ ] 允许单侧 loaded / 单侧 fallback。
- [ ] 传入 `SampleGeneratorFace` 的 policy / metadata / role / seed。
- [ ] seed 派生规则避免 src/dst 得到完全相同索引序列。
- [ ] `pretrain`、debug、random_ct 等现有路径检查。
- [ ] Generator 输出 contract 不变。

## 启动日志字段

src/dst 分别输出：

- role；
- requested/effective mode；
- faceset format 和 sample count；
- Metadata path/status/matched ratio/fingerprint；
- pose bucket counts；
- quality p05/median/p95；
- weight min/mean/max；
- uniform mix；
- fallback reason。

日志不得输出每张样本详细内容、绝对隐私路径列表或完整 Metadata。

## Fallback 状态机

| 条件 | 行为 |
|---|---|
| master off | 旧 uniform_yaw 路径 |
| Metadata missing | fallback_mode + warning |
| invalid JSON | fallback_mode + warning |
| unsupported schema | fallback_mode + warning |
| partial match 达标 | 缺失记录中性，允许智能模式 |
| match ratio 不足 | fallback_mode |
| invalid probabilities | fallback_mode |
| stats 失败 | 保持 effective mode，只关闭 stats |
| no training data | 抛出核心错误 |
| SampleProcessor/TensorFlow error | 抛出核心错误 |

`fallback_on_optional_error=False` 时 optional sampling 初始化错误应明确失败，而非静默 legacy；但 master off 仍是正常 legacy。

## 最小测试命令

```bash
python -m compileall core/enhancements models/Model_SAEHD/Model.py
python -m unittest \
  tests.smoke.test_batch2_sampling_config \
  tests.smoke.test_batch2_saehd_sampling_options \
  tests.smoke.test_batch2_sampling_fallback \
  tests.smoke.test_batch2_sampling_logging
```

并复跑 Batch 1 config/save-resume 相关测试。

## 禁止捷径与常见错误

- 不允许把 SamplingConfig 数值解析复制到 SAEHD 形成第二套默认值。
- 不允许旧模型加载时无条件写回新 config。
- 不允许用户 master flag 关闭时仍加载 Metadata。
- 不允许 `mode=legacy` 忽略旧 uniform_yaw。
- 不允许训练启动自动运行 Analyzer。
- 不允许 src/dst 共用同一个 Host 或同一个未偏移 seed。
- 不允许 fallback 捕获 no-data、SampleProcessor、TensorFlow、save/load 错误。
- 不允许周期日志每 iter 扫描全样本。
- 不允许修改 loss、optimizer、模型文件列表或 DFM/Merge。
- 不允许将 Windows GPU 未验证写为完整 done。

## 保存恢复

- [ ] 不新增 optimizer saveable。
- [ ] 不修改 `data.dat` 核心字段语义。
- [ ] 保存退出恢复后重新加载静态 Metadata 和配置。
- [ ] Metadata 丢失后可 fallback 继续恢复模型。
- [ ] 旧模型无 enhancements 正常加载。
- [ ] 明确 sampler draw state 不持久化。

## 验收标准

- [ ] 用户可在 SAEHD 启动中启用新模式。
- [ ] 日志能证明实际 effective mode。
- [ ] Metadata 异常不阻止传统训练。
- [ ] 核心训练错误不会被 fallback 吞掉。
- [ ] 旧模型、旧 uniform_yaw 和保存恢复兼容。
- [ ] FP32 + AdaBelief 是本 ticket 的唯一正式 GPU 验收组合。
- [ ] Ticket 11 可以直接按日志和配置判断各场景，不需阅读内部实现。

## 回退

设置 `training.metadata_sampling=False` 或删除新 config mapping，恢复 legacy Generator 路径。运行时代码应保留明确的 optional branch。

## 不在本 ticket

- 不测试最终视觉质量提升。
- 不加入动态 Loss sampler。
- 不开发脸型 Loss。
- 不修改 Lion / FP16 / BF16。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/10-config-saehd-logging-and-fallback-summary.md`。
- [ ] 记录最终选项、配置 Schema、优先级表、日志样例、fallback 状态机和保存恢复结果。
- [ ] 给 Ticket 11 提供可复制的启动命令/交互答案和预期日志关键字。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；实现完成后进入完整测试 ticket。
- 2026-07-27：补充弱模型九步接线顺序、Config/Runtime 对象、fallback 状态机和核心错误边界。