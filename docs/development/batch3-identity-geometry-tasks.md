# Batch 3：Minimal Loss Hook + Identity Geometry 训练基础详细施工设计

> 文档状态：`DOCUMENT-REVIEW-PASSED / READY-FOR-B3-01`  
> 路线：`GEOMETRY-FIRST`  
> 基线分支：`codex/batch2-ticket19-loss-window`  
> 复核日期：2026-07-30  
> 事实保护：Batch 2 Windows GPU Final Matrix 仍为 `DEFERRED-BY-MAINTAINER / NOT EXECUTED`；本次只完成代码锚点和文档 Review，没有实现 Batch 3代码，也没有执行 GPU训练。

## 1. 批次目标

在不修改 SAEHD/DF/LIAE主模型架构、不修改权重/optimizer/DFM/Merge格式的前提下，交付 Identity Geometry MVP所需的最小闭环：

```text
配置与 Gate
→ Minimal Loss Hook
→ SRC Shape Anchor
→ 与 target 同坐标系的 Geometry Supervision
→ 可微 Soft-mask Ratio + Stable Contour/SDF Loss
→ 最小 Curriculum
→ SAEHD src loss接入
→ 保存恢复、日志、自动测试与 Windows GPU A/B规约
```

所有能力默认关闭；全部新 Gate关闭或 runtime fallback时，Generator、图、Loss、梯度、保存恢复、采样、Merge和DFM必须保持基线等价。

## 2. 独立代码锚点复核结论

### 2.1 真实训练图

- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize_options` 规范化 `enhancements`。
- `SAEHDModel.on_initialize` 创建图像/mask placeholders、DF/LIAE网络、per-GPU forward、`gpu_src_loss/gpu_dst_loss`、`gpu_G_loss`、有限梯度 Gate和 `_unified_ops`。
- 当前 `_unified_ops` 为 `src_loss, dst_loss, all_gradients_finite, step_applied`。
- `onTrainOneIter()` 返回 src/dst两个通道，`ModelBase.train_one_iter()` 把返回通道写入 `loss_history`。
- `ModelBase.save()` 已保存 `iter/options/loss_history`；Curriculum可由 `iter + frozen config` 确定性恢复，无需新增checkpoint状态。

### 2.2 配置结论

现有唯一训练 Gate：

```text
training.enabled
training.loss_hooks
training.identity_geometry
```

`training.curriculum` 只控制 Curriculum。Review取消了重复的 `geometry.enabled`。新增 `geometry` section只保存权重、Anchor路径和阈值参数，默认值唯一位于 `core/enhancements/config.py`。

### 2.3 关键 P0：直接 Landmark Loss不可行

当前 SAEHD没有可微 landmark prediction head；`SampleProcessor.LANDMARKS_ARRAY` 只是原图坐标归一化，且未应用 target face alignment、random affine和flip。离线landmark只能作为监督目标，不能作为模型预测产生坐标梯度。

因此 Batch 3冻结为：

```text
Anchor/样本 landmarks
  → target-aligned landmarks
  → fixed ratios + stable contour SDF/region map
  → feed TensorFlow

existing differentiable gpu_pred_src_srcm
  → soft mask ratios / soft occupancy
  → Ratio Loss + Contour/SDF Loss
```

第一版明确不新增 landmark网络，不实现直接预测68点坐标Loss。眼距和鼻宽保留在 Anchor/报告字段中，但不从mask伪造可训练prediction。

### 2.4 SRC/DST职责

- Geometry只加入 `src -> src` predicted mask路径。
- `gpu_dst_loss`、`gpu_pred_src_dst`、DST Generator保持基线。
- 不要求SRC/DST样本按batch index或帧一一配对。
- Eyes/Mouth/Brows不进入stable contour region，避免静态化DST表情。

## 3. 固定范围

### 3.1 In Scope

- 参数Schema、三Gate、requested/effective/reason。
- Hook registry、per-sample result、固定日志通道。
- ShapeAnchorV1内部训练资产和loader/cache/fingerprint。
- target-aligned landmarks、固定ratio、stable contour SDF。
- Soft-mask Ratio和Contour Loss。
- deterministic Curriculum。
- SAEHD最小接入、旧checkpoint/optimizer兼容。
- 自动、控制流、GPU与视觉A/B矩阵。

### 3.2 Out of Scope

- Identity Appearance、Region、Boundary、Frequency、LPIPS/VGG/DINO/ArcFace。
- 新Backbone、landmark head、3DMM、Diffusion/Transformer。
- Batch 4 `.srcshape`正式Geometry Bridge。
- Batch 5 Hybrid Landmark/Piecewise Warp。
- Batch 6 Shape-aware Mask/Temporal。
- 完整GUI页面与自动权重搜索。

## 4. 关键数据契约

```text
Aligned landmarks: [N,68,2] float32, target canvas normalized [0,1]
  face alignment + target random affine + flip semantic remap
  no non-rigid random warp

Geometry target map: image-like 2 channels
  channel0 SDF [-1,1]
  channel1 stable-region weight [0,1]

Ratio target: [N,12]
  6 fixed values + 6 validity

Geometry validity: [N,3]
  anchor_valid, contour_valid, ratio_valid

