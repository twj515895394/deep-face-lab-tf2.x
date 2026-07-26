# Batch 1：P0 正确性与扩展安全骨架详细设计

> 文档版本：v1.0  
> 创建日期：2026-07-26  
> 基线提交：`afece7f10311650e2a50a40faf75f4a86268ba87`  
> 当前状态：详细设计完成，代码尚未实施  
> 批次定位：承接 `Stage 1：P0 训练正确性修复` 与 `Stage 2：配置与扩展骨架`  
> 执行原则：先修已确认错误，再建立观测与回归；不在本批次引入新的训练 Loss、Sampling、Identity Geometry 或 Shape-aware Merge 算法。

---

## 1. 文档目的

本文件是 Batch 1 的文件级、函数级施工说明，不是新的总体架构路线。

它负责回答：

1. 当前源码中已经确认了哪些 P0 正确性问题。
2. 每个问题应修改哪些文件、函数和数据接口。
3. Feature Flag 与配置兼容骨架如何接入现有 `ModelBase.options` 和 `MergerConfig`。
4. 训练、保存恢复和 Merge 的 smoke test 如何落地。
5. 每个任务如何回退、如何验收、如何拆分提交。
6. Batch 1 完成后，什么条件下才允许进入 Batch 2。

总体实施顺序仍以：

```text
docs/implementation/enhanced-dfl-master-implementation-plan.md
```

为唯一总入口。

---

## 2. Batch 1 范围

### 2.1 本批次必须完成

```text
B1-00  冻结代码与验证基线
B1-01  修复 Eyes / Mouth Priority 真实 mask 传递
B1-02  统一训练异常处理与失败语义
B1-03  建立精度、梯度和 optimizer slot 审计能力
B1-04  修复 Lion 更新公式并定义 optimizer state 迁移规则
B1-05  明确 FP32 / FP16 / BF16 数值契约与 Loss Scaling 策略
B1-06  建立向后兼容的 Enhancement Config / Feature Flag 骨架
B1-07  建立训练、保存恢复 smoke test
B1-08  建立 Merge 默认路径 smoke test
B1-09  建立增强关闭时的兼容回归与交接记录
```

### 2.2 本批次不做

- 不新增 Region Loss、Boundary Loss、Frequency Loss。
- 不新增 Identity Appearance / Identity Geometry Loss。
- 不新增 metadata、quality sampling、pose sampling。
- 不实现 Source Shape Template。
- 不实现 Hybrid Landmark、Piecewise Affine Warp、Shape-aware Mask。
- 不实现 Temporal Stabilization。
- 不重写 SAEHD。
- 不建设完整 YAML 配置体系、Web UI 或服务化 API。
- 不以视觉质量提升作为本批次完成标准。

### 2.3 Batch 1 的最终产出

Batch 1 完成后，项目应拥有一个可信的工程底座：

```text
真实训练输入正确
+
错误不会被静默吞掉
+
精度行为可观测
+
optimizer state 可验证
+
新能力默认关闭
+
旧模型与旧 Merge 可回退
+
smoke test 可重复执行
```

---

## 3. 当前源码复核结论

以下结论基于本文件创建时的 `main` 分支源码，不再只是历史文档推测。

### 3.1 Eyes / Mouth Priority 当前实际失效

当前样本生成器在 `eyes_mouth_prio=True` 时，会为 src 和 dst 各追加一个真实的 `EYES_MOUTH` mask：

```text
src_samples = [warped_src, target_src, target_srcm, target_srcm_em]
dst_samples = [warped_dst, target_dst, target_dstm, target_dstm_em]
```

但 `SAEHDModel.onTrainOneIter()` 当前只读取前三项：

```python
warped_src, target_src, target_srcm = src_samples[0], src_samples[1], src_samples[2]
warped_dst, target_dst, target_dstm = dst_samples[0], dst_samples[1], dst_samples[2]
```

随后 `unified_train()` 在 `_has_eyes_mouth=True` 时向占位符传入：

```python
np.zeros_like(target_srcm)
np.zeros_like(target_dstm)
```

因此，虽然训练图中存在 Eyes / Mouth Priority loss，实际参与计算的区域 mask 为全零，优先损失没有产生有效梯度。

### 3.2 当前低精度实现不是标准“混合精度”契约

当前 BF16 路径同时使用：

1. Keras `mixed_bfloat16` global policy；
2. `DeepFakeArchi(..., use_bf16=True)`；
3. Conv2D 权重直接创建为 `tf.bfloat16`；
4. optimizer slot 使用 `v.dtype`，因此同样可能为 BF16；
5. 手工 `loss_scale_var=32768`；
6. 独立的 `MixedPrecisionManager`，但该管理器又认为 BF16 不需要激进 Loss Scaling。

这与目标契约：

```text
FP32 Master Weight
→ BF16 / FP16 Forward Compute
→ FP32 Gradient Accumulation
→ FP32 Optimizer State / Update
```

并不一致。

Batch 1 不允许直接把当前实现称为“已验证混合精度”，必须先通过 dtype 审计矩阵确认真实行为。

### 3.3 FP16 与 BF16 的 Loss Scaling 策略互相矛盾

当前行为：

