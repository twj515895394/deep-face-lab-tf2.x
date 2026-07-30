# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Round 5 语义微修落地）  
> 当前交接：Batch 2 Ticket 14 Round-5 微修已落地，等待独立 Reviewer Gate  
> 当前状态：`TICKET14-R5-IMPL-COMPLETE / AWAITING-INDEPENDENT-REVIEW / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 当前实施 Summary（Round 5 微修）](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
2. [Ticket 14 第五轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round5.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第四轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round4.md)
5. [Ticket 14 第三轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
6. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
7. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)

### Commit 锚点

```text
Round-4 实现提交：    b6b0e79d6866c089deff905e00bb900a58da547f
Round-5 Review 提交： 77f507ed3087b1effcdd00b5e838023abf637e72
Round-5 开工前 HEAD： e8d0a0b07ea13bfc1d321c168ba9f8f5c7e9579a
Round-5 实现提交：    37e99255e195d73dbd3720858ec1a93b4c8619cc
```

施工 Summary 自审 `PASS` **不能**覆盖独立 Reviewer。当前权威状态：

```text
IMPLEMENTATION COMPLETE
AWAITING INDEPENDENT REVIEWER
R5-01 MALFORMED SIBLING INDEPENDENT FLAGS: FIXED IN CODE/TESTS
R4-01 EXPLICIT NULL POSE.VALID: CLOSED
R4-02 ARRAYS AND ACCESSORS: CLOSED (incl. independent read semantics after R5)
INDEPENDENT REVIEWER APPROVED/PASS NOT ISSUED
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：ROUND-5 IMPL COMPLETE / AWAITING INDEPENDENT REVIEW
Metadata Sampling：NOT PRODUCTION READY
Windows spawn：未通过真实验收
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 REMEDIATION
```

安全判断：

```text
legacy_random / legacy_uniform_yaw：继续使用
Faceset Analyzer：可用于报告与开发验证
pose_balanced / quality_pose_balanced：Ticket 14—20 完成前不用于正式训练结论
```

---

## 3. Ticket 14 已关闭（含 Round 5 自测）

```text
Canonical bucket 主链路：PASS
Ordinary / Packed E2E：PASS
Warning 聚合有界：PASS
bool 数字/字符串/float 边界：PASS
混合畸形 child：PASS
显式 pose.valid:null vs 缺失：PASS（R4-01）
record_matched / image_valid / landmarks_valid：PASS（R4-02）
畸形 sibling 独立 child flags：PASS（R5-01 自测）
usable masks 仍要求 metadata_valid & business_valid：PASS
强制测试矩阵 / order 不变：PASS
```

---

## 4. 剩余阻断

```text
独立 Reviewer Round-5+ Gate：未签发 APPROVED / PASS
```

若 Reviewer 仍 REQUEST_CHANGES：仅修新问题，不扩大范围。

已知但不属于本 Ticket 阻断：

```text
全量 test_batch2_*.py：unittest 报告 143 OK，
但进程退出阶段可能因 daemon host_thread 抢 stderr 锁
导致非零 shell exit（Ticket 16 范围）
```

---

## 5. Frontier

```text
Ticket 14：AWAITING-INDEPENDENT-REVIEW
Ticket 15—18 / 20—21：BLOCKED-BY-14
Ticket 19：可独立并行
```

Ticket 14 PASS 后立即并行启动：

```text
Ticket 15：SRC/DST options-json Sampling 配置
Ticket 16：Windows spawn / WeightedIndexHost 生命周期（含 daemon 退出）
Ticket 17：workers / strong fingerprint / stale detection
Ticket 19：若未完成则继续
```

---

## 6. Round-5 改动范围（已落地）

```text
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_loader.py
.scratch/.../reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md
.handoff/current.md
```

不得进入 Ticket 15/16/17/18/20。

---

## 7. 测试证据（本机，非 GitHub Actions）

```text
Python 3.11.7
compileall samplelib/metadata samplelib/sampling → exit 0
核心 schema/loader/analyzer/e2e：Ran 50 → OK，exit 0
全量 test_batch2_*.py：Ran 143 → OK；shell exit -1073740791（daemon 关机）
新增：test_loader_malformed_sibling_preserves_independent_child_flags → OK
```

---

## 8. 执行规则

- Summary 自审 PASS 不能代替独立 Reviewer Gate
- 不得回退已通过的 canonical / E2E / warning 有界逻辑
- 未执行 Windows GPU 时不得写正式 Batch 2 DONE

---

## 9. Ticket 14 最终通过条件

```text
独立 Reviewer 确认 R5-01 已关闭
+
全量 smoke unittest OK 且旧测试未削弱
+
APPROVED / PASS 签发
```

---

## 10. 历史入口

见既有 `handoff-20260729-batch2-ticket0*` 与 `handoff-20260727-batch2-detailed-design.md`。
