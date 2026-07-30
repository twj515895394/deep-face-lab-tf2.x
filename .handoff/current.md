# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Ticket 15 实现落地）  
> 当前交接：Ticket 15 配置契约实现完成，等待独立 Review；Ticket 14 已 PASS  
> 当前状态：`TICKET14-PASS / TICKET15-IMPL-COMPLETE-AWAITING-REVIEW / REMEDIATION-IN-PROGRESS / PENDING-WINDOWS-SPAWN`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 15 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-summary.md)
2. [Ticket 15 施工规约](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
3. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)
4. [Ticket 14 最终 PASS Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)
5. [Ticket 14 PASS 后并行任务](handoff-20260730-batch2-ticket14-pass-next-frontier.md)
6. [Ticket 16](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
7. [Ticket 17](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
8. [Ticket 19](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

### Commit 锚点

```text
Ticket 14 最终实现：      37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 14 最终 Review：   94f57f9ec9c488d140eb37fbe0ba03fa26f1b020
Ticket 15 开工基线：      d4d0b20b91a0bdf5a06586f345f974255aa46002
Ticket 15 工作分支：      codex/batch2-ticket15-config-contract
Ticket 15 实现提交：      （待 commit）
```

权威状态：

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEWER
--options-json 文档：v1.1 已同步
```

---

## 2. 当前真实状态

```text
Ticket 14：PASS / CLOSED
Ticket 15：IMPL COMPLETE / AWAITING REVIEW
Ticket 16：UNBLOCKED / OPEN / P0 HIGH RISK
Ticket 17：UNBLOCKED / OPEN / P1 HIGH
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT
Ticket 20：BLOCKED-BY-15+16+17（15 待 Reviewer PASS）
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

## 3. Ticket 15 已落地能力

```text
enhancements 唯一合法顶层路径
双 Gate 4 组合
扁平 sampling 向后兼容
sampling.src / sampling.dst + base override
resolve_metadata_path 逃逸拒绝
ModelBase 错误顶层 key warning
SAEHD 分侧 sampling_config_for + runtime
分侧 startup log（gates / config source / path / seed）
options-json 文档 v1.1 + Analyzer 使用说明同步
```

---

## 4. 并行 Frontier（Review 后）

```text
Lane B — Ticket 16：Windows spawn / daemon exit（强制强 Review）
Lane C — Ticket 17：fingerprint / workers / stale
Lane D — Ticket 19：Loss Window
```

Ticket 15 独立 Reviewer PASS 前，Ticket 20 仍视为 blocked。

---

## 5. Ticket 15 改动范围

```text
core/enhancements/config.py
core/enhancements/__init__.py
samplelib/sampling/config.py
samplelib/sampling/runtime.py
models/Model_SAEHD/Model.py
models/ModelBase.py
docs/implementation/options-json-training-configuration-reference.md
docs/usage/faceset-analyzer-complete-guide.md
tests/smoke/test_batch2_sampling_config.py
tests/smoke/test_batch2_saehd_sampling_options.py
reports/15-...-summary.md
.handoff/current.md
```

---

## 6. 测试证据（本机，非 GitHub Actions）

```text
Python 3.11.7
相关 44 tests OK exit 0
全量 test_batch2_*.py Ran 169 OK
shell exit -1073740791 → Ticket 16
```

---

## 7. 执行规则

- Summary 自审 ≠ 独立 Reviewer PASS
- 一个弱模型一次一个 Ticket
- Ticket 16 强制强 Review + Windows 实机
- 未 Windows GPU 不得写 Batch 2 DONE
