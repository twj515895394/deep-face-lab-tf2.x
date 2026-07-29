# DeepFaceLab Faceset Metadata 与智能采样使用指南

> 文档版本：v1.0  
> 更新日期：2026-07-29  
> 适用版本：DeepFaceLab TF2.x Batch 2  
> 核心模块：Faceset Analyzer (`main.py faceset-analyze`) 与 RuntimeMetadata Loader / Sampler

---

## 1. 功能概述

DeepFaceLab Batch 2 引入了静态 Faceset Metadata 分析与智能平衡采样机制，旨在不破坏 SAEHD 模型网络、Loss、Checkpoint 和 Merge 格式的前提下，解决训练数据分布不均与低质量样本过采样问题：

- **姿态平衡采样（Pose-balanced Sampling）**：自动矫正 Yaw 姿态分布倾斜（如大角度偏头样本少、正脸过多），提升跨角度转脸拟合能力。
- **质量与姿态联合采样（Quality & Pose Balanced Sampling）**：在姿态平衡的基础上，根据清晰度、曝光和关键点置信度等启发式指标对模糊/过曝/异常样本适度降权。
- **元数据侧边栏（Sidecar Metadata）**：元数据独立保存在 faceset 目录中，不修改图片文件或 `.pak` 包，不改变原始图像文件。
- **安全回退机制（Graceful Fallback）**：元数据缺失、损坏或样本哈希不匹配时，自动安全回退至传统随机或 Pitch/Yaw 采样，保证训练决不中断。

---

## 2. 前置要求

- **Python 环境**：Python 3.9+（推荐项目统一虚拟环境 `./.venv/bin/python`）。
- **数据集格式**：支持普通文件夹已切脸集（Ordinary aligned faceset）及打包数据集（Packed `faceset.pak`）。
- **训练模型**：支持 SAEHD、AMP、Quick96 等全量 DFL 训练模型。

---

## 3. Faceset Analyzer 使用指南

Faceset Analyzer 用于在训练前对样本集进行离线质量与姿态评估，并生成原子元数据文件。

### 3.1 基础分析命令

对指定切脸目录（普通文件夹或包含 `faceset.pak` 的目录）执行分析：

```bash
./.venv/bin/python main.py faceset-analyze --input-dir /path/to/aligned_faces
```

### 3.2 CLI 参数详解

| 参数 | 类型 | 必填 | 默认值 | 作用说明 |
|---|---|---|---|---|
| `--input-dir` | Path | 是 | 无 | 包含切脸图片或 `faceset.pak` 的数据集目录路径 |
| `--output-file` | Path | 否 | `<input-dir>/faceset_metadata.v1.json` | 元数据 JSON 输出路径 |
| `--report-file` | Path | 否 | `<input-dir>/faceset_metadata_report.v1.json` | 机器与人类可读分析报告路径 |
| `--incremental` | Flag | 否 | False | 增量分析模式：校验样本哈希与修改时间，仅对新增/修改样本重新分析 |
| `--force` | Flag | 否 | False | 强制全量重新分析，忽略增量缓存 |
| `--workers` | Int | 否 | 自动（CPU核心数） | 多进程并发分析工作进程数 |
| `--strong-fingerprint` | Flag | 否 | False | 启用 SHA256 字节完整哈希生成 Dataset Fingerprint（默认使用轻量级样本特征指纹） |
| `--strict` | Flag | 否 | False | 严格校验模式：遇到损坏/无效样本时立即报错中断，而非跳过 |

### 3.3 示例场景

#### 场景 1：对 Packed 目录进行分析
```bash
./.venv/bin/python main.py faceset-analyze --input-dir ./data_src/aligned
```
程序将自动识别普通图像或 `faceset.pak`，在目录下生成 `faceset_metadata.v1.json` 与 `faceset_metadata_report.v1.json`。

#### 场景 2：数据集中新增少量图片后进行增量分析
```bash
./.venv/bin/python main.py faceset-analyze --input-dir ./data_src/aligned --incremental
```
自动跳过未改变样本，极速计算新增样本元数据并更新原子文件。

---

## 4. 分析报告字段解读 (`faceset_metadata_report.v1.json`)

运行 Analyzer 后生成的报告文件包含数据集完整统计分布：

```json
{
  "schema_version": "1.0.0",
  "analyzer_version": "1.0.0",
  "dataset_path": "/path/to/aligned",
  "dataset_format": "ordinary",
  "dataset_fingerprint": "a1b2c3d4...",
  "total_samples": 1200,
  "usable_samples": 1198,
  "invalid_samples": 2,
  "time_elapsed_sec": 3.45,
  "samples_per_sec": 347.8,
  "pose_distribution": {
    "yaw_buckets": {
      "left_profile": 120,
      "left_half": 280,
      "center": 500,
      "right_half": 260,
      "right_profile": 38
    }
  },
  "quality_summary": {
    "blurriness": { "min": 12.3, "max": 185.6, "mean": 94.2, "median": 91.0 },
    "overall_quality": { "min": 0.21, "max": 0.98, "mean": 0.72, "median": 0.74 }
  }
}
```

