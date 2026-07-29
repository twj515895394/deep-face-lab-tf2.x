# 交接文档：`--options-json` 训练配置权威参考

**创建时间**：2026-07-29 15:30（UTC+8）  
**交接主题**：建立独立 `--options-json` 参数文档，并冻结 Batch 2 参数同步规则

---

## 1. 本轮完成

新增权威文档：

```text
docs/implementation/options-json-training-configuration-reference.md
```

文档定位为：

```text
ACTIVE / SINGLE SOURCE OF TRUTH
```

它统一维护：

- 当前 `--options-json` 调用链；
- 非空 JSON 与 silent start 的关系；
- 配置覆盖和持久化语义；
- 已有 SAEHD 顶层训练参数；
- Batch 2 `enhancements.training/sampling/runtime` 完整 Schema；
- 参数类型、默认值、范围和状态；
- PowerShell、CMD、BAT 与 GUI argv 示例；
- Unicode/UTF-8 要求；
- Ticket 10 必须增加的测试；
- 后续参数变更同步清单和变更记录。

## 2. Batch 2 固定 JSON 形状

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "quality_pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": 12345,
      "log_interval_draws": 10000
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

智能 Sampling 的双 Gate：

```text
enhancements.training.enabled == true
AND
enhancements.training.metadata_sampling == true
```

## 3. 新增维护规则

已更新根目录 `AGENTS.md`：

- 所有新增、删除、重命名或改变语义的训练参数，必须在同一提交或 PR 中同步权威文档；
- 必须同步参数表、示例、变更记录和测试；
- 未同步文档的训练参数 Ticket/PR 不得标记 resolved；
- 相关 Ticket summary 必须记录文档同步状态和文档版本。

## 4. 当前实现状态

```text
--options-json 顶层参数注入：IMPLEMENTED
非空 JSON 触发 silent start：IMPLEMENTED
已有模型结构参数保护：IMPLEMENTED
EnhancementConfig 基础骨架：IMPLEMENTED
Batch 2 sampling mapping 解析：BATCH2-PLANNED
Batch 2 SAEHD/Generator 接线：BATCH2-PLANNED
Batch 2 Windows FP32 验收：PENDING-WINDOWS
```

文档使用状态标记区分已实现和计划参数，避免弱模型或 UI 提前把 Batch 2 参数当成已可用。

## 5. 后续执行要求

Batch 2 Ticket 06、09、10、11、12 修改参数或实际语义时，必须同步：

```text
docs/implementation/options-json-training-configuration-reference.md
```

重点：

- Ticket 06：最终 `SamplingConfig` 默认和范围；
- Ticket 09：Host 相关运行时参数是否对外暴露；
- Ticket 10：真实解析、持久化、silent start 与交互优先级；
- Ticket 11：Windows 实际命令和验收状态；
- Ticket 12：用户文档和最终 IMPLEMENTED 状态。

## 6. 本轮未做

- 未修改 `ModelBase.load_train_step_config()`；
- 未实现 Batch 2 Sampling；
- 未运行训练或自动测试；
- 未把计划参数标记为已实现。

本轮仅新增和强化配置文档与维护约束。
