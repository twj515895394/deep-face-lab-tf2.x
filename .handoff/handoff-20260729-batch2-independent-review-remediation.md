# Handoff — Batch 2 独立 Review、Faceset Analyzer 使用说明与修复 Ticket 14—21

> 时间：2026-07-29 20:33 +08:00  
> 状态：REVIEW-FAILED / FIXES-REQUIRED  
> 分支：`codex/batch2-metadata-sampling-design`  
> 适用范围：Batch 2 Metadata / Sampling 全链路  
> Windows GPU：PENDING

---

## 1. 本次完成内容

本次没有修改运行时代码，而是对弱模型完成的 Batch 2 进行独立代码审查，并把审查结论转化为可执行的修复规格。

新增用户文档：

```text
docs/usage/faceset-analyzer-complete-guide.md
```

新增独立 Review 总报告：

```text
.scratch/batch2-training-data-and-sampling/reports/
batch2-independent-code-review-and-remediation-plan.md
```

新增修复 Ticket：

```text
14-unify-metadata-bucket-schema-and-e2e-contract.md
15-fix-options-json-and-src-dst-sampling-contract.md
16-fix-weighted-index-host-windows-spawn.md
17-implement-analyzer-workers-strong-fingerprint-and-stale-detection.md
18-fix-incremental-summary-and-report-schema.md
19-fix-loss-window-save-boundary-and-observability.md
20-narrow-fallback-exception-boundaries.md
21-docs-handoff-windows-gpu-final-acceptance.md
```

---

## 2. 独立 Review 最终判定

此前 Batch 2 的“175/175 PASS”和综合 Review 报告不足以证明真实功能可用。独立审查发现：

### P0

1. Analyzer 与 Loader 使用不同 yaw/pitch bucket 名称，`pose_balanced` 可能静默退化；
2. 使用指南给出的 options JSON 层级错误，缺少顶层 `enhancements`；
3. 双 Gate 中缺少 `training.enabled=true` 时功能不会启用；
4. 文档宣称支持 `sampling.src/dst`，代码只支持一份扁平配置；
5. WeightedIndexHostClient 在 Windows spawn 下有 `_host_ref` 序列化风险。

### P1

1. `--workers` 未使用；
2. `--strong-fingerprint` 未使用；
3. 同名替换图片可能继续使用旧 Metadata；
4. Incremental summary 读取旧顶层 Schema；
5. Loss Window 多包含保存后的一个 batch；
6. Metadata fallback 捕获范围可能吞掉 SampleLoader 核心错误。

当前状态必须改为：

```text
REVIEW-FAILED
FIXES-REQUIRED
LEGACY-SAFE
METADATA-SAMPLING-NOT-PRODUCTION-READY
PENDING-WINDOWS-GPU
```

---

## 3. Faceset Analyzer 用户结论

Faceset Analyzer 不是像 XSeg 一样所有训练都必须执行。

只有启用：

```text
pose_balanced
quality_pose_balanced
```

才需要先生成 Metadata。

使用 legacy：

```text
legacy_random
legacy_uniform_yaw
```

不需要 Analyzer。

执行单位是一个最终版本的 aligned faceset：

- SRC 和 DST 需要分别分析；
- 同一 faceset 被多个模型复用时不重复分析；
- faceset 新增、删除、替换、重新 Pack 后必须更新；
- 少量变更使用 `--incremental`；
- 状态不可信使用 `--force`。

Ticket 14—21 完成前，Analyzer 可以用于报告和开发验证，但不建议正式训练依赖 Metadata Sampling。

---

## 4. 修复依赖顺序

```text
14
├── 15
├── 16
└── 17
     ↓
18

19 可独立施工

15 + 16 + 17
     ↓
20

14—20 全部 PASS
     ↓
21 Windows GPU 最终验收
```

推荐当前 frontier：

```text
Ticket 14
Ticket 19（可由另一个 Agent 并行）
```

Ticket 16、20 完成后必须独立强 Review。

---

## 5. 弱模型施工要求

每次只分配一个 Ticket，并同时提供：

```text
AGENTS.md
spec.md
独立 Review 总报告
当前 Ticket
Blocked by summary
Ticket 指定源码
```

施工模型必须先输出源码事实复核，不能直接编码。

禁止：

- 跳过 Ticket 14 直接修配置或 GPU；
- 用手工构造的旧 Schema 测试代替真实 Analyzer；
- 用 debug=True 代替多进程；
- broad except 通过 fallback 掩盖错误；
- macOS fork 代替 Windows spawn；
- 文档完成后直接签发 done。

---

## 6. 最终验收

Batch 2 重新签发 DONE 必须同时通过：

```text
Analyzer → Loader → Policy E2E
Canonical bucket contract
Stale signature detection
Incremental == force full
Windows spawn
Windows FP32 + AdaBelief
Ordinary + Packed
四种 sampling mode
SRC/DST side config
Fallback boundary
Save / Exit / Resume
Loss Window offline recompute
Docs consistency
```

Windows 未执行时，最多签发：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
PENDING-WINDOWS-GPU
```

---

## 7. 下一步

第一优先：执行 Ticket 14。  
可并行：独立 Agent 执行 Ticket 19。  
Batch 3 在 Ticket 21 最终签发前保持 BLOCKED。