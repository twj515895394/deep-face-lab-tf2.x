# B3-14 Loss Window、保存退出恢复、Master Matrix 与 Windows GPU A/B

## 1. 基本信息

- Ticket ID：`B3-14`
- 状态：`BLOCKED-BY-B3-13`
- 优先级：P0
- 前置 Ticket：B3-13
- 阻塞 Ticket：B3-15
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

Batch 2 已建立 TrainerSaveController、session-local LossWindow、非有限梯度 gate、manual save/exit/resume 和资源清理规则。Batch 3 增加 loss 通道、src generator payload 和图 op 后，必须证明这些控制流没有回归。

自动测试通过不等于真实 Windows GPU 与视觉 A/B 通过；所有环境项目必须保留真实状态。

## 3. Scope

### In Scope

- 扩展 Master Test Matrix。
- 回归 first iter、scheduled/manual save、exit、target iter、resume、save failure。
- 回归 loss window channel labels/维度。
- 回归 worker/session/GPU资源清理。
- 定义 Short GPU Smoke 与 Long Visual A/B规约。
- 定义 shape retention、pose/expression、性能指标。

### Out of Scope

- 不以主观单帧宣布效果完成。
- 不自动选择默认 Geometry权重。
- 不修改 TrainerSaveController事务语义。
- 不把未执行 GPU测试写成 PASS。

### Forbidden Changes

- 禁止为通过测试降低异常传播等级。
- 禁止 save失败后清空 Loss Window。
- 禁止 non-finite step 写入正常 loss history。
- 禁止只验证正脸单图。
- 禁止复用 Batch 2 的 GPU豁免作为 Batch 3 PASS。

## 4. 代码锚点

- `mainscripts/Trainer.py::trainerThread`
- `mainscripts/trainer_save_control.py::TrainerSaveController`
- `samplelib/sampling/loss_stats.py::LossWindowTracker`
- `models/ModelBase.py::train_one_iter/save/finalize`
- `models/Model_SAEHD/Model.py::onTrainOneIter/onSave`
- B3-13 integration tests

## 5. Automated Gate

必须覆盖：

1. Geometry disabled 完整 Batch 1/2 smoke。
2. Geometry requested但 Anchor缺失 fallback。
3. ratio only、contour only、both。
4. eyes/mouth on/off。
5. random warp on/off。
6. df/liae 至少 fake graph或可用 CPU graph组合。
7. fp32；fp16/bf16 纯契约测试。
8. manual save、scheduled save、exit save、target iter save。
9. save failure后窗口保留并在下一次成功提交。
10. resume后 Curriculum multiplier一致。
11. non-finite geometry loss/gradient不污染参数。
12. spawn worker clean exit与进程差集。
13. ordinary/packed、Unicode/中文/空格路径。

统一命令：

```bash
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

结果记录必须包括 OS、Python、start method、测试数、EXIT code、Commit SHA。

## 6. Short Windows GPU Smoke Gate

最小矩阵：

```text
SAEHD df + fp32 + Geometry disabled 50 iter
SAEHD df + fp32 + ratio 100 iter
SAEHD df + fp32 + ratio+contour 100 iter
SAEHD liae + fp32 + ratio+contour 100 iter
manual save -> exit -> resume 50 iter
```

每项记录：

- GPU/driver/CUDA/TF。
- model options/config hash/Anchor fingerprint。
- iter time、VRAM峰值、loss channels。
- non-finite/skip count。
- save/exit/resume结果。
- 训练结束线程/进程/GPU资源差集。

未执行写 `NOT EXECUTED`；失败保留日志和复现条件。

## 7. Long Visual A/B Gate

固定同一：

- src/dst faceset；
- 初始 checkpoint；
- sampling seed；
- batch/architecture/precision；
- iteration预算；
- merge 参数（先用传统 Merge，避免 Batch 5变量）；
- preview帧和视频片段。

实验：

```text
A: Geometry disabled
B: ratio only
C: ratio + contour
```

指标：

- Anchor ratio error变化。
- predicted src mask soft ratio error。
- Shape Retention：脸宽、颧、jaw、chin。
- Pose/Expression preservation：眼嘴动作与yaw/pitch样本人工评分。
- Reconstruction src/dst loss变化。
- artifact、mask异常、收敛稳定性。
- iter time、VRAM。

完成不能只看训练 mask；必须同时说明传统 Merge可能重新裁回 dst轮廓，Batch 4–6仍是最终视频闭环前置。

## 8. Pass/Fail 规则

### Code Gate PASS

- 全自动测试通过。
- disabled基线、checkpoint、optimizer、control flow无回归。
- 文档/Review/SHA完整。

### Short GPU PASS

- 所有规定短矩阵执行成功，save/resume与资源清理通过。

### Visual A/B Result

使用 `PROMISING / NEUTRAL / REGRESSION / INCONCLUSIVE`，不得仅写 PASS。必须附数据和样本说明。

Batch 3 是否允许在 Long A/B未完成时推进 Batch 4，由维护者明确决定；文档不能自行假设。

## 9. 实施步骤

1. 更新 `reports/master-test-matrix.md` 为逐场景表。
2. 更新 `reports/windows-gpu-geometry-acceptance.md`。
3. 扩展 LossWindow labels和control tests。
4. 扩展 save controller fake model tests。
5. 添加 process/thread/resource snapshot helper。
6. 建立 A/B report模板和输入清单。
7. 执行可用自动测试；环境不可用项明确 deferred。
8. 独立 Review测试证据。

## 10. 完成定义

- 自动、控制流、兼容、GPU、视觉矩阵彼此分层。
- save failure/window/resume语义有测试。
- disabled基线完整回归。
- 未执行环境项未伪写。
- A/B指标和输入可复现。
- Summary、Review、SHA齐全。

## 11. Review 检查表

- 是否把自动测试等同 GPU？
- 是否把短跑等同长期效果？
- 是否改变 save controller语义？
- 是否 loss通道维度不一致？
- 是否遗漏 resource cleanup？
- 是否忽略传统 Merge 对最终轮廓的影响？

## 12. 交付物

- 完整 Master Test Matrix
- Windows GPU Geometry A/B规约/报告模板
- control-flow/resource tests
- Summary、Review、Commit SHA
