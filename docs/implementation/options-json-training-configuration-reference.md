# `--options-json` 训练配置权威参考

> 文档状态：**ACTIVE / SINGLE SOURCE OF TRUTH**  
> 适用分支：`codex/batch2-metadata-sampling-design` 及后续合并分支  
> 首次建立：2026-07-29  
> 当前文档版本：v1.1  
> 维护原则：任何新增、删除、重命名或改变语义的训练参数，必须在同一提交或同一 PR 中同步更新本文档、对应测试和示例。

---

## 1. 文档定位

本文档专门维护 DeepFaceLab TF2.x 的：

```text
main.py train --options-json '<JSON_OBJECT>'
```

配置接口，包括：

- 当前 `--options-json` 的真实传递和覆盖行为；
- 已实现的 SAEHD 顶层训练参数；
- Batch 2 Metadata / Sampling 新增参数；
- 参数类型、默认值、范围、持久化与回退语义；
- Windows CMD、PowerShell、批处理和 GUI 的调用示例；
- 新参数接入 `--options-json` 时必须完成的代码与测试检查；
- 参数变更记录。

本文档是 `--options-json` 参数的权威登记表。设计文档、Ticket、UI 表单、启动脚本和用户文档中的参数名与默认值都必须与本文档一致。

### 1.1 状态标记

| 状态 | 含义 |
|---|---|
| `IMPLEMENTED` | 当前分支源码已支持并可通过 `--options-json` 注入 |
| `BATCH2-PLANNED` | Batch 2 已冻结设计，等待对应 Ticket 实现 |
| `EXPERIMENTAL` | 源码存在，但不属于当前正式验收主线 |
| `DEFERRED` | 明确延期，不得在当前批次使用 |
| `REMOVED` | 已移除，仅保留迁移说明 |

不得把 `BATCH2-PLANNED` 参数描述成当前已经可用。

---

## 2. 当前调用链

当前真实调用链：

```text
main.py
  --options-json
      ↓
mainscripts/Trainer.py
  options_json=...
      ↓
models/ModelBase.py::__init__
  self.options_json
      ↓
ModelBase.load_train_step_config()
  json.loads(options_json)
  覆盖 self.options
      ↓
Model_SAEHD.on_initialize_options()
  读取、补默认值、执行模型级校验
      ↓
Model_SAEHD.on_initialize()
  构建真实训练运行时
      ↓
ModelBase.save()
  将 self.options 持久化到 <model>_data.dat
```

对应源码：

- `main.py::process_train`
- `mainscripts/Trainer.py::trainerThread`
- `models/ModelBase.py::__init__`
- `models/ModelBase.py::load_train_step_config`
- `models/ModelBase.py::save`
- `models/Model_SAEHD/Model.py::on_initialize_options`
- `models/Model_SAEHD/Model.py::on_initialize`

---

## 3. 当前基础行为

### 3.1 参数格式

`--options-json` 接收的是一个 **JSON 字符串**，不是 JSON 文件路径。

正确：

```bash
--options-json '{"batch_size":8,"precision":"fp32"}'
```

当前不支持：

```bash
--options-json config.json
--options-json @config.json
```

如后续增加 `--options-json-file`，必须作为独立参数设计，不得偷偷改变当前参数语义。

### 3.2 顶层必须是 JSON Object

推荐且受支持的形状：

```json
{
  "batch_size": 8,
  "precision": "fp32",
  "optimizer": "adabelief",
  "enhancements": {}
}
```

不得使用数组、字符串或数字作为根节点。

### 3.3 非空 `--options-json` 会触发静默启动

当前 `ModelBase` 行为：

```text
options_json 非空
→ silent_start=True
→ 自动选择最新模型（未指定 force model 时）
→ 自动选择 Best GPU
→ 不进入普通模型选择交互
```

因此 GUI 或自动化调用建议同时显式传入：

```text
--force-model-name <目标模型名>
```

避免“最新修改模型”变化后启动到错误模型。

### 3.4 配置优先级

固定优先级：

```text
内建默认值
→ 已保存 <model>_data.dat options
→ --options-json 显式覆盖
→ 交互输入（仅无 non-interactive override 时）
```