Hook addition: [device_batch], per-sample
```

Invalid样本使用独立validity=0；承载数组仍必须有限，禁止NaN sentinel。

## 5. Shape Anchor与Batch 4边界

Batch 3内部资产：

```text
faceset_shape_anchor.v1.json
```

包含src identity、faceset fingerprint、canonical landmarks、固定ratio、confidence和sample summary。它不命名为 `.srcshape`，不提供Merge discovery，不绑定模型名。Batch 4将基于Batch 3最终真实接口重新Review并生成正式 `model_name.srcshape` Geometry Bridge。

## 6. Ticket DAG

```text
B3-01 contracts/fixtures
  ├─ B3-02 config schema
  ├─ B3-03 minimal loss hook
  └─ B3-06 ShapeAnchorV1

B3-02 + B3-03 -> B3-04 runtime state/logging -> B3-05 errors/fallback
B3-06 + B3-02 -> B3-07 anchor loader/cache
B3-01 + B3-07 -> B3-08 aligned supervision/SDF
B3-03 + B3-05 + B3-08 -> B3-09 soft-mask ratio loss
B3-03 + B3-05 + B3-08 -> B3-10 stable contour/SDF loss
B3-09 + B3-10 -> B3-11 SRC/DST isolation
B3-04 + B3-11 -> B3-12 deterministic curriculum
B3-02..B3-12 -> B3-13 SAEHD integration/checkpoint compat
B3-13 -> B3-14 control flow/master matrix/GPU A-B
B3-14 -> B3-15 docs/review/handoff closeout
```

可并行：B3-02/B3-03/B3-06；B3-09/B3-10在B3-08稳定后可并行。B3-13不得提前。

## 7. Ticket列表

| ID | 标题 | 前置 |
|---|---|---|
| B3-01 | 基线、术语、Tensor/Mask/DType契约与Fixtures | 无 |
| B3-02 | 配置Schema、默认值、三Gate与options-json | B3-01 |
| B3-03 | Minimal Loss Hook API、注册与零影响 | B3-01 |
| B3-04 | Loss结果、日志、requested/effective状态 | B3-02,B3-03 |
| B3-05 | 数值保护、错误传播与Optional Fallback | B3-04 |
| B3-06 | ShapeAnchorV1、生成契约与身份绑定 | B3-01 |
| B3-07 | Anchor加载、缓存、失效与回退 | B3-02,B3-06 |
| B3-08 | Aligned Landmark、Ratio与SDF监督 | B3-01,B3-07 |
| B3-09 | 可微Soft-mask Ratio Geometry Loss | B3-03,B3-05,B3-08 |
| B3-10 | Landmark-derived Stable Contour/SDF Loss | B3-03,B3-05,B3-08 |
| B3-11 | SRC/DST职责与Geometry/Expression隔离 | B3-09,B3-10 |
| B3-12 | Reconstruction→Ramp→Stable Curriculum | B3-04,B3-11 |
| B3-13 | SAEHD接入、旧Checkpoint/Optimizer兼容 | B3-02..B3-12 |
| B3-14 | 控制流、Master Matrix、Windows GPU A/B | B3-13 |
| B3-15 | 用户/GUI Schema、Review与Handoff收口 | B3-14 |

每票详细施工文档位于 `.scratch/batch3-identity-geometry/issues/`，已细化到文件、函数、输入输出、Forbidden Changes、测试命令和Review清单。

## 8. 统一错误边界

可回退仅限启动阶段可选Anchor/Geometry资产缺失、版本/身份/fingerprint/confidence不满足，并受 `strict_validation` 与 `fallback_on_optional_error`矩阵控制。

必须传播：OOM、worker/IPC崩溃、核心SampleLoader、tensor shape/dtype、非有限Loss/梯度、checkpoint损坏、optimizer state不兼容、save/load失败。

Per-sample无效使用validity=0；整批无有效样本addition=0并记录active_fraction=0。

## 9. 保存恢复与日志

- 不增加权重/optimizer文件和slot。
- Curriculum由保存的`iter + options`确定性重建。
- Geometry disabled时loss history仍为src/dst两个通道。
- enabled时使用审核后固定通道顺序，运行中不得热切换。
- Loss Window保存失败不commit，沿用Batch 2事务语义。
- startup日志分别输出requested/effective/reason、Anchor来源和Curriculum状态。

## 10. 完成Gate

```text
Code Gate
Automated Test Gate
Short Windows GPU Smoke Gate
Long GPU / Visual A-B Result
```

四者必须分别记录。自动测试不等价GPU，Short Smoke不等价长期视觉效果。Long A/B使用 `PROMISING/NEUTRAL/REGRESSION/INCONCLUSIVE`，不得只写PASS。

## 11. 当前签发状态

```text
Batch 3 code-anchor audit: COMPLETE
Batch 3 document review: PASS-AFTER-FIXES
Batch 3 ticket design: FROZEN-FOR-B3-01
Batch 3 coding: READY-FOR-B3-01-ONLY
Batch 3 implementation/GPU validation: NOT STARTED
```

`READY-FOR-B3-01-ONLY` 表示可以按票开始第一张基础契约Ticket，不表示后续Ticket可跳过前置、Summary和独立Review。
