# B3-13 SAEHD 主训练链路接入、旧 Checkpoint 与 Optimizer 兼容

## 1. 基本信息

- Ticket ID：`B3-13`
- 状态：`BLOCKED-BY-B3-02-TO-B3-12`
- 优先级：P0
- 前置 Ticket：B3-02～B3-12
- 阻塞 Ticket：B3-14、B3-15
- 目标分支：`codex/batch2-ticket19-loss-window`
- 建议提交粒度：先 generator/feed，再 graph，再 return/log；每一步独立测试和 Review

## 2. 背景与问题

本 Ticket 是 Batch 3 唯一允许修改 SAEHD 主训练图的 Ticket。此前所有模块必须已经稳定，执行 Agent 不得在此重新设计 Schema、公式或 fallback。

当前图结构：

```text
SampleGeneratorFace
 -> placeholders
 -> per-GPU forward
 -> gpu_src_loss / gpu_dst_loss
 -> gpu_G_loss
 -> gradients finite gate
 -> unified_train
 -> onTrainOneIter
 -> ModelBase.loss_history
```

Geometry 必须以最小侵入方式只加入 src loss，关闭时保持图、feed、fetch、权重文件和 optimizer slot 基线等价。

## 3. Scope

### In Scope

- 在 startup 解析 Anchor/runtime state。
- effective 时仅扩展 src generator outputs。
- effective 时创建固定 Geometry placeholders。
- 在每 GPU src loss 完成后调用 ratio/contour hooks。
- 扩展 `_unified_ops`、`unified_train` 和 `onTrainOneIter` 的可选 metrics。
- 旧 options/checkpoint/optimizer 加载兼容。
- disabled 图零影响证据。

### Out of Scope

- 不实现新公式或 Schema。
- 不修改网络层和 trainable weights。
- 不修改 DFM 导出/merge predictor outputs。
- 不新增 optimizer。
- 不修改 Merge。
- 不增加 GUI 交互询问。

### Forbidden Changes

- 禁止在本票临时修改 B3-02～12 契约。
- 禁止把 Geometry 写入 `model_filename_list`。
- 禁止创建新的 trainable variable。
- 禁止 Geometry addition 加到 dst、GAN、true-face 或 style loss。
- 禁止 disabled 时追加 generator output、placeholder、fetch 或 loss channel。
- 禁止吞核心训练异常。

## 4. 精确代码锚点

- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize_options`
- `SAEHDModel.on_initialize`
- placeholder 创建块：`warped_src/target_src/target_srcm/...`
- `_base_src_types` / `_base_dst_types`
- per-GPU slice 块
- `gpu_pred_src_srcm`
- `gpu_src_loss` 完成位置、`gpu_G_loss` 创建前
- `_unified_ops`、`unified_train`
- `_unpack_training_samples`
- `_unpack_unified_train_result`
- `SAEHDModel.onTrainOneIter`
- `SAEHDModel.get_model_filename_list/onSave/export_dfm/predictor_func`

## 5. Startup 顺序

1. `on_initialize_options` 只规范化配置，不访问 faceset/Anchor 文件。
2. `on_initialize` 在模型图创建前解析 Geometry config state。
3. 若 requested：加载 Anchor，构造 compact supervision spec，解析 curriculum state。
4. 若 optional failure 可 fallback：冻结 runtime effective=false，并走完整基线图。
5. 若 effective=true：冻结本会话 config hash、Anchor snapshot 和 loss channel definition。
6. startup 后禁止热切换 effective。

## 6. Generator 输出顺序

Baseline src：

```text
warped_src, target_src, target_srcm[, target_srcm_em]
```

Geometry effective src：

```text
warped_src, target_src, target_srcm[, target_srcm_em],
geometry_target_map, geometry_ratio_target, geometry_validity
```

DST 始终保持 baseline 顺序。

新增 helper：

```python
def _unpack_training_samples(samples, has_eyes_mouth, domain, has_geometry=False):
    # 返回命名 tuple/dataclass，严格验证数量和 shape
```

禁止调用方按魔法下标自行猜测。

## 7. Placeholder 契约

只在 effective 时创建：

```text
target_src_geometry_map: image-like 2 channel, current data_format
target_src_geometry_ratio: [batch,12]  # 6 values + 6 validity
target_src_geometry_validity: [batch,3]
```

- dtype 使用 `nn.floatx` feed compatibility；Hook 内统计 cast float32。
- 不创建 DST geometry placeholder。
- 多 GPU 使用与其他 placeholder 相同 CPU slice。

## 8. Loss 插入点

在每 GPU：

```python
# existing reconstruction + eyes/mouth + mask + style additions complete
gpu_src_loss = existing_src_loss

