# 10 — 接入 Enhancement Config、SAEHD 用户选项、启动日志与安全回退

Status: open
Type: AFK
Blocked by: `09-weighted-index-host-and-generator-integration.md`

**构建内容：** 把 Analyzer sidecar 和 Sampling Policy 正式接入 `FP32 + AdaBelief` SAEHD 训练入口；解析向后兼容配置，分别处理 src/dst，输出 requested/effective/fallback 日志，并保证 Metadata 失败时传统训练继续、核心训练错误仍然抛出。

## 风险级别

High。该 ticket 修改 SAEHD options 和 Generator 构造，但不得修改网络、Loss、optimizer 或 checkpoint 格式。

## Enhancement Config

- [ ] 扩展 `core/enhancements/config.py`，保留 `schema_version=1`。
- [ ] 保持 `training.metadata_sampling` 为 bool master flag。
- [ ] 新增可选 top-level `sampling` mapping。
- [ ] 定义 `SamplingConfig` 安全解析和 `to_dict()`。
- [ ] 旧配置无 sampling 时只构造运行时默认，不强制改写旧 `data.dat`。
- [ ] 只有新模型或用户明确 override 时保存新配置。
- [ ] 未知字段、错误类型、高版本 schema 按现有安全策略处理。

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

## SAEHD Options

- [ ] 在 `on_initialize_options()` 读取/归一化增强配置。
- [ ] 新模型或 override 可询问 `Enable metadata sampling?`。
- [ ] 开启后询问简化 mode：legacy、pose_balanced、quality_pose_balanced。
- [ ] metadata_path 默认 auto，不要求用户每次输入绝对路径。
- [ ] 高级参数不在普通交互逐项询问，使用保守默认或配置文件。
- [ ] 旧 `uniform_yaw` 保留，不静默改写。

## Legacy 优先级

- [ ] metadata_sampling=False：按旧 uniform_yaw。
- [ ] metadata_sampling=True + mode=legacy：按旧 uniform_yaw。
- [ ] explicit legacy_random / legacy_uniform_yaw：显式模式生效。
- [ ] 新 mode：使用 Metadata policy。
- [ ] 所有映射都有单元测试。

## Runtime Wiring

- [ ] src、dst 分别调用 SampleLoader 和 Metadata Loader。
- [ ] src、dst 分别 Resolver policy。
- [ ] 允许 src loaded / dst fallback 或反向组合。
- [ ] 传入 `SampleGeneratorFace` 的 policy / metadata / role / seed。
- [ ] seed 派生规则避免 src/dst 得到完全相同索引序列。
- [ ] `pretrain`、debug、random_ct 等现有路径检查。
- [ ] Generator 输出 contract 不变。

## 启动日志

src/dst 分别输出：

- [ ] role。
- [ ] requested/effective mode。
- [ ] faceset format 和 sample count。
- [ ] Metadata path/status/matched ratio/fingerprint。
- [ ] pose bucket counts。
- [ ] quality p05/median/p95。
- [ ] weight min/mean/max。
- [ ] uniform mix。
- [ ] fallback reason。

日志不得输出每张样本详细内容。

## 周期日志

- [ ] 按 draws 间隔读取 Host stats。
- [ ] 输出实际 pose bucket 抽样比例。
- [ ] 输出 quality quantile、fallback draws、duplicate retry。
- [ ] 统计失败不影响训练，只降低观测能力并告警。

## Fallback 语义

- [ ] Metadata missing/invalid/unsupported/mismatch → fallback_mode。
- [ ] partial match 达标 → 缺失记录中性权重。
- [ ] 权重无效 → legacy fallback。
- [ ] optional sampling error 可由 `fallback_on_optional_error` 控制。
- [ ] `strict_validation` 只影响智能模式是否启用，不得伪造 legacy 成功。
- [ ] no training data、SampleProcessor error、TensorFlow error 继续抛出，不能被 optional fallback 吞掉。

## 保存恢复

- [ ] 不新增 optimizer saveable。
- [ ] 不修改 `data.dat` 核心字段语义。
- [ ] 保存退出恢复后重新加载静态 Metadata 和配置。
- [ ] Metadata 丢失后可 fallback 继续恢复模型。
- [ ] 旧模型无 enhancements 正常加载。

## 测试矩阵

- [ ] 旧模型无 enhancements。
- [ ] 新模型增强关闭。
- [ ] uniform_yaw False/True。
- [ ] src/dst Metadata 完整。
- [ ] 单侧缺失。
- [ ] JSON 损坏。
- [ ] unsupported schema。
- [ ] partial match。
- [ ] invalid weights。
- [ ] ordinary/packed。
- [ ] restart/save/resume harness 结构。

## 验收标准

- [ ] 用户可在 SAEHD 启动中启用新模式。
- [ ] 日志能证明实际 effective mode。
- [ ] Metadata 异常不阻止传统训练。
- [ ] 核心训练错误不会被 fallback 吞掉。
- [ ] 旧模型、旧 uniform_yaw 和保存恢复兼容。
- [ ] FP32 + AdaBelief 是本 ticket 的唯一正式 GPU 验收组合。

## 回退

设置 `training.metadata_sampling=False` 或删除新 config mapping，恢复 legacy Generator 路径。运行时代码应保留明确的 optional branch。

## 不在本 ticket

- 不测试最终视觉质量提升。
- 不加入动态 Loss sampler。
- 不开发脸型 Loss。
- 不修改 Lion / FP16 / BF16。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/10-config-saehd-logging-and-fallback-summary.md`，记录选项、配置 Schema、日志样例、fallback 和保存恢复结果。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；实现完成后进入完整测试 ticket。