- `precision=fp16` 时 `loss_scale_var=None`，没有手工 Loss Scaling；
- `precision=bf16` 时创建初始值为 32768 的 Loss Scale；
- `MixedPrecisionManager` 的设计却是 FP16 需要动态缩放、BF16 默认 scale=1；
- `precision_choices` 不包含 `auto`，但初始化逻辑保留了仅在 `precision == 'auto'` 时执行的路径。

必须收敛为一个唯一的精度解析和 Loss Scaling 决策入口。

### 3.4 当前 Inf / NaN 检查发生在参数更新之后

当前 `unified_train()` 一次 `tf_sess.run()` 同时 fetch：

```text
src_loss
dst_loss
src_dst_loss_gv_op
可选 discriminator update op
```

也就是说，检查返回 loss 是否 finite 时，optimizer update 已经执行。

如果梯度已经包含 Inf / NaN：

- 参数可能已经被污染；
- 当前代码只会在更新后降低 Loss Scale；
- 不能保证坏 step 被跳过。

正确设计必须做到：

```text
计算 scaled loss
→ 生成 gradient
→ unscale gradient
→ 检查 gradient finite
→ finite 才执行 update
→ 非 finite 时跳过整个 step 并降低 scale
```

### 3.5 Loss Scale 运行状态当前不会完整恢复

`loss_scale_var`、连续稳定步数、调整计数器未作为明确 runtime state 写入 `data.dat`，也未作为独立 saveable 加入 `model_filename_list`。

因此动态缩放状态在重新启动后可能回到初始值，恢复训练不具备严格连续性。

### 3.6 Lion 更新公式当前不符合标准 Lion 语义

当前 `Lion`：

- 定义了 `beta_1` 与 `beta_2`；
- 实际更新只使用 `beta_1`；
- 保存的状态 `c` 直接被赋值为 `beta_1 * c + (1-beta_1) * grad`；
- `beta_2` 没有参与状态更新。

目标公式应为：

```text
update_direction = sign(beta1 * momentum + (1-beta1) * grad)
new_momentum     = beta2 * momentum + (1-beta2) * grad
new_weight       = weight - lr * update_direction
```

修复后，旧 Lion slot 与新 Lion slot 的语义不同，不能静默继续恢复。

### 3.7 optimizer slot dtype 当前继承参数 dtype

AdaBelief、Lion、RMSprop 的状态变量均以 `dtype=v.dtype` 创建。

如果模型参数直接为 FP16 / BF16：

- momentum、variance、accumulator 也会进入低精度；
- 与 P0 审计目标中的 FP32 optimizer state 不一致；
- 保存时虽然统一 `force_dtype=np.float32`，重新加载后仍会赋值回当前 slot dtype。

必须通过审计报告和测试确认保存前、文件中、加载后的实际 dtype 与数值误差。

### 3.8 非 OOM 训练异常当前可能被静默吞掉

`onTrainOneIter()` 当前对异常的处理只对 OOM 重新抛出，非 OOM 异常没有稳定日志和明确 re-raise，之后还可能继续访问未赋值的 `src_loss` / `dst_loss`。

Batch 1 必须统一为：

```text
OOM：记录上下文并重新抛出
非 OOM：记录完整 traceback、关键配置与 batch shape，然后重新抛出
数值异常：按精度策略跳过 step，不走通用异常吞噬
```

---

## 4. 实施原则

### 4.1 正确性修复与增强功能分开

Eyes / Mouth Priority 是已有功能的正确性修复：

- 由现有 `eyes_mouth_prio` 控制；
- 不再额外套一层 `enhanced_training_enabled`；
- 当 `eyes_mouth_prio=False` 时保持现有三输出数据路径；
- 当其为 True 时必须传递真实 mask。

未来 Loss、Sampling、Shape-aware Merge 才由新的 Enhancement Config 控制。

### 4.2 默认行为优先

所有新增增强 Flag：

- 缺失时视为 False；
- 读取失败时视为 False；
- 未知字段不得改变旧流程；
- 新模块初始化失败时，只有明确允许 fallback 的模块才能回到传统路径；
- 训练正确性错误不得被 fallback 掩盖。

### 4.3 先观测，再改变低精度底层语义

Batch 1 的第一步不是立刻重构所有权重为 FP32 master weight，而是：

1. 建立 dtype 审计报告；
2. 固定 FP32 基线；
3. 验证保存恢复；
4. 把 FP16 / BF16 标记为 `experimental`，直到通过契约；
5. 再决定是否实施 FP32 master weight。

如果在 Batch 1 内无法完成安全的 FP32 master weight 改造：

- FP32 必须成为唯一“已验证”训练精度；
- FP16 / BF16 必须保留显式风险提示；
- 不得阻塞旧模型以原精度加载；
- 不得把未验证状态写成已完成。

### 4.4 小提交、可回退

每个提交只处理一种目的。禁止把 mask 修复、Lion 修复、配置骨架和 Merge 新算法放在同一个提交中。

---

## 5. 目标模块与目录

### 5.1 现有文件

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

### 5.2 建议新增文件

```text
core/enhancements/__init__.py
core/enhancements/config.py
core/leras/precision_contract.py

tests/smoke/__init__.py
tests/smoke/test_batch1_config_defaults.py
tests/smoke/test_batch1_eyes_mouth_masks.py
tests/smoke/test_batch1_lion_formula.py
tests/smoke/test_batch1_optimizer_roundtrip.py
tests/smoke/test_batch1_precision_contract.py
tests/smoke/test_batch1_merge_masked.py

tools/smoke/run_batch1_integration.py
tests/fixtures/batch1/README.md
tests/fixtures/batch1/manifest.example.json
```

