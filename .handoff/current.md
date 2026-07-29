# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Round 5 Review）  
> 当前交接：Batch 2 Ticket 14 第五轮独立 Review 与最后一次语义微修  
> 当前状态：`REVIEW-FAILED / TICKET14-ONE-SEMANTICS-GAP / MICRO-FIX-REQUIRED / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 第五轮独立 Review 与最后一次语义返修](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round5.md)
2. [Ticket 14 当前实施 Summary（Round 4 返修）](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第四轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round4.md)
5. [Ticket 14 第三轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
6. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
7. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)

### Commit 锚点

```text
Round-4 开工前 Base：5fc3b9ee007ee771cfbb6ab77cc98f84bce11b7d
Round-4 Review 文档：  420f15bd61d1fc76f607fb15720440f260699111
Round-4 实现提交：    b6b0e79d6866c089deff905e00bb900a58da547f
Round-5 Review 提交： 77f507ed3087b1effcdd00b5e838023abf637e72
```

施工 Summary 自审 `PASS` 不能覆盖独立 Reviewer。当前权威结论：

```text
REQUEST_CHANGES
ONE-SEMANTICS-GAP-REMAINS
R4-01 EXPLICIT NULL POSE.VALID: CLOSED
R4-02 ARRAYS AND ACCESSORS: IMPLEMENTED
R4-02 INDEPENDENT READ SEMANTICS: NOT FULLY CLOSED
TICKET 14: VERY CLOSE, BUT NOT PASS
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：ROUND-5 / ONE-MICRO-FIX / FIXES-REQUIRED
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

## 3. Ticket 14 已确认关闭

```text
Canonical bucket 主链路：PASS
Analyzer → Loader 固定 IDs：PASS
Ordinary / Packed E2E：PASS
非均匀权重 / empirical draw：PASS
Warning 按 code 聚合且有界：PASS
bool int/string/float/null Schema 契约：PASS
混合畸形 child 的 metadata_valid：PASS
record_matched / image_valid / landmarks_valid arrays：已实现
get_record_landmarks_valid：已实现
精确 threshold / alias / canonical / roundtrip / Unicode：PASS
Packed reversed/shuffled order：PASS
Summary 不可变实现 SHA 与 distribution：PASS
```

以上内容不得重新设计或回退。

---

## 4. Ticket 14 唯一剩余阻断

### 4.1 畸形 sibling 会阻止其它 child 独立读取

当前 Loader 在唯一 record 命中后先执行整体结构检查：

```python
if not is_record_structurally_valid(rec):
    metadata_valid[i] = False
    continue
```

因此：

```json
{
  "image": {"valid": true},
  "landmarks": {"valid": true},
  "pose": "BROKEN",
  "quality": {"quality_score": 0.8}
}
```

会错误得到：

```text
record_matched=True
metadata_valid=False
image_valid=False
landmarks_valid=False
quality_valid=False
pose_valid=False
```

正确语义应为：

```text
record_matched=True
metadata_valid=False
image_valid=True
landmarks_valid=True
quality_valid=True
pose_valid=False
usable_for_pose_sampling=False
usable_for_quality_sampling=False
```

独立 child flags 用于诊断；采样安全仍由 `metadata_valid & business_valid` 保证。

### 4.2 最小修复方式

唯一 record 命中后：

```text
1. record_matched=True
2. 用异常安全 accessor 独立读取 image / landmarks / quality / pose
3. 单独计算 metadata_valid=is_record_structurally_valid(rec)
4. 不得因一个 sibling 畸形而在读取其它 child 前 continue
```

必须新增：

```text
test_loader_malformed_sibling_preserves_independent_child_flags
```

---

## 5. 当前 Ticket 依赖与 Frontier

```text
Ticket 14：ROUND-5 / FIXES-REQUIRED
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：允许独立并行
```

当前 frontier：

```text
Ticket 14 最终语义微修
Ticket 19（可由另一个独立 Agent 并行）
```

Ticket 14 PASS 后，立即并行启动：

```text
Ticket 15：SRC/DST options-json Sampling 配置
Ticket 16：WeightedIndexHost Windows spawn / 生命周期
Ticket 17：Analyzer workers / strong fingerprint / stale detection
Ticket 19：若尚未完成则继续
```

后续依赖：

```text
Ticket 17 完成 -> Ticket 18
Ticket 15 + 16 + 17 完成 -> Ticket 20
Ticket 14—20 全部 PASS -> Ticket 21
```

Ticket 16 优先处理已观察到的 daemon 退出 stderr 锁告警与非零 shell exit code。

---

## 6. 下一轮 Agent 施工范围

只允许修改：

```text
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_loader.py
Ticket 14 summary
.handoff/current.md
```

除非直接测试失败，不要修改：

```text
contracts.py
schema.py
canonical bucket 主逻辑
Analyzer / Ordinary / Packed fixture
Policy 权重公式
Ticket 15/16/17/18/20 实现
SAEHD 网络 / Loss / optimizer / DFM / Merge / pak 格式
```

---

## 7. 测试要求

```bash
python -m compileall samplelib/metadata samplelib/sampling
python -m unittest tests.smoke.test_batch2_metadata_schema
python -m unittest tests.smoke.test_batch2_metadata_loader
python -m unittest tests.smoke.test_batch2_analyzer_core
python -m unittest tests.smoke.test_batch2_metadata_sampling_e2e
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

必须记录：

```text
完整 Base / Head SHA
Python 版本
Ran N tests
OK / failures / skips
shell exit code
```

当前 GitHub 无 Actions/status check。本机 unittest 日志不能描述为独立 CI。

---

## 8. Ticket 14 最终通过条件

```text
畸形 sibling 不阻止其它安全 child 的独立 flags
+
metadata_valid=False 时 image/landmarks/quality 可保持各自正确语义
+
usable masks 继续要求 metadata_valid & business_valid
+
新增混合 sibling 自动测试
+
完整 Batch 2 smoke 与 shell exit code 被记录
+
独立 Reviewer APPROVED / PASS
```

---

## 9. 执行规则

- 弱模型一次只领取一个 Ticket；
- Summary 自审 PASS 不能代替独立 Reviewer Gate；
- 不得降低断言或依赖测试执行顺序；
- 不得回退已通过的 canonical / E2E / warning 逻辑；
- 所有新增能力继续默认关闭；
- 未完成 Windows GPU 验收时不得写正式 Batch 2 DONE；
- Ticket 19 可以由另一个独立 Agent 并行。

---

## 10. 历史入口

历史 `handoff-20260729-batch2-ticket0*` 与 `handoff-20260727-batch2-detailed-design.md` 用于理解实施过程，不覆盖本 Round-5 独立 Review。