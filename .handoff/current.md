# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30（Ticket 15 Round 2 Final Review）  
> 当前交接：Ticket 15 已通过 Round 2 独立 Review，配置契约正式关闭  
> 当前状态：`TICKET14-PASS / TICKET15-PASS-CLOSED / REMEDIATION-IN-PROGRESS / PENDING-WINDOWS-SPAWN`

---

## 1. 最新必读入口

1. [Ticket 15 Round 2 Final Review — APPROVED / PASS](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-review-round2-final.md)
2. [Ticket 15 实施 Summary（含 R1 remediation 与测试证据）](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-summary.md)
3. [Ticket 15 独立 Review Round 1 — CHANGES REQUIRED](../.scratch/batch2-training-data-and-sampling/reports/15-fix-options-json-and-src-dst-sampling-contract-review-round1.md)
4. [options-json 权威参考 v1.1](../docs/implementation/options-json-training-configuration-reference.md)
5. [Ticket 15 施工规约](../.scratch/batch2-training-data-and-sampling/issues/15-fix-options-json-and-src-dst-sampling-contract.md)
6. [Ticket 14 最终 PASS](../.scratch/batch2-training-data-and-sampling/reports/14-unify-metadata-bucket-schema-and-e2e-contract-review-round6-final.md)
7. [Ticket 16](../.scratch/batch2-training-data-and-sampling/issues/16-fix-weighted-index-host-windows-spawn.md)
8. [Ticket 17](../.scratch/batch2-training-data-and-sampling/issues/17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md)
9. [Ticket 19](../.scratch/batch2-training-data-and-sampling/issues/19-fix-loss-window-save-boundary-and-observability.md)

### Commit 锚点

```text
Ticket 14 最终实现：       37e99255e195d73dbd3720858ec1a93b4c8619cc
Ticket 15 首轮实现：       43a3c437fee4454b54abb192727797dbbe20a4e7
Ticket 15 Review R1：      b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de
Ticket 15 R1 前 HEAD：     35c42c4379aaa387c9130d4941ec6a5982217ff6
Ticket 15 remediation：    6ee5eceb2be9230f8e292364ec4a425e445c83d7
Ticket 15 Review R2 Final：4fd7d062cc817589fd964efdae3bd3e793247b68
Ticket 15 工作分支：       codex/batch2-ticket15-config-contract
```

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CONFIG CONTRACT CLOSED
  R1-01..R1-05：CLOSED
  Review Round 2：FINAL
Ticket 20：BLOCKED-BY-16+17
```

---

## 2. Ticket 15 最终验收摘要

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

---

## 3. 测试证据与限制

```text
focused Ticket 15：Ran 59 / OK / shell exit 0
full Batch 2 assertions：Ran 175 / OK
full process exit：-1073740791 → BLOCKED-BY-TICKET16
GitHub Actions：无 workflow run / 无 CI status
```

不得把全量断言 OK 与非零进程退出写成“全量 Batch 2 PASS”。Ticket 15 focused contract 已 PASS，但 Windows spawn/daemon 仍由 Ticket 16 负责。

---

## 4. 当前真实状态

```text
Ticket 14：PASS / CLOSED
Ticket 15：PASS / CLOSED
Ticket 16：UNBLOCKED / OPEN / P0 HIGH RISK
Ticket 17：UNBLOCKED / OPEN / P1 HIGH
Ticket 18：BLOCKED-BY-17
Ticket 19：OPEN / INDEPENDENT
Ticket 20：BLOCKED-BY-16+17
Ticket 21：BLOCKED-BY-14—20
Metadata Sampling：NOT PRODUCTION READY
Windows spawn / GPU：PENDING
Batch 3：BLOCKED
```

安全判断：

```text
legacy_random / legacy_uniform_yaw：继续使用
pose_balanced / quality_pose_balanced：Ticket 16—20 与 Windows GPU 验收完成前，不用于正式生产结论
```