测试优先使用 Python 标准库 `unittest`，避免 Batch 1 为项目强制增加 pytest 依赖。

统一执行入口：

```bash
python -m unittest discover -s tests/smoke -p "test_batch1_*.py"
```

---

## 6. B1-00：冻结基线

### 6.1 目标

在改代码前保存可重复的工程基线，防止后续无法判断变化来自修复还是环境差异。

### 6.2 必须记录

```text
Git commit SHA
Python version
TensorFlow version
CUDA / cuDNN version
GPU 型号与驱动
nn.data_format
模型架构 df / liae
resolution
batch size
precision
optimizer
models_opt_on_gpu
opt_states_on_gpu
random_warp
eyes_mouth_prio
GAN / TrueFace 是否开启
```

### 6.3 基线运行项

1. FP32 模型初始化。
2. 固定 synthetic batch 的单步 forward / loss。
3. 模型权重保存、销毁 session、重新加载。
4. dummy predictor 驱动一次 `MergeMaskedFace()`。
5. 缺失 Enhancement Config 时读取默认值。

### 6.4 产物

建议输出到工作区而非提交运行日志：

```text
workspace/validation/batch1/<timestamp>/environment.json
workspace/validation/batch1/<timestamp>/precision-contract.json
workspace/validation/batch1/<timestamp>/smoke-summary.json
workspace/validation/batch1/<timestamp>/logs/
```

---

## 7. B1-01：Eyes / Mouth Priority 修复设计

### 7.1 修改文件

```text
models/Model_SAEHD/Model.py
```

### 7.2 修改函数

```text
SAEHDModel.on_initialize()
内部 unified_train()
SAEHDModel.onTrainOneIter()
```

### 7.3 目标数据流

关闭时：

```text
SampleGeneratorFace
→ [warped, target, full_mask]
→ onTrainOneIter
→ unified_train(6 个主输入)
→ 不 feed eyes / mouth placeholder
```

开启时：

```text
SampleGeneratorFace
→ [warped, target, full_mask, eyes_mouth_mask]
→ onTrainOneIter
→ unified_train(主输入 + src_em + dst_em)
→ feed 真实 eyes / mouth mask
→ priority loss 生效
```

### 7.4 推荐实现

新增局部纯函数或静态辅助函数：

```python
def _unpack_training_samples(samples, has_eyes_mouth, domain):
    expected = 4 if has_eyes_mouth else 3
    if len(samples) != expected:
        raise ValueError(...)

    warped, target, full_mask = samples[:3]
    eyes_mouth_mask = samples[3] if has_eyes_mouth else None
    return warped, target, full_mask, eyes_mouth_mask
```

`onTrainOneIter()` 改为：

```python
warped_src, target_src, target_srcm, target_srcm_em = ...
warped_dst, target_dst, target_dstm, target_dstm_em = ...

src_loss, dst_loss = self.unified_train(
    warped_src, target_src, target_srcm,
    warped_dst, target_dst, target_dstm,
    target_srcm_em=target_srcm_em,
    target_dstm_em=target_dstm_em,
)
```

`unified_train()`：

- 开启时不允许使用 `zeros_like()` 作为静默替代；
- 校验 src / dst EM mask 非 None；
- 校验 shape 与 full mask 相同；
- 校验 dtype 可安全转换为 placeholder dtype；
- 校验 finite；
- 允许单个 batch 的覆盖率很低，但 debug 模式下输出 coverage；
- 关闭时不额外传输 EM mask，继续保留当前 IPC 优化。

### 7.5 失败策略

当 `eyes_mouth_prio=True` 但生成器未返回 mask：

```text
立即抛出 ValueError
+
日志打印 domain、实际输出数量、期望数量、batch shape
```

不得自动使用全零 mask，因为这会把配置错误伪装成正常训练。

### 7.6 单元验证

`test_batch1_eyes_mouth_masks.py` 至少覆盖：

1. Flag 关闭时接受 3 个输出。
2. Flag 开启时接受 4 个输出。
3. Flag 开启但只有 3 个输出时失败。
4. EM mask shape 不一致时失败。
5. synthetic target / prediction 只在 EM 区域有差异时，开启 priority 后 loss 明显增加。
6. feed_dict 中 EM placeholder 对应的数组与输入 mask 内容一致，而不是全零数组。

### 7.7 完成标准

- `zeros_like(target_srcm)` 与 `zeros_like(target_dstm)` 不再作为正常训练输入。
- Priority 关闭时训练接口与原流程一致。
- Priority 开启时真实 mask 进入训练图。
- smoke test 能证明 priority loss 对 synthetic 输入产生非零贡献。

---

## 8. B1-02：训练异常处理设计

### 8.1 修改文件

```text
models/Model_SAEHD/Model.py
```

### 8.2 修改函数

```text
SAEHDModel.onTrainOneIter()
```

### 8.3 异常分类

#### A. OOM

识别 TensorFlow / CUDA OOM 后：

- 记录当前 batch size、resolution、precision、optimizer、GPU；
- 重新抛出原异常；
- 不在本批次自动调整 batch size。

#### B. 数值异常

由训练图返回明确状态：

```text
all_gradients_finite
step_applied
current_loss_scale
```

如果梯度不 finite：

