# Ticket 21 — 文档、Handoff、Windows GPU 最终验收与 Batch 2 重新签发

> 状态：OPEN / FINAL GATE  
> Blocked by：Ticket 14、15、16、17、18、19、20 全部完成并有 summary  
> Blocks：Batch 3 正式启动、Batch 2 合并 main  
> 特别规则：本 Ticket 不是“只改文档”；没有 Windows 实机证据不得 resolved

---

## 1. 目标

本 Ticket 负责在全部修复完成后：

1. 清理所有错误或过时文档；
2. 更新完整 Faceset Analyzer 使用说明；
3. 更新 `--options-json` 权威参考；
4. 修复 `.handoff/current.md` 冲突和状态；
5. 标记原错误 Review 报告已被独立审查取代；
6. 在 Windows GPU 上完成真实 SAEHD 验收；
7. 形成可复核证据；
8. 重新决定 Batch 2 是否可以签发 `done`。

---

## 2. 开工前硬性条件

以下 summary 必须全部存在：

```text
14-unify-metadata-bucket-schema-and-e2e-contract-summary.md
15-fix-options-json-and-src-dst-sampling-contract-summary.md
16-fix-weighted-index-host-windows-spawn-summary.md
17-implement-analyzer-workers-strong-fingerprint-and-stale-detection-summary.md
18-fix-incremental-summary-and-report-schema-summary.md
19-fix-loss-window-save-boundary-and-observability-summary.md
20-narrow-fallback-exception-boundaries-summary.md
```

任何一个缺失或状态为 FAIL/BLOCKED，本 Ticket 必须标：

```text
BLOCKED-BY-XX
```

不得先写 done 文档再补代码。

---

## 3. 文档审计范围

至少全文搜索：

```text
pose_balanced
quality_pose_balanced
faceset-analyze
metadata_sampling
sampling.src
sampling.dst
strong-fingerprint
workers
AMP
Quick96
all models
JSON file
PENDING-WINDOWS
done-macos
175/175
```

审计文件：

```text
README.md
docs/README.md
docs/usage/*
docs/implementation/options-json-training-configuration-reference.md
docs/development/batch2-training-data-and-sampling-tasks.md
.scratch/batch2-training-data-and-sampling/spec.md
.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md
.scratch/batch2-training-data-and-sampling/reports/*
.handoff/current.md
相关 handoff
```

---

## 4. 文档必须达到的事实一致性

### Analyzer

必须准确写明：

- 是离线工具；
- 与 XSeg 的区别；
- 何时必须运行；
- SRC/DST 分别分析；
- 不需要每次训练运行；
- Ordinary/Packed 工作流；
- incremental/force；
- workers 实际语义；
- quick/strong fingerprint；
- 输出文件；
- stale detection；
- strict；
- 退出码。

### Sampling

必须准确写明：

- 支持模型范围，以真实接线为准；
- 四种 mode；
- 双 Gate；
- flat compatibility；
- src/dst side config；
- fallback/strict；
- Metadata path；
- 权重只调整概率；
- 不自动删除样本。

### `--options-json`

必须准确写明：

- 当前是 JSON 字符串；
- 是否支持文件，以源码为准；
- 顶层 `enhancements`；
- silent start；
- `--force-model-name`；
- 持久化；
- side inheritance；
- 路径安全；
- 参数表和默认值。

### 平台

