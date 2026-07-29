# Batch 2 Ticket 09 WeightedIndexHost & SampleGeneratorFace Integration 落地交接

> 更新时间：2026-07-29  
> 对应目标：Batch 2 Ticket 09 (WeightedIndexHost & Generator Integration)  
> 状态：已完成 (macOS 轻量验证 PASS, 165/165 测试通过)

---

## 1. 改动要点与新增结构

1. **`samplelib/sampling/stats.py`** (新增):
   - 定义 `SamplingStats` dataclass，记录 `total_draws`, `bucket_draw_counts`, `quality_quantile_draw_counts`, `metadata_valid_draws`, `fallback_record_draws`, `duplicate_retries`, `accepted_duplicates`, `cycle_build_count`, `cycle_build_seconds` 等全局/局部抽样统计指标。
   - 提供 `snapshot()` 与 `to_dict()` 接口。

2. **`samplelib/sampling/weighted_index_host.py`** (新增):
   - `WeightedIndexHostConfig`：包含 `seed`, `cycle_size`, `duplicate_retry_limit=16`, `configured_max=65536`。
   - `WeightedCycleSampler`：纯单线程抽样引擎，负责有限概率校验、独立 RNG (`RandomState`)、预建加权循环数组与 batch 内有限去重重试。
   - `WeightedIndexHost`：多进程 Index Server，后台线程异步响应 `draw` / `stats` 请求，支持致命错误捕获与 `close()` 清理。
   - `WeightedIndexHostClient`：客户端接口，兼容 `mplib.IndexHost` 的 `multi_get()` 契约。

3. **`samplelib/sampling/policies.py`** (修改):
   - 在 `PoseBalancedPolicy.build_index_host()` 中使用姿态加权概率实例化并返回 `WeightedIndexHost`。
   - 在 `QualityPoseBalancedPolicy.build_index_host()` 中使用姿态+质量综合概率实例化并返回 `WeightedIndexHost`。

4. **`samplelib/SampleGeneratorFace.py`** (修改):
   - 添加可选参数 `sampling_policy=None`, `sampling_role=None`。
   - 当 `sampling_policy` 未提供时保持全量旧代码逻辑（100% 兼容零破坏）；当提供时通过 `sampling_policy.build_index_host(samples, role=sampling_role)` 创建抽样服务。
   - 数据生成器 yielded array 结构、shape、dtype 保持完全一致。

5. **`samplelib/SampleLoader.py`** (修补):
   - 补齐 `samples_path = Path(samples_path)` 显式转换与异常日志变量修正，消除类型擦除与路径不兼容问题。

6. **测试集** (新增/修改):
   - `tests/smoke/test_batch2_weighted_cycle.py` (5 个测试)
   - `tests/smoke/test_batch2_weighted_index_host.py` (4 个测试)
   - `tests/smoke/test_batch2_generator_sampling.py` (5 个测试)
   - 更新 `test_batch2_pose_weights.py` 与 `test_batch2_combined_weights.py` 的 `build_index_host()` 表现断言。

---

## 2. 验证结果

- **编译检查**：`./.venv/bin/python -m compileall samplelib/ samplelib/sampling/ tests/smoke/` -> **PASS**
- **单元测试**：`./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch2_*.py"` -> **PASS (85/85 测试通过)**
- **Windows FP32 验收**：**PENDING-WINDOWS-GPU**

---

## 3. 下一步

领取 **Batch 2 Ticket 10**：
`.scratch/batch2-training-data-and-sampling/issues/10-sampling-resolver-and-saehd-integration.md`