- 跳过 optimizer update；
- 降低 Loss Scale；
- 返回可识别的 skipped-step 状态；
- 不增加 optimizer iteration；
- 模型总 iteration 是否增加必须统一定义，推荐不增加。

#### C. 其他异常

- 打印完整 traceback；
- 打印 batch shape 和关键 options；
- 重新抛出；
- 不允许无日志继续运行。

### 8.4 完成标准

- 删除重复 `raise`。
- 非 OOM 异常不会被吞掉。
- 数值异常不会在参数已经更新后才被发现。
- 日志可以定位到配置与输入上下文。

---

## 9. B1-03：Precision Contract 审计设计

### 9.1 新增模块

```text
core/leras/precision_contract.py
```

### 9.2 职责

该模块不直接定义网络，而是统一：

- 请求精度解析；
- 有效精度解析；
- Keras policy 设置；
- Loss Scaling 策略；
- dtype 审计报告；
- fallback 日志。

### 9.3 建议数据结构

为兼容 Python 3.6，使用普通类或 dict，不强制依赖 dataclass。

```python
{
  "requested_precision": "bf16",
  "effective_precision": "bf16",
  "status": "experimental",
  "compute_dtype": "bfloat16",
  "master_weight_dtype": "bfloat16",
  "gradient_dtype": "bfloat16",
  "optimizer_slot_dtypes": ["bfloat16"],
  "loss_scale_mode": "none",
  "loss_scale_value": 1.0,
  "fallback_reason": None
}
```

### 9.4 必须观测的对象

- placeholder dtype；
- Conv2D weight / bias dtype；
- Dense weight / bias dtype；
- encoder / inter / decoder 首个和末个权重 dtype；
- generator gradient dtype；
- 多 GPU 聚合前后 gradient dtype；
- AdaBelief ms / vs dtype；
- Lion momentum dtype；
- RMSprop accumulator dtype；
- 保存文件写出 dtype；
- 重建图后 load 的 variable dtype；
- load 后数值最大绝对误差。

### 9.5 单一解析入口

建议新增：

```python
resolve_precision_contract(requested_precision, device_config)
```

规则：

```text
fp32：稳定支持，默认
fp16：实验状态；需要 gradient finite gate + dynamic loss scaling
bf16：实验状态；默认不使用激进 loss scaling
无效值：回退 fp32，并更新 effective_precision
初始化失败：回退 fp32，后续 DeepFakeArchi 必须使用 effective_precision，而不是原始 requested_precision
```

### 9.6 清理重复逻辑

`models/Model_SAEHD/Model.py` 与 `core/leras/optimizations.py` 不应各自独立决定 precision policy。

Batch 1 完成后：

- `MixedPrecisionManager` 可保留为底层实现；
- SAEHD 只调用统一 resolver；
- `precision == 'auto'` 要么正式加入可选值并测试，要么删除不可达分支；
- 日志只报告实际生效的 `effective_precision`。

### 9.7 状态分级

```text
validated：通过 dtype、finite、roundtrip、短训练 smoke
experimental：可显式启用，但未满足完整契约
blocked：当前硬件或 TensorFlow 不支持，自动回退 FP32
```

### 9.8 完成标准

- 每次模型初始化都能输出 precision contract 摘要。
- 请求 BF16 但初始化失败时，不会继续创建 BF16 网络。
- FP32 报告稳定通过。
- FP16 / BF16 的真实权重和 slot dtype 被明确记录，不再用“mixed”名称掩盖实际实现。

---

## 10. B1-04：Lion 与 optimizer state 设计

### 10.1 Lion 修改文件

```text
core/leras/optimizers/Lion.py
```

### 10.2 正确更新顺序

```python
update_direction = tf.sign(
    beta_1 * momentum + (1.0 - beta_1) * gradient
)

new_momentum = (
    beta_2 * momentum + (1.0 - beta_2) * gradient
)

new_weight = weight - lr * update_direction
```

如果未来支持 weight decay：

- 必须是显式参数；
- 默认值为 0；
- 不在修复公式时偷偷改变现有学习率和 decay 行为。

### 10.3 旧 Lion state 迁移

旧 `c` 的语义与修复后 momentum 不一致。

推荐方案：

```text
optimizer_state_meta = {
  "optimizer": "lion",
  "schema_version": 2,
  "formula": "lion-beta1-update-beta2-momentum"
}
```

加载规则：

1. 新模型直接使用 v2。
2. 旧模型缺少 metadata 时视为 legacy。
3. legacy Lion state 不自动加载到 v2。
4. 模型主权重继续加载。
5. Lion optimizer state 重新初始化，并打印一次明确警告。
6. 不删除旧文件，便于回退旧代码。

建议固定的新文件名：

```text
src_dst_opt_lion_v2.npy
D_code_opt_lion_v2.npy
GAN_opt_lion_v2.npy
```

AdaBelief / RMSprop 在未改变状态语义前继续兼容原有文件。

### 10.4 optimizer state 通用 metadata

建议保存到 `ModelBase` 的 `data.dat`：

```python
"optimizer_state_meta": {
    "main": {"name": "adabelief", "schema_version": 1},
    "code": {"name": "adabelief", "schema_version": 1},
    "gan":  {"name": "adabelief", "schema_version": 1}
}
```

### 10.5 optimizer 切换语义

当用户从 AdaBelief 切换到 Lion / RMSprop：

