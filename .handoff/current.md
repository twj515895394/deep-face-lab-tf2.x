# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30 09:03 +08:00  
> 当前交接：Ticket 14 最终 PASS，Batch 2 下一阶段并行施工  
> 当前状态：`TICKET14-PASS / NEXT-FRONTIER-UNLOCKED / REMEDIATION-IN-PROGRESS / PENDING-WINDOWS-SPAWN / PENDING-WINDOWS-GPU`

---

## 1. 最新必读入口

按顺序阅读：

1. [Ticket 14 第六轮独立 Review 与最终 PASS](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)
2. [Ticket 14 PASS 后的 Batch 2 下一阶段任务安排](handoff-20260730-batch2-ticket14-pass-next-frontier.md)
3. [Ticket 14 最终实施总结](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-summary.md)
4. [Batch 2 独立代码审查与修复总计划](../.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md)
5. [Ticket 15](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
6. [Ticket 16](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
7. [Ticket 17](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
8. [Ticket 19](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

### Commit 锚点

```text
Ticket 14 最终实现：      37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 14 最终 Review：   94f57f9ec9c488d140eb37fbe0ba03fa26f1b020
Ticket 14 Summary 更新： a714765d4135186e21f64ee95e525ec298909054
下一阶段 Handoff：       0894007ecb7a941fe34d580eb1a71acdafc6e65f
```

独立 Reviewer 权威结论：

```text
APPROVED
PASS
TICKET 14 CONTRACT CLOSED
CANONICAL METADATA BUCKET CONTRACT CLOSED
ANALYZER → LOADER → POLICY E2E CLOSED
PER-SAMPLE VALIDITY CONTRACT CLOSED
```

---

## 2. 当前真实状态

```text
Batch 1：已完成 macOS 轻量验证
Batch 2 Ticket 01—13：已有实现与轻量测试
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：UNBLOCKED / OPEN / P0
Ticket 16：UNBLOCKED / OPEN / P0 HIGH RISK
Ticket 17：UNBLOCKED / OPEN / P1 HIGH
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT / P1 HIGH
Ticket 20：BLOCKED-BY-15+16+17
Ticket 21：BLOCKED-BY-14—20
Metadata Sampling：NOT PRODUCTION READY
Windows spawn：PENDING
Windows FP32 + AdaBelief：PENDING
Batch 3：BLOCKED BY BATCH 2 FINAL ACCEPTANCE
```

安全判断：

```text
legacy_random：继续回归和使用
legacy_uniform_yaw：继续回归和使用
Faceset Analyzer：可用于报告与开发验证
pose_balanced：Ticket 15—20 完成前不用于正式训练结论
quality_pose_balanced：Ticket 15—20 完成前不用于正式训练结论
```

---

## 3. Ticket 14 最终关闭内容

```text
Canonical yaw 7 buckets / pitch 3 buckets：PASS
Analyzer canonical 输出 → Loader 固定 IDs：PASS
Legacy aliases 只读兼容：PASS
旧 extreme → unknown / pose invalid / warning：PASS
Schema / Loader bool-compatible 单一契约：PASS
pose.valid 缺失 vs 显式 null：PASS
Runtime warning 按 code 聚合且有界：PASS
record_matched / image_valid / landmarks_valid：PASS
pose_valid / quality_valid / metadata_valid 语义独立：PASS
畸形 sibling 保留其它安全 child flags：PASS
usable masks = metadata_valid & business_valid：PASS
Ordinary / Packed 完整 E2E：PASS
非均匀权重 / strength=0 / probabilities / empirical draw：PASS
reversed / shuffled order：PASS
JSON roundtrip / Unicode / compact arrays：PASS
```

Ticket 15—21 必须复用 Ticket 14 的公共 contracts 和 accessors，禁止再实现第二套 bucket、bool 或 record validity 解释。

---

## 4. 当前并行 Frontier

允许四个不同 Agent 同时启动：

```text
Lane A — Ticket 15
--options-json / 双 Gate / SRC-DST Sampling 配置

Lane B — Ticket 16
WeightedIndexHost Windows spawn / Generator / 生命周期

Lane C — Ticket 17
Analyzer workers / strong fingerprint / stale detection

Lane D — Ticket 19
Loss Window 保存边界 / 失败语义 / 可观测性
```

### 4.1 Ticket 15

```text
状态：UNBLOCKED / OPEN / P0
可与 16、17 并行
不得由同一弱模型同时施工多个 Ticket
```

必须先复核真实调用链：

```text
main.py
→ ModelBase options-json
→ SAEHD enhancements
→ EnhancementConfig
→ SamplingConfig
→ SRC / DST Runtime
```

目标：错误层级配置不得静默失效，SRC 和 DST 最终配置必须分别解析和打印。

### 4.2 Ticket 16

```text
状态：UNBLOCKED / OPEN / P0 HIGH RISK
强制独立强 Review
最终必须 Windows 实机
```

第一优先复现：

```text
全量 test_batch2_*.py
unittest：Ran 143 / OK
shell exit：-1073740791
原因：解释器关机阶段 daemon host thread 抢 stderr 锁
```

必须做到真实 spawn、`debug=False` Generator、确定性 close、fatal/timeout 传播，并让测试进程 exit code 0。

### 4.3 Ticket 17

```text
状态：UNBLOCKED / OPEN / P1 HIGH
完成后解锁 Ticket 18
```

建议顺序：

```text
17A：signature / trusted ratio / stale detection
17B：workers / strong fingerprint / Packed 与 Windows pickle 安全
```

不得继续保留接受但无效的 `--workers` 或 `--strong-fingerprint`。

### 4.4 Ticket 19

```text
状态：OPEN / INDEPENDENT / P1 HIGH
Blocked by：无
```

必须在保存前冻结 loss history 边界；只有保存成功才消费窗口，保存失败必须保留窗口并传播原异常。

---

## 5. 后续依赖

```text
Ticket 17 完成
      ↓
Ticket 18

Ticket 15 + Ticket 16 + Ticket 17 完成
                     ↓
                  Ticket 20

Ticket 14—20 全部 PASS
          ↓
Ticket 21：文档、交接、Windows GPU 最终验收
```

Ticket 21 未签发前，Batch 3 保持 BLOCKED。

---

## 6. Agent 分配规则

1. 一个弱模型一次只领取一个 Ticket；
2. Ticket 15、16、17、19 使用独立工作分支；
3. 每个分支从 Ticket 14 PASS 后的共同基线开始；
4. 开工前先输出源码事实复核和修改计划；
5. Summary 自审 PASS 不等于独立 Review PASS；
6. Ticket 16 与 Ticket 20 必须强模型独立 Review；
7. Ticket 17 与 Ticket 18 不得由同一弱模型无 Review 连续完成；
8. Ticket 21 不得提前施工；
9. 不修改 SAEHD 网络、Loss 公式、optimizer、checkpoint、DFM、Merge 或 `faceset.pak` 格式；
10. 所有增强继续默认关闭。

建议分支：

```text
codex/batch2-ticket15-config-contract
codex/batch2-ticket16-windows-spawn
codex/batch2-ticket17-fingerprint-workers
codex/batch2-ticket19-loss-window-boundary
```

---

## 7. 每个 Ticket 必须提交

```text
实际源码修改
新增/更新自动测试
完整 Base / Head SHA
Python / OS / 依赖版本
compileall 结果
相关测试 Ran N / OK / failures / skips
全量相关 smoke 与 shell exit code
Ticket Summary
独立 Review 报告
current.md 状态同步
```

禁止：

```text
只改 Summary
只增加测试数量
删除或放宽旧断言
debug=True 代替真实多进程
macOS fork 代替 Windows spawn
broad except 代替异常分类
```

---

## 8. Batch 2 最终完成定义

```text
Ticket 14—20 全部 PASS
+
Analyzer → Loader → Policy E2E PASS
+
Stale signature detection PASS
+
Incremental == Force Full
+
Windows spawn / lifecycle PASS
+
Windows FP32 + AdaBelief PASS
+
Ordinary + Packed PASS
+
四种 sampling mode PASS
+
SRC / DST side config PASS
+
Fallback boundary PASS
+
Save / Exit / Resume PASS
+
Loss Window 离线重算一致
+
文档与 Handoff 一致
```

Windows GPU 未执行时不得写正式 Batch 2 DONE。
