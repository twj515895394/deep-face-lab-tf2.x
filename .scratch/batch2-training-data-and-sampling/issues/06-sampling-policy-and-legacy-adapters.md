# 06 — 建立 Sampling Policy API、配置对象与 legacy 适配层

Status: open
Type: AFK
Blocked by: `05-metadata-loader-folder-packed-compat.md`

**构建内容：** 在不改变当前 `IndexHost` / `Index2DHost` 默认行为的前提下，建立统一 Sampling Policy、requested/effective mode 解析、配置校验和 legacy adapter，为 Pose、Quality 和后续扩展提供稳定接入点。

## 目标

- 新模式不直接堆进 `SampleGeneratorFace.__init__` 条件分支。
- legacy_random 和 legacy_uniform_yaw 有明确适配器。
- requested mode、effective mode、fallback reason 可观测。
- 所有新参数有安全默认和边界裁剪。
- policy 构建不依赖 TensorFlow。

## 详细任务

### SamplingConfig

- [ ] 新增 `samplelib/sampling/config.py`。
- [ ] 字段：mode、metadata_path、fallback_mode、pose_balance_strength、quality_strength、uniform_mix、min/max weight、min_match_ratio、seed、log interval。
- [ ] mode 严格枚举：legacy、legacy_random、legacy_uniform_yaw、pose_balanced、quality_pose_balanced。
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

## 建议结果对象

```python
resolution = SamplingResolution(
    requested_mode="quality_pose_balanced",
    effective_mode="legacy_random",
    fallback_reason="metadata_missing",
    policy=LegacyRandomPolicy(...),
)
```

## 测试矩阵

- [ ] metadata_sampling=False + uniform_yaw False/True。
- [ ] mode=legacy + uniform_yaw False/True。
- [ ] explicit legacy_random / legacy_uniform_yaw。
- [ ] pose mode + metadata loaded。
- [ ] pose mode + metadata missing。
- [ ] quality mode + partial match above/below threshold。
- [ ] invalid mode / invalid numbers / NaN。
- [ ] strict runtime config。
- [ ] src loaded、dst fallback。
- [ ] config roundtrip。

## 验收标准

- [ ] 现有 legacy 两种行为可以通过统一 policy 调用。
- [ ] new mode 未实现完成前不会被错误启用。
- [ ] requested/effective/fallback 字段完整。
- [ ] 配置异常回到安全默认。
- [ ] policy 模块不读取图片、不导入模型。
- [ ] 为 Ticket 07/08 提供稳定接口。

## 回退

Factory 可以直接返回 legacy adapter；删除新 policy 文件后，Generator 仍可恢复当前旧分支。

## 不在本 ticket

- 不计算 pose 或 quality 权重。
- 不实现 WeightedIndexHost。
- 不修改 SAEHD 用户选项。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/06-sampling-policy-and-legacy-adapters-summary.md`，记录最终配置、模式解析表、legacy 一致性证据和 fallback 测试。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 05 完成。
