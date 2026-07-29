# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 00:30 +08:00  
> 当前交接：Batch 2 Ticket 14 Round-4 返修已落地，等待独立 Reviewer Gate  
> 当前状态：`TICKET14-R4-IMPL-COMPLETE / AWAITING-INDEPENDENT-REVIEW / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 当前实施 Summary（Round 4 返修）](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
2. [Ticket 14 第四轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round4.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第三轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
5. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
6. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)

### Commit 锚点

```text
Round-4 开工前 Base：5fc3b9ee007ee771cfbb6ab77cc98f84bce11b7d
Round-4 被审 R3 实现：7b482c9ced3631b7cde7dcdd3f07bff47ab28960
Round-4 Review 文档：  420f15bd61d1fc76f607fb15720440f260699111
Round-4 实现提交：    见本轮 push 后 HEAD（summary/handoff 同步）
```

施工 Summary 自审 `PASS` **不能**覆盖独立 Reviewer。当前权威状态：

```text
IMPLEMENTATION COMPLETE
AWAITING INDEPENDENT REVIEWER
R4-01 EXPLICIT NULL POSE.VALID: FIXED IN CODE/TESTS
R4-02 PER-SAMPLE VALIDITY ARRAYS: FIXED IN CODE/TESTS
INDEPENDENT REVIEWER APPROVED/PASS NOT ISSUED
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：ROUND-4 IMPL COMPLETE / AWAITING INDEPENDENT REVIEW
Metadata Sampling：NOT PRODUCTION READY
Windows spawn：未通过真实验收
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 REMEDIATION
```

安全判断：

```text
legacy_random / legacy_uniform_yaw：继续使用
pose_balanced / quality_pose_balanced：Ticket 14—20 完成前不用于正式训练结论
```

---

## 3. Ticket 14 已关闭（含 Round 3 + Round 4 自测）

```text
Canonical bucket 主链路：PASS
Ordinary / Packed E2E：PASS
Warning 聚合有界：PASS
bool 数字/字符串/float 边界：PASS
混合畸形 child：PASS
显式 pose.valid:null vs 缺失：PASS（R4-01 自测）
record_matched / image_valid / landmarks_valid：PASS（R4-02 自测）
语义独立数组：PASS（自测）
强制测试矩阵 / order 不变：PASS
```

---

## 4. 剩余阻断

```text
独立 Reviewer Round-5 Gate：未签发 APPROVED / PASS
```

若 Reviewer 仍 REQUEST_CHANGES：仅修新问题，不扩大范围。

---

## 5. Frontier

```text
Ticket 14：AWAITING-INDEPENDENT-REVIEW
Ticket 15—18 / 20—21：BLOCKED-BY-14
Ticket 19：可独立并行
```

---

## 6. Round-4 改动范围（已落地）

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_analyzer_core.py
Ticket 14 summary
.handoff/current.md
```

不得进入 Ticket 15/16/17/18/20。

---

## 7. 执行规则

- Summary 自审 PASS 不能代替独立 Reviewer Gate
- 不得回退已通过的 canonical / E2E / warning 有界逻辑
- 未执行 Windows 时不得写正式 Batch 2 DONE

---

## 8. Ticket 14 最终通过条件

```text
独立 Reviewer 确认 R4-01 / R4-02 已关闭
+
全量 smoke PASS 且旧测试未削弱
+
APPROVED / PASS 签发
```

---

## 9. 历史入口

见既有 `handoff-20260729-batch2-ticket0*` 与 `handoff-20260727-batch2-detailed-design.md`。
