# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-29 23:52 +08:00（Round 4 Review）  
> 当前交接：Batch 2 Ticket 14 第四轮独立 Review 与最终契约返修  
> 当前状态：`REVIEW-FAILED / TICKET14-TWO-CONTRACT-GAPS / FIXES-REQUIRED / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 第四轮独立 Review 与最终剩余返修](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round4.md)
2. [Ticket 14 当前实施 Summary（Round 3 返修）](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
3. [Ticket 14 施工规约](../.scratch/batch2-training-data-and-sampling/issues/14-unify-metadata-bucket-schema-and-e2e-contract.md)
4. [Ticket 14 第三轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round3.md)
5. [Ticket 14 第二轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round2.md)
6. [Ticket 14 第一轮独立 Review](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review.md)
7. [Batch 2 独立 Review、Analyzer 使用说明与修复 Ticket 14—21](handoff-20260729-batch2-independent-review-remediation.md)
8. [Batch 2 独立代码审查、问题汇总与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
9. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)

### Commit 锚点

```text
Round-4 被审实现：  7b482c9ced3631b7cde7dcdd3f07bff47ab28960
Round-3 文档锚点：  c08f25ae50bbdab620b0798faaaf058b4aa49271
Round-4 Review 提交：420f15bd61d1fc76f607fb15720440f260699111
```

施工 Summary 的自审 `PASS` 不能覆盖独立 Reviewer。当前权威结论：

```text
REQUEST_CHANGES
TWO-CONTRACT-GAPS-REMAIN
R3-01 WARNING BOUND: CLOSED
R3-02 BOOL NUMERIC/STRING RULE: MOSTLY CLOSED
R3-03 MALFORMED CHILD: CLOSED
R3-04 TEST MATRIX: MOSTLY CLOSED
R3-05 PACKED ORDER: CLOSED
TICKET 14 ORIGINAL VALIDITY CONTRACT: NOT FULLY CLOSED
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Issue 15 Unicode / 中文路径：已完成
预览阈值 400：已完成
Merger 参数双语：已完成
模型加载 OOM / 分块 assign：已修复并验证

Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：ROUND-4 / FIXES-REQUIRED / TWO-CONTRACT-GAPS
Metadata Sampling：NOT PRODUCTION READY
Windows spawn：未通过真实验收
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 REMEDIATION
```

安全判断：

```text
legacy_random：继续回归和使用
legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：可用于报告与开发验证
pose_balanced：Ticket 14—20 完成前不用于正式训练结论
quality_pose_balanced：Ticket 14—20 完成前不用于正式训练结论
```

---

## 3. Ticket 14 已确认通过

```text
Canonical yaw/pitch bucket 单一契约：PASS
Analyzer canonical 输出 → Loader 固定 ID：PASS
旧 rec.get("valid", True) 默认漏洞：已移除
顶层 valid-only record：不再 metadata_valid
Analyzer bucket contract version 与 canonical lists：PASS
Ordinary 多 yaw bucket / 非均匀权重 / strength=0：PASS
Ordinary empirical draw：PASS
Packed Analyzer→Loader→Policy→IndexHost→draw：PASS
uniform_mix empirical 基线 0.0：PASS
Legacy extreme：unknown + pose invalid + warning
Unicode 目录与 Unicode 文件名：PASS
compact-array <2MB：现有 arrays PASS
RuntimeMetadata schema warnings 按 code 聚合且有界：PASS
其它 int / float / 字符串 bool 边界：PASS
混合畸形 child 不误标 metadata_valid：PASS
精确 threshold、alias、Analyzer、Loader、Packed order 测试：已补齐大部分
Summary 不可变 Base/Head 与 distribution 数值：PASS
```

以上主链路不得重新设计或回退。

---

## 4. Ticket 14 剩余阻断

### 4.1 显式 `pose.valid: null` 契约不一致

当前公共 helper 将 `None` 定义为不兼容，但 Schema 使用 `valid_val is not None`，导致显式 JSON null 不产生 `INVALID_POSE_VALID_TYPE`。测试也跳过了 None 的 Schema 一致性断言。

必须固定：

```text
字段缺失：允许，读取为 false
字段存在且为 null：INVALID_POSE_VALID_TYPE，读取为 false
```

### 4.2 RuntimeMetadata 未实现完整逐样本有效性契约

原 Ticket 要求区分：

```text
record_matched
image_valid
landmarks_valid
pose_valid
quality_valid
metadata_valid
```

当前 RuntimeMetadata 只有 `pose_valid / quality_valid / metadata_valid`。

必须增加 compact arrays：

```text
record_matched: bool[N]
image_valid: bool[N]
landmarks_valid: bool[N]
```

并让 Loader 主链路真实填充；增加 `get_record_landmarks_valid()`，将 `landmarks` 纳入已知结构，但业务 `valid=false` 不得使 metadata_valid=false。

### 4.3 测试补齐

```text
pose.valid 缺失 vs 显式 null
record_matched 未匹配 vs 已匹配畸形
image_valid 嵌套读取
landmarks_valid 嵌套读取
全部 validity arrays 独立
compact-array 内存测试包含新增 arrays
```

非阻断建议：收紧 Analyzer 测试，使 `pose.valid=True` 时 yaw/pitch 必须直接属于 canonical set，不允许测试层放行 unknown。

---

## 5. 当前 Ticket 依赖与 Frontier

```text
Ticket 14：ROUND-4 / FIXES-REQUIRED
Ticket 15：BLOCKED-BY-14
Ticket 16：BLOCKED-BY-14
Ticket 17：BLOCKED-BY-14
Ticket 18：BLOCKED-BY-14
Ticket 20：BLOCKED-BY-14
Ticket 21：BLOCKED-BY-14
Ticket 19：允许另一个独立 Agent 并行
```

当前 frontier：

```text
Ticket 14 最终契约返修
Ticket 19（可由另一个独立 Agent 并行）
```

Ticket 14 最终 PASS 后，下一批立即解锁并行：

```text
Ticket 15：options-json 与 SRC/DST Sampling 配置
Ticket 16：WeightedIndexHost Windows spawn / 生命周期
Ticket 17：Analyzer workers / strong fingerprint / stale detection
Ticket 19：若尚未完成，继续独立并行
```

其中 Ticket 16 必须优先处理施工侧已观察到的 daemon 退出时 stderr 锁告警和非零 shell exit code。

---

## 6. 下一轮 Agent 施工范围

只允许修改：

```text
samplelib/metadata/contracts.py
samplelib/metadata/schema.py
samplelib/metadata/loader.py
tests/smoke/test_batch2_metadata_schema.py
tests/smoke/test_batch2_metadata_loader.py
tests/smoke/test_batch2_analyzer_core.py（仅收紧断言，可选）
Ticket 14 summary
.handoff/current.md
```

不得重新修改：

```text
canonical bucket 主逻辑
Policy 权重公式
Ordinary/Packed fixture 几何
Ticket 15/16/17/18/20 实现
SAEHD 网络 / Loss / optimizer / DFM / Merge / pak 格式
```

---

## 7. 测试要求

```bash
python -m compileall samplelib/metadata samplelib/sampling
python -m unittest tests.smoke.test_batch2_pose
python -m unittest tests.smoke.test_batch2_metadata_schema
python -m unittest tests.smoke.test_batch2_analyzer_core
python -m unittest tests.smoke.test_batch2_metadata_loader
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

