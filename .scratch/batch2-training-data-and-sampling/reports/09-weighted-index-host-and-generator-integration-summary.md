# Batch 2 Ticket 09: WeightedIndexHost & SampleGeneratorFace Integration Summary

## 基础信息

- **Ticket编号**：Batch 2 Ticket 09
- **构建内容**：实现 `WeightedCycleSampler` / `WeightedIndexHost` 中心加权索引服务端，支持预建加权循环数组、有限去重重试限制与非阻塞抽样统计 `SamplingStats`；在 `PoseBalancedPolicy` / `QualityPoseBalancedPolicy` 中完备实装 `build_index_host()`；在 `SampleGeneratorFace` 中以可选方式接入新 Policy，保证数据生成器输出 Tensor 契约 100% 兼容。
- **关联文件**：
  - [stats.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/sampling/stats.py)
  - [weighted_index_host.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/sampling/weighted_index_host.py)
  - [policies.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/sampling/policies.py)
  - [SampleGeneratorFace.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/SampleGeneratorFace.py)
  - [test_batch2_weighted_cycle.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_weighted_cycle.py)
  - [test_batch2_weighted_index_host.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_weighted_index_host.py)
  - [test_batch2_generator_sampling.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/tests/smoke/test_batch2_generator_sampling.py)

---

## 验证结论与测试状态

```text
--options-json 文档同步：NA (本 Ticket 未新增/修改训练 CLI 参数)
代码编译检查 (compileall)：PASS
单元测试 (test_batch2_weighted_cycle.py)：PASS (5/5)
单元测试 (test_batch2_weighted_index_host.py)：PASS (4/4)
单元测试 (test_batch2_generator_sampling.py)：PASS (5/5)
Batch 2 整体烟雾测试套件 (165/165)：PASS
Windows FP32 + AdaBelief 验收：PENDING-WINDOWS-GPU
```

---

## 核心设计与契约保持

1. **加权循环抽样引擎 (WeightedCycleSampler)**：
   - 严格校验概率分布 (1D, N>0, finite, 非负, sum>0)，转 `float64` 归一化。
   - 使用独立 `np.random.RandomState(seed)`，通过 `choice(N, size=cycle_size, p=probs)` + `shuffle` 预建 cycle 循环数组，规避每个 batch 动态加权计算的 O(N) 性能开销。
   - 在 N >= batch_size 时执行有限去重重试 (`duplicate_retry_limit=16`)，在 retry 上限或 N < batch_size 时允许重复，杜绝无界死循环。
2. **多进程 Index Server (WeightedIndexHost)**：
   - 与 `mplib.IndexHost` 请求格式契约兼容，提供后台服务线程与 `multiprocessing.Queue` 交互。
   - 捕捉内部异常标记 fatal 状态并支持显式 `close()`，客户端 `multi_get` 具备存活与超时检查，防止 worker 永久阻塞。
3. **数据生成器 Zero-Break 回退保障**：
   - `SampleGeneratorFace` 添加可选 `sampling_policy` 参数。为 `None` 时继续走 legacy `IndexHost` / `Index2DHost` 逻辑；传入新 policy 时调用其 `build_index_host()`。
   - yielded NDArray 数量、顺序、shape 和 dtype 保持完全一致，未向 batch 插入额外 sample_id。
   - src 和 dst 采样服务相互独立，不共享 host 或随机状态。

---

## 交付与后续准备

- 本 Ticket 修改全部集中于 `samplelib/sampling/` 与 `SampleGeneratorFace.py` 的可选分支，默认行为与 legacy 100% 保持一致。
- 为下一个任务 **Ticket 10 (Resolver & SAEHD Integration)** 奠定了加权采样 Host 与 Generator 基础。
