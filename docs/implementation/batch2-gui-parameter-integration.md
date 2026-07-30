# Batch 2 GUI 参数接入说明

> 适用对象：通过 `--options-json` 静默调用 DeepFaceLab 训练的 GUI 项目与开发 Agent  
> 适用分支：`codex/batch2-ticket19-loss-window`  
> 范围：仅说明 Batch 2 新增的 Faceset Analyzer 参数与 Metadata Sampling 训练参数，不涉及 GUI 布局设计。

## 1. 接入范围

GUI 需要增加两类能力：

1. 调用 `faceset-analyze`，分别分析 SRC 和 DST 的 aligned faceset；
2. 在现有训练 `--options-json` 中生成 `enhancements` 配置，用于启用 Pose / Quality Metadata Sampling。

Faceset Analyzer 是离线预处理工具。它生成 Metadata Sidecar，但不会训练模型、修改图片或删除样本。传统采样模式不依赖 Analyzer；`pose_balanced` 和 `quality_pose_balanced` 依赖对应 faceset 的 Metadata。

---

## 2. Faceset Analyzer 参数

### 2.1 参数模型

| GUI 内部参数 | CLI 参数 | 类型 | 默认值 | 是否建议开放 | 说明 |
|---|---|---:|---:|---:|---|
| `input_dir` | `--input-dir` | path | 无 | 是，必填 | SRC 或 DST 的 aligned 根目录。支持 Ordinary、Person 和包含 `faceset.pak` 的 Packed Faceset。SRC/DST 必须分别执行。 |
| `output_file` | `--output-file` | path/null | `null` | 高级可选 | Metadata Sidecar 输出位置。`null` 时固定为 `<input_dir>/faceset_metadata.v1.json`，也是最推荐的训练自动发现位置。 |
| `report_file` | `--report-file` | path/null | `null` | 高级可选 | 分析报告输出位置。`null` 时为 `<input_dir>/faceset_metadata_report.v1.json`。报告用于 GUI 展示和验收，不是训练器的唯一可信输入。 |
| `analysis_mode` | `--incremental` / `--force` | enum | `full` | 是 | `full`：普通全量分析；`incremental`：复用未变化样本；`force`：忽略旧 Sidecar 并全量重算。三选一。 |
| `workers` | `--workers` | int/null | `null` | 是 | 并行分析进程数。`null` 表示自动选择，当前 auto 上限为 `min(cpu, 8)`。小数据或排错使用 `1`；常规建议 `2` 或 auto。 |
| `fingerprint_mode` | `--strong-fingerprint` | enum | `quick` | 是 | `quick` 使用有限首尾数据与文件信息，速度快；`strong` 对完整样本字节做 SHA256，检测同名替换更可靠，但读取量更大。 |
| `strict` | `--strict` | bool | `false` | 是 | 关闭时，无效样本写入报告但分析可成功；开启时，发现 invalid sample 返回非零，并拒绝覆盖正式 Sidecar。适合正式验收或严格数据检查。 |

### 2.2 `analysis_mode` 说明

#### `full`

不传 `--incremental` 和 `--force`。

适用：

- 第一次分析；
- 当前没有旧 Sidecar；
- 正常重新建立 Metadata。

#### `incremental`

传入：

```text
--incremental
```

适用：

- 新增少量 aligned 图片；
- 删除少量图片；
- 替换少量同名图片；
- faceset 大部分内容未变化。

Analyzer 会复用签名未变化记录，并对最终 faceset 重新计算全局质量归一化和 Summary。

#### `force`

传入：

```text
--force
```

适用：

- 旧 Sidecar 来源不明；
- Metadata Schema 或 Analyzer 版本发生变化；
- Packed Faceset 被重新生成；
- 报告、样本数或 fingerprint 明显不一致；
- 需要验收 full 与 incremental 等价性。

### 2.3 `fingerprint_mode` 说明

| 值 | CLI | 特点 | 建议使用场景 |
|---|---|---|---|
| `quick` | 不传 `--strong-fingerprint` | 速度快，适合日常分析 | 普通工作流、大多数本地数据 |
| `strong` | `--strong-fingerprint` | 完整字节 SHA256，更可靠但更慢 | 最终验收、同名替换风险高、数据归档 |