当前 GitHub 没有 Actions/status check；本机测试日志不能描述为独立 CI。

---

## 8. Ticket 14 最终通过条件

```text
显式 pose.valid:null 产生 INVALID_POSE_VALID_TYPE
+
RuntimeMetadata 提供并填充 record_matched/image_valid/landmarks_valid
+
完整 validity arrays 独立语义测试 PASS
+
compact-array 内存目标继续 PASS
+
现有 Ordinary/Packed E2E、warning、bool、order 测试不回退
+
全量 smoke PASS
+
独立 Reviewer APPROVED / PASS
```

---

## 9. Batch 2 后续执行顺序

```text
当前：Ticket 14 final contract fix
并行：Ticket 19

Ticket 14 PASS 后：15 + 16 + 17 并行
17 完成后：18
15 + 16 + 17 完成后：20
14—20 全部 PASS 后：21 文档、Handoff、Windows GPU 最终验收
```

Windows 未执行时最多状态：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
PENDING-WINDOWS-GPU
```

---

## 10. 历史 Batch 2 入口

- [Batch 2 详细设计](handoff-20260727-batch2-detailed-design.md)
- [Ticket 01 基线](handoff-20260729-batch2-ticket01-baseline.md)
- [Ticket 02 Metadata Schema](handoff-20260729-batch2-ticket02-metadata-schema.md)
- [Ticket 03 Analyzer Core](handoff-20260729-batch2-ticket03-analyzer-core.md)
- [Ticket 04 Analyzer CLI](handoff-20260729-batch2-ticket04-analyzer-cli.md)
- [Ticket 05 Metadata Loader](handoff-20260729-batch2-ticket05-metadata-loader.md)
- [Ticket 06 Sampling Policy](handoff-20260729-batch2-ticket06-sampling-policy.md)
- [Ticket 07 Pose-balanced](handoff-20260729-batch2-ticket07-pose-balanced-sampling.md)
- [Ticket 08 Quality Weighting](handoff-20260729-batch2-ticket08-quality-aware-weighting.md)
- [Ticket 09 WeightedIndexHost](handoff-20260729-batch2-ticket09-weighted-index-host.md)
- [Ticket 10 SAEHD/Config/Fallback](handoff-20260729-batch2-ticket10-config-saehd-logging.md)
- [Ticket 11 Master Matrix](handoff-20260729-batch2-ticket11-master-matrix.md)
- [Ticket 12 Docs/Handoff](handoff-20260729-batch2-ticket12-docs-and-handoff.md)
- [Ticket 13 Loss Window](handoff-20260729-ticket13-loss-window-logging.md)
- [`--options-json` 权威参考交接](handoff-20260729-options-json-reference.md)

历史文档用于理解实现过程，不覆盖当前第四轮独立 Review 结论。
