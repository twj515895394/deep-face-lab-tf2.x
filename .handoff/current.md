# 当前项目交接入口

> 更新时间：2026-07-30  
> 当前分支：`codex/batch03-identity-geometry`  
> 分支来源：`codex/batch2-ticket19-loss-window`，创建基线提交 `0823d5aea08579610876f5a3b42f9d5fb42df23f`。  
> 本文件是新会话、新Agent和后续开发者的固定入口。  
> 当前唯一可执行编码Ticket：`B3-01`。  
> Batch 4–6已经详细拆票，但均为滚动设计草案，禁止直接编码。

---

## 1. 当前权威状态

```text
Batch 1 implementation: COMPLETE
Batch 2 implementation/automated/code acceptance: COMPLETE
Batch 2 Windows GPU Final Matrix: DEFERRED-BY-MAINTAINER / NOT EXECUTED
Batch 2 progression: APPROVED-FOR-BATCH3

Batch 3 code-anchor audit: COMPLETE
Batch 3 document review: PASS-AFTER-FIXES
Batch 3 ticket design: FROZEN-FOR-B3-01
Batch 3 coding: READY-FOR-B3-01-ONLY
Batch 3 implementation/tests/GPU: NOT STARTED / NOT EXECUTED

Batch 4 ticket design: COMPLETE-DRAFT
Batch 4 coding: BLOCKED-BY-BATCH3-AND-REVALIDATION
Batch 5 ticket design: COMPLETE-DRAFT
Batch 5 coding: BLOCKED-BY-BATCH4-AND-REVALIDATION
Batch 6 ticket design: COMPLETE-DRAFT
Batch 6 coding: BLOCKED-BY-BATCH5-AND-REVALIDATION
```

必须准确理解：

```text
允许推进Batch 3
!= Batch 2 Windows GPU Matrix通过

Batch 4-6已拆详细Issues
!= 可以跳过前置批次直接编码
```

历史Batch 2未执行GPU项目不得伪写为PASS。

---

## 2. 最新必读入口

按顺序读取：

1. 本文件。
2. `docs/implementation/enhanced-dfl-master-implementation-plan.md`
3. `docs/implementation/training-enhancement-implementation-plan.md`
4. `docs/optimization/src-face-shape-preservation-design.md`
5. `docs/optimization/src-face-shape-training-and-shape-aware-merge-design.md`
6. `docs/development/batch3-identity-geometry-tasks.md`
7. `.scratch/batch3-identity-geometry/reviews/code-anchor-audit-20260730.md`
8. `.scratch/batch3-identity-geometry/reviews/document-review-20260730.md`
9. `.scratch/batch3-identity-geometry/issues/01-baseline-contracts-fixtures.md`
10. `docs/development/face-shape-batch4-6-rolling-ticket-plan.md`
11. 仅在规划/复核后批次时读取Batch 4–6正式草案和对应`.scratch`目录。

---

## 3. Batch 3 Review后的关键技术决策

### 3.1 配置Gate

唯一Geometry请求Gate：

```text
training.enabled
AND training.loss_hooks
AND training.identity_geometry
```

取消重复的`geometry.enabled`。`geometry` section只含权重、Anchor路径、阈值和warmup/ramp参数，默认值唯一位于核心配置。

### 3.2 P0设计修复：不做伪可微Landmark Loss

真实代码没有可微landmark prediction head。当前`SampleProcessor.LANDMARKS_ARRAY`也没有跟随target face alignment、random affine和flip。

Batch 3冻结路线：

```text
src Shape Anchor / sample landmarks
 -> target-aligned landmarks
 -> fixed ratio + stable contour SDF/region supervision
 -> TensorFlow feed

existing differentiable gpu_pred_src_srcm
 -> soft mask ratios / soft occupancy
 -> Ratio Loss + Contour/SDF Loss
```

禁止：

- 新增landmark网络或大型外部模型；
- 直接声称预测68点坐标Loss；
- 用NumPy/OpenCV从预测Tensor提取不可导landmark；
- 训练眼距/鼻宽的伪mask prediction。

### 3.3 SRC/DST职责

- Geometry只加入`src -> src` predicted mask路径。
- `gpu_dst_loss`、`gpu_pred_src_dst`、DST Generator保持基线。
- 不要求src/dst样本逐帧或batch index配对。
- Eyes/Mouth/Brows不进入stable contour强约束。

### 3.4 兼容

- 全部新能力默认关闭。
- disabled或optional fallback时，不扩展Generator、placeholder、图、fetch和loss history。
- 不修改模型网络、权重文件、optimizer slot、`data.dat`核心格式、DFM和Merge。
- Curriculum由已有`iter + frozen config`确定性恢复。

