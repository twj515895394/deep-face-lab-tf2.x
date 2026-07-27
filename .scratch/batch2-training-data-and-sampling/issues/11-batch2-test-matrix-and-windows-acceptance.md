# 11 — 建立 Batch 2 完整测试矩阵并完成 Windows FP32 验收

Status: open
Type: AFK + Windows GPU
Blocked by: `10-config-saehd-logging-and-fallback.md`

**构建内容：** 将 Schema、Analyzer、Loader、权重、WeightedIndexHost、Generator、配置和 SAEHD 组合成可重复验证矩阵；在 Windows 48GB Blackwell 环境使用 FP32 + AdaBelief 完成真实训练、保存恢复、普通/Packed、fallback 和性能记录。

## 目标

- 自动测试证明工程和概率逻辑正确。
- Windows GPU 证明真实训练链路可长期使用。
- 明确区分“功能正确”“采样分布符合设计”“最终视觉质量人工判断”。
- 不以 macOS 轻量测试代替 Windows 真实验收。

## Layer 1：纯函数

- [ ] identity / sample id / path normalization。
- [ ] signature / fingerprint add-modify-delete。
- [ ] Schema roundtrip / partial / unsupported / duplicate。
- [ ] pose boundary 和左右符号。
- [ ] quality percentile、degenerate 分布、finite。
- [ ] config parse、clip、roundtrip。
- [ ] pose / quality / combined weights。
- [ ] probability normalize、uniform mix。
- [ ] resolver requested/effective/fallback。

## Layer 2：Analyzer / Store

- [ ] synthetic 清晰/模糊/曝光/坏文件。
- [ ] invalid landmarks。
- [ ] ordinary / packed 指标一致。
- [ ] full analyze。
- [ ] incremental all reuse。
- [ ] add/modify/delete。
- [ ] atomic write failure 保留旧文件。
- [ ] report issue counts 与 sample list。
- [ ] workers=1 和多 worker。

## Layer 3：Loader

- [ ] full match。
- [ ] missing / invalid / unsupported。
- [ ] partial 95% / 50%。
- [ ] collision / extra records。
- [ ] ordinary / packed / person faceset。
- [ ] runtime compact arrays dtype、shape、内存。

## Layer 4：Host / 分布

- [ ] fixed seed deterministic。
- [ ] 不同 seed。
- [ ] 多 CLI 并发。
- [ ] N=1、N<batch、N>>batch。
- [ ] batch duplicate retry。
- [ ] invalid probabilities。
- [ ] 长时间 draw 无死锁。
- [ ] pose imbalance simulation。
- [ ] quality + pose conflict。
- [ ] 每样本非零覆盖。

## Layer 5：Generator

- [ ] debug 单线程。
- [ ] generators_count=1。
- [ ] generators_count>1。
- [ ] ordinary / packed。
- [ ] src/dst 不同 policy。
- [ ] eyes_mouth False/True。
- [ ] random_ct。
- [ ] output count/shape/dtype 与 baseline。
- [ ] worker error propagation 和正常退出。

## Windows GPU 固定基线

```text
GPU: RTX PRO 5000 Blackwell 48GB
precision: fp32
optimizer: adabelief
GAN: off
TrueFace: off
style loss: off for first acceptance
small/known resolution and batch
fixed src/dst test workspace
```

实际硬件、驱动、CUDA、TensorFlow、容器/宿主版本必须记录，不允许只写“Windows 已通过”。

## Windows 场景

### W1 Legacy Random

- [ ] 功能关闭。
- [ ] 启动、训练、保存、退出、恢复。
- [ ] 记录 loss、iter time、GPU/CPU 内存。

### W2 Legacy Uniform Yaw

- [ ] 现有 uniform_yaw 行为可用。
- [ ] 输出 contract 与 W1 相同。

### W3 Pose Balanced

- [ ] src/dst Metadata 完整。
- [ ] effective mode 正确。
- [ ] 实际侧脸抽样比例高于原始分布且受限。
- [ ] loss finite、训练稳定。

### W4 Quality + Pose

- [ ] quality/pose 权重和日志正确。
- [ ] 低质量样本仍有抽样记录。
- [ ] uniform exploration 可观察。
- [ ] 训练稳定。

### W5 单侧 Metadata 缺失

- [ ] src 智能、dst fallback 或反向。
- [ ] 两侧日志分开。
- [ ] 训练继续。

### W6 损坏与不匹配

- [ ] invalid JSON。
- [ ] unsupported schema。
- [ ] fingerprint mismatch。
- [ ] partial match above/below threshold。
- [ ] effective fallback 正确。

### W7 Packed Faceset

- [ ] Analyzer 无需解包。
- [ ] Loader 正确匹配。
- [ ] 多进程训练、保存恢复。

### W8 Save / Exit / Resume

- [ ] 智能模式训练若干 iter。
- [ ] 保存并完全退出进程。
- [ ] 重新加载模型和 Metadata。
- [ ] model/optimizer iter 连续。
- [ ] sampling requested/effective 一致。
- [ ] Metadata 丢失时可 legacy 恢复。

### W9 Performance

记录：

- [ ] Analyzer samples/sec 和峰值 RSS。
- [ ] Metadata load/build time。
- [ ] Generator samples/sec。
- [ ] legacy 与 weighted 稳定 iter time。
- [ ] CPU 使用率、内存和 GPU 显存。
- [ ] 启动额外耗时。

不预先拍脑袋写死阈值；先跑 baseline，再在 summary 中固化合理门槛。

## 人工数据检查

- [ ] 随机抽查 pose 标签。
- [ ] 抽查低/中/高 quality 样本。
- [ ] 检查稀缺侧脸是否被适度提升。
- [ ] 检查低质量样本未完全消失。
- [ ] 检查报告是否足够指导人工清理 faceset。

## 阻断条件

- [ ] 任一模式导致训练卡死或 worker 无法退出。
- [ ] 关闭功能与 legacy contract 不一致。
- [ ] Metadata 错配到错误样本。
- [ ] src/dst 权重串用。
- [ ] 权重产生零概率、NaN 或 Inf。
- [ ] fallback 吞掉训练核心异常。
- [ ] save/resume 受影响。
- [ ] Packed 必须解包才能训练。
- [ ] 仅完成自动测试却宣称 Windows GPU 完成。

## 验收标准

- [ ] 所有适用自动测试通过。
- [ ] 所有 Windows W1-W9 有结果或明确阻断记录。
- [ ] FP32 + AdaBelief 主线稳定。
- [ ] legacy 开关关闭行为不变。
- [ ] new mode 真实改变采样分布。
- [ ] 保存恢复和 fallback 可长期使用。
- [ ] 性能回退有数据和结论。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/11-batch2-test-matrix-and-windows-acceptance-summary.md`。
- [ ] 单独生成/更新 `reports/windows-gpu-acceptance.md`，包含命令、环境、日志摘要和未完成项。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建。此 ticket 未完成前 Batch 2 不得标记 done。
