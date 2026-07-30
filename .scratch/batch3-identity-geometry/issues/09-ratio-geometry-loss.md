# B3-09 可微 Soft-mask Ratio Geometry Loss MVP

## 1. 基本信息

- Ticket ID：`B3-09`
- 状态：`BLOCKED-BY-B3-03-B3-05-B3-08`
- 优先级：P0
- 前置 Ticket：B3-03、B3-05、B3-08
- 阻塞 Ticket：B3-11、B3-12、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

直接从预测图像得到可微 68 点 landmark 在当前架构中不可行。现有模型已经输出可微 `gpu_pred_src_srcm`，因此 Ratio MVP 必须只约束该 mask 能可靠表达的稳定外轮廓比例。

Batch 3 可训练比例固定为：

```text
face_width_over_height
cheek_width_over_face_width
jaw_width_over_face_width
chin_length_over_face_height
```

以下 Anchor 比例保留用于报告和 Batch 4/5，但 Batch 3 不从 mask 伪造对应预测：

```text
eye_distance_over_face_width
nose_width_over_face_width
```

## 3. Scope

### In Scope

- 从预测 src-src mask 构建可微 soft geometry observables。
- 与 B3-08 提供的 target ratio/validity 比较。
- 实现 per-feature raw、per-sample weighted addition。
- 支持 NHWC/NCHW、fp32/fp16/bf16 图输入。
- 明确 frontal/validity gate。

### Out of Scope

- 不对 `gpu_pred_src_dst` 施加 Ratio Loss。
- 不训练眼距、鼻宽。
- 不新增模型 head。
- 不改 predicted mask 网络结构。
- 不自动调权。

### Forbidden Changes

- 禁止硬 threshold 后使用不可导 argwhere/bounding box。
- 禁止从 NumPy 计算预测 mask ratio。
- 禁止对侧脸样本强制 frontal anchor ratio。
- 禁止标量 loss 隐式广播到 batch。
- 禁止把 target validity 乘在含 NaN 的张量上。
- 禁止加入 dst_loss。

## 4. 当前代码锚点

- `models/Model_SAEHD/Model.py` 的 `gpu_pred_src_srcm`
- `gpu_src_loss` per-sample tensor
- `core/enhancements/losses` contracts/registry
- B3-08 geometry ratio target 和 validity
- `core/leras/nn`/TensorFlow math ops

## 5. 目标模块

```text
core/enhancements/geometry/
├── observables.py
└── losses.py
```

公开纯图函数：

```python
def build_soft_mask_ratios(pred_mask, *, data_format, epsilon=1e-6):
    # -> values [N,4], validity [N,4]
```

```python
def build_ratio_geometry_loss(predicted, target, validity, weight, delta):
    # -> LossHookResult
```

## 6. Soft Observable 定义

统一把 mask 显式转为 float32 统计，保留梯度；最终 addition 再 cast 到 `gpu_src_loss.dtype`。

### 6.1 Soft Mass 与坐标网格

```text
m = clip(pred_mask, 0, 1)
x_grid, y_grid ∈ [0,1]
mass = sum(m) + epsilon
```

### 6.2 Face Width / Height

使用二阶矩近似软宽高：

```text
center_x = sum(m*x)/mass
center_y = sum(m*y)/mass
sigma_x = sqrt(sum(m*(x-center_x)^2)/mass + epsilon)
sigma_y = sqrt(sum(m*(y-center_y)^2)/mass + epsilon)
face_width_over_height = sigma_x / (sigma_y + epsilon)
```

### 6.3 Cheek/Jaw Width Profile

使用固定 normalized y band 对 mask 横向 mass 做加权平均，不使用 hard row selection。band window 由平滑三角/高斯权重实现：

```text
cheek band center≈0.58
jaw band center≈0.72
```

精确 center/width 在 fixtures 上冻结，不允许编码 Agent凭感觉改变。