- 模型权重继续恢复；
- 不尝试把不同 optimizer 的 slot 互相解释；
- 新 optimizer state 从零初始化；
- 输出“optimizer changed, state reset”日志；
- 模型 iteration 可保留，但 optimizer iteration 从 0 开始，日志必须可见。

### 10.6 单元测试

`test_batch1_lion_formula.py`：

- 使用一个标量或小向量；
- 手工计算两步标准 Lion；
- 比较 TensorFlow 实现结果；
- 验证 `beta_2` 改变时第二步 momentum 与权重轨迹发生变化。

`test_batch1_optimizer_roundtrip.py`：

对 AdaBelief、Lion v2、RMSprop：

1. 固定变量和梯度。
2. 执行 N 步。
3. 保存参数和 optimizer state。
4. 重建 session 与 optimizer。
5. 加载。
6. 验证 iteration、slot 和下一步更新与连续训练一致。

### 10.7 完成标准

- Lion 的 `beta_2` 实际参与状态更新。
- legacy Lion state 不会静默按新公式继续训练。
- 三种 optimizer 均有最小 roundtrip 测试。
- optimizer 从 GPU state 切换到 CPU state 后，保存恢复数值保持一致。

---

## 11. B1-05：Loss Scaling 与 finite gate 设计

### 11.1 目标策略

#### FP32

```text
Loss Scaling：关闭
finite gate：保留基础检查
```

#### BF16

```text
默认 Loss Scale：1.0
原因：BF16 指数范围通常不需要 FP16 式激进缩放
状态：在 FP32 master weight / slot 契约未满足前标记 experimental
```

#### FP16

```text
动态 Loss Scaling：开启
初始值：32768，可配置但不在 UI 暴露高级调节
finite gradient：更新前检查
非 finite：跳过 step，scale / 2
连续稳定：达到窗口后 scale * 2，上限受控
```

### 11.2 图执行拆分

不再用一个 fetch 同时无条件执行所有 update op。

推荐构造：

```text
loss tensors
gradient tensors
unscaled gradient tensors
all_finite tensor
apply_update_op
skip_update_op
```

执行可采用：

```python
if sess.run(all_finite, feed_dict):
    sess.run([losses, apply_update_op], feed_dict)
else:
    sess.run(reduce_loss_scale_op)
```

为了避免重复 forward，可在图中使用 `tf.cond(all_finite, apply, skip)`，并一次 fetch：

```text
losses
all_finite
step_applied
current_loss_scale
```

最终选择应以不重复大规模 forward 为优先。

### 11.3 多 GPU 顺序

```text
每 GPU 计算 scaled gradients
→ 每 GPU unscale
→ 转为约定聚合 dtype
→ average_gv_list
→ finite check
→ apply optimizer
```

不得在不同 GPU 上用不同 Loss Scale。

### 11.4 runtime state

建议扩展 `ModelBase`：

```python
def get_runtime_state(self):
    return {}
```

保存到：

```python
model_data["runtime_state"]
```

SAEHD 保存：

```text
effective_precision
loss_scale
consecutive_finite_steps
steps_since_adjustment
last_numeric_skip_iter
```

旧 `data.dat` 缺失该字段时使用默认值。

### 11.5 完成标准

- 非 finite gradient 时 optimizer 不更新。
- FP16 动态 scale 可保存恢复。
- BF16 不再默认使用 32768 激进缩放，除非后续实验明确证明需要。
- `optimizer.iterations` 只在真实 update 时增加。

---

## 12. B1-06：Enhancement Config / Feature Flag 骨架

### 12.1 设计目标

为 Batch 2 及以后提供统一入口，但不改变当前默认行为。

### 12.2 新增文件

```text
core/enhancements/config.py
```

### 12.3 配置结构

建议使用版本化嵌套 dict：

```python
{
    "schema_version": 1,
    "training": {
        "enabled": False,
        "metadata_sampling": False,
        "loss_hooks": False,
        "identity_geometry": False,
        "curriculum": False,
    },
    "merge": {
        "enabled": False,
        "source_shape_template": False,
        "shape_aware_warp": False,
        "shape_aware_mask": False,
        "temporal_stabilization": False,
    },
    "runtime": {
        "fallback_on_optional_error": True,
        "strict_validation": False,
    },
}
```

### 12.4 读取优先级

Batch 1 只接入已有模型 options：

```text
self.options.get("enhancements")
→ normalize_enhancement_config()
→ 缺失字段补默认值
→ 未知字段保留到 raw 或忽略并警告
```

暂不引入独立 YAML，避免形成：

```text
model data.dat
+
training.yaml
+
merge.yaml
```

三套互相冲突的配置源。

未来 UI / 服务化需要外部配置时，由统一适配层映射到同一 schema。

### 12.5 API 建议

```python
cfg = EnhancementConfig.from_mapping(raw_mapping)

cfg.training_enabled
cfg.is_enabled("training.loss_hooks")
cfg.merge_enabled
cfg.fallback_on_optional_error
cfg.to_dict()
```

要求：

- 不直接暴露可变的内部默认 dict；
- bool 类型严格归一化；
- schema_version 缺失按 v1 legacy-safe 处理；
- schema_version 高于当前支持版本时默认关闭增强并告警；
- 不因配置解析失败阻断传统 DFL 流程。

### 12.6 SAEHD 接入

