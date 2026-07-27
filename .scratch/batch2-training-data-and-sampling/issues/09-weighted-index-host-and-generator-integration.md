# 09 — 实现 WeightedIndexHost 并接入多进程 SampleGeneratorFace

Status: open
Type: AFK
Blocked by: `07-pose-balanced-sampling.md`, `08-quality-aware-weighting.md`

**构建内容：** 使用中心 Host + 多 CLI queue 架构，把静态样本概率真正接入当前多进程 `SampleGeneratorFace`；保证 src/dst 独立、batch tensor contract 不变、固定 seed 可复现、极小 faceset 不死循环，并提供实际抽样统计。

## 风险级别

High。该 ticket 首次改变训练时样本索引来源，必须单独提交、单独回退，不能同时修改 Analyzer 公式、SAEHD Loss、配置 Schema 或用户交互。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 01 baseline summary，尤其 legacy Generator tensor contract
3. Ticket 06 summary，确认 Policy/Factory/legacy adapter API
4. Ticket 07、08 summary，确认最终 probabilities、dtype、shape 和统计字段
5. `core/mplib/__init__.py::IndexHost/Index2DHost`
6. `samplelib/SampleGeneratorFace.py` 全文件
7. `core/joblib/SubprocessGenerator.py` 与 `ThisThreadGenerator`
8. 项目现有进程关闭、异常传播和 queue 使用方式

本 Ticket 不允许根据设计文档猜多进程行为。必须先读实际 `SubprocessGenerator` 实现。

## 当前源码事实必须先确认

编码前在 summary 草稿记录：

- `IndexHost` queue 请求格式和 CLI 响应格式；
- host thread 是否有 stop/close；
- `Index2DHost` 如何维护多个 CLI；
- `SampleGeneratorFace` 在 debug/subprocess 下如何创建 generator；
- `SubprocessGenerator.start_in_parallel()` 何时启动；
- worker 错误如何回传主进程；
- Generator 对象生命周期结束时是否显式关闭子进程；
- `random_ct_samples_path` 使用的 `ct_index_host` 是否完全独立；
- Ticket 07/08 输出是否为 probabilities，且 sum≈1、N 与 samples_len 一致。

若当前基础设施没有安全 close API，不要擅自大规模重写 joblib；先在本 Ticket 中定义最小 host lifecycle，并记录遗留风险。

## 目标

- 复用当前 `IndexHost` 的中心线程/queue 模式。
- 所有 Generator 子进程共享同一静态分布。
- 不把完整 Metadata JSON 发送到每个 worker。
- Generator 输出 tensor 数量、顺序、shape、dtype 完全不变。
- 不返回 sample_id，不引入动态 Loss 反馈。
- 提供统计证明新 policy 真的生效。
- 任何 queue/worker 异常不得形成永久等待。

## 推荐架构

```text
Main Process
├─ RuntimeMetadata compact arrays
├─ SamplingPolicy
├─ final probabilities[N]
├─ WeightedIndexHost
│  ├─ host thread
│  ├─ request queue
│  ├─ response queue per CLI
│  ├─ deterministic RNG
│  └─ SamplingStats
└─ SampleGeneratorFace
   ├─ worker 1: host_cli.multi_get(batch_size)
   ├─ worker 2: host_cli.multi_get(batch_size)
   └─ worker N: host_cli.multi_get(batch_size)
```

Metadata JSON 和 Analyzer 对象不得进入 worker。

## 建议接口骨架

```python
@dataclass(frozen=True)
class WeightedIndexHostConfig:
    seed: Optional[int] = None
    cycle_size: Optional[int] = None
    duplicate_retry_limit: int = 16

class WeightedIndexHost:
    def __init__(self, probabilities: np.ndarray, config: WeightedIndexHostConfig, bucket_ids=None, quality_quantiles=None): ...
    def create_cli(self): ...
    def snapshot_stats(self) -> dict: ...
    def close(self): ...

class WeightedIndexHostClient:
    def multi_get(self, count: int): ...
```

`multi_get()` 返回 `list[int]`，保持当前 Generator 用法。

## 建议施工顺序

### Step 1：先实现纯单线程 draw engine

不要一开始写 queue/thread。先实现：

```python
class WeightedCycleSampler:
    def build_cycle(self) -> np.ndarray: ...
    def draw(self, count: int) -> list[int]: ...
```

输入检查：

- N>0；
- 1D；
- finite；
- 全部 >0；
- sum finite 且 >0；
- 转 `float64` 归一化后再交 `RandomState.choice`；
- 不接受 NaN/Inf/负数/全零。

### Step 2：实现 weighted cycle

默认：

```text
cycle_size = max(N, 4096)
```

但大 N 时不应无界放大额外内存。建议：

```text
cycle_size = explicit or max(min(N, configured_max), 4096)
```

若正式设计已固定最大值，以正式设计为准，并在 summary 记录。

构建：

```python
cycle = rng.choice(N, size=cycle_size, replace=True, p=probabilities)
rng.shuffle(cycle)
```

