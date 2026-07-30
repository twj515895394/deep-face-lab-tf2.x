# Batch 2 GUI 参数接入说明

> 适用对象：通过 `--options-json` 静默调用 DeepFaceLab 训练的 GUI 项目与开发 Agent  
> 适用分支：`codex/batch2-ticket19-loss-window`  
> 范围：仅说明 Batch 2 新增的 Faceset Analyzer 参数与 Metadata Sampling 训练参数，不涉及 GUI 布局。

## 1. 核心原则

Batch 2 的默认值已经定义在 DFL 内部：

```text
core/enhancements/config.py
samplelib/sampling/config.py
```

因此 GUI 不应重复维护一套固定默认值，也不应把所有默认字段都塞进 `--options-json`。

正确规则：

```text
DFL 负责默认值与参数校验
GUI 只传：
1. 启用智能采样所需的开关
2. SRC / DST 采样模式
3. 用户明确修改的可调参数
4. 自定义 Metadata 路径（仅使用非默认位置时）
```

这样可以避免未来 DFL 默认值变化后，GUI 仍继续传旧值。

---

## 2. Faceset Analyzer 参数

GUI 通过以下命令调用：

```text
python main.py faceset-analyze [参数]
```

| GUI 参数 | CLI 参数 | 类型 | DFL 默认行为 | 说明 |
|---|---|---:|---|---|
| `input_dir` | `--input-dir` | path | 无，必填 | SRC 或 DST 的 aligned 根目录；两侧分别运行 |
| `output_file` | `--output-file` | path/null | `<input_dir>/faceset_metadata.v1.json` | 通常不要传，自定义保存位置时才传 |
| `report_file` | `--report-file` | path/null | `<input_dir>/faceset_metadata_report.v1.json` | 通常不要传，自定义报告位置时才传 |
| `analysis_mode` | `--incremental` / `--force` | enum | `full` | `full`、`incremental`、`force` 三选一 |
| `workers` | `--workers` | int/null | auto，当前上限 `min(cpu, 8)` | `null` 时不要传；排错可设 `1` |
| `fingerprint_mode` | `--strong-fingerprint` | enum | `quick` | `strong` 时才传该开关 |
| `strict` | `--strict` | bool | `false` | 仅为 `true` 时传 |

### 2.1 分析模式

```text
full
→ 不传 --incremental 和 --force
→ 第一次分析或普通全量分析

incremental
→ 传 --incremental
→ faceset 少量新增、删除或替换后使用

force
→ 传 --force
→ 忽略旧 Sidecar，重新全量分析
```

禁止同时传 `--incremental` 和 `--force`。

### 2.2 指纹模式

```text
quick
→ 不传 --strong-fingerprint
→ 日常分析默认模式

strong
→ 传 --strong-fingerprint
→ 完整内容 SHA256，适合最终验收或同名替换风险较高的数据
```

迁移规则：

```text
quick → quick：允许增量复用
strong → strong：允许增量复用
quick → strong：完整升级重算
strong → quick：退出码 7，拒绝覆盖旧 Sidecar
```

### 2.3 Analyzer 返回值

GUI 至少记录：

```text
exit_code
stdout
stderr
metadata_file
report_file
```

| Exit Code | 含义 |
|---:|---|
| `0` | 成功 |
| `2` | workers 参数非法 |
| `3` | 输入目录或样本加载失败 |
| `4` | 分析过程或 worker fatal |
| `5` | strict 检测到 invalid sample，拒绝覆盖正式 Sidecar |
| `6` | 原子写入失败 |
| `7` | strong → quick 降级被拒绝 |

---

## 3. DFL 已有的 Batch 2 默认值

### 3.1 Enhancement 默认值

```json
{
  "schema_version": 1,
  "training": {
    "enabled": false,
    "metadata_sampling": false
  },
  "runtime": {
    "fallback_on_optional_error": true,
    "strict_validation": false
  }
}
```

### 3.2 Sampling 默认值

```json
{
  "mode": "legacy",
  "metadata_path": null,
  "fallback_mode": "legacy_random",
  "pose_balance_strength": 0.5,
  "quality_strength": 0.5,
  "uniform_mix": 0.1,
  "min_sample_weight": 0.5,
  "max_sample_weight": 2.0,
  "min_metadata_match_ratio": 0.9,
  "seed": null,
  "log_interval_draws": 10000
}
```

这些字段被省略时，DFL 会自动使用以上默认值。

非法数值也会由 DFL 解析层执行范围限制、安全回退或 warning。

---

## 4. GUI 必须管理的训练参数

### 4.1 智能采样总开关

GUI 可以只维护一个内部字段：

```text
metadata_sampling_enabled
```

开启时必须同时传：

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

DFL 中这两个字段默认均为 `false`，所以启用智能采样时 GUI 必须显式传 `true`。

关闭时推荐直接不传 `enhancements`，即可保持原有 legacy 行为；不必重复传两个 `false`。

### 4.2 SRC / DST 模式

JSON Path：

```text
enhancements.sampling.src.mode
enhancements.sampling.dst.mode
```

建议 GUI 提供：

```text
legacy_random
legacy_uniform_yaw
pose_balanced
quality_pose_balanced
```

其中：

