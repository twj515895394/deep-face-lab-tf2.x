# 09 — 实现 WeightedIndexHost 并接入多进程 SampleGeneratorFace

Status: open
Type: AFK
Blocked by: `07-pose-balanced-sampling.md`, `08-quality-aware-weighting.md`

**构建内容：** 使用中心 Host + 多 CLI queue 架构，把静态样本概率真正接入当前多进程 `SampleGeneratorFace`；保证 src/dst 独立、batch tensor contract 不变、固定 seed 可复现、极小 faceset 不死循环，并提供实际抽样统计。

## 风险级别

High。该 ticket 首次改变训练时样本索引来源，必须单独提交、单独回退，不能同时修改 Analyzer 公式或 SAEHD Loss。

## 目标

- 复用当前 `IndexHost` 的中心线程/queue 模式。
- 所有 Generator 子进程共享同一静态分布。
- 不把完整 Metadata JSON 发送到每个 worker。
- Generator 输出 tensor 数量、顺序、shape、dtype 完全不变。
- 不返回 sample_id，不引入动态 Loss 反馈。
- 提供统计证明新 policy 真的生效。

## WeightedIndexHost

- [ ] 新增 `samplelib/sampling/weighted_index_host.py`。
- [ ] 构造参数：weights/probabilities、rnd_seed、cycle_size、duplicate_retry_limit。
- [ ] 校验 N>0、shape、finite、正概率、概率和。
- [ ] 异常概率返回结构化错误，由上层 fallback，不在 Host 内静默猜测。
- [ ] Host 创建 daemon thread，与当前 queue 协议兼容或明确扩展。
- [ ] `create_cli().multi_get(count)` 保持当前调用形式。

## Weighted Cycle

- [ ] 默认 `cycle_size=max(N,4096)`，允许配置/测试覆盖。
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

建议新增参数：

```python
sampling_policy=None
sampling_metadata=None
sampling_seed=None
sampling_role=None
```

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

## 测试场景

### Host

- [ ] deterministic sequence。
- [ ] 不同 seed 序列不同。
- [ ] 概率统计容差。
- [ ] N=1、N<batch、N=batch、N>>batch。
- [ ] invalid weights。
- [ ] 多 CLI 并发请求。
- [ ] 长循环无 queue 堆积和死锁。
- [ ] Host/worker 可正常退出。

### Generator

- [ ] legacy_random tensor contract 前后对比。
- [ ] legacy_uniform_yaw 前后对比。
- [ ] pose_balanced 普通目录。
- [ ] quality_pose Packed。
- [ ] src/dst 不同 policy。
- [ ] eyes_mouth False/True。
- [ ] random_ct_samples_path。
- [ ] generators_count=1 和 >1。
- [ ] Windows spawn。

## 性能记录

- [ ] Host build time。
- [ ] multi_get latency。
- [ ] cycle generation latency。
- [ ] generator samples/sec。
- [ ] legacy vs weighted 稳定训练 iter time，留给 Ticket 11 Windows 记录。

## 验收标准

- [ ] 实际抽样分布与期望方向一致。
- [ ] 多进程无死锁、无重复启动、可退出。
- [ ] batch tensor contract 与 legacy 相同。
- [ ] src/dst 权重不串用。
- [ ] 所有样本有非零抽样机会。
- [ ] 关闭/缺失 policy 后完全回到当前旧代码。
- [ ] 不修改 SAEHD loss、optimizer、checkpoint。

## 回退

保留 `SampleGeneratorFace` 当前 IndexHost / Index2DHost 分支。出现问题时 `sampling_policy=None` 或 Resolver 返回 legacy adapter 即可完全回退。

## 不在本 ticket

- 不新增用户交互选项。
- 不自动加载 Metadata 路径。
- 不做动态权重更新。
- 不做 GPU loss 反馈。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/09-weighted-index-host-and-generator-integration-summary.md`，记录并发模型、序列/分布测试、tensor contract、性能和 Windows 待验收项。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；是本批次运行时最高风险 ticket。
