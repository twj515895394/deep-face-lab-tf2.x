# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 10:44 +08:00（Ticket 15 独立 Review Round 1）  
> 当前交接：Ticket 15 独立 Review 已完成，结论为 CHANGES REQUIRED；等待按 Review 报告做最小修复  
> 当前状态：`TICKET14-PASS / TICKET15-REVIEW-R1-CHANGES-REQUIRED / REMEDIATION-IN-PROGRESS / PENDING-WINDOWS-SPAWN`

---

## 1. 最新必读入口

按顺序阅读，禁止跳过第 1 项直接改代码：

1. [Ticket 15 独立 Review Round 1 — CHANGES REQUIRED](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-review-round1.md)
2. [Ticket 15 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-summary.md)
3. [Ticket 15 施工规约](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
4. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)
5. [Ticket 14 最终 PASS Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)
6. [Ticket 14 PASS 后并行任务](handoff-20260730-batch2-ticket14-pass-next-frontier.md)
7. [Ticket 16](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
8. [Ticket 17](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
9. [Ticket 19](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

### Commit 锚点

```text
Ticket 14 最终实现：       37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 14 最终 Review：    94f57f9ec9c488d140eb37fbe0ba03fa26f1b020
Ticket 15 开工基线：       d4d0b20b91a0bdf5a06586f345f974255aa46002
Ticket 15 实现提交：       43a3c437fee4454b54abb192727797dbbe20a4e7
Ticket 15 Review R1 报告： b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de
Ticket 15 工作分支：       codex/batch2-ticket15-config-contract
```

权威状态：

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：INDEPENDENT REVIEW ROUND 1 / CHANGES REQUIRED / REMEDIATION OPEN
Ticket 20：BLOCKED-BY-15+16+17
--options-json 文档：v1.1 已同步，但最终实现仍待 remediation 对齐
```

---

## 2. 当前真实状态

```text
Ticket 14：PASS / CLOSED
Ticket 15：REVIEW R1 CHANGES REQUIRED / REMEDIATION OPEN
Ticket 16：UNBLOCKED / OPEN / P0 HIGH RISK
Ticket 17：UNBLOCKED / OPEN / P1 HIGH
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT
Ticket 20：BLOCKED-BY-15+16+17
Ticket 21：BLOCKED-BY-14—20
Metadata Sampling：NOT PRODUCTION READY
Windows spawn / GPU：PENDING
Batch 3：BLOCKED
```

安全判断：

```text
legacy_random / legacy_uniform_yaw：继续使用
pose_balanced / quality_pose_balanced：Ticket 15—20 完成并验收前不用于正式训练结论
```

---

## 3. Ticket 15 Round 1 必修项

只修 Review 报告中的以下 5 项，不得扩大范围：

```text
R1-01  对最终 self.options 检测 persisted + injected 错误顶层 Batch 2 keys
R1-02  SAEHD 显式传入 side config 时保留真实 config_source
R1-03  普通交互 Override 不得删除 sampling.src / sampling.dst
R1-04  side-specific validation warning 按 SRC/DST 隔离
R1-05  min_sample_weight >= max_sample_weight 均视为非法
```

Review 已确认主体方向正确，以下能力不要重写：

```text
默认 → base → side 的解析优先级
双 Gate 4 组合
扁平 sampling 向后兼容
sampling_config_for(src/dst)
SRC/DST metadata path 独立解析
resolve_metadata_path 逃逸拒绝
side seed 优先与 +1000/+2000 派生
```

---

## 4. 强制范围控制

本次 remediation 禁止顺手处理：

```text
Ticket 16 Windows spawn / daemon exit / WeightedIndexHost 生命周期
Ticket 17 workers / strong fingerprint / stale signature
Ticket 18 incremental summary
Ticket 19 Loss Window
Ticket 20 SampleLoader 核心异常分类
SAEHD 网络 / Loss / optimizer / checkpoint
GUI Sampling 控件
大范围配置架构重构
```

弱模型一次只处理 Ticket 15，按 Review 报告 R1-01 → R1-05 顺序完成。遇到 Ticket 16 的 `-1073740791` 只能记录 `BLOCKED-BY-TICKET16`，不得跨 Ticket 修复。

---

## 5. Ticket 15 当前改动范围

```text
core/enhancements/config.py
core/enhancements/__init__.py
samplelib/sampling/config.py
samplelib/sampling/runtime.py
models/Model_SAEHD/Model.py
models/ModelBase.py
docs/implementation/options-json-training-configuration-reference.md
docs/usage/faceset-analyzer-complete-guide.md
tests/test_options_json.py
tests/smoke/test_batch2_sampling_config.py
tests/smoke/test_batch2_saehd_sampling_options.py
tests/smoke/test_batch2_sampling_fallback.py
tests/smoke/test_batch2_sampling_logging.py
Ticket 15 summary / review / handoff
```

只修改真正需要的文件，不要求全部触碰。

---

## 6. 已有测试证据的正确解释

```text
Python 3.11.7
focused 相关 44 tests：OK / shell exit 0
全量 test_batch2_*.py：Ran 169 / assertions OK
全量 shell exit：-1073740791 → BLOCKED-BY-TICKET16
```

不得把 `Ran 169 OK + shell exit -1073740791` 写成“全量回归 PASS”。正确表述是：

```text
断言通过，但测试进程退出仍被 Ticket 16 daemon shutdown 问题阻断。
```

Ticket 15 remediation 后，focused Ticket 15 tests 必须 shell exit 0。

---

## 7. remediation 提交要求

修复完成后必须提交：

```text
单一 Ticket 15 remediation commit
Previous Head / New Head SHA
R1-01—R1-05 逐项关闭证据
实际修改函数列表
focused tests Ran N / OK / shell exit 0
full Batch 2 assertions 与 process exit 分开记录
更新后的 Ticket 15 Summary
Round 2 独立 Review 请求
```

推荐 commit message：

```text
fix(sampling): address Ticket 15 review findings
```

在 Round 2 Reviewer 签发前，禁止把 Ticket 15 状态改成 PASS/CLOSED。