Batch 2 Sampling 实现后，非空 `--options-json` 不得再次弹出 Sampling 交互并覆盖注入值。

### 3.5 持久化

成功注入的参数进入 `self.options`。模型后续成功执行 `save()` 时，当前 `self.options` 会写入：

```text
<model_name>_data.dat
```

这意味着 `--options-json` 默认不是“仅本次临时参数”。调用方在覆盖长期模型前必须清楚其持久化影响。

### 3.6 当前类型转换

`ModelBase.load_train_step_config()` 当前对 **顶层值** 执行：

| 输入 | 顶层转换 |
|---|---|
| JSON `true/false` | Python `bool` |
| 字符串 `"true"/"false"` | Python `bool` |
| JSON integer/float | 保持数值 |
| 数字字符串 | 尝试转为 `int/float` |
| 其他字符串 | 保持字符串 |
| object/array/null | 原样传递 |

特殊兼容：

```text
lr_dropout=true  → "y"
lr_dropout=false → "n"
```

嵌套对象不会由 `ModelBase` 递归转换。`enhancements` 内部字段必须由 `EnhancementConfig` / `SamplingConfig` 自行严格解析和校验。

### 3.7 解析失败

当前行为：

```text
JSON 解析或注入失败
→ 输出 [GUI_OPTIONS] 错误日志
→ 不抛出为 Metadata missing
→ 使用原有/默认 options 继续后续初始化
```

Batch 2 不得把损坏的 `--options-json` 误判为 Metadata 文件缺失或 Sampling fallback。

### 3.8 未知字段

当前 `ModelBase` 会把未知顶层字段写入 `self.options`，但这不代表模型会使用它。

规则：

- 只有本文档登记、源码消费且测试覆盖的字段才算受支持；
- UI 不得因为未知字段未报错就认为配置生效；
- Batch 2 启动日志必须输出 requested/effective/fallback，证明实际生效模式。

---

## 4. 结构参数保护

当前 `ModelBase` 对以下顶层结构参数进行保护：

```text
resolution
archi
ae_dims
e_dims
d_dims
d_mask_dims
head_name
```

行为：

```text
新模型 / iter == 0
→ 可以通过 --options-json 注入

已有模型 / iter != 0
→ 忽略这些结构参数的动态覆盖
```

### 4.1 原因

这些参数可能改变模型网络和权重 shape。已有模型动态修改会导致权重不兼容或错误加载。

### 4.2 UI 要求

GUI 应把这些字段标记为：

```text
仅新模型可设置
```

不得向用户显示为已有模型可热修改。

---

## 5. 已实现的常用 SAEHD 顶层参数

以下登记基于当前 `Model_SAEHD/Model.py`。实际边界仍以模型级校验为准。

### 5.1 模型结构

| JSON Key | 类型 | 当前默认 | 状态 | 说明 |
|---|---:|---:|---|---|
| `resolution` | int | `128` | `IMPLEMENTED` | 64-640；新模型使用；按架构调整到 16/32 倍数 |
| `face_type` | string | `"f"` | `IMPLEMENTED` | `h/mf/f/wf/head` |
| `archi` | string | `"liae-ud"` | `IMPLEMENTED` | SAEHD 架构字符串 |
| `ae_dims` | int | `256` | `IMPLEMENTED` | 新模型结构参数 |
| `e_dims` | int | `64` | `IMPLEMENTED` | 新模型结构参数 |
| `d_dims` | int | `64` | `IMPLEMENTED` | 新模型结构参数 |
| `d_mask_dims` | int | 派生值 | `IMPLEMENTED` | 新模型结构参数 |

### 5.2 训练运行参数

