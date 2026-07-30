# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30  
> 当前交接：Batch 2 的 Ticket 14—21 **计划内代码、测试、Summary、使用文档与 Handoff 实施均已完成**；Ticket 18/20 已完成独立代码 Review。  
> 当前状态：`ALL-TICKET-IMPLEMENTATION-COMPLETE / T14-20-CODE-GATES-COMPLETE / T21-WINDOWS-GPU-PENDING / BATCH2-CODE-COMPLETE-NOT-PRODUCTION-SIGNED`  
> 路线更新：Batch 3 之后改为 **Identity Geometry / Face Shape 闭环优先**；通用 Appearance / Region / Boundary / Frequency Loss 后移到 Batch 7。

---

## 1. 最新必读入口

按顺序阅读：

1. [本文档](current.md)
2. [增强版总实施计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
3. [Ticket 18 / 20 独立 Review 与 Batch 2 完成状态](../.scratch/batch2-training-data-and-sampling/reports/18-20-independent-review-and-batch2-completion-status.md)
4. [Ticket 21 规约](../.scratch/batch2-training-data-and-sampling/issues/21-docs-handoff-windows-gpu-final-acceptance.md)
5. [Ticket 21 Summary](../.scratch/batch2-training-data-and-sampling/reports/21-docs-handoff-windows-gpu-final-acceptance-summary.md)
6. [Windows GPU 验收记录](../.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md)
7. [Faceset Analyzer 完整使用说明](../docs/usage/faceset-analyzer-complete-guide.md)
8. [options-json 权威参考](../docs/implementation/options-json-training-configuration-reference.md)
9. [Batch 2 GUI 参数接入说明](../docs/implementation/batch2-gui-parameter-integration.md)

后续脸型开发必读：

1. `docs/implementation/training-enhancement-implementation-plan.md`
2. `docs/optimization/src-face-shape-preservation-design.md`
3. `docs/optimization/src-face-shape-training-and-shape-aware-merge-design.md`
4. `docs/implementation/merge-shape-aware-implementation-plan.md`
5. `docs/implementation/deepfacelab-code-modification-map.md`
6. `docs/implementation/deepfacelab-config-and-extension-architecture.md`

---

## 2. 统一工作分支

```text
codex/batch2-ticket19-loss-window
```

状态约束：

```text
代码、测试和文档事实以当前分支最新 HEAD 为准
未执行的 GPU / 大规模性能项目必须标记 deferred 或 pending
不得把 PENDING-WINDOWS-GPU 写成 PASS-WINDOWS-GPU
Batch 2 DONE / 合入 main 仍需要最终环境签发
路线文档更新不等价于 Batch 3 已获准实施
```

---

## 3. 最新 Commit 锚点

### Batch 2 实施与 Review

```text
Ticket 18 implementation： 9a2c28bf2da5a5bd4182ef8731fa22c1d5b2e058
Ticket 20 implementation： 1ca7f178981c971c331108969c62f657f773000a
Wave 1 Review R4：         0742381d10ad49848c9cfba33fc72a622c567e52
Ticket 21 docs/handoff：   c53e8e1c521d3e8b9ec3260a750e32b6a2ee1abd
Ticket 18/20 Final Review：5440770c47c4415bd018d24da92ba42b2a6a8566
```

### GUI 参数文档

```text
Batch 2 GUI integration：2730deb0b6ef1949e450a4108b011ffd1b411978
```

### Post-Batch 2 路线调整

```text
Master plan：             b7b2ae65c4c1bddf1c7a3c2b081baeb7d532ce2a
Training implementation：0b083e19dc81210cd22564bd78366959df8ebf4e
Training roadmap：       51c3f6b294658974b1b551be9170e6381167f461
Face shape design：      e9730a99b0bb7bb51e55f7c1c3c3055fea06efab
Training/Merge design：  31e28ef3345a770ecb5b5f437642754a472e7fcd
Merge implementation：  40e0ce345657ea7acbf0db5170d13c83970cb581
Code modification map：  118109243ecb52634e7b9c2d1b27bca629c516a4
Config architecture：    6f42f7ffb893de6df48838ada771d5caf67781c6
```

当前分支 HEAD 应以 `git rev-parse HEAD` 或 GitHub 分支最新 Commit 为准。

---

## 4. 权威 Ticket 状态

```text
Ticket 14：APPROVED / PASS / CLOSED
Ticket 15：APPROVED / PASS / CLOSED

Ticket 16：APPROVED / PASS-CODE
           GPU / thread attribution validation deferred

Ticket 17：APPROVED / PASS-CODE
           1k/10k performance/RSS validation deferred

Ticket 18：APPROVED / PASS / CLOSED
           incremental / force-full equivalence closed
           canonical summary/report schema closed

Ticket 19：APPROVED / PASS / CLOSED
           save window / trainer control / fatal propagation closed

Ticket 20：APPROVED / PASS / CLOSED
           optional Metadata fallback boundary closed
           core SampleLoader/Memory/worker errors propagate
           strict_validation and options-json docs synchronized

Ticket 21：IMPLEMENTATION + DOCS COMPLETE
           Windows GPU SAEHD final matrix pending
           NOT CLOSED
```

准确表述：

```text
全部 Batch 2 Ticket 的计划内实施工作已经完成。
Ticket 14—20 的代码门已经完成签发。
Ticket 21 只剩真实 Windows GPU 最终环境验收，不再有计划内开发项。
```

---

## 5. 已完成的 Batch 2 能力

```text
Metadata Schema / Identity / Fingerprint
Faceset Analyzer ordinary + packed
quick / strong fingerprint
incremental / force-full equivalence
trusted match / stale detection / strict atomic write
legacy_random / legacy_uniform_yaw
pose_balanced / quality_pose_balanced
SRC / DST side configuration
spawn-safe WeightedIndexHost and deterministic process cleanup
optional Metadata fallback + core error propagation
Trainer loss window / save / exit / resume control flow
Unicode / 中文 / 空格路径 smoke
完整使用文档、options-json 参考、GUI 接入说明、Summary 和 Handoff
```

Batch 2 对素材的作用是分析和调整训练抽样概率，不修改、删除或重写原始 aligned 图片。

---

## 6. 自动测试证据

实现侧最新记录：

```text
OS：Windows
Python：3.11.7
start method：spawn

python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
Ran 331 tests
OK
shell EXIT=0
```

覆盖包含：

```text
Analyzer workers / strong / incremental / strict
Incremental vs force-full equivalence
Ordinary / Packed / Unicode
Sampling fallback exception boundaries
WeightedIndexHost / spawn lifecycle
Trainer save controller（非 GPU）
```

GitHub 当前无 Actions/status check，因此不得写作 GitHub CI PASS。

---

## 7. Ticket 21 最终环境门

当前 `windows-gpu-acceptance.md` 的事实状态：

```text
acceptance Python 未安装 TensorFlow
SAEHD GPU 训练未启动
Matrix A/B 未执行
Ticket 21 GPU gate：NOT PASS / PENDING-WINDOWS-GPU
```

仍需在带 TensorFlow + CUDA 的 Windows 机器执行：

```text
SAEHD
precision=fp32
optimizer=adabelief
ordinary + packed
legacy_random / legacy_uniform_yaw
pose_balanced / quality_pose_balanced
连续训练 ≥500 iter
manual save / exit
resume ≥200 iter
SRC / DST side config
Fallback boundaries
Loss Window 实际日志核对
训练结束资源差集
```

完成后更新：

```text
.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md
.scratch/batch2-training-data-and-sampling/reports/21-docs-handoff-windows-gpu-final-acceptance-summary.md
.handoff/current.md
```

---

## 8. Post-Batch 2 路线调整结论

原计划：

```text
Batch 3：Region / Boundary / Frequency / Identity Appearance
Batch 4：Identity Geometry
Batch 5：Shape Template
Batch 6：Shape-aware Merge
Batch 7：Mask / Temporal
```

调整后：

```text
Batch 3：Minimal Loss Hook + Identity Geometry MVP
Batch 4：Source Shape Template
Batch 5：Hybrid Landmark + Piecewise Affine Warp
Batch 6：Shape-aware Soft Mask + Temporal
Batch 7：Identity Appearance / Region / Boundary / Frequency
Batch 8：联调、A/B、默认值、GUI、兼容与文档
```

关键约束：

> 不是完全跳过 Loss Hook，而是只保留 Geometry 必需的最小 Loss 基础设施，将通用画质 Loss 后移。

原因：

- 当前核心差异化问题是 src 脸型在训练和 Merge 中不能形成闭环；
- 通用 Loss 可改善纹理、局部和边缘，但不能替代 Shape Template、Hybrid Landmark、Warp 和 Mask；
- 先稳定脸型闭环，后续通用 Loss 的消融和归因更清楚；
- 可以更早判断增强版 DFL 的核心技术路线是否成立。

---

## 9. 下一批 Batch 3 计划边界

### 必须包含

```text
Minimal Loss Hook
独立 Loss 开关和权重
单项 Loss 日志
shape / dtype / mask 契约
NaN / Inf 保护
Shape Anchor
Landmark / Ratio Loss
Identity Geometry
Reconstruction → Geometry Ramp → Geometry Stable
保存恢复和旧 checkpoint 兼容
Windows GPU Geometry A/B Matrix
```

### 明确不包含

```text
Identity Appearance Loss
Region Loss
Boundary Loss
Frequency Loss
大型外部身份模型
完整 Multi-objective Curriculum
自动参数搜索
Shape-aware Merge 实施
```

后四项分别属于 Batch 7 或后续；Shape-aware Merge 属于 Batch 4—6 链路。

### 启动条件

```text
Ticket 21 Windows GPU Final Matrix PASS
或
维护者明确记录新的验收豁免 / 延期策略
```

在此之前，只允许完成 Batch 3 设计、Ticket 拆分和验收矩阵准备，不应把 Batch 3 写成 IN-PROGRESS implementation。

---

## 10. 后续 Batch 依赖

```text
Batch 2 Final Sign-off
        ↓
Batch 3 Minimal Loss Hook + Identity Geometry
        ↓
Batch 4 Source Shape Template
        ↓
Batch 5 Hybrid Landmark + Piecewise Affine Warp
        ↓
Batch 6 Shape-aware Mask + Temporal
        ↓
Batch 7 Appearance / Region / Boundary / Frequency
        ↓
Batch 8 Integration / A-B / Defaults / GUI / Docs
```

不得提前：

- 未有 Minimal Loss Hook，不实现 Geometry Loss 主链路；
- 未有可信 Shape Template，不正式实现 Hybrid Landmark；
- 未有稳定 Warp，不实现复杂 Mask / Temporal；
- 未完成脸型闭环，不批量叠加通用画质 Loss；
- 核心链路未稳定，不进入完整 UI / Linux 服务化。

---

## 11. 当前 Frontier

```text
开发 Frontier：无剩余 Batch 2 计划内代码 Ticket
验收 Frontier：Ticket 21 Windows GPU Final Matrix
Batch 2 implementation：COMPLETE
Batch 2 production sign-off：PENDING-WINDOWS-GPU
Next planned batch：Batch 3 Identity Geometry 训练基础
Batch 3 implementation：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```

若维护者决定豁免或延期 Ticket 21 的 Windows GPU 硬门，必须明确记录新的验收策略；不得把未执行的 Matrix 描述为已经通过。

---

## 12. 安全判断

```text
legacy_random / legacy_uniform_yaw：可继续使用
Analyzer 与 Metadata Sampling：代码门完成，可用于开发和环境验收
pose_balanced / quality_pose_balanced：代码功能完成，生产签发等待 Ticket 21
Batch 3 路线：设计已收口，正式实施仍被 Ticket 21 阻塞
合入 main / Batch 2 DONE：等待 Windows GPU 最终签发或维护者明确变更验收规约
```

---

## 13. 新 Agent 接手检查清单

1. 读取本文；
2. 读取总实施计划；
3. 确认当前分支和 HEAD；
4. 不修改历史 Batch 2 Ticket / Summary 的事实状态；
5. 若执行 GPU 验收，严格按 Ticket 21 Matrix；
6. 若准备 Batch 3，只拆分 Geometry-first 范围；
7. 不把 Batch 7 通用 Loss 提前混入 Batch 3；
8. 所有新功能默认关闭并保持旧 checkpoint / Merge 兼容；
9. 每个视觉算法必须准备固定条件人工 A/B；
10. 完成任何状态变化后同步更新总计划、Handoff 和对应专项文档。