使用独立 `np.random.RandomState(seed)`。不得使用全局 `np.random.choice`。

### Step 3：实现 batch 重复控制

只对当前请求结果做有限去重，不在整个 cycle 强制无重复。

建议伪代码：

```python
for each output position:
    candidate = next_from_cycle()
    if N >= count and candidate already in batch:
        retry up to limit
    accept candidate
```

规则：

- N<count：明确允许重复；
- retry 达上限：接受重复并统计；
- 不得 while True 无限重抽；
- 去重不能破坏概率到完全不可预测，但允许轻微 batch 局部偏差。

### Step 4：为 draw engine 写完整测试

完成 deterministic、概率、N 边界、duplicate retry 后，才进入线程/queue。

### Step 5：实现 Host thread 与 CLI

尽量复用 `IndexHost` 请求形状：

```text
request: (cli_id, count)
response: list[int]
```

增加控制命令时必须使用明确 tag，例如：

```text
("draw", cli_id, count)
("stop",)
("stats", cli_id)
```

不要混用魔法整数且无注释。

Host thread 必须：

- 捕获内部异常；
- 将结构化错误返回请求方或设置 fatal state；
- 不让 CLI 永久轮询；
- 支持 `close()`；
- daemon 仅作为最后保护，不替代正常关闭。

若当前项目 queue API 无 timeout，建议 client 轮询同时检查 host fatal/closed flag；不要直接无限等待。

### Step 6：实现非阻塞 Stats

Stats 更新只做整数计数，不在 draw 热路径计算大数组。

建议：

```python
@dataclass
class SamplingStats:
    total_draws: int
    bucket_draw_counts: np.ndarray
    quality_quantile_draw_counts: np.ndarray
    metadata_valid_draws: int
    fallback_record_draws: int
    duplicate_retries: int
    accepted_duplicates: int
    cycle_build_count: int
    cycle_build_seconds: float
```

`snapshot_stats()` 返回复制的紧凑 dict/array，不暴露内部可变对象。

### Step 7：接入 SampleGeneratorFace，但先保持新参数可选

建议新增参数：

```python
sampling_policy=None
sampling_metadata=None
sampling_seed=None
sampling_role=None
```

接入顺序：

```python
if sampling_policy is None:
    执行原代码，逐行尽量不动
else:
    index_host = sampling_policy.build_index_host(...)
```

不要把 legacy adapter 强制改走新 Host。legacy 继续使用现有 `IndexHost/Index2DHost`，这是回退边界。

### Step 8：验证 batch_func 完全不变

`batch_func()` 应继续：

```text
indexes = index_host.multi_get(bs)
→ samples[index]
→ load_bgr
→ SampleProcessor.process
→ yield arrays
```

不得返回 sample_id 或 stats，不得修改 yielded arrays。

### Step 9：验证 src/dst 与 random_ct 隔离

- src policy/Host 独立；
- dst policy/Host 独立；
- seed 使用稳定派生，例如 base seed + role 固定偏移；
- ct_index_host 仍按旧逻辑；
- 任何一侧 fallback 不改变另一侧 Host。

### Step 10：最后做多进程和退出测试

先 debug/ThisThread，再 subprocess 1 worker，再多 worker，最后 Windows spawn。

## WeightedIndexHost 详细任务

- [ ] 新增 `samplelib/sampling/weighted_index_host.py`。
- [ ] 构造参数：weights/probabilities、rnd_seed、cycle_size、duplicate_retry_limit。
- [ ] 校验 N>0、shape、finite、正概率、概率和。
- [ ] 异常概率返回结构化错误，由上层 fallback，不在 Host 内静默猜测。
- [ ] Host 创建 daemon thread，与当前 queue 协议兼容或明确扩展。
- [ ] `create_cli().multi_get(count)` 保持当前调用形式。
- [ ] 增加明确 close/fatal 状态或记录基础设施限制。

## Weighted Cycle

- [ ] 默认 cycle 规则明确并有最大内存考虑。
- [ ] 用独立 `np.random.RandomState(seed)`，不污染全局 RNG。
- [ ] 按 p_final 带 replacement 预生成 cycle，再打乱。
- [ ] cycle 用尽后生成下一轮。
- [ ] 不随请求大小产生 O(N) 重算。
- [ ] 记录 cycle build time 和 total draws。

## Batch 内重复控制

- [ ] N>=batch_size 时有限尝试避免同 batch 重复。
- [ ] 设置最大 retry，达到后允许重复，避免卡死。
- [ ] N<batch_size 时明确允许重复。
- [ ] 记录 duplicate retry / accepted duplicate。

## Stats

- [ ] 新增 `samplelib/sampling/stats.py`。
- [ ] total draws。
- [ ] yaw bucket draw counts。
- [ ] quality quantile draw counts。
- [ ] metadata-valid / fallback record draws。
- [ ] duplicate retry。
- [ ] stats snapshot 不阻塞 Host 主线程。
- [ ] stats 可以被 SAEHD 周期日志读取。

## SampleGeneratorFace 接入