| JSON Key | 类型 | 当前默认 | 状态 | 说明 |
|---|---:|---:|---|---|
| `batch_size` | int | `1`/设备建议值 | `IMPLEMENTED` | 训练 batch |
| `precision` | string | `"fp32"` | `IMPLEMENTED` | `fp32/fp16/bf16`；Batch 2 正式验收仅 fp32 |
| `optimizer` | string | `"adabelief"` | `IMPLEMENTED` | `adabelief/lion/rmsprop`；Batch 2 正式主线 AdaBelief |
| `models_opt_on_gpu` | bool | `true` | `IMPLEMENTED` | 模型和 optimizer 放置策略 |
| `opt_states_on_gpu` | bool | `true` | `IMPLEMENTED` | optimizer state 放置策略 |
| `lr_dropout` | string | `"n"` | `IMPLEMENTED` | `n/y/cpu` |
| `random_warp` | bool | `true` | `IMPLEMENTED` | 随机扭曲 |
| `random_hsv_power` | float | `0.0` | `IMPLEMENTED` | 0.0-0.3 |
| `masked_training` | bool | `true` | `IMPLEMENTED` | Masked training |
| `eyes_mouth_prio` | bool | `false` | `IMPLEMENTED` | 眼口优先 |
| `uniform_yaw` | bool | `false` | `IMPLEMENTED` | 传统 128 格 yaw 采样 |
| `blur_out_mask` | bool | `false` | `IMPLEMENTED` | Mask 外模糊 |
| `ct_mode` | string | `"none"` | `IMPLEMENTED` | `none/rct/lct/mkl/idt/sot` |
| `clipgrad` | bool | `false` | `IMPLEMENTED` | 梯度裁剪 |
| `pretrain` | bool | `false` | `IMPLEMENTED` | 预训练模式 |

### 5.3 Loss / GAN 相关

| JSON Key | 类型 | 当前默认 | 状态 | 说明 |
|---|---:|---:|---|---|
| `gan_power` | float | `0.0` | `IMPLEMENTED` | 0.0-5.0 |
| `gan_patch_size` | int | `resolution/8` | `IMPLEMENTED` | GAN 开启时使用 |
| `gan_dims` | int | `16` | `IMPLEMENTED` | GAN 开启时使用 |
| `true_face_power` | float | `0.0` | `IMPLEMENTED` | 仅 DF 架构有效 |
| `face_style_power` | float | `0.0` | `IMPLEMENTED` | 0.0-100.0 |
| `bg_style_power` | float | `0.0` | `IMPLEMENTED` | 0.0-100.0 |

### 5.4 ModelBase 通用参数

| JSON Key | 类型 | 常用默认 | 状态 | 说明 |
|---|---:|---:|---|---|
| `autobackup_hour` | int | `0` | `IMPLEMENTED` | 自动备份周期 |
| `write_preview_history` | bool | `false` | `IMPLEMENTED` | 预览历史 |
| `target_iter` | int | `0` | `IMPLEMENTED` | 目标迭代 |
| `random_src_flip` | bool | `false` | `IMPLEMENTED` | SRC 随机翻转 |
| `random_dst_flip` | bool | `true` | `IMPLEMENTED` | DST 随机翻转 |
| `save_interval_min` | int | `25` | `IMPLEMENTED` | Trainer 自动保存间隔，最小运行时为 1 分钟 |

> 说明：本文档只登记项目实际读取的参数。后续源码出现新的 `self.options[...]` 或 `load_or_def_option(...)` 字段时，必须在同一提交同步登记。

---

## 6. Batch 2 `enhancements` 配置总结构

Batch 2 新增参数全部放在顶层 `enhancements` 对象内，不把 `sampling` 错放成 `self.options` 的独立顶层键。

正式形状：

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "quality_pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": 12345,
      "log_interval_draws": 10000,
      "src": {
        "mode": "quality_pose_balanced"
      },
      "dst": {
        "mode": "pose_balanced"
      }
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

`training` / `sampling` / `runtime` 若出现在 `enhancements` 之外的 options 顶层，启动时会输出明确 warning，且不会被当作 Batch 2 配置生效。

当前状态：

```text
EnhancementConfig 基础骨架：IMPLEMENTED
training.enabled：IMPLEMENTED
training.metadata_sampling：IMPLEMENTED（双 Gate）
sampling 扁平解析：IMPLEMENTED
sampling.src / sampling.dst：IMPLEMENTED（Ticket 15）
SAEHD Generator 分侧接线：IMPLEMENTED（Ticket 15）
Windows spawn / 生产验收：PENDING（Ticket 16—21）
```

---

## 7. Batch 2 Master Gate

