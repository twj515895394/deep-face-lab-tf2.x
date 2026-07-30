# B3-11 SRC/DST 非对称职责与 Geometry/Expression 隔离

## 1. 基本信息

- Ticket ID：`B3-11`
- 状态：`BLOCKED-BY-B3-09-B3-10`
- 优先级：P0
- 前置 Ticket：B3-09、B3-10
- 阻塞 Ticket：B3-12、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

目标关系是 `src stable identity geometry + dst pose/expression/motion`。若 Geometry Loss 被错误加到 DST reconstruction、src-dst prediction，或要求 src/dst 样本逐帧配对，会静态化表情并破坏现有 SAEHD 语义。

本 Ticket 冻结职责边界和测试护栏，不新增第三类 Loss。

## 3. Scope

### In Scope

- 冻结 Geometry 只作用 `src -> src` reconstruction 的 predicted src mask。
- 冻结 DST generator 不增加 Geometry supervision 输出。
- 冻结 `gpu_dst_loss` 和 `gpu_pred_src_dst` 在 Batch 3 不接受 Geometry addition。
- 定义 stable/dynamic landmark 区域表。
- 建立图结构/数值回归，证明 dst 路径未改变。

### Out of Scope

- 不实现 Hybrid Landmark。
- 不在训练中建立 src/dst 样本配对。
- 不改变随机 warp、pose sampling 或 expression transfer。
- 不修改 Merge。

### Forbidden Changes

- 禁止 Geometry addition 加到 `gpu_dst_loss`。
- 禁止 Geometry addition 加到 `gpu_pred_src_dst` 相关 loss。
- 禁止把 dst landmark 与 src Anchor 完整 68 点直接比较。
- 禁止使用同一 batch index 假设 src/dst 是同一姿态或表情。
- 禁止约束 eyes、mouth、brows 接近 src Anchor。

## 4. 当前代码锚点

- `gpu_pred_src_src`、`gpu_pred_src_srcm`
- `gpu_pred_dst_dst`、`gpu_pred_dst_dstm`
- `gpu_pred_src_dst`、`gpu_pred_src_dstm`
- `gpu_src_loss`、`gpu_dst_loss`、`gpu_G_loss`
- `_base_src_types`、`_base_dst_types`
- `SampleGeneratorFace` src/dst 独立实例

## 5. 冻结职责表

| 属性 | 来源 | Batch 3 训练处理 |
|---|---|---|
| 脸宽、颧部、下颌、下巴 | SRC Anchor | 对 src-src predicted mask 施加 ratio/contour loss |
| SRC 五官纹理 | SRC 图像 | 仍由 reconstruction 等现有 Loss 学习 |
| yaw/pitch/roll | DST | 不由 Batch 3 Geometry 约束 |
| 眼睛开合、嘴型、眉毛 | DST/当前样本 | 不进入 stable contour region |
| 视频运动/遮挡 | DST/Merge | Batch 3 不处理 |

## 6. 图接入硬约束

每 GPU：

```text
base gpu_src_loss
+ ratio addition on gpu_pred_src_srcm
+ contour addition on gpu_pred_src_srcm
= enhanced gpu_src_loss

gpu_dst_loss = exact existing formula
```

随后才构建：

```text
gpu_G_loss = enhanced gpu_src_loss + unchanged gpu_dst_loss
```

不得在 `gpu_pred_src_dst_no_code_grad`、style loss、GAN loss 或 true-face discriminator 中插入 Geometry。

## 7. Generator/Feed 约束

- Geometry effective 时只扩展 src generator 输出。
- dst generator 输出数量和顺序保持 3/4 项基线。
- `_unpack_training_samples` 必须按 domain 分支验证，不能让 dst 可选地吞下多余输出。
- src/dst 仍由各自 sampling policy 独立抽样。

## 8. 实施步骤

1. 新建 `core/enhancements/geometry/regions.py`，冻结 stable/dynamic region constants。
2. 添加 pure validator，确保 ratio/contour Hook 仅接受 `domain='src'`。
3. 添加 fake graph integration helper 测试，验证 addition 只进入 src。
4. 为 `_base_dst_types` 建立结构快照。
5. 为 disabled/enabled 两种情况下的 dst feed keys 和 dst loss ops 建立回归。
6. 记录不配对原则到用户/开发者文档。

## 9. 测试要求

测试文件：`tests/smoke/test_batch3_src_dst_isolation.py`

必须覆盖：

- Hook context `domain='dst'` 立即拒绝。
- Geometry enabled 前后 dst generator output specs 完全相同。
- 相同 fake dst tensors 下 `gpu_dst_loss` 数值相同。
- Geometry target 改变只影响 src addition。
- eyes/mouth target 区变化不影响 stable contour loss。
- src/dst batch 顺序打乱不改变 Geometry 结果。
- 不存在 src/dst landmark pairing API。
- disabled 图无 Geometry op 名称。

命令：

```bash
python -m unittest tests.smoke.test_batch3_src_dst_isolation -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 10. 完成定义

- SRC/DST 职责通过代码常量和测试冻结。
- DST generator/loss/prediction 路径未被 Geometry 修改。
- 无 src/dst 配对假设。
- 动态表情区域不进入 stable supervision。
- Summary、Review、SHA 齐全。

## 11. Review 检查表

- 是否触碰 `gpu_dst_loss`？
- 是否触碰 `gpu_pred_src_dst`？
- 是否扩展了 dst output specs？
- 是否隐含 batch-index 配对？
- 是否把动态 landmark 加入 stable region？
- 是否混入 Merge 或 Temporal？

## 12. 交付物

- stable/dynamic region constants
- `tests/smoke/test_batch3_src_dst_isolation.py`
- 职责说明
- Summary、Review、Commit SHA
