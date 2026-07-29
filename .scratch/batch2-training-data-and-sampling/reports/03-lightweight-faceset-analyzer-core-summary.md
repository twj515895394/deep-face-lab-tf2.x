# Ticket 03 — Lightweight Faceset Analyzer 核心指标总结报告

- **更新时间**: 2026-07-29

## 测试与状态总览

- **测试状态**: PASS (macOS 轻量级验证已通过)
- **单元测试包含**: 104 项全量 Smoke 测试全通过（包含 10 项 Pose / Quality / Analyzer 核心专项测试）
- **`--options-json` 文档同步**: NA (本 Ticket 不涉及训练参数 CLI 选项变更)

## 详细模块与指标规范

### 1. 姿态分析 (`samplelib/metadata/pose.py`)
- **`validate_landmarks`**: 严格判断 68 点 2D Landmarks、坐标有限性与像素边界开度；
- **姿态映射**:
  - 调用 `LandmarksProcessor.estimate_pitch_yaw_roll`；
  - **Yaw 分桶**: `extreme_left` (< -0.8), `major_left` (-0.8~-0.4), `minor_left` (-0.4~-0.15), `center` (-0.15~0.15), `minor_right` (0.15~0.4), `major_right` (0.4~0.8), `extreme_right` (> 0.8)；
  - **Pitch 分桶**: `up` (< -0.15), `level` (-0.15~0.15), `down` (> 0.15)。

### 2. 质量分析 (`samplelib/metadata/quality.py`)
- **`validate_image`**: 判断 3 通道 BGR 图像、非零尺寸及有限像素值；
- **Raw Quality**:
  - `sharpness_raw`: 灰度图 Laplacian 方差；
  - `exposure_score`: 1.0 - (暗区比例 + 过暴区比例)；
- **Pass 2 Normalization**:
  - 对数据集使用 `log1p(sharpness_raw)` 计算稳健百分位数 `p05` 与 `p95` 进行 [0, 1] 平滑归一化；
  - 导出 `quality_score = 0.7 * sharpness_norm + 0.3 * exposure_score`。

### 3. 两遍分析器管线 (`samplelib/metadata/analyzer.py`)
- **`FacesetAnalyzer`**:
  - **Pass 1**: 单次图像像素载入，无内存积压，安全生成单图原始指标；
  - **Pass 2**: 数据集 Percentile 平滑归一化与 Dataset Fingerprint 计算；
  - 汇总 Sample count, Valid count, Bucket distribution, Quality quartiles (min, p05, median, p95, max) 及 Failure 列表；
  - 导出符合规范的 `FacesetMetadataV1` 实例。

## 可供 Ticket 04 (CLI & Atomic Store) 直接调用的 API

```python
from samplelib.metadata import (
    FacesetAnalyzer,
    FacesetAnalyzerConfig,
    FacesetPoseConfig,
    FacesetQualityConfig,
    AnalyzerResult,
)

# 默认模式调用
analyzer = FacesetAnalyzer()
result: AnalyzerResult = analyzer.analyze(samples_path)
```
