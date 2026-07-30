# B3-10 Landmark-derived Stable Contour / SDF Geometry Loss MVP

## 1. 基本信息

- Ticket ID：`B3-10`
- 状态：`BLOCKED-BY-B3-03-B3-05-B3-08`
- 优先级：P0
- 前置 Ticket：B3-03、B3-05、B3-08
- 阻塞 Ticket：B3-11、B3-12、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

当前 SAEHD 没有可微 landmark prediction head，因此本 Ticket 不实现“预测 68 点坐标减目标 68 点坐标”。Landmark 只负责在 Generator 侧生成稳定外轮廓监督；训练图中的可微 prediction 仍是 `gpu_pred_src_srcm`。

目标是让 src-src predicted mask 的 jaw、cheek、chin 外轮廓靠近 Shape Anchor 派生的稳定 contour，同时不约束 eyes、mouth、brows 等动态表情区域。

## 3. Scope

### In Scope

- 使用 B3-08 的 target SDF、stable-region weight 和 validity。
- 从 predicted src mask 构造可微 soft occupancy/boundary。
- 实现 per-sample contour loss、raw/weighted metrics、active fraction。
- 支持 NHWC/NCHW 和当前 precision。
- 明确低置信度、侧脸与无有效 contour 的行为。

### Out of Scope

- 不增加 landmark detector/head。
- 不在 `gpu_pred_src_dst`、DST reconstruction 或 Merge 上计算本 Loss。
- 不训练 eyes、mouth、brows。
- 不实现 Boundary Loss；Batch 7 的图像边界质量 Loss 与本几何 contour Loss 不同。
- 不实现 Shape-aware Mask；该能力属于 Batch 6。

### Forbidden Changes

- 禁止使用 OpenCV/NumPy 从预测 Tensor 提取 contour。
- 禁止 hard threshold + argwhere 作为训练 prediction。
- 禁止把完整 face hull 当作所有区域同权重。
- 禁止将 contour loss 加入 `gpu_dst_loss`。
- 禁止在无有效样本时产生 NaN 或除零。

## 4. 当前代码锚点

- `models/Model_SAEHD/Model.py`：`gpu_pred_src_srcm`、`gpu_src_loss`
- B3-08：`GEOMETRY_TARGET_MAP` 两通道输出
- B3-03：`LossHookContext` / `LossHookResult`
- B3-05：finite/contract error boundary
- `core/leras/nn` TensorFlow 操作

## 5. 冻结输入

```text
pred_mask: [N,H,W,1] 或 [N,1,H,W]
target_sdf: 与 pred_mask 同 spatial/layout，范围 [-1,1]
stable_region_weight: 同 shape，范围 [0,1]
contour_valid: [N]
weight: 非负 float
curriculum_multiplier: [0,1]
```

所有统计内部转 `float32`。validity=0 的样本承载张量仍必须有限。

## 6. MVP 公式

第一版冻结为“目标软占用 + 近轮廓加权 Huber”，不引入复杂 differentiable morphology：

```text
target_occupancy = sigmoid(-target_sdf / tau)
near_contour = exp(-abs(target_sdf) / contour_band)
region_weight = stable_region_weight * (base_region_weight + near_contour)
error = pred_mask - target_occupancy
per_pixel = huber(error, delta=0.1)
per_sample_raw = sum(per_pixel * region_weight) / max(sum(region_weight), epsilon)
per_sample_weighted = per_sample_raw * contour_weight * curriculum_multiplier * contour_valid
```

冻结常量：

```text
tau = 0.05
contour_band = 0.10
base_region_weight = 0.25
delta = 0.10
```

这些常量由测试固定，不增加用户配置旋钮。后续实验若要修改，必须新 Ticket 和 A/B 证据。

## 7. 语义边界

- target SDF 来源于 Anchor stable contour 经过当前样本的安全 pose/alignment 处理。
- 侧脸或 pose 超出 B3-08 安全范围时 `contour_valid=0`，本 Loss 不强行拉回正脸。
- eyes/mouth/brows 的 stable-region weight 必须为 0。
- predicted mask 允许表达当前表情内部结构；本 Loss 只作用外轮廓权重区。
- 该 Loss 改善训练 mask 的身份几何倾向，不保证最终视频轮廓；最终应用仍依赖 Batch 4–6。

## 8. 输出契约

Hook 注册名：

```text
identity_geometry_contour
```

`LossHookResult`：

- `per_sample_addition`: `[N]`
- raw metrics：`geometry_contour_raw`
- weighted metrics：`geometry_contour_weighted`
- `active_count` / `active_fraction`
- warnings 只返回稳定 code，不直接打印

## 9. 实施步骤

1. 在 `core/enhancements/geometry/losses.py` 实现 layout normalize。
2. 实现 `build_contour_geometry_loss()` 纯图函数。
3. 提供 NumPy reference，仅用于测试。
4. 实现 `ContourGeometryLossHook` 并显式注册。
5. 添加 shape/dtype/range/finite 校验。
6. 验证 addition 与当前 `gpu_src_loss` 每样本 shape 一致。
7. 暂不接 SAEHD；主图接入属于 B3-13。

## 10. 测试要求

测试文件：`tests/smoke/test_batch3_contour_geometry_loss.py`

必须覆盖：

- prediction=target occupancy 时 loss 接近 0。
- jaw/cheek/chin contour 位移使 loss 单调增加。
- eyes/mouth 区域变化不影响结果或影响低于固定容差。
- contour_valid=0 时 addition=0。
- region weight 全 0 时安全返回 0。
- NHWC/NCHW 等价。
- fp16/bf16 输入，float32 统计。
- target SDF 超范围、非有限、wrong channel/batch 必须失败。
- TensorFlow gradient 对 pred_mask 非 None 且有限。
- `weight=0` 与 Noop 等价。
- NumPy reference 与图结果在容差内一致。

命令：

```bash
python -m unittest tests.smoke.test_batch3_contour_geometry_loss -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- Landmark 仅生成监督，不被描述成可微 prediction。
- Loss 对 predicted src mask 有有限梯度。
- 动态表情区域不受强 contour 约束。
- per-sample、validity、dtype 和 zero-weight 有测试。
- 不修改 DST、Merge 或模型结构。
- Summary、Review、Commit SHA 齐全。

## 12. Review 检查表

- 是否误实现直接 landmark coordinate loss？
- 是否使用不可导 contour extraction？
- 是否约束 eyes/mouth？
- 是否把 Batch 7 Boundary Loss 混入？
- 是否在无 region 时除零？
- 是否错误接入 `gpu_pred_src_dst`？

## 13. 交付物

- `ContourGeometryLossHook`
- NumPy reference
- `tests/smoke/test_batch3_contour_geometry_loss.py`
- 公式与常量说明
- Summary、Review、Commit SHA