`SAEHDModel.on_initialize_options()`：

- 读取 `enhancements`；
- 归一化；
- 保存回 `self.options['enhancements']` 仅在创建新模型或用户明确修改时进行；
- 旧模型仅加载时，不强制重写 data.dat。

### 12.7 Merge 接入边界

Batch 1 不实现 Shape-aware Merge，仅提供默认读取工具。

未来 `MergerConfigMasked` 可接入：

```text
enhanced merge disabled → 当前 MergeMasked 路径
enhanced merge enabled  → 可选 shape pipeline
异常且允许 fallback     → 当前 MergeMasked 路径
```

本批次只验证：

- 配置缺失时当前 `MergerConfigMasked` 行为不变；
- 所有 merge flag 默认 False；
- 传统路径不依赖任何新 sidecar。

### 12.8 单元测试

`test_batch1_config_defaults.py`：

1. `None` 输入全部增强关闭。
2. 空 dict 全部增强关闭。
3. 只开启一个 flag 不影响其他 flag。
4. 类型错误回到安全默认。
5. 未知 schema version 全部增强关闭并产生 warning。
6. `to_dict()` roundtrip 一致。
7. 旧 `self.options` 无 `enhancements` 时不报错。

---

## 13. B1-07：训练与保存恢复 smoke test

### 13.1 测试分层

#### Layer 1：纯单元测试

不依赖真实 faceset 和 GPU：

- 配置归一化；
- sample unpack；
- Lion 公式；
- optimizer roundtrip；
- MergeMasked dummy predictor。

#### Layer 2：图级 smoke

使用 synthetic tensor：

- 创建小型 Leras variable；
- 计算 loss / gradient；
- 执行一次 optimizer update；
- 保存、重建、恢复；
- 比较下一步轨迹。

#### Layer 3：SAEHD 集成 smoke

需要项目负责人准备极小测试工作区：

```text
src aligned：建议 8～16 张
dst aligned：建议 8～16 张
resolution：64 或 96
batch size：2
architecture：df 或 liae 选一个主基线
optimizer：AdaBelief
precision：fp32
GAN / TrueFace：关闭
```

运行：

```text
初始化模型
→ 训练 2～5 iter
→ 保存
→ 关闭进程 / session
→ 重新加载
→ 继续 2～5 iter
```

### 13.2 集成 manifest

不把测试 faceset 和模型权重提交到仓库。

`tests/fixtures/batch1/manifest.example.json`：

```json
{
  "src_dir": "<absolute path>",
  "dst_dir": "<absolute path>",
  "model_dir": "<absolute path>",
  "merge_input_dir": "<absolute path>",
  "merge_aligned_dir": "<absolute path>",
  "merge_output_dir": "<absolute path>",
  "merge_mask_output_dir": "<absolute path>"
}
```

### 13.3 训练 smoke 检查项

- 能启动；
- generator 输出数量符合 flag；
- loss finite；
- 权重至少一个发生变化；
- optimizer iteration 增加；
- 保存文件存在且非空；
- 恢复后 model iteration 连续；
- optimizer slot 与 iteration 恢复；
- 下一步 loss 不出现无解释跳变；
- EM priority 开启时 mask coverage 非全零；
- 新 Enhancement Config 缺失时不报错。

### 13.4 验收容差

CPU / 同设备固定图级测试可使用严格容差。

GPU 集成测试不要求 byte-for-byte 相同，建议记录：

```text
loss absolute difference
weight max absolute difference
weight mean absolute difference
optimizer slot max absolute difference
```

阈值由 FP32 基线运行后固化，不在没有实际数据前拍脑袋写死。

---

## 14. B1-08：Merge smoke test

### 14.1 目标

Batch 1 不评价换脸质量，只保证传统 Merge 工程路径可运行。

### 14.2 修改与测试入口

```text
mainscripts/Merger.py
merger/MergerConfig.py
merger/MergeMasked.py
models/Model_SAEHD/Model.py::get_MergerConfig
```

原则上不要求修改 `MergeMasked.py` 的算法逻辑；如需测试辅助，应优先通过 dummy predictor 和 fixture 注入。

### 14.3 dummy predictor

返回：

```text
predicted face：与输入相同或固定渐变
predicted src mask：有效 [0,1] mask
predicted dst mask：有效 [0,1] mask
```

构造：

- 一张 synthetic BGR frame；
- 一组固定 68 landmarks fixture；
- `MergerConfigMasked(default_mode='overlay')`；
- super resolution、XSeg、STCO 全关闭。

### 14.4 检查项

- 返回图像 shape 正确；
- 返回 mask shape 正确；
- dtype 正确；
- 数值 finite；
- 图像和 mask 均在允许范围；
- `mode='original'` 可返回；
- 默认配置不要求新 sidecar；
- Enhancement Config 缺失时仍走原路径；
- 所有 merge 增强 flag 为 False 时，输出与改造前 baseline 在容差内一致。

### 14.5 真实模型集成 smoke

使用已有可加载模型：

```text
加载模型
→ get_MergerConfig()
→ predictor_func 单次推理
→ 处理 1～3 帧
→ 输出图片和 mask
```

不要求完成长视频，不要求人工判断视觉效果。

---

## 15. B1-09：兼容回归矩阵

### 15.1 模型配置矩阵

