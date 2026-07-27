# 03 — 实现轻量 Faceset Analyzer 核心指标

Status: open
Type: AFK
Blocked by: `02-sample-identity-and-metadata-schema.md`

**构建内容：** 在不引入大型外部模型的前提下，对普通和 Packed Faceset 的每张样本计算图片合法性、landmark 合法性、pitch/yaw/roll、可解释姿态桶、清晰度、曝光和基础 quality score，形成 Schema v1 原始记录。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 02 summary，确认 Schema、issue code、sample identity 和 fingerprint API
3. `samplelib/Sample.py::load_bgr/get_pitch_yaw_roll`
4. `samplelib/SampleLoader.py::load`
5. `facelib/LandmarksProcessor.py` 中姿态估计函数
6. 项目现有 blur、brightness、pose sort 实现，避免重复发明不一致公式
7. Ticket 01 synthetic fixture

如果 Ticket 02 的正式 API 尚未存在，不得在本 Ticket 自行创建第二套 Schema。

## 当前源码事实必须先确认

编码前记录：

- `sample.load_bgr()` 的 dtype、范围和 channel 顺序；
- `get_pitch_yaw_roll()` 返回顺序、单位和 yaw 正负号；
- ordinary 与 packed 是否使用完全相同的 `load_bgr()`；
- landmarks 正常点数和 shape；
- 项目现有 blur sort 使用的 Laplacian 或其他公式；
- 项目是否已有 exposure/brightness helper 可复用。

## 目标

- Analyzer 只依赖现有 SampleLoader、cv2、NumPy 和 LandmarksProcessor。
- 单图失败不拖垮整个 faceset。
- 指标可解释、可测试、有版本号。
- quality score 只用于静态训练采样，不宣称为最终人脸质量评分。
- 普通与 Packed 使用相同像素读取和计算路径。

## 建议模块边界

```text
pose.py
  ├─ validate_landmarks
  ├─ estimate_pose
  └─ assign_yaw/pitch_bucket

quality.py
  ├─ validate_image
  ├─ compute_raw_metrics
  ├─ fit_faceset_normalization
  └─ compute_quality_score

analyzer.py
  ├─ Pass 1 per-sample raw records
  ├─ Pass 2 normalization
  └─ summary / failures / timing
```

不要把所有公式写进一个 500 行函数。

## 建议施工顺序

### Step 1：先实现图片和 landmarks 校验纯函数

建议返回结构化结果：

```python
@dataclass
class ImageValidation:
    valid: bool
    height: int | None
    width: int | None
    channels: int | None
    issues: list[str]

@dataclass
class LandmarkValidation:
    valid: bool
    point_count: int
    issues: list[str]
```

Python 3.9 不支持 `int | None` 时使用 `Optional[int]`。

测试通过后再计算指标。

### Step 2：实现 pose 和 bucket

- 使用现有姿态估计，不引入新网络；
- 首先在固定 fixture 上确认 yaw 左右符号；
- 阈值只定义在一个版本化常量对象中；
- 精确边界要明确属于左区间还是右区间；
- pose 失败返回 unknown，不抛出导致整批终止。

建议接口：

```python
pose = analyze_pose(sample, landmarks_validation, config)
pose.valid
pose.pitch
pose.yaw
pose.roll
pose.yaw_bucket
pose.pitch_bucket
pose.issues
```

### Step 3：实现 raw quality metrics

每张图只计算 raw 值：

```text
sharpness_raw = variance(Laplacian(gray))
dark_ratio = mean(gray <= dark_threshold)
bright_ratio = mean(gray >= bright_threshold)
exposure_score_raw = ...
```

不要在单图函数里计算全 faceset percentile。

### Step 4：实现 Pass 2 归一化

只保留 raw 数值数组，不保留全量像素。对有效 raw sharpness：

```text
log_value = log1p(max(raw, 0))
p05, p95 = finite percentile
normalized = clip((log_value-p05)/(p95-p05), 0, 1)
```

当有效样本过少或 `p95-p05` 很小时返回中性 0.5，并记录 summary warning。

### Step 5：实现 quality score

权重和公式必须版本化并写入 `analysis_config`。第一版保持简单，可解释。landmark invalid 不应让清晰可读图片直接变 0。

### Step 6：组装 Analyzer 两遍管线

第一遍逐样本：

```text
identity/signature
→ load image once
→ image validation
→ landmark validation
→ pose
→ raw quality
→ issues
```

第二遍：

```text
faceset percentile
→ normalized quality
→ summary
```

单图异常只影响该记录；顶层 Loader/empty faceset 等错误仍按明确语义返回失败。

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
config = FacesetAnalyzerConfig(...)
result = FacesetAnalyzer(config).analyze(samples_path)
result.metadata
result.summary
result.failures
result.timing
```

建议 `analyze_sample()` 可独立测试：

```python
raw_record = analyzer.analyze_sample(sample, context)
```

Pass 2 独立函数：

```python
final_records, normalization = finalize_quality(raw_records, config)
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

## 最小测试命令

```bash
python -m compileall samplelib/metadata
python -m unittest \
  tests.smoke.test_batch2_pose \
  tests.smoke.test_batch2_quality \
  tests.smoke.test_batch2_analyzer_core
```

测试模块名按实际创建调整，并写入 summary。

## 禁止捷径与常见错误

- 不允许根据文件名或目录猜 pose。
- 不允许对每张图独立 min/max 归一化 sharpness。
- 不允许把全部图片像素保存在列表中做第二遍。
- 不允许 catch 所有异常后返回 quality=1 且无 issue。
- 不允许把 invalid landmark 直接等同于图片质量为 0。
- 不允许引入 ArcFace、DINO、LPIPS 或其他大型模型。
- 不允许普通和 packed 使用两套不同指标实现。
- 不允许把 quality score 描述为“最终换脸质量评分”。

## 验收标准

- [ ] 同一输入、同一版本配置得到确定性 Metadata。
- [ ] issue code 可定位失败原因。
- [ ] 左右姿态标签经 fixture 和人工抽查确认。
- [ ] quality 分数排序大体符合 synthetic 清晰/模糊关系。
- [ ] Analyzer 核心可在 CPU 环境运行。
- [ ] 不修改原始图片和 faceset.pak。
- [ ] 所有公式、阈值和退化行为在 summary 中可供 Ticket 04 复用。

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
- [ ] 列出 Ticket 04 应调用的 Analyzer config/result API。
- [ ] 明确哪些 Windows 多 worker 项仍为 pending。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 02 完成。
- 2026-07-27：补充弱模型模块边界、两遍处理顺序、接口骨架和禁止捷径。