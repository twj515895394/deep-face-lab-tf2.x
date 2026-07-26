# DeepFaceLab TF2.x 项目交接文档：Batch 1 详细设计补齐

> 交接编号：H-002  
> 创建日期：2026-07-26  
> 仓库：`twj515895394/deep-face-lab-tf2.x`  
> 默认分支：`main`  
> 上一份交接：`handoff-20260726-initial-project-state.md`  
> 本次定位：完成 Batch 1 的源码复核与文件级、函数级详细设计，尚未开始运行时代码修改。

---

## 1. 本次会话目标

根据 H-001 的下一步要求：

```text
进入 Batch 1：P0 正确性与扩展骨架
```

完成：

```text
docs/development/batch1-correctness-and-extension-foundation-tasks.md
```

该文档必须基于当前源码重新复核，而不是重复已有架构概念。

---

## 2. 已完成工作

### 2.1 读取并确认实施入口

已读取：

```text
.handoff/current.md
.handoff/handoff-20260726-initial-project-state.md
docs/README.md
docs/implementation/enhanced-dfl-master-implementation-plan.md
docs/implementation/deepfacelab-code-modification-map.md
docs/implementation/deepfacelab-training-call-chain-analysis.md
docs/implementation/deepfacelab-config-and-extension-architecture.md
docs/implementation/deepfacelab-merger-call-chain-analysis.md
docs/implementation/manual-quality-acceptance-and-development-validation-standard.md
docs/optimization/training-correctness-audit.md
```

### 2.2 重新复核当前源码

重点读取：

```text
models/Model_SAEHD/Model.py
models/ModelBase.py
core/leras/optimizations.py
core/leras/archis/DeepFakeArchi.py
core/leras/layers/Conv2D.py
core/leras/layers/Dense.py
core/leras/optimizers/AdaBelief.py
core/leras/optimizers/Lion.py
core/leras/optimizers/RMSprop.py
mainscripts/Merger.py
merger/MergerConfig.py
merger/MergeMasked.py
main.py
```

### 2.3 新增 Batch 1 详细设计

已新增：

```text
docs/development/batch1-correctness-and-extension-foundation-tasks.md
```

内容覆盖：

- 当前源码已确认问题；
- Batch 1 范围与禁止范围；
- Eyes / Mouth Priority 真实 mask 修复；
- 训练异常处理；
- Precision Contract；
- FP32 / FP16 / BF16 与 Loss Scaling；
- Lion 更新公式与旧 state 迁移；
- optimizer roundtrip；
- runtime state 保存恢复；
- Enhancement Config / Feature Flag；
- 训练 smoke test；
- Merge smoke test；
- 兼容回归矩阵；
- 文件级任务表；
- 推荐提交拆分；
- Batch 1 阻断条件与完成标准。

### 2.4 同步文档入口

已完成：

```text
.handoff/current.md
```

现在指向 H-002，并明确下一步为 B1-00 与 B1-01。

已完成：

```text
docs/README.md
```

已加入：

- `development/` 目录定位；
- Batch 1 详细设计入口；
- 当前真实状态；
- Batch 1 推荐阅读顺序；
- 当前 P0 任务顺序；
- “详细设计完成不等于代码已实现”的状态说明。

---

## 3. 本次确认的关键源码事实

### 3.1 Eyes / Mouth Priority 确认实际失效

当前样本生成器在 `eyes_mouth_prio=True` 时，会输出第 4 个真实 EYES_MOUTH mask。

但：

```text
SAEHDModel.onTrainOneIter()
```

只读取 src / dst 的前三项。

随后：

```text
unified_train()
```

使用 `np.zeros_like(full_mask)` 填充 Eyes / Mouth placeholder。

结论：

```text
训练图存在 priority loss
但实际 mask 为全零
因此该 loss 没有有效监督
```

这是下一步第一优先代码修复。

### 3.2 当前 BF16 不是目标中的标准混合精度结构

当前 BF16 路径会直接创建 BF16 Conv2D 权重，optimizer slot 又继承参数 dtype。

因此当前更接近：

```text
BF16 Weight
+
BF16 Compute
+
可能的 BF16 Optimizer Slot
```

而不是：

```text
FP32 Master Weight
+
BF16 Compute
+
FP32 Optimizer State
```

下一步必须先建立 dtype 审计报告，不能只看 Keras global policy。

### 3.3 当前 Loss Scaling 策略存在冲突

当前：

- FP16 没有手工 Loss Scale；
- BF16 使用初始值 32768；
- `MixedPrecisionManager` 又定义 BF16 默认 scale=1；
- `auto` 分支在当前选项中不可达。

详细设计已规定统一 requested / effective precision resolver。

### 3.4 当前数值检查发生在 optimizer update 之后

`unified_train()` 的单次 session run 同时 fetch loss 和 update op。

之后才检查 loss 是否 finite，无法保证坏 step 被跳过。

目标顺序：

```text
unscale gradient
→ finite check
→ finite 才 apply update
```

### 3.5 Lion 公式确认存在 P0 问题

当前 Lion 定义了 `beta_2`，但实际更新没有使用它。

修复后旧 slot 语义不兼容，因此详细设计规定：

- 新 Lion state 使用 v2 schema；
- legacy Lion 主权重可以加载；
- legacy optimizer state 不静默恢复；
- 新 optimizer state 从零开始并明确告警。

### 3.6 非 OOM 异常处理不可靠