| 场景 | 期望 |
|---|---|
| 旧模型，无 `enhancements` | 正常加载，全部增强关闭 |
| 新模型，全部增强关闭 | 与传统路径一致 |
| `eyes_mouth_prio=False` | generator 保持三输出，不增加 EM IPC |
| `eyes_mouth_prio=True` | generator 四输出，真实 EM mask 进入训练 |
| 旧 AdaBelief state | 正常恢复 |
| 旧 RMSprop state | 正常恢复 |
| legacy Lion state + 新 Lion 公式 | 主权重恢复，optimizer state 明确重置 |
| optimizer 类型切换 | 主权重恢复，新 optimizer state 初始化并告警 |
| 请求低精度但初始化失败 | effective precision 回退 FP32 |
| Merge 无增强配置 | 传统 Merge 正常运行 |
| 新 sidecar 缺失 | Batch 1 不依赖 sidecar，不受影响 |

### 15.2 “增强关闭时行为不变”的定义

不是只验证“没有抛异常”，而是验证：

```text
相同模型权重
相同输入
相同随机种子或固定 synthetic tensor
相同旧配置
所有 enhancement flags=False
```

得到：

- 相同执行分支；
- 相同输出 shape / dtype；
- loss 与权重更新在既定容差内一致；
- Merge 输出在既定容差内一致；
- 不生成额外必需文件；
- 不改变旧命令参数要求。

### 15.3 CLI 兼容

Batch 1 不新增必须参数。

以下命令保持原用法：

```bash
python main.py train ...
python main.py merge ...
python main.py exportdfm ...
```

未来需要 CLI flag 时必须是可选参数，默认值为关闭。

---

## 16. 文件级任务清单

| ID | 文件 | 函数 / 类 | 修改内容 | 风险 | 回退 |
|---|---|---|---|---|---|
| B1-01 | `models/Model_SAEHD/Model.py` | `onTrainOneIter` | 读取第 4 个 EM mask | 中 | 关闭 `eyes_mouth_prio` 回到三输出 |
| B1-01 | `models/Model_SAEHD/Model.py` | `unified_train` | 接收并 feed 真实 EM mask | 中 | 单独回滚该提交 |
| B1-02 | `models/Model_SAEHD/Model.py` | `onTrainOneIter` | 统一异常日志和 re-raise | 低 | 回滚异常处理提交 |
| B1-03 | `core/leras/precision_contract.py` | 新模块 | 统一 requested/effective precision 和审计 | 中 | SAEHD 继续使用旧 precision 逻辑 |
| B1-03 | `models/Model_SAEHD/Model.py` | `on_initialize` | 调用 precision resolver | 高 | 默认强制 FP32 |
| B1-04 | `core/leras/optimizers/Lion.py` | `get_update_op` | 修复标准 Lion 更新 | 高 | 恢复 legacy Lion 代码和文件 |
| B1-04 | `models/Model_SAEHD/Model.py` | optimizer 初始化 / 文件列表 | Lion v2 state 文件与迁移 | 中 | 只重置 optimizer state |
| B1-05 | `models/ModelBase.py` | `save` / 初始化 | 保存 runtime_state / optimizer metadata | 中 | 缺失字段默认空 dict |
| B1-05 | `models/Model_SAEHD/Model.py` | gradient/update graph | finite gate、Loss Scaling | 高 | FP32 路径不使用 scaling |
| B1-06 | `core/enhancements/config.py` | 新模块 | Feature Flag schema 与默认值 | 低 | 不调用模块即完全回退 |
| B1-06 | `models/Model_SAEHD/Model.py` | options 初始化 | 读取兼容配置 | 低 | 缺失即全部 False |
| B1-07 | `tests/smoke/*` | unittest | 训练、optimizer、恢复测试 | 低 | 测试文件不影响运行时 |
| B1-08 | `tests/smoke/test_batch1_merge_masked.py` | unittest | dummy predictor Merge smoke | 低 | 测试文件不影响运行时 |
| B1-09 | `docs/*` / `.handoff/*` | 文档 | 更新状态与交接 | 低 | 历史 handoff 不删除 |

---

## 17. 推荐开发顺序

### Step 1：只做确定性修复

```text
B1-00 基线
→ B1-01 Eyes / Mouth mask
→ B1-02 异常处理
```

这三个任务不得与精度底层重构混在同一个提交。

### Step 2：建立可观测性

```text
B1-03 Precision Contract 报告
→ B1-07 optimizer roundtrip 基础测试
```

先输出事实，再决定低精度修改范围。

### Step 3：修复 optimizer 正确性

```text
B1-04 Lion v2
→ legacy state 保护
→ roundtrip 测试
```

### Step 4：收敛低精度策略

```text
B1-05 finite gate
→ FP16 scaling
→ BF16 scale=1
→ runtime state 保存恢复
```

如果风险过高，允许以“FP32 validated、FP16/BF16 experimental”作为 Batch 1 的安全出口，但必须记录未完成项。

### Step 5：接入安全配置骨架

```text
B1-06 Enhancement Config
→ 默认全关闭
→ 旧 options 回归
```

### Step 6：完成 smoke 与交接

```text
B1-07 Training smoke
→ B1-08 Merge smoke
→ B1-09 Compatibility matrix / handoff
```

---

## 18. 推荐提交拆分

