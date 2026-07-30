# Windows GPU Geometry A/B 验收规约

> 初始状态：`NOT EXECUTED`

## 矩阵

1. Baseline：全部 Batch3 flag off。
2. Ratio only。
3. Landmark only。
4. Ratio + Landmark + Curriculum。

每组至少覆盖 ordinary faceset；packed faceset 若环境可用再执行并独立记录。每组记录配置 JSON、GPU/驱动/CUDA/TF、模型架构、分辨率、batch、checkpoint 来源和素材 fingerprint。

## Short GPU Smoke

- 启动并完成至少 50 iter。
- loss 与单项 geometry loss 有限。
- manual save、exit、resume 后继续至少 20 iter。
- requested/effective/reason 与实际配置一致。
- 无 worker/thread/process 明显泄漏。

## Long / Visual A-B

- 固定 seed、素材、模型配置和 preview set。
- baseline 与 geometry 组使用可比训练预算。
- 检查脸宽、下颌、下巴、颧骨稳定性；同时检查眼口表情、姿态响应和边缘伪影。
- 人工评价必须附截图或视频证据，不得只写“更好”。

## 状态规则

`PASS` 仅限真实执行且证据完整。未执行、环境不具备或维护者跳过时分别写 `NOT EXECUTED`、`BLOCKED-BY-ENV`、`DEFERRED-BY-MAINTAINER`，不得复用 Batch 2 的豁免结论。