智能 Metadata Sampling 只有在以下两个开关都为 `true` 时才允许启用：

```text
enhancements.training.enabled == true
AND
enhancements.training.metadata_sampling == true
```

决策表：

| `training.enabled` | `metadata_sampling` | 行为 |
|---:|---:|---|
| false | false | Legacy；不加载 Metadata |
| false | true | Legacy；不加载 Metadata，并输出 gate warning |
| true | false | Legacy；不加载 Metadata |
| true | true | 按 side config 加载 Metadata 并解析 Policy |

这两个字段必须在 `--options-json` 测试中单独覆盖。

---

## 8. Batch 2 Sampling 参数注册表

### 8.0 扁平 base 与 SRC/DST 继承（Ticket 15）

解析优先级：

```text
SamplingConfig 默认值
→ enhancements.sampling 扁平 base 字段
→ enhancements.sampling.src / .dst override
```

规则：

| 场景 | SRC | DST |
|---|---|---|
| 仅扁平 `mode` 等 | 使用 base | 使用 base |
| 仅 `src` / `dst` | 各自 override（其余字段默认） | 各自 override |
| base + side | base 字段 + side 覆盖 | base 字段 + side 覆盖 |
| 只有 `src` | base+src | **base**（不复制 src） |
| 非法 `"src": "pose_balanced"` | 忽略该侧并 warning | 不受影响 |

API：

```python
enhancements.sampling_config          # base/global，仅兼容旧调用
enhancements.sampling_config_for("src")
enhancements.sampling_config_for("dst")  # 未知 role → ValueError
```

### 8.1 `mode`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.mode`（base）或 `enhancements.sampling.src.mode` / `.dst.mode` |
| 类型 | string |
| 默认 | `"legacy"` |
| 状态 | `IMPLEMENTED` |

允许值：

| 值 | 行为 |
|---|---|
| `legacy` | 保留当前 `uniform_yaw` 的选择结果 |
| `legacy_random` | 显式使用传统随机采样 |
| `legacy_uniform_yaw` | 显式使用传统 128 格 yaw 采样 |
| `pose_balanced` | 使用 Metadata yaw bucket 权重 |
| `quality_pose_balanced` | 使用 Pose + Quality 组合权重 |

未知字符串不得模糊匹配，必须回退或按严格模式失败。

### 8.2 `metadata_path`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.metadata_path`（及 side override） |
| 类型 | null 或 string |
| 默认 | `null` |
| 状态 | `IMPLEMENTED` |

解析函数：`samplelib.sampling.config.resolve_metadata_path(samples_path, configured_path)`

```text
null / ""
→ <该侧 faceset>/faceset_metadata.v1.json

相对路径
→ 相对该侧 faceset 根目录解析
→ 规范化后不得逃逸 faceset 根；`../` 逃逸抛配置错误（不 fallback 为 missing）

绝对路径
→ 允许；启动日志显式记录 resolved path
```

安全规则：

- 拒绝 `..` 越界；
- 支持中文、空格、emoji 和其他 Unicode；
- SRC/DST 各自解析，互不影响；
- 不扫描目录猜测多个 JSON；
- 训练启动时不自动运行 Analyzer。

### 8.3 `fallback_mode`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.fallback_mode` |
| 类型 | string |
| 默认 | `"legacy_random"` |
| 状态 | `IMPLEMENTED` |

只允许：

```text
legacy_random
legacy_uniform_yaw
```

不得回退到另一个 Metadata 智能模式。

### 8.4 `pose_balance_strength`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.pose_balance_strength` |
| 类型 | finite float |
| 默认 | `0.5` |
| 安全范围 | `0.0 .. 1.0` |
| 状态 | `IMPLEMENTED` |

语义：

```text
0.0 → 不做姿态补偿
0.5 → 默认保守补偿
1.0 → 最强 v1 补偿，但仍受 bucket weight 上下限约束
```

### 8.5 `quality_strength`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.quality_strength` |
| 类型 | finite float |
| 默认 | `0.5` |
| 安全范围 | `0.0 .. 1.0` |
| 状态 | `IMPLEMENTED` |