```text
chore(validation): add Batch 1 baseline and smoke harness

fix(training): wire real eyes and mouth masks into priority loss

fix(training): rethrow non-OOM training failures with context

feat(validation): add precision and optimizer dtype contract report

fix(optimizer): implement Lion beta2 momentum update

feat(compat): version Lion optimizer state and reset legacy slots safely

fix(training): gate optimizer updates on finite gradients

feat(training): persist dynamic loss scaling runtime state

feat(config): add backward-compatible enhancement feature flags

test(training): add Batch 1 save-resume and optimizer roundtrip smoke

test(merge): add legacy MergeMasked smoke coverage

docs(handoff): record Batch 1 implementation and remaining risks
```

---

## 19. Batch 1 完成标准

### 19.1 必须全部满足

- [ ] 当前 `main` 分支可启动。
- [ ] FP32 SAEHD 可初始化并完成最小训练 step。
- [ ] Eyes / Mouth Priority 开启时使用真实 mask。
- [ ] Priority 关闭时仍使用原三输出数据路径。
- [ ] 非 OOM 异常不再静默吞掉。
- [ ] Lion 标准公式通过手工数值测试。
- [ ] legacy Lion state 不会静默按新公式恢复。
- [ ] AdaBelief、Lion v2、RMSprop 至少通过小图 roundtrip。
- [ ] precision contract 能报告 weight、gradient、slot 与恢复 dtype。
- [ ] 非 finite gradient 不会执行 optimizer update。
- [ ] 动态 Loss Scale 状态可保存恢复，或低精度明确保持 experimental。
- [ ] Enhancement Config 缺失时全部增强关闭。
- [ ] 旧模型无新字段时可加载。
- [ ] 默认 Merge smoke 可运行。
- [ ] 所有增强关闭时通过兼容回归。
- [ ] smoke test 命令和 fixture 说明已写入仓库。
- [ ] 文档索引、状态矩阵和 handoff 已同步。

### 19.2 不作为完成条件

- 不要求视觉效果优于 baseline。
- 不要求 BF16 吞吐提升。
- 不要求多 GPU 性能优化完成。
- 不要求 Shape-aware Merge 有任何视觉产出。

---

## 20. 阻断条件

出现以下任一情况，不得进入 Batch 2：

1. Eyes / Mouth mask 仍可能被全零替代且无错误。
2. 保存恢复后 optimizer 下一步更新与连续训练明显不一致。
3. 非 finite gradient 仍会更新参数。
4. 新配置缺失会导致旧模型加载失败。
5. 所有增强关闭时 Merge 路径发生未解释变化。
6. FP16 / BF16 被标记为 validated，但没有 dtype 与恢复证据。
7. legacy Lion state 被新公式静默加载。
8. smoke test 只能依赖开发者手工点击，无法重复执行。

---

## 21. 风险与回退

### 21.1 Eyes / Mouth 修复导致 loss 上升

这是预期可能性，因为原 priority loss 实际没有生效。

处理：

- 不把 loss 上升直接判断为回归；
- 观察 total loss、单项 priority loss 与 preview；
- 允许用户关闭已有 `eyes_mouth_prio`；
- 不降低权重来掩盖传递错误。

### 21.2 Lion 修复导致训练轨迹变化

这是正确性修复的必然结果。

处理：

- legacy state 不迁移；
- 主权重保留；
- optimizer state 重置；
- 日志明确说明；
- 旧代码和旧 state 文件可用于回退复现。

### 21.3 FP32 master weight 改造显存增加

如果在 Batch 1 实施：

- 必须记录显存差异；
- 不得让旧低显存配置无提示 OOM；
- 可将 FP32 master weight 作为独立 experimental flag；
- 若无法安全完成，保持 FP32 validated、低精度 experimental。

### 21.4 新 runtime_state 影响旧 data.dat

处理：

- 所有新 key 使用 `.get(..., default)`；
- 默认 getter 返回空 dict；
- 不改变旧字段名称；
- 不在读取旧模型时强制覆盖原文件。

### 21.5 Smoke fixture 不可公开

处理：

- 仓库只提交 manifest 示例和生成说明；
- 实际人脸素材保留在本地工作区；
- 单元测试使用 synthetic array 和 dummy predictor。

---

## 22. 下一批次入口

只有 Batch 1 完成后，Batch 2 才开始：

```text
Dataset Metadata
+
Quality / Pose / Shape-aware Sampling
+
metadata 缺失回退
```

Batch 2 不应再次修改 Batch 1 已冻结的：

- 样本主输出顺序；
- Feature Flag 默认语义；
- optimizer state metadata 基础结构；
- runtime state 保存入口；
- smoke test 基线格式。

如 Batch 2 需要扩展这些接口，必须保持 schema version 和向后兼容。

---

## 23. 新会话启动顺序

后续 Agent 开始 Batch 1 代码开发时，按以下顺序阅读：

```text
.handoff/current.md
.handoff/handoff-20260726-initial-project-state.md
docs/implementation/enhanced-dfl-master-implementation-plan.md
docs/development/batch1-correctness-and-extension-foundation-tasks.md
docs/optimization/training-correctness-audit.md
models/Model_SAEHD/Model.py
core/leras/optimizers/Lion.py
models/ModelBase.py
merger/MergeMasked.py
```

第一份代码提交只处理：

```text
Eyes / Mouth Priority 真实 mask
+
对应最小单元测试
```

不得在同一提交中顺便加入新的 Loss、Sampling 或 Shape-aware Merge。