必须区分：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
PASS-WINDOWS-GPU
PENDING-WINDOWS
```

不得将 macOS synthetic 测试写成 Windows 训练完成。

---

## 5. 原 Review 报告处理

原文件：

```text
.scratch/batch2-training-data-and-sampling/reports/
batch2-comprehensive-code-review.md
```

不得删除历史，但必须在顶部追加醒目标记：

```text
SUPERSEDED / INVALIDATED BY INDEPENDENT REVIEW
```

并链接：

```text
batch2-independent-code-review-and-remediation-plan.md
```

说明：

- 原 PASS 结论基于不完整测试；
- Ticket 14—21 是修复入口；
- 最终状态以新 Windows 验收为准。

---

## 6. `.handoff/current.md` 修复

必须：

- 删除全部 Git 冲突标记；
- 删除互相矛盾状态；
- 指向最新独立 Review；
- 指向 14—21；
- 写明真实 frontier；
- 写明 Windows 状态；
- 写明 Batch 3 是否 blocked；
- 保留历史 handoff 链接；
- 不声称未验证功能完成。

修复期间示例：

```text
Batch 2 remediation: IN PROGRESS
Current frontier: Ticket 14 / 19
Metadata Sampling: NOT PRODUCTION READY
Windows GPU: PENDING
Batch 3: BLOCKED BY BATCH 2 REMEDIATION
```

全部验收后才可改：

```text
Batch 2: DONE
Windows GPU: PASS
```

---

## 7. Windows GPU 固定环境

必须记录：

```text
OS 版本
Python 版本
TensorFlow 版本
CUDA/cuDNN（如适用）
GPU 型号与显存
CPU 与内存
branch
commit SHA
start method
模型名
分辨率
batch size
precision=fp32
optimizer=adabelief
workers
faceset format
sample counts
```

不得使用 FP16/BF16 代替本批验收。

---

## 8. 数据集验收准备

准备至少：

### Ordinary SRC/DST

- 每侧至少包含 center、left、right 和 extreme/major 姿态；
- 质量分布包含清晰、轻微模糊、曝光差异；
- 包含中文/空格路径副本测试；
- 不使用隐私数据写入仓库。

### Packed SRC/DST

从同一清理后 Ordinary Pack；运行 Analyzer；验证 fingerprint 与记录数。

### 故障 Sidecar

准备：

- missing；
- invalid JSON；
- unsupported schema；
- partial match above threshold；
- below threshold；
- stale same-name replacement；
- duplicate ID；
- alias bucket 兼容文件。

---

## 9. Windows 验收矩阵

### Matrix A：Legacy Baseline

| Format | Mode | 要求 |
|---|---|---|
| Ordinary | legacy_random | 训练、保存、恢复 |
| Ordinary | legacy_uniform_yaw | 训练、保存、恢复 |
| Packed | legacy_random | 训练、保存、恢复 |
| Packed | legacy_uniform_yaw | 训练、保存、恢复 |

目的：证明修复没有破坏旧路径。

### Matrix B：Metadata Sampling

| Format | SRC | DST | 要求 |
|---|---|---|---|
| Ordinary | pose_balanced | pose_balanced | 训练与分布 |
| Ordinary | quality_pose_balanced | pose_balanced | side 独立 |
| Ordinary | pose_balanced | legacy_random | side 独立 |
| Packed | pose_balanced | pose_balanced | spawn + pak |
| Packed | quality_pose_balanced | quality_pose_balanced | 完整链路 |

每项至少：

- 初始化成功；
- 连续训练建议 500 iter 以上；
- 无 worker crash；
- 无 timeout；
- 实际 draws 统计；
- 手动 save；
- exit；
- resume 200 iter 以上。

### Matrix C：Fallback

| 场景 | fallback=true strict=false | strict=true |
|---|---|---|
| missing | legacy fallback | fail |
| invalid JSON | legacy fallback | fail |
| unsupported schema | legacy fallback | fail |
| low trusted ratio | legacy fallback | fail |
| stale ratio low | partial usable | 按契约 |
| SampleLoader core failure | fail | fail |
| worker fatal | fail | fail |

### Matrix D：Analyzer

- workers=1；
- workers=2/auto；
- quick；
- strong；
- Ordinary；
- Packed；
- incremental；
- same-name replace；
- Unicode path；
- strict invalid sample。

---

## 10. 采样分布验收

每种智能模式至少采集足够 draws，建议：

```text
>= 50,000 draws
```

记录：

- expected per-bucket distribution；
- empirical distribution；
- absolute error；
- relative error；
- unknown ratio；
- quality quantile distribution；
- duplicate retries；
- accepted duplicates；
- cycle build time。

验收：

- probabilities finite、positive、sum=1；
- 稀缺 bucket 相对 legacy 得到提升；
- empirical 与 expected 在预先定义容差内；
- 不要求所有 bucket 完全等量；
- 不允许 pose valid 全 false；
- 不允许“effective mode 正确但概率全均匀”。

容差应根据样本量和 draws 数在 Ticket 14/16 的测试契约中冻结，不能验收后临时放宽。

---

## 11. Loss Window 验收

在实际训练中完成：

1. 新会话启动；
2. 训练若干 iter；
3. 手动保存；
4. 记录窗口 count/mean/last；
5. 离线从对应 loss buffer 重算；
6. 继续训练；
7. 自动保存；
8. 退出保存；
9. 恢复训练；
10. 确认恢复首窗口不含旧 history。

必须确认：

- 保存日志立即出现；
- 不等下一 batch；
- 保存失败模拟不消费窗口；
- checkpoint iter 与窗口 end 一致。

---

## 12. 性能记录

每种主要模式记录：

```text
平均 iter time
P50/P95 iter time（如方便）
GPU 显存
CPU 使用
worker 数
queue timeout 次数
cycle build 时间
Analyzer samples/sec
Analyzer peak memory
```

比较：

```text
legacy_random baseline
pose_balanced overhead
quality_pose_balanced overhead
ordinary vs packed
```

本 Ticket 不要求零开销，但必须量化，不得只写“性能正常”。

---

## 13. 证据文件

生成或更新：

```text
.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md
.scratch/batch2-training-data-and-sampling/reports/21-docs-handoff-windows-gpu-final-acceptance-summary.md
.handoff/handoff-<timestamp>-batch2-remediation-final.md
.handoff/current.md
```

Windows 报告必须包含：

- 命令；
- 配置 JSON；
- 数据集摘要；
- 日志关键片段；
- 测试结果；
- 性能表；
- failures；
- 是否重试；
- commit SHA；
- 最终 verdict。

不得只写 checklist PASS 而无命令和输出依据。

---

## 14. Git/状态检查

最终检查：

```bash
git status
git grep -n "<<<<<<<\|=======\|>>>>>>>"
git grep -n "PENDING-WINDOWS"
git grep -n "BATCH2-PLANNED"
git grep -n "175/175"
```

目标：

- 无冲突标记；
- 所有 pending 状态与实际一致；
- 不保留错误能力声明；
- 文档索引可达；
- 新 issue 和 summary 链接无断链。

---

## 15. 最终签发规则

### 可以签发 DONE

只有：

```text
Tickets 14—20 全部 PASS
+
全量自动测试 PASS
+
Windows spawn PASS
+
Windows FP32 + AdaBelief PASS
+
Ordinary/Packed PASS
+
四种采样模式 PASS
+
SRC/DST side config PASS
+
Fallback 边界 PASS
+
Save/Exit/Resume PASS
+
Loss Window PASS
+
文档一致
```

### 只能签发 pending-windows

如果代码和模拟 spawn 通过但未执行 Windows GPU：

```text
PASS-MACOS-LIGHTWEIGHT
PASS-SPAWN-SIMULATION
PENDING-WINDOWS-GPU
```

不得写 DONE。

### 必须 fixes-required

任一 P0、spawn、真实训练、save/resume 或文档一致性失败。

---

## 16. 禁止范围

- 不在最终验收 Ticket 顺手开发 Batch 3；
- 不修改网络或 Loss；
- 不通过降低测试门槛签发；
- 不删除失败日志；
- 不把 fallback 当模式成功；
- 不把 10 iter smoke 当稳定训练；
- 不用单一 Ordinary 模式代替 Packed；
- 不用 macOS fork 代替 Windows spawn；
- 不用文档完成代替代码验收。

---

## 17. Summary 模板

```text
Ticket 14: PASS/FAIL
Ticket 15: PASS/FAIL
Ticket 16: PASS/FAIL
Ticket 17: PASS/FAIL
Ticket 18: PASS/FAIL
Ticket 19: PASS/FAIL
Ticket 20: PASS/FAIL