`0.5` 对应 Quality 权重大致为 `0.5 .. 1.5`。它只影响抽样概率，不乘训练 Loss。

### 8.6 `uniform_mix`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.uniform_mix` |
| 类型 | finite float |
| 默认 | `0.1` |
| 硬范围 | `0.0 .. 1.0`（推荐 `0.05 .. 0.30`） |
| 状态 | `IMPLEMENTED` |

公式：

```text
p_final = (1-uniform_mix) * p_weighted + uniform_mix * (1/N)
```

`0` 仅允许用户显式指定；任何样本仍必须因正权重保持非零概率。

### 8.7 `min_sample_weight`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.min_sample_weight` |
| 类型 | finite float |
| 默认 | `0.5` |
| 硬范围 | `0.01 .. 100.0`（解析层） |
| 状态 | `IMPLEMENTED` |

不得设置为 0。

### 8.8 `max_sample_weight`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.max_sample_weight` |
| 类型 | finite float |
| 默认 | `2.0` |
| 硬范围 | `0.01 .. 100.0`（解析层） |
| 状态 | `IMPLEMENTED` |

必须满足严格不等式：

```text
min_sample_weight < max_sample_weight
```

`min > max` 与 `min == max` 均非法：回安全默认 `0.5 / 2.0` 并输出 warning，不允许交换用户值后静默继续。

### 8.9 `min_metadata_match_ratio`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.min_metadata_match_ratio` |
| 类型 | finite float |
| 默认 | `0.9` |
| 范围 | `0.0 .. 1.0` |
| 状态 | `IMPLEMENTED` |

语义：当前 faceset 与 Metadata 精确匹配比例低于此值时，不允许启用智能 Sampling。

### 8.10 `seed`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.seed`（及 side override） |
| 类型 | null 或 integer |
| 默认 | `null` |
| 支持范围 | integer 可解析范围 |
| 状态 | `IMPLEMENTED` |

规则：

- `null`：从模型 `seed` 派生（SRC = base+1000，DST = base+2000）；
- integer / side seed：固定该侧 Batch 2 Sampling RNG；
- 不污染 NumPy 全局 RNG；
- SRC/DST 不得得到同一默认索引流；
- 不承诺不同 OS 并发调度下逐 worker batch 完全一致。

### 8.11 `log_interval_draws`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.sampling.log_interval_draws` |
| 类型 | integer |
| 默认 | `10000` |
| 安全范围 | `>= 100` |
| 状态 | `IMPLEMENTED` |

表示累计抽样多少次后输出一次 Sampling Stats。不得按每 iteration 扫描全量样本。

---

## 9. Batch 2 Runtime 参数

### 9.1 `fallback_on_optional_error`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.runtime.fallback_on_optional_error` |
| 类型 | bool |
| 默认 | `true` |
| 状态 | `IMPLEMENTED`（Ticket 20：Sampling 异常边界已收窄） |

`true` 时允许以下 **optional Metadata** 错误回退到 legacy sampling：

- Metadata missing；
- invalid JSON sidecar；
- unsupported schema；
- 匹配率不足 / stale / duplicate 等 loader 结构化状态；
- Metadata 专属 I/O 与 JSON parse 窄异常。

**不得**因本开关吞掉（无论 true/false 均 raise）：

- SampleLoader / 训练数据为空 / 权限错误；
- MemoryError / OOM；
- SampleProcessor / TensorFlow / 模型 save-load；
- WeightedIndexHost / worker 核心失败；
- 编程错误与未分类 Exception；
- 用户传入的 `--options-json` 本身损坏。

SampleLoader 在 optional Metadata try **之外**执行（Ticket 20）。

### 9.2 `strict_validation`

| 项目 | 值 |
|---|---|
| JSON Path | `enhancements.runtime.strict_validation` |
| 类型 | bool |
| 默认 | `false` |
| 状态 | `IMPLEMENTED`（Ticket 20：Sampling 已接入） |

当 `strict_validation=true` 时：

- optional Metadata missing/invalid/mismatch **拒绝**启动 metadata sampling 模式（raise）；
- 即使 `fallback_on_optional_error=true` 也不得静默回退；
- 不影响 `training.enabled=false` 时的纯 legacy 入口。