当前 `onTrainOneIter()` 对非 OOM 异常没有稳定 re-raise 路径，并存在重复 `raise`。

该问题已纳入 Batch 1 独立任务。

---

## 4. 实际修改文件

本次只修改文档，没有修改运行时代码。

新增：

```text
docs/development/batch1-correctness-and-extension-foundation-tasks.md
.handoff/handoff-20260726-batch1-detailed-design.md
```

更新：

```text
.handoff/current.md
docs/README.md
```

所有计划中的 Python 运行时文件仍保持原状。

---

## 5. 关键技术决策

### 5.1 第一份代码提交只修 Eyes / Mouth mask

不得同时加入：

- 新 Loss；
- Sampling；
- Shape-aware Merge；
- 大规模 mixed precision 重构。

推荐提交：

```text
fix(training): wire real eyes and mouth masks into priority loss
```

### 5.2 正确性修复不使用新 master flag

Eyes / Mouth Priority 已经由现有：

```text
eyes_mouth_prio
```

控制。

它属于已有功能修复，不应再被 `enhanced_training` 包一层。

### 5.3 低精度先审计再重构

最低安全出口：

```text
FP32 = validated
FP16 / BF16 = experimental
```

只有 dtype、finite gate、保存恢复证据完整后，才能提升状态。

### 5.4 Batch 1 不增加独立 YAML

当前继续使用：

```text
ModelBase.options
+
版本化 enhancements dict
```

避免立即形成多配置源冲突。

### 5.5 smoke test 使用 unittest 与 synthetic fixture

- 不强制引入 pytest；
- 单元测试不依赖私有人脸素材；
- 真实 faceset 通过本地 manifest 指定；
- Merge 通过 dummy predictor 覆盖工程路径。

---

## 6. 代码当前状态

```text
Batch 1 详细设计：已完成
Batch 1 代码修改：未开始
Eyes / Mouth bug：已源码确认，未修复
Lion 公式问题：已源码确认，未修复
Precision Contract：未实现
Feature Flag 骨架：未实现
Training smoke：未实现
Merge smoke：未实现
```

当前主分支仍存在已确认 P0 问题，不能把 Batch 1 标记为完成。

---

## 7. 测试与验证结果

本次未执行训练或 Merge 运行测试。

原因：

- 本次目标是详细设计补齐；
- 当前会话通过 GitHub 读取源码，没有本地 GPU / faceset 运行环境；
- 所有运行收益仍需后续代码会话实际验证。

已完成的是静态源码复核、调用链确认和施工设计。

---

## 8. 未完成事项

按顺序：

1. 新增最小 `tests/smoke` 测试框架。
2. 修复 Eyes / Mouth Priority mask 传递。
3. 修复训练异常 re-raise。
4. 建立 Precision Contract 报告。
5. 添加 optimizer roundtrip 测试。
6. 修复 Lion 公式并保护 legacy state。
7. 建立 finite gradient gate。
8. 明确 FP16 / BF16 Loss Scaling。
9. 保存恢复 runtime state。
10. 增加 Enhancement Config 默认骨架。
11. 建立 SAEHD 小数据集集成 smoke。
12. 建立 MergeMasked smoke。
13. 完成兼容回归矩阵。
14. 更新 implementation status、索引与下一份 handoff。

---

## 9. 已知风险

### 9.1 Eyes / Mouth 修复后 loss 可能上升

因为原 loss 实际无效，修复后数值变化不等于回归。

### 9.2 Lion 修复后不能延续旧优化轨迹

必须重置 legacy Lion optimizer state，但保留主模型权重。

### 9.3 FP32 master weight 可能增加显存

不能为了满足理论契约直接破坏低显存用户；需要独立观测和回退。

### 9.4 低精度改造可能影响旧 checkpoint dtype

所有改造必须先做保存恢复和 state dtype 报告。

### 9.5 当前没有实际训练验证

文档中的目标行为不是已实现事实。

---

## 10. 下一步明确任务

下一会话直接执行：

```text
B1-00：建立最小 smoke harness
B1-01：修复 Eyes / Mouth Priority 真实 mask
```

建议第一轮只修改：

```text
models/Model_SAEHD/Model.py
tests/smoke/test_batch1_eyes_mouth_masks.py
```

完成后验证：

- Flag 关闭时三输出；
- Flag 开启时四输出；
- feed_dict 使用真实 mask；
- synthetic priority loss 非零；
- 旧默认训练路径不变。

---

## 11. 新会话启动顺序

```text
1. .handoff/current.md
2. .handoff/handoff-20260726-batch1-detailed-design.md
3. docs/development/batch1-correctness-and-extension-foundation-tasks.md
4. models/Model_SAEHD/Model.py
5. core/leras/optimizers/Lion.py
6. models/ModelBase.py
7. merger/MergeMasked.py
```

不要重新开始泛化架构设计。

---

## 12. 相关提交

```text
11f9e9367d19b6da0725112b178d06e58b17fc06
docs: add Batch 1 correctness and extension foundation design

c504979dfba366f958692a703b370282c1c8842f
docs: add Batch 1 detailed design handoff

0915be8d79842353e3b4a1e10afc06ea41c6e35c
docs: point current handoff to Batch 1 detailed design

2b7e997d79c3f93ad0b05caac50a8aaf45e64b9d
docs: index Batch 1 detailed development design
```

本文件最终状态同步提交：

```text
docs: finalize Batch 1 design handoff status
```