---

## 4. Batch 3 Ticket DAG与执行规则

15票：

```text
B3-01 Contracts/Fixtures
B3-02 Config Schema/Gates
B3-03 Minimal Loss Hook
B3-04 Runtime State/Logging
B3-05 Errors/Fallback
B3-06 ShapeAnchorV1
B3-07 Anchor Loader/Cache
B3-08 Aligned Supervision/Ratio/SDF
B3-09 Soft-mask Ratio Loss
B3-10 Stable Contour/SDF Loss
B3-11 SRC/DST Isolation
B3-12 Deterministic Curriculum
B3-13 SAEHD Integration/Checkpoint Compat
B3-14 Control Flow/Test/GPU A-B
B3-15 Docs/Review/Handoff
```

当前只允许执行B3-01。一次只做一票：

```text
实现
-> 指定测试
-> Summary
-> 独立Review
-> 修复P0/P1
-> 更新状态/Handoff
-> 才进入DAG下一票
```

不得一次实现Hook + Anchor + Loss + SAEHD接入。

---

## 5. Batch 4–6滚动拆票决策

可以提前做详细设计，以保护跨批次接口；但必须逐批重新复核。

```text
现在：详细草案到文件/函数/数据/测试级
Batch 3完成：重审并冻结Batch 4
Batch 4完成：重审并冻结Batch 5
Batch 5完成：重审并冻结Batch 6
```

滚动策略入口：

```text
docs/development/face-shape-batch4-6-rolling-ticket-plan.md
```

### Batch 4：Source Shape Template

- 正式草案：`docs/development/batch4-source-shape-template-tasks.md`
- 工作区：`.scratch/batch4-source-shape-template/`
- Ticket数：13
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`
- 未来第一票：B4-01真实产物/坐标/路径Revalidation。
- 边界：交付`model_name.srcshape` Geometry Bridge，不实现Merge Warp。

### Batch 5：Hybrid Landmark + Piecewise Affine Warp

- 正式草案：`docs/development/batch5-hybrid-landmark-piecewise-warp-tasks.md`
- 工作区：`.scratch/batch5-hybrid-landmark-warp/`
- Ticket数：14
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`
- 未来第一票：B5-01读取最终`.srcshape`与Merge真实代码。
- 边界：Hybrid/Warp/Merge接入，不实现Shape Mask/Temporal。

### Batch 6：Shape-aware Soft Mask + Temporal

- 正式草案：`docs/development/batch6-shape-aware-soft-mask-temporal-tasks.md`
- 工作区：`.scratch/batch6-shape-mask-temporal/`
- Ticket数：14
- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`
- 未来第一票：B6-01读取最终WarpResult/Mask顺序/多脸生命周期。
- 边界：Mask和Temporal，不实现Batch 7通用训练Loss。

---

## 6. 后批次必须重新复核的输入

### Batch 4前

- 最终ShapeAnchorV1、ratio顺序、SDF/contour定义。
- Geometry训练A/B和已知局限。
- 模型命名、保存目录和实际权限。

### Batch 5前

- 最终`.srcshape` Schema、loader、identity/fingerprint/confidence。
- Template默认路径、显式Override和fallback。
- 当前Merge入口、MergerConfig/session真实行为。

### Batch 6前

- 最终Hybrid landmarks、triangle topology、WarpResult/QualityResult。
- RGB/mask geometry mapping和Merge插入顺序。
- 多脸、worker、prefetch、session实际行为。

若实现与草案冲突，必须先修订受影响Ticket并独立Review；不得让弱模型临场猜测。

---

## 7. 事实与测试保护

每个批次分别记录：

```text
Code Gate
Automated Test Gate
Windows/Environment Gate
Performance Gate
Visual A-B Result
```

自动测试不等价GPU，短跑不等价长期视觉。视觉结果使用`PROMISING/NEUTRAL/REGRESSION/INCONCLUSIVE`并附素材和指标。任何未执行项目写`NOT EXECUTED/DEFERRED/PENDING`。

---

## 8. 当前Frontier

```text
开发分支：codex/batch03-identity-geometry
开发Frontier：B3-01 基线、术语、Tensor/Mask/DType契约与Fixtures
Batch 3 later tickets：BLOCKED-BY-DAG
Batch 4–6：ROLLING-DESIGN-DRAFT ONLY
训练代码修改：NONE in latest planning/review work
最新自动测试/GPU执行：NONE in latest planning/review work
```

新Agent接手后不得继续拆票或直接做Geometry Loss；应先读取B3-01详细文档并只执行该Ticket。
