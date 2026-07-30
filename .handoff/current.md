# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Ticket 16+17 实现完成，等待 Wave 1 集中 Review）  
> 当前交接：Ticket 15 PASS/CLOSED；Ticket 16/17 实现完成；Ticket 19 仍 OPEN  
> 当前状态：`TICKET14-PASS / TICKET15-PASS-CLOSED / TICKET16-IMPL-COMPLETE / TICKET17-IMPL-COMPLETE / WAVE1-IN-PROGRESS`

---

## 1. 最新必读入口

1. [Ticket 17 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md)
2. [Ticket 16 实施 Summary](../.scratch/batch2-training-data-and-sampling/reports/16-fix-weighted-index-host-windows-spawn-summary.md)
3. [Ticket 16 施工规约](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
4. [Ticket 17 施工规约](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
5. [Ticket 15 Round 2 Final Review — APPROVED / PASS](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-review-round2-final.md)
6. [Ticket 19](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)
7. [Ticket 18](../.scratch/batch2-training-data-and-sampling/issues/18-implement-incremental-summary-and-analyzer-cache.md)
8. [Ticket 20](../.scratch/batch2-training-data-and-sampling/issues/20-close-sampleloader-production-contract.md)
9. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)
10. [Ticket 14 最终 PASS](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)

### Commit 锚点

```text
Ticket 14 最终实现：       37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 首轮实现：       43a3c437fee4454b54abb192727797dbbe20a4e7
Ticket 15 Review R1：      b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de
Ticket 15 remediation：    6ee5eceb2be9230f8e292364ec4a425e445c83d7
Ticket 15 Review R2 Final：4fd7d062cc817589fd964efdae3bd3e793247b68
Ticket 15 工作分支：       codex/batch2-ticket15-config-contract
Ticket 16 工作分支：       codex/batch2-ticket16-windows-spawn
Ticket 16 base：           0bb1fa094c3ddf0304eaf6cfcb9b11aac2eff400
Ticket 16 impl commit：    f9f846ab255a97005890a4ed7b6d3740ee4119e8
Ticket 17 工作分支：       codex/batch2-ticket17-analyzer-workers
Ticket 17 base：           f9f846ab255a97005890a4ed7b6d3740ee4119e8
Ticket 17 impl commit：    e0e619ae7acc2b25e2f422db1b8efd5597723e55
```

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CONFIG CONTRACT CLOSED
Ticket 16：IMPLEMENTATION COMPLETE / WINDOWS-SPAWN-UNIT-PASS / PENDING-SAEHD-GPU / AWAITING WAVE-1 REVIEW
Ticket 17：IMPLEMENTATION COMPLETE / WORKERS+STRONG-FP+TRUSTED-MATCH / AWAITING WAVE-1 REVIEW
           （实现者不得签发 APPROVED/PASS/CLOSED）
Ticket 19：UNBLOCKED / WAVE 1 / OPEN
Ticket 18：PROVISIONAL-OK-AFTER-17-SHA / WAVE 2
Ticket 20：PROVISIONAL-OK-AFTER-16+17-SHA / WAVE 2
```

---

## 2. 后续固定执行模式

后续不再要求每个 Ticket 完整经历“实现 → Review → 修复 → Final Review”后才启动下一个 Ticket。

统一采用：

```text
多 Agent 并行开发
+
每 Ticket 独立分支
+
每 Ticket 独立 implementation commit
+
一个 Wave 集成分支
+
一次集中 Review
+
一次集中 remediation
+
一次 Final Review
```

并行不等于混合提交。以下边界强制保留：

```text
一个 Ticket 一个独立工作分支
一个 Ticket 一个或一组可单独审查的 implementation commits
一个 Ticket 一份独立 summary
每个 Ticket 单独记录 focused tests 和退出码
禁止多个 Ticket 混成一个无法拆分的巨型 commit
禁止实现者自行写 APPROVED / PASS / CLOSED
集成冲突与跨 Ticket 适配必须使用单独 integration commit
```

---

## 3. Wave 1：立即并行执行

Wave 1 同时实施：

```text
Agent A → Ticket 16：Windows spawn / daemon shutdown / WeightedIndexHost 生命周期
Agent B → Ticket 17：Analyzer workers / strong fingerprint / stale detection
Agent C → Ticket 19：Loss Window save boundary / observability
```

推荐独立分支：

```text
codex/batch2-ticket16-windows-spawn
codex/batch2-ticket17-analyzer-workers
codex/batch2-ticket19-loss-window
```

三个 Ticket 完成后，统一集成到：

```text
codex/batch2-wave1-integration
```

Wave 1 集成分支必须保留：

```text
Ticket 16 implementation commit(s)
Ticket 17 implementation commit(s)
Ticket 19 implementation commit(s)
必要时单独的 integration commit
组合测试证据
每个 Ticket 的 summary
Wave 1 集成 summary
```

集中 Review 将同时检查：

```text
Ticket 16 独立契约
Ticket 17 独立契约
Ticket 19 独立契约
三个 Ticket 合并后的交叉影响
Windows spawn 与 Analyzer workers 生命周期交互
全量 Batch 2 回归与进程退出
日志、配置、缓存、持久化和失败语义
```

Review 结论必须按 Ticket 分开：

```text
Ticket 16：PASS 或 CHANGES REQUIRED
Ticket 17：PASS 或 CHANGES REQUIRED
Ticket 19：PASS 或 CHANGES REQUIRED
Wave 1 Integration：PASS 或 CHANGES REQUIRED
```

一个 Ticket 失败不得自动否定另外两个已闭环 Ticket。

---

## 4. Wave 2：依赖稳定后并行推进

Wave 2：

```text
Ticket 18：依赖 Ticket 17
Ticket 20：依赖 Ticket 16 + Ticket 17
```

允许在上游实现 commit 固定但尚未 Final Review 时提前施工，以减少等待：

```text
Ticket 17 implementation SHA 固定
→ Ticket 18 可基于该 SHA 开始 provisional implementation

Ticket 16 + Ticket 17 implementation SHA 固定
→ Ticket 20 可基于 Wave 1 provisional integration 开始 implementation
```

此时下游状态必须明确写为：

```text
PROVISIONAL / PENDING-UPSTREAM-REVIEW
```

若 Wave 1 Review 要求调整上游接口，Ticket 18/20 必须同步适配，不得以“已经完成”为理由拒绝修正。

推荐分支：

```text
codex/batch2-ticket18-incremental-summary
codex/batch2-ticket20-sampleloader-closeout
codex/batch2-wave2-integration
```

---

## 5. Ticket 16 特殊验收要求

Ticket 16 可以与 Ticket 17/19 同时开发和集中 Review，但必须提供额外 Windows 实机证据：

```text
Windows spawn 模式
正常退出码 0
worker / host 正常 terminate + join
异常路径可退出
极小数据集
N < batch
重复初始化与关闭
训练退出后无残留子进程
不得依赖 Unix fork 语义
```

若全量断言显示 OK，但进程最终仍为非零退出，不得签发 Ticket 16 PASS。

---

## 6. Ticket 15 最终验收摘要

```text
R1-01  最终 self.options 检测 misplaced Batch 2 keys（含 data.dat）
R1-02  SAEHD 显式 sampling_config_source 保留 base/side 来源
R1-03  普通交互 Override 保留 sampling.src/dst
R1-04  side validation warning 按 SRC/DST 隔离
R1-05  min_sample_weight >= max_sample_weight 视为非法
```

主体配置契约：

```text
enhancements.* 唯一合法 Batch 2 配置入口
默认 → base → side override
SRC/DST mode / path / seed 独立
双 Gate 四组合
Gate 关闭不加载 Metadata
相对路径逃逸拒绝
非空 --options-json 不被交互覆盖
```

测试证据与限制：

```text
focused Ticket 15：Ran 59 / OK / shell exit 0
full Batch 2 assertions：Ran 175 / OK
full process exit：-1073740791 → BLOCKED-BY-TICKET16
GitHub Actions：无 workflow run / 无 CI status
```

不得把全量断言 OK 与非零进程退出写成“全量 Batch 2 PASS”。

---

## 7. 当前真实状态

```text
Ticket 14：PASS / CLOSED
Ticket 15：PASS / CLOSED
Ticket 16：IMPL COMPLETE / SPAWN UNIT PASS / PENDING SAEHD GPU / AWAITING CENTRAL REVIEW
Ticket 17：IMPL COMPLETE / WORKERS+STRONG-FP+STALE / AWAITING CENTRAL REVIEW
Ticket 18：WAVE 2（可 provisional 基于 Ticket 17 SHA）
Ticket 19：OPEN / WAVE 1
Ticket 20：WAVE 2（可 provisional 基于 16+17）
Ticket 21：BLOCKED-BY-14—20
Metadata Sampling：NOT PRODUCTION READY
Windows spawn unit：PASS
Windows SAEHD GPU training：PENDING
Batch 3：BLOCKED
```

### Ticket 16 实现摘要（非 Final Review）

```text
Client pickle 后 _host_ref=None
closed_event / fatal_event 跨进程状态
request_id 匹配，丢弃 stale response
禁止 Queue.empty() 同步
SampleGeneratorFace 持有 index_host 并 finalize
focused 26 tests OK / process EXIT=0
SAEHD 500 iter / save-resume：未跑
impl：f9f846a
```

### Ticket 17 实现摘要（非 Final Review）

```text
--workers / --strong-fingerprint 真正生效
quick/strong signature + analysis_config 持久化
Loader trusted match + stale 不装旧 quality/pose
spawn Pool workers；Packed path+offset 多进程
focused 53 tests OK / EXIT=0
1k/10k 性能基准：PARTIAL
```

安全判断：

```text
legacy_random / legacy_uniform_yaw：继续使用
pose_balanced / quality_pose_balanced：Wave 1 中央 Review + SAEHD GPU + Ticket 18—20 完成前，不用于正式生产结论
```