Full tests: PASS/FAIL
Windows spawn: PASS/FAIL/PENDING
Windows GPU FP32 AdaBelief: PASS/FAIL/PENDING
Ordinary: PASS/FAIL
Packed: PASS/FAIL
Legacy regression: PASS/FAIL
Pose E2E: PASS/FAIL
Quality+Pose E2E: PASS/FAIL
SRC/DST config: PASS/FAIL
Fallback boundaries: PASS/FAIL
Save/Exit/Resume: PASS/FAIL
Loss Window: PASS/FAIL
Docs consistency: PASS/FAIL
Conflict markers: PASS/FAIL

Final verdict:
DONE / PENDING-WINDOWS / FIXES-REQUIRED / BLOCKED
```

---

## 18. 验收标准

- [ ] 所有前置 summary 存在；
- [ ] 所有文档与源码一致；
- [ ] 原 Review 有 superseded 标记；
- [ ] current.md 无冲突且状态唯一；
- [ ] Analyzer 指南完整；
- [ ] options-json 权威文档完整；
- [ ] Windows 固定环境记录；
- [ ] 全部矩阵执行；
- [ ] 采样分布有量化；
- [ ] 性能有量化；
- [ ] save/resume 有证据；
- [ ] Loss Window 离线重算一致；
- [ ] 最终状态没有夸大。

本 Ticket 完成后，才允许进入 Batch 3 正式开发。