- [ ] 未提供 policy 时执行现有分支，代码路径和默认行为不变。
- [ ] legacy adapter 使用现有 IndexHost/Index2DHost。
- [ ] new policy 返回 WeightedIndexHost。
- [ ] `batch_func` 仍只消费 indexes。
- [ ] 不修改 `SampleProcessor.process()` 输入和返回。
- [ ] 不把 sample id 加到 yielded batches。
- [ ] src/dst 各自拥有 Host，不能共享权重。
- [ ] random color transfer 的 ct_index_host 不受影响。
- [ ] debug 单线程与 subprocess 都支持。
- [ ] worker 启动失败、Host thread 异常和关闭语义明确。

## 必须实现的测试层次

### A. Pure sampler

- deterministic sequence；
- different seed；
- distribution tolerance；
- N=1、N<batch、N=batch、N>>batch；
- invalid probabilities；
- duplicate retry limit；
- cycle rollover。

### B. Host

- 一个 CLI；
- 多 CLI 并发请求；
- 不同请求大小；
- 长循环；
- host fatal error 可被 client 感知；
- close 后请求明确失败；
- queue 不持续增长。

### C. Generator

- legacy_random tensor contract 前后对比；
- legacy_uniform_yaw 前后对比；
- pose_balanced ordinary；
- quality_pose packed；
- src/dst 不同 policy；
- eyes_mouth False/True；
- random_ct_samples_path；
- generators_count=1 和 >1；
- worker error propagation；
- Windows spawn。

## 概率统计测试建议

不要对随机序列做精确相等断言，除 deterministic 测试外。分布测试：

- 固定 seed；
- draws 至少 50k 或根据 N 调整；
- 对高概率/低概率方向和绝对误差设合理容差；
- 不使用过窄阈值制造 flaky test；
- summary 记录理论概率、实际频率和最大误差。

## 最小测试命令

```bash
python -m compileall samplelib/sampling samplelib/SampleGeneratorFace.py
python -m unittest \
  tests.smoke.test_batch2_weighted_cycle \
  tests.smoke.test_batch2_weighted_index_host \
  tests.smoke.test_batch2_generator_sampling
```

Windows spawn 测试命令和结果必须单独记录；非 Windows 只能标记 pending。

## 性能记录

- [ ] Host build time。
- [ ] `multi_get` 平均/p95 latency。
- [ ] cycle generation latency。
- [ ] generator samples/sec。
- [ ] stats snapshot latency。
- [ ] legacy vs weighted 稳定训练 iter time 留给 Ticket 11 Windows 记录。

## 禁止捷径与常见错误

- 不允许每个 worker 各自创建独立 RNG/权重 Host；会造成不可控分布和重复。
- 不允许每个 batch 调用 `np.random.choice(N, p=...)` 并重新归一化全数组。
- 不允许无限 retry 去重。
- 不允许 N<batch 时拒绝返回。
- 不允许 CLI 永久 `while True` 等待且没有 fatal/close 检查。
- 不允许把完整 Metadata JSON 传到 worker。
- 不允许修改 yielded batch 增加 sample_id。
- 不允许改动 `SampleProcessor.process()`。
- 不允许让 legacy_random/legacy_uniform_yaw 走新加权 Host。
- 不允许 catch worker 核心加载错误后继续返回空 batch。
- 不允许将 Host thread daemon 视作完整关闭机制。
- 不允许此 Ticket 同时修改 SAEHD options 或用户提示。

## 验收标准

- [ ] 实际抽样分布与期望方向一致。
- [ ] 多进程无死锁、无重复启动、可退出。
- [ ] batch tensor contract 与 legacy 相同。
- [ ] src/dst 权重不串用。
- [ ] 所有样本有非零抽样机会。
- [ ] 关闭/缺失 policy 后完全回到当前旧代码。
- [ ] 不修改 SAEHD loss、optimizer、checkpoint。
- [ ] Host 异常不会造成 client 永久阻塞。
- [ ] Ticket 10 可以读取结构化 stats 并构造 Generator，无需了解 Host 内部 queue。

## 回退

保留 `SampleGeneratorFace` 当前 IndexHost / Index2DHost 分支。出现问题时 `sampling_policy=None` 或 Resolver 返回 legacy adapter 即可完全回退。高风险实现必须集中在独立模块和小范围 optional branch 中。

## 不在本 ticket

- 不新增用户交互选项。
- 不自动加载 Metadata 路径。
- 不做动态权重更新。
- 不做 GPU loss 反馈。
- 不修改训练配置持久化。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/09-weighted-index-host-and-generator-integration-summary.md`。
- [ ] 记录并发模型、queue 协议、lifecycle、序列/分布测试、tensor contract、性能和 Windows 待验收项。
- [ ] 给 Ticket 10 明确 Generator 新参数、Policy build 接口、stats snapshot API 和 fallback 方法。
- [ ] 若 Windows spawn 未执行，状态不得写 resolved-windows。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；是本批次运行时最高风险 ticket。
- 2026-07-27：补充弱模型十步施工顺序、queue/lifecycle 约束、接口骨架、分层测试和高风险禁止项。