模式迁移规则：

```text
quick → quick：允许增量复用
strong → strong：允许增量复用
quick → strong：执行完整升级重算
strong → quick：拒绝，退出码 7，旧 Sidecar 保持不变
```

GUI 因此应读取现有 Metadata 的指纹模式，或在收到退出码 `7` 时提示继续使用 strong，而不是自动删除 Sidecar。

### 2.4 Analyzer 命令生成

GUI 应使用参数数组启动进程，不要拼接整条 shell 字符串。

```python
argv = [
    python_executable,
    "main.py",
    "faceset-analyze",
    "--input-dir",
    input_dir,
]

if output_file:
    argv += ["--output-file", output_file]
if report_file:
    argv += ["--report-file", report_file]
if analysis_mode == "incremental":
    argv.append("--incremental")
elif analysis_mode == "force":
    argv.append("--force")
if workers is not None:
    argv += ["--workers", str(workers)]
if fingerprint_mode == "strong":
    argv.append("--strong-fingerprint")
if strict:
    argv.append("--strict")
```

禁止同时传 `--incremental` 和 `--force`。

### 2.5 Analyzer 返回值

GUI 至少保存：

```text
exit_code
stdout
stderr
metadata_file
report_file
```

| Exit Code | 含义 | GUI 建议处理 |
|---:|---|---|
| `0` | 分析成功 | 读取 Report 和 Metadata 摘要，标记该侧可进入训练检查 |
| `2` | `workers` 参数非法 | 阻止继续，恢复 auto 或合法正整数 |
| `3` | 输入目录或样本加载失败 | 检查是否为 aligned/Packed 根目录及路径权限 |
| `4` | 分析过程或 worker fatal | 显示 stderr，不得标记 Metadata 可用 |
| `5` | strict 模式发现 invalid sample | 保留旧 Sidecar；展示 invalid 详情并要求清理或关闭 strict 重跑 |
| `6` | Metadata 原子写入失败 | 检查文件占用、权限和磁盘状态 |
| `7` | strong → quick 降级被拒绝 | 改用 strong，或用户明确删除旧 Sidecar 后重新创建 quick |

---

## 3. Batch 2 训练参数总结构

Batch 2 参数必须位于 `--options-json` 根对象中的 `enhancements`：

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {},
    "sampling": {},
    "runtime": {}
  }
}
```

不能把 `training`、`sampling` 或 `runtime` 直接放在 options 根节点。

---

## 4. 建议开放给 GUI 的训练参数

### 4.1 总开关

#### `metadata_sampling_enabled`

GUI 自定义字段，不直接对应单个 JSON Path，而是同时生成：

```json
{
  "enhancements": {
    "training": {
      "enabled": true,
      "metadata_sampling": true
    }
  }
}
```

类型：`bool`  
默认：`false`

说明：这是 Batch 2 智能采样总开关。两个 Gate 必须同步开启；只开其中一个不会加载 Metadata。

映射：

```text
false → training.enabled=false
        training.metadata_sampling=false

true  → training.enabled=true
        training.metadata_sampling=true