```text
legacy_random / legacy_uniform_yaw
→ 不依赖 Faceset Analyzer

pose_balanced / quality_pose_balanced
→ 必须存在对应侧 Metadata Sidecar
```

SRC 与 DST 应独立配置，不要自动复制另一侧的模式。

### 4.3 Metadata 路径

JSON Path：

```text
enhancements.sampling.src.metadata_path
enhancements.sampling.dst.metadata_path
```

DFL 默认值是 `null`，会自动读取：

```text
<SRC aligned>/faceset_metadata.v1.json
<DST aligned>/faceset_metadata.v1.json
```

因此使用默认 Sidecar 位置时，GUI 不应传 `metadata_path`。

只有 Sidecar 保存到其他位置时才传自定义路径。

---

## 5. 建议开放的可调参数

以下参数会实际影响智能采样行为，适合由 GUI 配置。

| 参数 | JSON Path | 默认 | 范围/取值 | 作用 |
|---|---|---:|---|---|
| `pose_balance_strength` | `enhancements.sampling.pose_balance_strength` | `0.5` | `0.0..1.0` | 稀缺姿态补偿强度 |
| `quality_strength` | `enhancements.sampling.quality_strength` | `0.5` | `0.0..1.0` | 质量分数对抽样概率的影响；仅联合模式有意义 |
| `uniform_mix` | `enhancements.sampling.uniform_mix` | `0.1` | `0.0..1.0`，建议 `0.05..0.30` | 混入均匀随机概率，避免样本长期抽不到 |
| `min_metadata_match_ratio` | `enhancements.sampling.min_metadata_match_ratio` | `0.9` | `0.0..1.0` | Metadata 可信匹配比例门槛 |
| `fallback_mode` | `enhancements.sampling.fallback_mode` | `legacy_random` | `legacy_random` / `legacy_uniform_yaw` | Metadata 不可用时的传统回退模式 |
| `fallback_on_optional_error` | `enhancements.runtime.fallback_on_optional_error` | `true` | bool | optional Metadata 问题是否允许回退 |
| `strict_validation` | `enhancements.runtime.strict_validation` | `false` | bool | Metadata 缺失、损坏或回退时是否阻止训练 |
| `seed` | `enhancements.sampling.seed` | `null` | int/null | 固定智能采样随机流，主要用于验收与对照实验 |

GUI 只有在用户修改这些值时才需要传入；保持默认值时可以省略。

---

## 6. GUI 不需要管理的默认字段

以下字段已经由 DFL 提供默认值，首版 GUI 不需要保存、显示或传递：

```text
enhancements.schema_version = 1
enhancements.sampling.min_sample_weight = 0.5
enhancements.sampling.max_sample_weight = 2.0
enhancements.sampling.log_interval_draws = 10000
```

说明：

- `schema_version` 省略时，DFL 使用当前支持版本；
- `min_sample_weight` / `max_sample_weight` 是底层安全边界；
- `log_interval_draws` 只控制采样统计日志频率；
- 不应在 GUI 内复制这些默认值作为第二套配置来源。

未来确有高级调试需求时，可以再开放，但默认仍应由 DFL 维护。

---

## 7. 最小训练 JSON

### 7.1 SRC / DST 都使用 Pose Balanced

```json
{
  "enhancements": {
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "src": {
        "mode": "pose_balanced"
      },
      "dst": {
        "mode": "pose_balanced"
      }
    }
  }
}
```

省略的参数由 DFL 自动补为默认值。

### 7.2 SRC 使用 Quality + Pose，DST 使用 Pose

```json
{
  "enhancements": {
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "src": {
        "mode": "quality_pose_balanced"
      },
      "dst": {
        "mode": "pose_balanced"
      }
    }
  }
}
```

这里会自动使用：

```text
pose_balance_strength=0.5
quality_strength=0.5
uniform_mix=0.1
min_metadata_match_ratio=0.9
fallback_mode=legacy_random
fallback_on_optional_error=true
strict_validation=false
```

### 7.3 用户修改部分参数

```json
{
  "enhancements": {
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "pose_balance_strength": 0.7,
      "uniform_mix": 0.15,
      "src": {
        "mode": "quality_pose_balanced"
      },
      "dst": {
        "mode": "pose_balanced"
      }
    },
    "runtime": {
      "strict_validation": true
    }
  }
}
```

只有被用户修改的值需要写入 JSON。

---

## 8. GUI 开发 Agent 最小任务

1. 增加 `faceset-analyze` 调用及 SRC/DST 独立执行；
2. 支持 Analyzer 输入目录、可选输出路径、模式、workers、fingerprint 和 strict；
3. 保存 Analyzer 退出码、stdout、stderr 和报告路径；
4. 在现有 `--options-json` 中合并 `enhancements`，不得覆盖其他训练参数；
5. 智能采样开启时生成双 Gate；关闭时可完全省略 `enhancements`；
6. 支持 SRC/DST 独立 mode 和可选 metadata_path；
7. 只输出用户修改的可调参数；
8. 不输出第 6 节的 DFL 默认字段；
9. 使用 `json.dumps()` 和 subprocess 参数数组传递 JSON；
10. 非空 `--options-json` 时继续显式传 `--force-model-name`；
11. 支持中文、空格和 Unicode 路径；
12. 记录 SRC/DST 的 requested、effective、metadata status 与 fallback reason，供后续 GPU 验收。