> [!NOTE]
> **质量得分说明**：
> `overall_quality` 为用于训练采样权重的相对启发式指标（结合图像拉普拉斯方差、亮度曝光分布与关键点置信度），**不代表最终换脸渲染画质，程序绝不会根据质量得分自动删除任何图片**。

---

## 5. 训练中启用智能采样

通过 `--options-json` 训练参数注入机制，可以在 SAEHD 等模型训练中开启或配置智能采样。

### 5.1 采样模式（Sampling Mode）

目前支持以下 4 种采样模式：

| 模式名称 | 依赖 Metadata | 说明 |
|---|---|---|
| `legacy_random` | 否 | 传统完全均匀随机采样 |
| `legacy_uniform_yaw` | 否 | 传统基于 Pitch/Yaw 姿态桶的分布采样 |
| `pose_balanced` | 是 | 基于 Metadata 侧边栏的精确 Yaw 桶平滑平衡采样 |
| `quality_pose_balanced` | 是 | 结合姿态平衡与质量分数的加权复合采样 |

### 5.2 `--options-json` 配置示例

启动训练时传入 JSON 配置字符串或文件：

#### 示例 1：为 src 启用姿态平衡，dst 保持传统采样
```bash
./.venv/bin/python main.py train \
  --training-data-src-dir ./data_src/aligned \
  --training-data-dst-dir ./data_dst/aligned \
  --model-dir ./saved_models \
  --model SAEHD \
  --options-json '{"training": {"metadata_sampling": true}, "sampling": {"src": {"mode": "pose_balanced"}, "dst": {"mode": "legacy_random"}}}'
```

#### 5.3 采样高级参数映射 (`sampling.<side>.*`)

可在 JSON 中对 `src` 或 `dst` 精细微调以下控制参数：

```json
{
  "training": {
    "metadata_sampling": true
  },
  "sampling": {
    "src": {
      "mode": "quality_pose_balanced",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.90
    }
  }
}
```

- `pose_balance_strength` (0.0~1.0): 姿态平衡强度，默认 0.5。
- `quality_strength` (0.0~1.0): 质量加权强度，默认 0.5。
- `uniform_mix` (0.0~1.0): 基础均匀采样混合比例，保障极少姿态样本不被遗漏，默认 0.1。
- `min_sample_weight` / `max_sample_weight`: 采样权重裁剪范围，防止极端极差样本权重过高或过低，默认 [0.5, 2.0]。
- `min_metadata_match_ratio`: 侧边栏样本与当前目录匹配率阈值，低于该比例自动触发 fallback，默认 0.90 (90%)。

---

## 6. 运行时日志与 Fallback 解读

训练启动时，控制台将输出采样器的匹配与加载状态：

```text
[Sampling][src]
  requested: quality_pose_balanced
  effective: quality_pose_balanced
  metadata: /path/to/data_src/aligned/faceset_metadata.v1.json (usable=1198/1200, match=99.8%)
  fallback: none
```

如果未生成元数据或文件损坏，将显示优雅回退日志：

```text
[Sampling][src]
  requested: pose_balanced
  effective: legacy_random
  metadata: missing
  fallback reason: missing
```

常见 Fallback 原因：
- `missing`: 未在该目录下找到 `faceset_metadata.v1.json` 文件。
- `invalid_file`: Metadata JSON 格式损坏或无法解析。
- `unsupported_schema`: Schema 版本不兼容。
- `partial_match`: 元数据中包含的有效样本数与当前数据集重合率低于 90%。

---

## 7. 常见问题与故障排查

| 现象 / 日志提示 | 可能原因 | 建议解决方法 |
|---|---|---|
| `metadata: missing` | 尚未生成 Metadata 侧边栏文件 | 运行 `./.venv/bin/python main.py faceset-analyze --input-dir <dir>` |
| `fallback reason: partial_match` | 分析完后，在 faceset 目录中增删了较多图片 | 运行 `./.venv/bin/python main.py faceset-analyze --input-dir <dir> --incremental` |
| `fallback reason: invalid_file` | JSON 被非法修改或存储中断 | 删除该 JSON 文件或重新运行 `--force` 全量分析 |
| 采样控制台未输出智能采样信息 | 未开启 `training.metadata_sampling` 全局总开关 | 在 `--options-json` 中添加 `"training": {"metadata_sampling": true}` |
| 某些异常样本仍被抽到 | 采样器使用加权概率而非彻底删除样本 | 智能采样仅调整抽取概率，若需彻底排除该样本请手动删除并增量分析 |

---

## 8. 已知限制与延期功能

1. **样本修改**：程序绝不会修改图像像素或自动删除样本。
2. **状态保存**：采样器内部随机游走游标（draw state）不随模型持久化，但模型权重与 Optimizer save/resume 100% 保持完全兼容。
3. **已明确延期的功能**：
   - 动态 Loss-aware Sampling（暂无）
   - Identity Geometry / 脸型 Loss（排班在 Batch 4）
   - Source Shape Template（排班在 Batch 5）
   - Shape-aware Merge（排班在 Batch 6）