if geometry_effective:
    ratio_result = ratio_hook.build(...)
    contour_result = contour_hook.build(...)
    gpu_src_loss += cast_loss_to_target(
        ratio_result.per_sample_addition + contour_result.per_sample_addition,
        gpu_src_loss.dtype,
    )

# existing dst loss remains unchanged
gpu_G_loss = cast(src) + cast(dst)
```

- Hook 使用 `gpu_pred_src_srcm`。
- target map/ratio/validity 使用当前 device slice。
- Geometry metrics 追加到 per-GPU lists，最后按 batch/device 正确聚合。
- addition 加入后再生成 gradients，因此梯度由现有 finite gate统一管理。

## 9. Unified Train 与日志

Geometry disabled：

```text
_unified_ops length=4
unified_train return length=4
onTrainOneIter return src_loss,dst_loss
```

Geometry enabled：

```text
_unified_ops length=5（第5项固定 ordered metrics）
unified_train return length=5
onTrainOneIter return固定已审核 loss channels
```

feed helper 必须：

- baseline 不引用不存在 placeholder；
- effective 时严格要求三项 Geometry outputs；
- 非有限/shape 错误在 session run 前失败；
- eyes/mouth 与 Geometry 组合覆盖四种输出布局。

## 10. Checkpoint/Optimizer 兼容

- `model_filename_list` 完全不增加 Geometry 文件。
- `src_dst_saveable_weights/trainable_weights` 完全不改变。
- `src_dst_opt.initialize_variables()` 输入列表完全不改变。
- 旧 `data.dat` 无 geometry fields 时默认关闭。
- 新 options 在 Geometry 关闭后仍能加载和训练。
- 新模型权重可被旧 Merge 使用，因为 predictor/export outputs 不改变。
- 不承诺旧代码读取含新 nested options，但当前代码必须 roundtrip。

## 11. 实施步骤

1. 先添加 startup runtime resolver 和测试，保持 effective=false。
2. 条件扩展 src output specs和 unpack/feed tests。
3. 条件创建 placeholders和 per-GPU slices。
4. 接入 ratio hook并测试。
5. 接入 contour hook并测试。
6. 聚合 ordered metrics，扩展 unified result。
7. 扩展 onTrainOneIter 返回和 logging。
8. 运行 checkpoint/optimizer filename/weight-list 快照测试。
9. 验证 export_dfm、predictor_func、AE_merge 不变。
10. 完成独立 Review，禁止一次大提交掩盖差异。

## 12. 测试要求

测试文件：

- `tests/smoke/test_batch3_saehd_geometry_integration.py`
- `tests/smoke/test_batch3_checkpoint_optimizer_compat.py`
- `tests/smoke/test_batch3_disabled_graph_equivalence.py`

必须覆盖：

- enabled/disabled × eyes_mouth on/off。
- src output数量、dst output不变。
- placeholder/fetch/feed keys。
- multi-GPU slice shape。
- addition只进入 src。
- metric device aggregation。
- weight=0、gates off、anchor fallback 的图等价。
- `model_filename_list` 快照相同。
- trainable/saveable weight names相同。
- optimizer slot names/count相同。
- 旧 data.dat/options 加载。
- 新 options关闭后恢复。
- export/predictor outputs相同。
- non-finite geometry 使用现有 gradient/exception语义。

命令：

```bash
python -m unittest tests.smoke.test_batch3_saehd_geometry_integration -v
python -m unittest tests.smoke.test_batch3_checkpoint_optimizer_compat -v
python -m unittest tests.smoke.test_batch3_disabled_graph_equivalence -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 13. 完成定义

- Geometry 路径真实进入 SAEHD src loss和梯度。
- disabled/fallback 图与基线等价。
- DST、GAN、true-face、style、Merge、DFM未改。
- 权重和 optimizer 文件/slot不变。
- 旧 checkpoint可恢复。
- Summary、Review、SHA齐全。

## 14. Review 检查表

- 是否提前在 options阶段访问文件？
- 是否 disabled仍创建图？
- 是否修改 weight list/optimizer？
- 是否接错 prediction mask？
- 是否影响 dst/其他 loss？
- 是否按 magic index unpack？
- 是否改变 export/merge outputs？

## 15. 交付物

- `models/Model_SAEHD/Model.py` 最小接入
- 三个 smoke test文件
- 图/compat快照
- Summary、独立 Review、Commit SHA
