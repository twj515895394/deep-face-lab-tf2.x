# 03 — 实现轻量 Faceset Analyzer 核心指标

Status: open
Type: AFK
Blocked by: `02-sample-identity-and-metadata-schema.md`

**构建内容：** 在不引入大型外部模型的前提下，对普通和 Packed Faceset 的每张样本计算图片合法性、landmark 合法性、pitch/yaw/roll、可解释姿态桶、清晰度、曝光和基础 quality score，形成 Schema v1 原始记录。

## 目标

- Analyzer 只依赖现有 SampleLoader、cv2、NumPy 和 LandmarksProcessor。
- 单图失败不拖垮整个 faceset。
- 指标可解释、可测试、有版本号。
- quality score 只用于静态训练采样，不宣称为最终人脸质量评分。
- 普通与 Packed 使用相同像素读取和计算路径。

## 详细任务

### Analyzer 管线

- [ ] 新增 `samplelib/metadata/analyzer.py`。
- [ ] 使用 `SampleLoader.load(SampleType.FACE, path)` 统一加载。
- [ ] 使用 `sample.load_bgr()` 读取 ordinary / packed 图片。
- [ ] 实现 Pass 1：合法性、pose、raw quality metrics。
- [ ] 实现 Pass 2：faceset percentile、normalized score、summary。
- [ ] 逐样本捕获异常，记录 issue code 和简短 reason。
- [ ] 非 strict 模式继续；strict 模式聚合后返回失败。

### Image Validation

- [ ] 检查可读性、HWC、channel、尺寸、finite 和范围。
- [ ] 无效图片不继续计算 pose/quality，但保留记录。
- [ ] 不把所有图片同时驻留内存。

### Landmark Validation

- [ ] 检查存在、二维 shape、点数、finite、合理边界比例。
- [ ] 区分 missing、count invalid、nonfinite、out-of-bounds。
- [ ] 不引入新的 confidence 网络。
- [ ] 验证失败时 pose.valid=False，但质量可使用图片指标生成中性/降级值。

### Pose

- [ ] 新增 `samplelib/metadata/pose.py`。
- [ ] 调用现有 `get_pitch_yaw_roll()`。
- [ ] 用固定 fixture 校验左右 yaw 符号，不允许只按文档猜测。
- [ ] 实现 7 个 yaw bucket + unknown。
- [ ] 实现 up/level/down pitch bucket + unknown。
- [ ] 所有阈值集中版本化，写入 analysis_config。
- [ ] 对精确边界值写测试。

### Quality

- [ ] 新增 `samplelib/metadata/quality.py`。
- [ ] grayscale Laplacian variance 作为 sharpness_raw。
- [ ] 使用 log1p + p05/p95 稳健归一化。
- [ ] p95≈p05 时回到中性分数，不除零。
- [ ] 计算 dark/bright clipped ratio 和 exposure_score。
- [ ] 按版本化权重生成 quality_score `[0,1]`。
- [ ] landmark invalid 不直接把可读图片设为零质量。
- [ ] 所有数值 finite；异常写 issue。

### Summary

- [ ] 统计 sample count、valid count、issue counts。
- [ ] 统计 yaw/pitch bucket。
- [ ] 统计 sharpness/quality min、p05、median、p95、max。
- [ ] 列出有限数量的失败和低质量 sample key。

## 建议 API

```python
result = FacesetAnalyzer(config).analyze(samples_path)
result.metadata
result.summary
result.failures
result.timing
```

## 测试场景

- [ ] 正常清晰图。
- [ ] 高斯模糊图。
- [ ] 全黑、全白、过暗、过亮。
- [ ] invalid bytes。
- [ ] landmarks missing / wrong count / NaN / 越界。
- [ ] front、左右 minor/major/extreme。
- [ ] 所有 sharpness_raw 相同。
- [ ] empty faceset 按现有 Loader 语义报错。
- [ ] ordinary 与 packed 同图指标在容差内一致。

## 性能约束

- [ ] 单张图片只读取一次。
- [ ] 内存复杂度主要为 Metadata 记录，不保留全量像素。
- [ ] worker 异常能返回主进程，不产生僵尸进程。
- [ ] Windows spawn 相关代码必须位于安全入口。

## 验收标准

- [ ] 同一输入、同一版本配置得到确定性 Metadata。
- [ ] issue code 可定位失败原因。
- [ ] 左右姿态标签经 fixture 和人工抽查确认。
- [ ] quality 分数排序大体符合 synthetic 清晰/模糊关系。
- [ ] Analyzer 核心可在 CPU 环境运行。
- [ ] 不修改原始图片和 faceset.pak。

## 回退

Analyzer 是独立工具。未运行 Analyzer 时项目训练行为不变。

## 不在本 ticket

- 不写最终文件。
- 不做 CLI。
- 不做增量复用。
- 不接训练采样。
- 不自动删除低质量图片。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/03-lightweight-faceset-analyzer-core-summary.md`，记录公式、阈值版本、fixture 结果和已知限制。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 02 完成。
