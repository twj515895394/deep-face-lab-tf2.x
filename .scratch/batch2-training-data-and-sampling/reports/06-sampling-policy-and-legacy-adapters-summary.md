# Batch 2 Ticket 06 — Sampling Policy API & Legacy Adapters 研发总结

> 完成时间：2026-07-29  
> 状态：PASS (macOS / venv 验证通过)

## 1. 概述与核心变更

本 Ticket 建立了统一的采样策略包 **`samplelib/sampling/`**，包含配置解析、策略抽象接口、Legacy 适配器及安全的决断工厂：

1. **`samplelib/sampling/config.py`**:
   - `SamplingMode` (Enum): 支持 `LEGACY`, `LEGACY_RANDOM`, `LEGACY_UNIFORM_YAW`, `POSE_BALANCED`, `QUALITY_POSE_BALANCED`。
   - `SamplingConfig` (dataclass `frozen=True`): 提供了不可变的采配置与安全的转换转换函数 `from_mapping`，具备数值有限性检查 (`math.isfinite`)、合法区间剪裁及 `min_sample_weight > max_sample_weight` 自动修复防御机制。

2. **`samplelib/sampling/policies.py`**:
   - 抽象基类 `SamplingPolicy`: 定义 `build_index_host`, `validate`, `describe`。
   - `LegacyRandomPolicy`: 直接适配并复用 `mplib.IndexHost`。
   - `LegacyUniformYawPolicy`: 100% 保留并继承 `SampleGeneratorFace.py` 的 128 yaw 线性空间分桶与 `mplib.Index2DHost` 算法。

3. **`samplelib/sampling/factory.py`**:
   - `SamplingResolution`: 输出 `requested_mode`, `effective_mode`, `fallback_reason`, `policy`。
   - `SamplingPolicyFactory.resolve(...)`: 100% 覆盖规格说明书冻结的 8 种模式决断表。针对未准备好或未注册的新策略，自动安全降级至 `config.fallback_mode`，并透传降级原因，防止系统异常崩溃。

---

## 2. 自动化测试验证

### 2.1 单元测试套件
```bash
./.venv/bin/python -m compileall samplelib/sampling
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_*.py"
```
- 测试结果：**130/130 PASS (100% 通过)**。

### 2.2 决断决策表 (Resolution Decision Table Verification)
- 验证了所有 8 种主开关 (`metadata_sampling`)、`legacy_uniform_yaw` 及 `RuntimeMetadata` 状态组合，均与规格冻结预期 100% 一致。

---

## 3. `--options-json` 训练配置同步状态

```text
--options-json 文档同步：NA
文档版本：v1.0
修改章节：无（本 Ticket 仅为核心 API 与 Legacy 适配层，无 SAEHD CLI 训练参数改动）
```

---

## 4. Ticket 07/08 可依赖的扩展接口与注册点

- **新 Policy 动态注册**：
  ```python
  SamplingPolicyFactory.register_policy(
      SamplingMode.POSE_BALANCED,
      lambda config, runtime_metadata: PoseBalancedPolicy(config, runtime_metadata)
  )
  ```
- **配置透传**：`config.pose_balance_strength`, `config.quality_strength`, `config.uniform_mix`, `config.min_sample_weight`, `config.max_sample_weight`

---

## 5. Windows / GPU 待办

- **Windows 验收**：`PENDING-WINDOWS-GPU`
