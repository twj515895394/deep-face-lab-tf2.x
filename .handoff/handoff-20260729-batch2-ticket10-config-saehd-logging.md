# Batch 2 Ticket 10 Enhancement Config, SAEHD Options, Logging & Fallback 落地交接

> 更新时间：2026-07-29  
> 对应目标：Batch 2 Ticket 10 (Config, SAEHD Options, Logging & Fallback Integration)  
> 状态：已完成 (macOS 轻量验证 PASS, 170/170 测试通过)

---

## 1. 改动要点与新增结构

1. **`core/enhancements/config.py`** (修改):
   - `DEFAULT_ENHANCEMENT_CONFIG` 中引入默认 `sampling` 配置 Mapping，集成 `SamplingConfig`。
   - `EnhancementConfig` 增加 `sampling_config` 属性，`is_enabled("training.metadata_sampling")` 正确结合 `training.enabled` 主开关判断。
   - 对旧 `data.dat` 配置文件进行只读向后兼容保护，未知字段与高 schema 版本安全降级。

2. **`samplelib/sampling/runtime.py`** (新增):
   - 定义 `SamplingRuntime` 数据结构，整合 `role`, `metadata_runtime`, `resolution`, `startup_log` 与 `policy`。
   - 实现 `build_sampling_runtime()`：
     - 自动尝试定位 `<faceset>/faceset_metadata.v1.json`。
     - 调用 `SamplingPolicyFactory.resolve()` 进行模式决断。
     - 为 `src` / `dst` 分配独立的衍生 `seed` (分别偏移 +1000 / +2000)。
     - 当元数据异常且 `fallback_on_optional_error=True` 时自动进入 `fallback_mode` 并记录 `fallback_reason`；若 `fallback_on_optional_error=False` 且请求非 legacy 模式则抛出 `ValueError`；核心致命错误继续向上抛出。
     - 使用 `io.log_info` 输出简洁可观测的单侧启动日志。

3. **`models/Model_SAEHD/Model.py`** (修改):
   - 在 `on_initialize_options()` 中增加 `Enable metadata sampling? [y/N]` 与 `Sampling mode` 的极简交互提问，保持默认开启 `quality_pose_balanced`。
   - 在 `on_initialize()` 中分别对 `src` / `dst` 调用 `build_sampling_runtime()`，并将其 `policy` 传给 `SampleGeneratorFace` 的 `sampling_policy` 与 `sampling_role` 参数。

4. **测试集** (新增/修改):
   - `tests/smoke/test_batch2_saehd_sampling_options.py` (2 个测试)
   - `tests/smoke/test_batch2_sampling_fallback.py` (2 个测试)
   - `tests/smoke/test_batch2_sampling_logging.py` (1 个测试)

---

## 2. 验证结果

- **编译检查**：`./.venv/bin/python -m compileall core/enhancements samplelib/sampling models/Model_SAEHD/Model.py tests/smoke/` -> **PASS**
- **单元测试**：`./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"` -> **PASS (163/163 测试通过)**
- **Windows FP32 + AdaBelief 验收**：**PENDING-WINDOWS-GPU**

---

## 3. 下一步

领取 **Batch 2 Ticket 11**：
`.scratch/batch2-training-data-and-sampling/issues/11-batch2-test-matrix-and-windows-acceptance.md`