决策矩阵（optional Metadata 问题）：

| fallback_on_optional_error | strict_validation | 结果 |
|---|---|---|
| true | false | fallback + warning |
| true | true | raise |
| false | false | raise |
| false | true | raise |

---

## 10. Batch 2 推荐完整配置

### 10.1 Legacy，明确关闭增强

```json
{
  "precision": "fp32",
  "optimizer": "adabelief",
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": false,
      "metadata_sampling": false
    },
    "sampling": {
      "mode": "legacy"
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

### 10.2 Pose-balanced

```json
{
  "precision": "fp32",
  "optimizer": "adabelief",
  "uniform_yaw": false,
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.0,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": 12345,
      "log_interval_draws": 10000
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

### 10.3 Quality + Pose

```json
{
  "batch_size": 8,
  "precision": "fp32",
  "optimizer": "adabelief",
  "uniform_yaw": false,
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "quality_pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": 12345,
      "log_interval_draws": 10000
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

### 10.4 Metadata 缺失时回退到传统 uniform yaw

```json
{
  "uniform_yaw": false,
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "quality_pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_uniform_yaw"
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

`fallback_mode` 是显式模式，回退时不依赖顶层 `uniform_yaw`。

---

## 11. 命令行调用示例

下面示例省略部分必需路径参数。实际调用必须同时提供 `train` 所需目录和 `--model`。

### 11.1 PowerShell

PowerShell 推荐用单引号包裹 JSON：

```powershell
python main.py train `
  --training-data-src-dir "D:\DFL 工作区\data_src\aligned" `
  --training-data-dst-dir "D:\DFL 工作区\data_dst\aligned" `
  --model-dir "D:\DFL 工作区\model" `
  --model SAEHD `
  --force-model-name demo `
  --options-json '{"batch_size":8,"precision":"fp32","optimizer":"adabelief"}'
```

### 11.2 Windows CMD

CMD 需要转义内部双引号：

```bat
python main.py train ^
  --training-data-src-dir "D:\DFL 工作区\data_src\aligned" ^
  --training-data-dst-dir "D:\DFL 工作区\data_dst\aligned" ^
  --model-dir "D:\DFL 工作区\model" ^
  --model SAEHD ^
  --force-model-name demo ^
  --options-json "{\"batch_size\":8,\"precision\":\"fp32\",\"optimizer\":\"adabelief\"}"
```

### 11.3 `.bat` 变量

```bat
@echo off
setlocal
set "OPTIONS_JSON={\"batch_size\":8,\"precision\":\"fp32\",\"optimizer\":\"adabelief\"}"

python main.py train ^
  --training-data-src-dir "D:\DFL 工作区\data_src\aligned" ^
  --training-data-dst-dir "D:\DFL 工作区\data_dst\aligned" ^
  --model-dir "D:\DFL 工作区\model" ^
  --model SAEHD ^
  --force-model-name demo ^
  --options-json "%OPTIONS_JSON%"
endlocal
```

### 11.4 Python / GUI 进程调用

GUI 不要手工拼接一整条 shell 字符串。推荐使用参数数组：

```python
import json
import subprocess

options = {
    "batch_size": 8,
    "precision": "fp32",
    "optimizer": "adabelief",
    "enhancements": {
        "schema_version": 1,
        "training": {
            "enabled": True,
            "metadata_sampling": True,
        },
        "sampling": {
            "mode": "quality_pose_balanced",
            "metadata_path": None,
            "fallback_mode": "legacy_random",
            "pose_balance_strength": 0.5,
            "quality_strength": 0.5,
            "uniform_mix": 0.1,
            "min_sample_weight": 0.5,
            "max_sample_weight": 2.0,
            "min_metadata_match_ratio": 0.9,
            "seed": 12345,
            "log_interval_draws": 10000,
        },
        "runtime": {
            "fallback_on_optional_error": True,
            "strict_validation": False,
        },
    },
}

argv = [
    "python",
    "main.py",
    "train",
    "--training-data-src-dir",
    r"D:\DFL 工作区\data_src\aligned",
    "--training-data-dst-dir",
    r"D:\DFL 工作区\data_dst\aligned",
    "--model-dir",
    r"D:\DFL 工作区\model",
    "--model",
    "SAEHD",
    "--force-model-name",
    "demo",
    "--options-json",
    json.dumps(options, ensure_ascii=False, allow_nan=False, separators=(",", ":")),
]

subprocess.run(argv, check=True)
```

优势：

- 无需处理 CMD/PowerShell 引号转义；
- 中文路径直接作为 Unicode argv 传递；
- 避免 shell 注入；
- JSON 可以由真实对象生成；
- `allow_nan=False` 阻止非法数值。

---

## 12. Unicode 与 JSON 要求

调用方生成 JSON 时必须使用：

```python
json.dumps(
    options,
    ensure_ascii=False,
    allow_nan=False,
)
```

必须测试：

- 中文 faceset 目录；
- 路径包含空格；
- 非 ASCII person_name；
- emoji 文件或目录；
- `metadata_path` 包含中文；
- PowerShell 和 GUI argv 传递。

不得在 JSON 中写入：

- `NaN`；
- `Infinity`；
- 注释；
- 尾随逗号；
- Python `True/False/None` 文本。

JSON 标准形式是：

```text
true / false / null
```

---

## 13. 启动日志验收

Batch 2 实现后，`--options-json` 启动必须对 SRC/DST 分别输出：

```text
role
requested mode
effective mode
metadata path
metadata status
matched ratio
fallback reason
weight/probability min/mean/max
uniform mix
seed 或 random 状态
```

最低示例：

```text
[Sampling][src]
  gates: training.enabled=true, metadata_sampling=true
  requested: quality_pose_balanced
  effective: quality_pose_balanced
  config source: base+src_override
  metadata path: ...
  metadata: loaded, matched=1000/1000 (100.0%)
  trusted match: 1000/1000 (100.0%)
  fallback: none
  seed: 1042
```

不能只通过“成功注入 N 项参数”的日志判断 Batch 2 已经生效；必须断言 SRC/DST 的 `requested_mode` 分别符合配置。

---

## 14. Batch 2 必须增加的 `--options-json` 测试

Ticket 10 至少覆盖：

1. 无 `--options-json`，旧交互行为不变；
2. 非空 JSON 自动 silent start；
3. 显式 `--force-model-name` 启动正确模型；
4. 现有模型的结构参数覆盖被拒绝；
5. 新模型的结构参数可以注入；
6. `enhancements` 嵌套 object 可以 roundtrip；
7. `training.enabled=false + metadata_sampling=true` 保持 legacy；
8. `training.enabled=true + metadata_sampling=false` 保持 legacy；
9. 五种 mode 的 requested/effective 解析；
10. invalid mode 的 fallback/strict 行为；
11. `metadata_path=null` 分别自动解析 SRC/DST；
12. 中文相对 `metadata_path`；
13. 非法 `..` 路径被拒绝；
14. 数值边界、NaN/Inf 和错误类型；
15. SRC loaded / DST fallback；
16. options JSON 损坏不被误判为 Metadata missing；
17. 保存、退出、恢复后配置仍存在；
18. 非空 JSON 启动时不弹 Sampling prompt；
19. 功能关闭时不读取 Metadata；
20. 旧模型无 `enhancements` 正常加载。

推荐测试文件：

```text
tests/smoke/test_options_json_injection.py
tests/smoke/test_batch2_options_json_sampling.py
tests/smoke/test_batch2_saehd_sampling_options.py
tests/smoke/test_batch2_sampling_fallback.py
```

---

## 15. 新参数接入清单

今后任何训练参数要支持 `--options-json`，必须在同一 Ticket/PR 完成：

### 15.1 参数登记

- [ ] 本文档增加 JSON Path；
- [ ] 类型、默认值和允许范围明确；
- [ ] 标记 IMPLEMENTED / PLANNED / EXPERIMENTAL；
- [ ] 说明新模型/已有模型是否允许修改；
- [ ] 说明是否持久化；
- [ ] 说明与其他参数的优先级或互斥关系。

### 15.2 解析与校验

- [ ] `ModelBase` 或对应配置对象能够读取；
- [ ] 嵌套对象由专属 Config 解析，不复制第二套逻辑；
- [ ] 错误类型、NaN/Inf 和越界行为明确；
- [ ] 未知字段不会意外启用功能；
- [ ] 用户输入错误不会吞掉核心训练异常。

### 15.3 运行时

- [ ] 模型真实消费参数；
- [ ] requested/effective 可观测；
- [ ] 功能关闭路径不增加明显成本；
- [ ] 保存恢复语义明确；
- [ ] GUI/静默启动不会被交互重新覆盖。

### 15.4 测试

- [ ] 无 JSON 的 legacy 回归；
- [ ] JSON 注入正常路径；
- [ ] JSON 错误和边界；
- [ ] 新模型/已有模型；
- [ ] save/exit/resume；
- [ ] Windows/Unicode；
- [ ] 文档示例命令实际执行或标记 PENDING。

### 15.5 文档同步

- [ ] 更新本文档版本和更新时间；
- [ ] 更新参数注册表；
- [ ] 更新完整 JSON 示例；
- [ ] 更新变更记录；
- [ ] 相关 Ticket summary 链接到本文档。

缺少本文档同步的参数 PR 不应标记完成。

---

## 16. 安全与工程注意事项

### 16.1 不传递秘密

命令行参数可能出现在：

- 进程列表；
- 日志；
- shell 历史；
- 崩溃报告。

`--options-json` 不应包含密码、Token 或其他秘密。当前训练配置也不需要秘密字段。

### 16.2 不使用 shell 拼接用户输入

GUI 应使用 argv list 和 `shell=False`。路径、模型名和 JSON 不应拼进未经转义的命令字符串。

### 16.3 控制长度

Batch 2 配置规模适合直接传参。若未来 JSON 过大，应设计 `--options-json-file`，而不是依赖平台命令行极限。

### 16.4 不把动态状态放入配置

以下内容不得放入 `--options-json`：

- 单样本 Loss 历史；
- WeightedIndexHost 当前 cycle；
- sampler draw position；
- Metadata 全量 samples；
- GPU 临时对象；
- worker queue 状态。

`--options-json` 只传递静态、可序列化、可验证的启动配置。

---

## 17. 延期参数

以下能力不属于 Batch 2，不得提前加入当前 JSON Schema：

| 能力 | 状态 |
|---|---|
| Dynamic Loss-aware Sampling | `DEFERRED` |
| 单样本 Loss 历史持久化 | `DEFERRED` |
| Identity Geometry / 脸型 Loss | `DEFERRED`，Batch 4 |
| Source Shape Template | `DEFERRED`，Batch 5 |
| Shape-aware Merge | `DEFERRED`，Batch 6 |
| Lion 后续专项开发 | `DEFERRED/PAUSED` |
| FP16/BF16 正式验收 | `EXPERIMENTAL/PAUSED` |

未来启用时必须在本文档创建独立版本化章节，不能复用含义不相同的现有字段。

---

## 18. 变更记录

| 日期 | 文档版本 | 变更 | 关联 |
|---|---|---|---|
| 2026-07-30 | v1.1 | Ticket 15：登记 `sampling.src`/`dst`、双 Gate、metadata_path 逃逸规则、分侧日志与 API `sampling_config_for` | Ticket 15 |
| 2026-07-29 | v1.0 | 建立 `--options-json` 权威参考；登记当前 SAEHD 参数、Batch 2 Sampling Schema、调用示例和同步规则 | Batch 2 设计分支 |

---

## 19. 维护责任

以下任务修改参数时必须同步本文档：

- Batch 2 Ticket 06：`SamplingConfig`；
- Batch 2 Ticket 09：Generator/Host 运行时参数；
- Batch 2 Ticket 10：Enhancement Config、SAEHD 和 `--options-json` 接线；
- Batch 2 Ticket 11：Windows 实际验收与性能结果；
- Batch 2 Ticket 12：最终用户文档和状态收口；
- 未来所有新增训练参数的 Ticket/PR。

每个相关 summary 必须写明：

```text
--options-json 文档同步：PASS / NA / BLOCKED
文档版本：vX.Y
修改章节：...
```

不得只修改源码而把参数文档留到未来补写。