### 6.4 Chin Length

以 soft vertical mass 的下部 quantile proxy/连续权重计算，不使用不可导 `max index`。第一版可采用 lower-band center 相对 face center 的归一化距离；公式与目标生成必须使用同一个 observable 实现。

关键原则：target 不是直接使用 raw landmark ratio 与 mask proxy 比较，而是先由 B3-08 将 Anchor/target contour rasterize 成 target mask，再通过同一个 `build_soft_mask_ratios()` 生成目标值。这样预测和目标定义同构。

## 7. Loss 公式

固定使用 Smooth L1/Huber：

```text
error = predicted - target
per_feature = huber(error, delta=0.05)
valid_weight = validity * feature_weight
per_sample_raw = sum(per_feature * valid_weight) / max(sum(valid_weight), 1)
per_sample_weighted = per_sample_raw * runtime_weight * curriculum_multiplier
```

- 无有效 feature 的样本 raw/weighted 均为 0。
- `active_fraction` 单独输出。
- feature weights 第一版固定常量并文档化，不新增配置旋钮。
- `runtime_weight` 来自 `geometry.ratio_weight`。
- curriculum multiplier 来自 B3-12，范围 `[0,1]`。

## 8. DType/Shape

```text
pred_mask: [N,H,W,1] 或 [N,1,H,W]
target ratios: [N,6]，本票使用冻结的 4 项索引
target validity: [N,6]
output addition: [N]
metrics: scalar means + active count
statistics dtype: float32
```

输入 mask 的 channel 不为 1、batch 不一致、target R 不为 6必须抛 `GeometryContractError`。

## 9. 实施步骤

1. 在 `observables.py` 实现 layout normalize 和 soft ratio 纯图函数。
2. 用 NumPy reference 实现同公式，供测试对照；生产训练不得调用 NumPy reference。
3. 在 `losses.py` 实现 `RatioGeometryLossHook`。
4. 注册名固定为 `identity_geometry_ratio`。
5. 返回 raw/weighted 四项 feature mean、total、active_fraction。
6. 加入 finite assertions 和 per-sample shape validator。
7. 不接 SAEHD；B3-13 完成图接入。

## 10. 测试要求

测试文件：`tests/smoke/test_batch3_ratio_geometry_loss.py`

必须覆盖：

- 人工椭圆 mask 的宽高变化单调性。
- cheek/jaw band 局部扩张只影响对应指标。
- chin 延长指标单调性。
- target 与 prediction 相同，loss=0。
- feature validity 部分/全 0。
- frontal valid、侧脸 ratio validity=0。
- NHWC/NCHW 等价。
- float16/bfloat16 输入，float32 统计。
- 错误 channel/batch/R。
- finite gradient：对 mask 做 tf gradient，梯度非 None 且有限。
- `weight=0` addition 全 0。
- 不创建 eye/nose 可训练 metric。
- NumPy reference 与 TF 结果容差一致。

命令：

```bash
python -m unittest tests.smoke.test_batch3_ratio_geometry_loss -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- 所有 trainable ratio 都有真实可微 prediction observable。
- target 与 prediction 使用同构 observable。
- 眼距/鼻宽未被错误训练。
- per-sample addition、validity、dtype 有测试。
- 未接 DST 和 optimizer 独立路径。
- Summary、Review、SHA 齐全。

## 12. Review 检查表

- 是否用了 argwhere/硬 bounding box？
- 是否用 raw landmark ratio 与 mask proxy 直接比较？
- 是否对侧脸满权重？
- 是否生成了伪 eye/nose prediction？
- 是否先 batch mean 再加 per-sample loss？
- 是否在 NumPy 路径中断梯度？

## 13. 交付物

- `core/enhancements/geometry/observables.py`
- `RatioGeometryLossHook`
- NumPy reference
- `tests/smoke/test_batch3_ratio_geometry_loss.py`
- Summary、Review、Commit SHA