```

关闭时建议 GUI 不输出其余 sampling 高级参数，或保留配置但训练实际使用 legacy。

### 4.2 SRC/DST 采样模式

#### `src_mode`

JSON Path：

```text
enhancements.sampling.src.mode
```

#### `dst_mode`

JSON Path：

```text
enhancements.sampling.dst.mode
```

类型：`enum`

GUI 建议值：

| 值 | 是否需要 Metadata | 说明 |
|---|---:|---|
| `legacy_random` | 否 | 传统全样本随机抽取，兼容性最好 |
| `legacy_uniform_yaw` | 否 | 传统 128 yaw 区间均衡抽取 |
| `pose_balanced` | 是 | 根据 Metadata yaw bucket 提升稀缺姿态的抽取概率 |
| `quality_pose_balanced` | 是 | 先做姿态平衡，再结合质量分数调整概率 |

不建议 GUI 对普通用户暴露内部兼容值 `legacy`。`legacy` 会继续参考旧顶层 `uniform_yaw`，不如显式模式清晰。

SRC 和 DST 应独立配置，不要把 SRC 配置自动复制给 DST。常见做法是 SRC 使用 `quality_pose_balanced`，DST 使用 `pose_balanced`。

### 4.3 Metadata 路径

#### `src_metadata_path`

```text
enhancements.sampling.src.metadata_path
```

#### `dst_metadata_path`

```text
enhancements.sampling.dst.metadata_path
```

类型：`path/null`  
默认：`null`

说明：

- `null`：从对应 aligned 根目录读取 `faceset_metadata.v1.json`；
- 相对路径：相对对应 faceset 根目录解析，禁止 `..` 逃逸；
- 绝对路径：允许，适合 GUI 集中管理 Sidecar；
- 中文、空格和 Unicode 路径必须原样支持。

建议：GUI 默认固定为 `null`，只有用户开启“自定义 Metadata 路径”时才输出该字段。

### 4.4 `pose_balance_strength`

JSON Path：

```text
enhancements.sampling.pose_balance_strength
```

类型：`float`  
默认：`0.5`  
范围：`0.0 .. 1.0`

作用：控制对稀缺姿态 bucket 的补偿强度。

| 值 | 语义 |
|---:|---|
| `0.0` | 不做姿态补偿；即使选择智能模式，也接近基础分布 |
| `0.5` | 默认保守补偿，推荐起点 |
| `1.0` | 最强 v1 姿态补偿，但仍受样本权重上下限保护 |

建议开放。初次实机测试保持 `0.5`，确认分布正常后再调高。

### 4.5 `quality_strength`

JSON Path：

```text
enhancements.sampling.quality_strength
```

类型：`float`  
默认：`0.5`  
范围：`0.0 .. 1.0`

作用：控制质量分数对抽样概率的影响，只在 `quality_pose_balanced` 模式中有实际意义。

| 值 | 语义 |
|---:|---|
| `0.0` | 忽略质量分数，仅保留姿态权重 |
| `0.5` | 默认强度，质量权重约在 `0.5 .. 1.5` 范围变化 |
| `1.0` | 更明显降低低质量样本概率并提高高质量样本概率 |

它不会把质量分数乘到训练 Loss，也不会删除低质量图片。明显错脸和严重遮挡仍需人工清理。

### 4.6 `uniform_mix`

JSON Path：

```text
enhancements.sampling.uniform_mix
```

类型：`float`  
默认：`0.1`  
硬范围：`0.0 .. 1.0`  
推荐范围：`0.05 .. 0.30`

作用：在智能加权概率中混入一部分均匀随机概率，防止某些样本长期难以被抽中。

```text
p_final = (1-uniform_mix) × p_weighted + uniform_mix × uniform_probability
```

| 值 | 语义 |
|---:|---|
| `0.0` | 完全使用智能权重；仅建议明确实验时使用 |
| `0.1` | 默认，兼顾智能采样和随机探索 |
| `0.3` | 更接近均匀随机，智能权重效果减弱 |
| `1.0` | 完全均匀，基本失去智能采样意义 |

建议开放，但给出推荐范围提示。

### 4.7 `min_metadata_match_ratio`

JSON Path：

```text
enhancements.sampling.min_metadata_match_ratio
```

类型：`float`  
默认：`0.9`  
范围：`0.0 .. 1.0`

作用：要求当前 faceset 至少有多少比例的样本与 Metadata 通过 `sample_id + signature` 可信匹配。低于该比例时，不允许使用请求的智能模式。

| 值 | 语义 |
|---:|---|
| `0.9` | 默认，允许少量新增、删除或异常记录 |
| `1.0` | 要求全部样本精确匹配，适合正式严格验收 |
| `<0.9` | 容忍更多不匹配，可能降低智能采样可信度 |

建议作为高级参数开放。一般训练使用 `0.9`，GPU 最终验收可使用 `1.0` 或配合 strict。

### 4.8 `fallback_mode`

JSON Path：

```text
enhancements.sampling.fallback_mode
```

类型：`enum`  
默认：`legacy_random`

只允许：

```text
legacy_random
legacy_uniform_yaw
```

作用：Metadata 缺失、损坏、版本不支持或可信匹配率不足，并且运行时允许 optional fallback 时，选择哪种传统采样模式继续训练。

不能回退到另一个 Metadata 智能模式。

建议开放为二选一。默认 `legacy_random` 最稳妥；希望保留传统 yaw 均衡时选择 `legacy_uniform_yaw`。

### 4.9 `fallback_on_optional_error`

JSON Path：

```text
enhancements.runtime.fallback_on_optional_error
```

类型：`bool`  
默认：`true`

作用：控制“可选 Metadata 问题”是否允许退回传统采样继续训练。

`true` 可回退的典型情况：

- Sidecar 不存在；
- JSON 损坏；
- Schema 不支持；
- 匹配率不足；
- stale/duplicate 等 Metadata 状态。

无论该字段为何值，以下核心错误都必须失败，不能 fallback：

- SampleLoader 或 faceset 加载失败；
- 训练数据为空；
- PermissionError；
- MemoryError / OOM；
- worker / WeightedIndexHost fatal；
- TensorFlow、模型 save/load 或训练错误；
- 未分类编程错误。

建议开放。普通用户默认 `true`；严格验收或希望 Metadata 异常立即停止时设为 `false`。

### 4.10 `strict_validation`

JSON Path：

```text
enhancements.runtime.strict_validation
```

类型：`bool`  
默认：`false`

作用：开启后，只要 Metadata 缺失、损坏、不匹配或发生 fallback，智能采样训练即拒绝启动。

决策：

| fallback | strict | Optional Metadata 问题 |
|---:|---:|---|
| `true` | `false` | fallback + warning |
| `true` | `true` | raise，阻止启动 |
| `false` | `false` | raise，阻止启动 |
| `false` | `true` | raise，阻止启动 |

建议开放为“严格 Metadata 验证”。普通训练关闭；GPU 最终验收、发布检查和自动化测试开启。

### 4.11 `sampling_seed`

JSON Path：

```text
enhancements.sampling.seed
```

也可在 `sampling.src.seed`、`sampling.dst.seed` 单独覆盖。

类型：`int/null`  
默认：`null`

作用：固定智能 Sampling 的随机数流，便于重复实验和比较采样分布。

- `null`：从模型 base seed 派生，SRC=`base+1000`，DST=`base+2000`；
- integer：固定 base Sampling seed；
- side seed：固定对应侧；
- 不修改 NumPy 全局 RNG；
- 不承诺不同 OS 和并发调度下逐 worker batch 完全一致。

建议作为高级参数开放。一般用户保持 `null`；验收和对照实验固定整数。

---

## 5. 建议由 GUI 固定生成的参数

这些参数当前不建议作为普通用户可调项：

| JSON Path | 固定值 | 原因 |
|---|---:|---|
| `enhancements.schema_version` | `1` | 配置协议版本，必须跟源码支持版本一致 |
| `enhancements.training.enabled` | 跟随总开关 | 与 Metadata Sampling 双 Gate 联动 |
| `enhancements.training.metadata_sampling` | 跟随总开关 | 与 `training.enabled` 同步开关 |
| `enhancements.sampling.min_sample_weight` | `0.5` | 安全下限，防止低权重样本几乎消失 |
| `enhancements.sampling.max_sample_weight` | `2.0` | 安全上限，限制稀缺/高质量样本过度重复 |
| `enhancements.sampling.log_interval_draws` | `10000` | 只影响抽样统计日志频率，不改变算法 |

### 5.1 `min_sample_weight` / `max_sample_weight`

底层合法范围均为 `0.01 .. 100.0`，并且必须满足：

```text
min_sample_weight < max_sample_weight
```

但当前 GUI 首次接入不建议开放。过大的区间可能导致少量样本被高频重复，过窄则使智能采样效果不明显。固定 `0.5 / 2.0` 更适合本轮 Windows 实机验证。

### 5.2 `log_interval_draws`

表示累计多少次样本抽取后输出一次 Sampling Stats。默认 `10000`，最小 `100`。

该参数主要用于日志性能控制，不属于训练效果调节项。GUI 可固定为 `10000`；未来需要调试采样分布时再放入开发者设置。

---

## 6. SRC/DST 参数继承规则

推荐 GUI 总是生成 base 公共字段，并使用 `src` / `dst` 保存侧别差异：

```json
{
  "enhancements": {
    "sampling": {
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": null,
      "log_interval_draws": 10000,
      "src": {
        "mode": "quality_pose_balanced",
        "metadata_path": null
      },
      "dst": {
        "mode": "pose_balanced",
        "metadata_path": null
      }
    }
  }
}
```

解析优先级：

```text
SamplingConfig 默认值
→ sampling 扁平 base
→ sampling.src / sampling.dst 覆盖
```

只有 `src` 配置时，DST 使用 base，不会复制 SRC。

首版 GUI 可以只允许 SRC/DST 独立设置：

```text
mode
metadata_path
```

其他强度、fallback、seed 等先作为两侧共享 base。后续确有实测需求，再允许 side override `pose_balance_strength`、`quality_strength` 等字段。

---

## 7. 推荐的 GUI 配置对象

GUI 项目内部可使用：

```json
{
  "metadata_sampling_enabled": true,
  "src": {
    "mode": "quality_pose_balanced",
    "metadata_path": null
  },
  "dst": {
    "mode": "pose_balanced",
    "metadata_path": null
  },
  "pose_balance_strength": 0.5,
  "quality_strength": 0.5,
  "uniform_mix": 0.1,
  "min_metadata_match_ratio": 0.9,
  "fallback_mode": "legacy_random",
  "fallback_on_optional_error": true,
  "strict_validation": false,
  "sampling_seed": null
}
```

转换成 DFL：

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": null,
      "log_interval_draws": 10000,
      "src": {
        "mode": "quality_pose_balanced",
        "metadata_path": null
      },
      "dst": {
        "mode": "pose_balanced",
        "metadata_path": null
      }
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

---

## 8. 推荐测试预设

### 8.1 传统基线

```text
metadata_sampling_enabled=false
```

用于确认 GUI 新增逻辑没有改变旧训练。

### 8.2 Pose 基础测试

```text
SRC mode=pose_balanced
DST mode=pose_balanced
pose_balance_strength=0.5
uniform_mix=0.1
fallback=true
strict=false
```

### 8.3 Quality + Pose 测试

```text
SRC mode=quality_pose_balanced
DST mode=pose_balanced
pose_balance_strength=0.5
quality_strength=0.5
uniform_mix=0.1
fallback=true
strict=false
```

### 8.4 最终严格验收

```text
SRC/DST 对应模式按 Matrix 设置
fingerprint_mode=strong
min_metadata_match_ratio=1.0
fallback_on_optional_error=false
strict_validation=true
sampling_seed=固定整数
```

训练仍应使用 Batch 2 固定验收基线：

```text
precision=fp32
optimizer=adabelief
```

这两个是已有训练参数，不属于 Batch 2 新增字段，但最终 Windows GPU 验收必须固定使用。

---

## 9. GUI 开发 Agent 最小任务

1. 增加 Faceset Analyzer 进程调用参数模型；
2. SRC 和 DST 可分别执行 Analyzer；
3. 支持默认和自定义 Metadata/Report 路径；
4. 解析退出码并保留 stdout/stderr；
5. 在现有 `--options-json` 对象中合并 `enhancements`，不要覆盖其他已有训练参数；
6. 支持 SRC/DST 独立 `mode` 与 `metadata_path`；
7. 暴露本文件第 4 节列出的可调参数；
8. 固定生成第 5 节参数；
9. 使用 `json.dumps()` 生成 JSON 字符串，并通过 subprocess 参数数组传递；
10. 非空 `--options-json` 启动训练时继续显式传 `--force-model-name`，避免静默选择错误模型；
11. 支持中文、空格和 Unicode 路径；
12. 训练日志中记录 SRC/DST 的 `requested / effective / metadata status / fallback reason`，用于后续 GPU 验收。
