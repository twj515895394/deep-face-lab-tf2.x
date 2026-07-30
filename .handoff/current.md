# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Ticket 15 Round-1 remediation 落地）  
> 当前交接：Ticket 15 R1 五项必修已修复，等待 Round-2 独立 Review  
> 当前状态：`TICKET14-PASS / TICKET15-REMEDIATION-COMPLETE-AWAITING-R2-REVIEW / REMEDIATION-IN-PROGRESS / PENDING-WINDOWS-SPAWN`

---

## 1. 最新必读入口

1. [Ticket 15 实施 Summary（含 R1 关闭证据）](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-summary.md)
2. [Ticket 15 独立 Review Round 1](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-review-round1.md)
3. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)
4. [Ticket 15 施工规约](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
5. [Ticket 14 最终 PASS](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)
6. [Ticket 16](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)

### Commit 锚点

```text
Ticket 14 最终实现：       37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 首轮实现：       43a3c437fee4454b54abb192727797dbbe20a4e7
Ticket 15 Review R1：      b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de
Ticket 15 R1 前 HEAD：     35c42c4379aaa387c9130d4941ec6a5982217ff6
Ticket 15 remediation：    （commit 后回填）
Ticket 15 工作分支：       codex/batch2-ticket15-config-contract
```

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：REMEDIATION COMPLETE / AWAITING ROUND-2 REVIEW
  R1-01..R1-05：FIXED IN CODE/TESTS（自审）
  APPROVED/PASS NOT ISSUED
Ticket 20：BLOCKED-BY-15+16+17
```

---

## 2. R1 修复摘要

```text
R1-01  最终 self.options 检测 misplaced Batch 2 keys（含 data.dat）
R1-02  SAEHD 显式 sampling_config_source 保留 base/side 来源
R1-03  apply_interactive_sampling_base_update 保留 src/dst
R1-04  config_warnings_for(role) + sampling.<role>: 前缀
R1-05  min_sample_weight >= max_sample_weight → 默认 0.5/2.0
```

---

## 3. 测试证据

```text
focused：Ran 59 / OK / shell exit 0
full batch2 assertions：Ran 175 / OK
full process exit：-1073740791 → BLOCKED-BY-TICKET16
```

---

## 4. Frontier

```text
Ticket 15：AWAITING ROUND-2 INDEPENDENT REVIEW
Ticket 16 / 17 / 19：可并行（不同 Agent）
Ticket 20：仍 BLOCKED-BY-15+16+17
```

Round-2 签发前禁止写 Ticket 15 PASS/CLOSED。
