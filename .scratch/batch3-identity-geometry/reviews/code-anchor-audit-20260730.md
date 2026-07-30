# Batch 3 代码锚点复核报告（2026-07-30）

## 1. Review对象

- `models/Model_SAEHD/Model.py`
- `models/ModelBase.py`
- `core/enhancements/config.py`
- `samplelib/SampleProcessor.py`
- `core/imagelib/warp.py`
- `facelib/LandmarksProcessor.py`
- `samplelib/sampling/loss_stats.py`
- `mainscripts/Trainer.py`
- `merger/MergeMasked.py`
- `merger/MergerConfig.py`
- `merger/InteractiveMergerSubprocessor.py`

## 2. 复核结论

```text
代码锚点复核：COMPLETE
核心训练代码修改：NONE
自动测试执行：NOT EXECUTED（本轮为设计Review）
GPU训练：NOT EXECUTED
文档修订后可执行Ticket：B3-01 ONLY
```

## 3. 已确认调用链

```text
ModelBase.__init__
 -> load_train_step_config
 -> SAEHDModel.on_initialize_options
 -> SAEHDModel.on_initialize
    -> placeholders
    -> DF/LIAE forward
    -> per-GPU src/dst loss
    -> gpu_G_loss
    -> gradients finite gate
    -> unified_train
 -> SAEHDModel.onTrainOneIter
 -> ModelBase.train_one_iter
 -> loss_history
 -> TrainerSaveController / LossWindowTracker
 -> ModelBase.save/onSave
```

Merge侧：

```text
InteractiveMergerSubprocessor
 -> MergeMasked
 -> dst landmarks transform
 -> predictor
 -> mask selection/erode/blur
 -> inverse affine/blend
```

## 4. Findings与处置

### P0-01：原设计缺少可微预测Landmark来源

事实：SAEHD没有landmark head；样本landmark是监督数据。若直接比较“预测landmark”会没有真实梯度，或迫使执行Agent临时引入外部网络。

处置：B3-08～10重构为 `aligned landmark -> ratio/SDF target` 与现有可微 `gpu_pred_src_srcm` 的soft observable比较。禁止新增landmark网络和直接坐标Loss。

状态：`CLOSED-BY-DESIGN-FIX`

### P0-02：`geometry.enabled` 与现有Gate重复

事实：已有 `training.enabled/loss_hooks/identity_geometry`。额外开关会造成双来源。

处置：取消 `geometry.enabled`；`geometry`仅保存参数。

状态：`CLOSED-BY-DESIGN-FIX`

### P1-01：legacy `LANDMARKS_ARRAY` 未与target transform对齐

事实：当前只按原图宽高归一化，没有face alignment、random affine和flip semantic remap。

处置：保留legacy行为；B3-08新增显式aligned supervision类型和逐步骤契约。

状态：`CLOSED-BY-DESIGN-FIX`

### P1-02：Loss History通道维度可能变化

事实：ModelBase按返回loss通道写history，LossWindow拒绝窗口内维度不一致。

处置：disabled保持2通道；enabled使用冻结通道；会话中禁止热切effective。

状态：`CLOSED-BY-DESIGN-FIX`

### P1-03：Anchor与Batch 4 Template边界模糊

处置：Batch 3内部文件固定为`faceset_shape_anchor.v1.json`；不命名`.srcshape`、不提供Merge发现。Batch 4另行revalidation。

状态：`CLOSED-BY-DESIGN-FIX`

### P1-04：Loss Hook插入点不精确

处置：B3-13固定为每GPU `gpu_src_loss`完成后、`gpu_G_loss`创建前；只使用`gpu_pred_src_srcm`，不触碰dst/style/GAN/true-face。

状态：`CLOSED-BY-DESIGN-FIX`

### P1-05：Curriculum持久化可能过度设计

处置：使用已有`iter + options`确定性函数恢复，不新增权重、optimizer slot或sidecar状态。

状态：`CLOSED-BY-DESIGN-FIX`

## 5. 仍需实施阶段验证

- Soft-mask observables公式是否在真实分辨率上稳定。
- SDF target的CPU成本和IPC增量。
- Multi-GPU metric聚合。
- FP16/BF16 cast和gradient finite。
- Windows spawn、save/exit/resume、资源清理。
- Geometry训练对脸型、姿态和表情的实际影响。

这些不影响B3-01基础票启动，但会分别阻塞B3-08、B3-13、B3-14和批次签发。

## 6. Review签发

```text
APPROVED-FOR-B3-01-ONLY
```

禁止未完成前置Ticket就直接执行B3-08～13。每票仍需测试、Summary、独立Review和修复闭环。
