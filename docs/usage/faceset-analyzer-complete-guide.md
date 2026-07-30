# Faceset Analyzer 完整使用说明

> 文档状态：ACTIVE / REVIEW-GATED  
> 适用分支：`codex/batch2-metadata-sampling-design` 及后续修复分支  
> 面向对象：DeepFaceLab 使用者、训练脚本维护者、GUI 调用方、后续开发 Agent  
> 最后更新：2026-07-29  
> 相关功能：Faceset Metadata、Pose-balanced Sampling、Quality + Pose Sampling

---

## 1. 文档目的

Faceset Analyzer 是 Batch 2 新增的离线数据集分析工具。它读取已经完成切脸的 aligned faceset，计算每张样本的静态姿态、清晰度、曝光和有效性信息，并在 faceset 目录旁生成 Metadata Sidecar JSON。

Analyzer 本身不训练模型、不修改图片、不删除低质量样本，也不修改 `faceset.pak` 格式。训练器在明确启用 Metadata Sampling 后读取 Sidecar，并据此调整样本抽取概率。

完整数据流：

```text
原始视频 / 图片
    ↓
Extract + Align
    ↓
aligned faceset
    ↓
Faceset Analyzer（离线执行）
    ↓
faceset_metadata.v1.json
    ↓
SAEHD 训练启动
    ↓
Metadata Loader
    ↓
legacy / pose_balanced / quality_pose_balanced
```

---

## 2. Faceset Analyzer 与 XSeg 的区别

Faceset Analyzer 不是 XSeg 的替代品，两者解决的问题不同。

| 对比项 | Faceset Analyzer | XSeg |
|---|---|---|
| 主要目的 | 计算姿态、质量与数据集统计，用于采样 | 生成或使用人脸分割 Mask |
| 是否需要人工标注 | 不需要 | 训练 XSeg 时通常需要标注 |
| 是否训练新模型 | 不训练 | XSeg 训练会训练分割模型 |
| 是否修改 aligned 图片 | 不修改 | 标签可能写入 DFLIMG Metadata |
| 是否每次训练都要执行 | 不需要 | 取决于 Mask 工作流 |
| 训练时用途 | 调整样本抽取概率 | Masked Training / Merge Mask |
| 输出 | 独立 JSON Sidecar | XSeg 标签或模型结果 |

结论：

- 使用传统随机或传统 uniform yaw 训练时，可以完全不运行 Faceset Analyzer。
- 只有启用 `pose_balanced` 或 `quality_pose_balanced` 时，Analyzer 才是前置步骤。
- XSeg 是否需要执行，与是否启用 Faceset Analyzer 没有直接依赖关系。

---

## 3. 是否每套素材都需要分析

Analyzer 的执行单位是“一个确定版本的 aligned faceset”，不是模型，也不是训练会话。

### 3.1 需要分别分析 SRC 和 DST 的情况

如果 SRC 和 DST 都准备启用 Metadata Sampling，应分别执行：

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned

./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_dst/aligned
```

默认输出分别位于：

```text
workspace/data_src/aligned/faceset_metadata.v1.json
workspace/data_dst/aligned/faceset_metadata.v1.json
```

同一个 aligned faceset 被多个模型复用时，可以共用 Sidecar，不需要按模型重复分析。

### 3.2 不需要每次训练前重复执行

下列情况不需要重新分析：

- 只修改 SAEHD 模型参数；
- 继续训练同一个模型；
- 切换 batch size、optimizer 或保存间隔；
- 只修改 Merge 参数；
- aligned faceset 内容没有变化。

### 3.3 必须重新分析或增量更新的情况

出现以下任一情况后，应更新 Metadata：

- 新增 aligned 图片；
- 删除 aligned 图片；
- 替换图片但保留原文件名；
- 重新 Extract / Align；
- 清理模糊脸、错脸或重复脸；
- Ordinary Faceset 被重新 Pack；
- `faceset.pak` 被重新生成；
- 文件内容、大小、修改时间或 packed offset 发生变化；
- Analyzer 版本或 Metadata Schema 版本升级；
- 训练日志提示 `partial_match`、`fingerprint_mismatch` 或 stale signature。

少量变化优先使用增量模式：

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned \
  --incremental
```

不确定旧 Sidecar 是否可信时，使用强制全量分析：

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned \
  --force
```

---

## 4. 当前 Review Gate

本分支经过独立代码审查后发现 Analyzer、Loader、Sampling Runtime 和 Windows spawn 链路仍有阻断问题。修复 Ticket 14—21 完成并通过最终验收前：

- Analyzer 可用于生成报告和观察数据集分布；
- 不建议在正式训练中依赖 `pose_balanced`；
- 不建议把 `quality_pose_balanced` 视为已完成生产验收；
- 不得仅凭日志中的 `effective: pose_balanced` 判断姿态采样已经正确生效；
- Windows 多进程训练必须等待真实 spawn 测试通过。

修复入口：

```text
.scratch/batch2-training-data-and-sampling/reports/
  batch2-independent-code-review-and-remediation-plan.md

.scratch/batch2-training-data-and-sampling/issues/
  14-unify-metadata-bucket-schema-and-e2e-contract.md
  ...
  21-docs-handoff-windows-gpu-final-acceptance.md
```

---

## 5. 前置要求

### 5.1 Python

- 最低 Python 3.9；
- macOS 项目开发环境统一使用 `./.venv/bin/python`；
- Windows 应使用项目实际打包环境或对应虚拟环境 Python；
- 不要混用系统 Python 与项目环境。

### 5.2 输入目录

`--input-dir` 必须指向 aligned faceset 目录，支持：

- Ordinary：目录中包含 DFL aligned 图片；
- Person：按人物子目录组织的 aligned 图片；
- Packed：目录中包含 `faceset.pak`。

不要把以下目录传给 Analyzer：

- 原始视频帧目录；
- 未完成 Align 的普通照片目录；
- 模型保存目录；
- Merge 输出目录；
- XSeg 模型目录。

### 5.3 路径

路径必须支持中文、空格和 Unicode。建议始终使用引号：

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir "/Users/name/换脸项目/人物 A/aligned"
```

Windows CMD：

```bat
python main.py faceset-analyze ^
  --input-dir "D:\换脸项目\人物 A\aligned"
```

PowerShell：

```powershell
python main.py faceset-analyze `
  --input-dir 'D:\换脸项目\人物 A\aligned'
```

---

## 6. 基础命令

### 6.1 默认输出

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned
```

默认生成：

```text
<input-dir>/faceset_metadata.v1.json
<input-dir>/faceset_metadata_report.v1.json
```

### 6.2 自定义 Metadata 路径

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned \
  --output-file ./workspace/metadata/src_faceset_metadata.v1.json
```

训练时如果 Sidecar 不位于默认目录，必须通过训练配置显式指定 `metadata_path`。

### 6.3 自定义报告路径

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned \
  --report-file ./workspace/reports/src_faceset_report.v1.json
```

### 6.4 严格模式

```bash
./.venv/bin/python main.py faceset-analyze \
  --input-dir ./workspace/data_src/aligned \
  --strict
```

严格模式用于验收和数据清理：如果发现损坏图片、非法 Landmark 或其他无效样本，应返回非零退出码，而不是只记录问题后继续成功退出。

---

## 7. CLI 参数

| 参数 | 必填 | 当前语义 | 建议 |
|---|---:|---|---|
| `--input-dir` | 是 | aligned faceset 目录 | 始终使用绝对路径或明确相对路径 |
| `--output-file` | 否 | Metadata JSON 输出路径 | 默认路径最容易被训练器自动发现 |
| `--report-file` | 否 | 人类和机器可读报告路径 | 建议保留用于验收 |
| `--incremental` | 否 | 复用签名未变化的旧记录 | faceset 少量变化后使用 |
| `--force` | 否 | 忽略旧 Sidecar，全量重算 | 数据状态不可信时使用 |
| `--strict` | 否 | 无效样本导致非零退出 | CI、发布前验收使用 |
| `--workers` | 否 | 计划中的并行分析参数 | Ticket 17 修复前不要依赖 |
| `--strong-fingerprint` | 否 | 计划中的完整内容哈希 | Ticket 17 修复前不要依赖 |

重要说明：当前分支中 `--workers` 和 `--strong-fingerprint` 已暴露 CLI，但尚未形成可信的运行时效果和端到端验收。Ticket 17 必须选择“真正实现”或“移除空壳参数”，不得继续保留无效参数并在文档中宣称已生效。

---

## 8. 输出文件

### 8.1 `faceset_metadata.v1.json`

这是训练器使用的 Sidecar，主要包含：

```text
schema_version
analyzer_version
created_at
dataset
analysis_config
summary
samples[]
```

单样本记录包含：

- 稳定 `sample_id`；
- 规范化 `sample_key`；
- 文件或 packed signature；
- 图片有效性；
- Landmark 有效性；
- pitch / yaw / roll；
- yaw / pitch bucket；
- 清晰度原始值；
- 曝光相关指标；
- 归一化 quality score；
- issues。

该文件是运行时输入，不建议人工修改。人工修改后可能造成：

- JSON 结构错误；
- fingerprint 不匹配；
- bucket 名称无法识别；
- 非有限浮点数；
- 样本映射错误；
- 训练回退到 legacy。

### 8.2 `faceset_metadata_report.v1.json`

报告主要用于：

- 确认 Analyzer 是否成功；
- 检查总样本数、有效样本数和无效样本数；
- 检查姿态分布；
- 检查质量分布；
- 检查增量复用、重算、新增和删除数量；
- 记录耗时和处理速度；
- 为 Windows GPU 验收提供数据集证据。

报告不是训练器的唯一可信输入。训练器应读取 Metadata Sidecar，并重新验证 Schema、签名和匹配率。

### 8.3 `.bak` 文件

更新已有 Metadata 时，原子存储可能创建：

```text
faceset_metadata.v1.json.bak
```

它用于写入失败或数据损坏时人工恢复。恢复前必须确认 `.bak` 对应当前 faceset；旧备份不能绕过 signature 检查。

---

## 9. Analyzer 报告如何判断

完成后至少检查：

```text
total_samples == 当前 faceset 实际样本数
invalid_samples 可解释
usable_samples / valid_samples 不异常偏低
yaw 分布不是全部 unknown
quality_score 全部为有限值
incremental 计数与本次实际修改一致
Metadata 和 Report 文件均成功写入
进程退出码为 0（严格模式按规则判断）
```

### 9.1 异常信号

以下现象不能直接进入智能采样训练：

- total samples 为 0；
- 所有 yaw bucket 都为空或 unknown；
- pose valid 全部为 false；
- 大量图片加载失败；
- Metadata JSON 校验失败；
- 增量运行声称全部复用，但实际替换过图片；
- Packed 文件已重建，但 fingerprint 没有变化；
- Report 与 Metadata summary 数量不一致。

---

## 10. 训练采样模式

| 模式 | 是否依赖 Analyzer | 行为 |
|---|---:|---|
| `legacy` | 否 | 根据旧 `uniform_yaw` 设置解析为传统模式 |
| `legacy_random` | 否 | 传统随机采样 |
| `legacy_uniform_yaw` | 否 | 传统 128 yaw 桶采样 |
| `pose_balanced` | 是 | 根据静态姿态分布提升稀缺角度样本概率 |
| `quality_pose_balanced` | 是 | 姿态平衡后再结合质量分数加权 |

智能采样只调整概率：

- 不会自动删除模糊样本；
- 不会保证低质量样本永远不被抽到；
- 不会修改 Loss；
- 不会改变网络结构；
- 不会改变 checkpoint 格式；
- 不会替代人工 faceset 清理。

---

## 11. 正确的 `--options-json` 形状

### 11.1 重要约束

当前训练入口接受的是 JSON 字符串，不是文件路径：

```bash
--options-json '{"batch_size":8}'
```

当前不支持：

```bash
--options-json config.json
--options-json @config.json
```

Batch 2 配置必须位于顶层 `enhancements` 中。

双 Gate 必须同时开启：

```text
enhancements.training.enabled == true
enhancements.training.metadata_sampling == true
```

### 11.2 扁平采样配置（向后兼容）

扁平 `enhancements.sampling` 字段同时作为 SRC/DST 的 base：

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
      "seed": 42,
      "log_interval_draws": 10000
    },
    "runtime": {
      "fallback_on_optional_error": true,
      "strict_validation": false
    }
  }
}
```

默认 `metadata_path=null` 时：

- SRC 从 SRC aligned 目录读取 Sidecar；
- DST 从 DST aligned 目录读取 Sidecar；
- 两侧路径与 seed 独立派生。

### 11.3 正式 SRC/DST 侧别配置（Ticket 15 已实现）

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
      "uniform_mix": 0.1,
      "src": {
        "mode": "quality_pose_balanced",
        "quality_strength": 0.7
      },
      "dst": {
        "mode": "pose_balanced"
      }
    }
  }
}
```

解析优先级：默认值 → 扁平 base → `sampling.<role>` override。  
只有 `src` 时，DST 使用 base，**不会**自动复制 SRC。  
错误顶层 `training`/`sampling`/`runtime`（不在 `enhancements` 内）会输出明确 warning。

---

## 12. 启动示例

### 12.1 保持传统随机采样

不传 enhancements 即保持 legacy 行为：

```bash
./.venv/bin/python main.py train \
  --training-data-src-dir ./workspace/data_src/aligned \
  --training-data-dst-dir ./workspace/data_dst/aligned \
  --model-dir ./workspace/model \
  --model SAEHD
```

### 12.2 当前分支的全局智能采样示例

> 仅用于修复后验收。Ticket 14—21 完成前不建议用于正式模型。

```bash
./.venv/bin/python main.py train \
  --training-data-src-dir ./workspace/data_src/aligned \
  --training-data-dst-dir ./workspace/data_dst/aligned \
  --model-dir ./workspace/model \
  --model SAEHD \
  --force-model-name my_model \
  --options-json '{"enhancements":{"schema_version":1,"training":{"enabled":true,"metadata_sampling":true},"sampling":{"mode":"quality_pose_balanced","fallback_mode":"legacy_random","pose_balance_strength":0.5,"quality_strength":0.5,"uniform_mix":0.1,"min_sample_weight":0.5,"max_sample_weight":2.0,"min_metadata_match_ratio":0.9},"runtime":{"fallback_on_optional_error":true,"strict_validation":false}}}'
```

非空 `--options-json` 会触发 silent start。为避免自动选择到错误模型，建议同时传入：

```text
--force-model-name <目标模型名>
```

---

## 13. 启动日志检查

训练启动后，应分别看到 SRC 和 DST 日志：

```text
[Sampling][src]
  requested: quality_pose_balanced
  effective: quality_pose_balanced
  metadata: loaded, matched=1200/1200 (100.0%)
  fingerprint: ...
  fallback: none
```

但日志 `effective` 只是运行时解析结果，不等同于算法端到端正确。最终验收还必须检查：

- Analyzer bucket 可被 Loader 识别；
- `pose_valid` 不是全 false；
- yaw bucket IDs 不是全 `-1`；
- 采样概率有限且总和为 1；
- 稀缺 yaw bucket 的实际抽取比例按预期提高；
- Windows 子进程可以持续获取 index；
- save / exit / resume 不改变配置和数据契约。

### 13.1 常见 fallback

| 日志 | 含义 | 建议 |
|---|---|---|
| `metadata: missing` | 默认 Sidecar 不存在 | 运行 Analyzer |
| `invalid_file` | JSON 损坏或结构错误 | 备份后 `--force` 重建 |
| `unsupported_schema` | Schema 高于当前支持版本 | 使用匹配代码版本重建 |
| `partial_match` | 只有部分记录可可信匹配 | 增量或全量重建 |
| `fingerprint_mismatch` | 数据集内容与 Sidecar 不一致 | 不要强行使用旧 Metadata |
| `stale_signature` | 文件名相同但内容签名变化 | 对变化样本重算 |
| `policy_not_available` | requested mode 未正确注册 | 检查版本或回退 |

---

## 14. Ordinary 与 Packed 工作流

### 14.1 Ordinary

推荐顺序：

```text
Extract / Align
→ 人工清理 faceset
→ 可选 XSeg
→ Faceset Analyzer
→ 检查报告
→ 启动训练
```

如果清理后新增或删除文件：

```bash
python main.py faceset-analyze \
  --input-dir "D:\workspace\data_src\aligned" \
  --incremental
```

### 14.2 Packed

推荐顺序：

```text
清理 Ordinary aligned
→ Pack Faceset
→ 对 Packed 目录运行 Analyzer
→ 不再修改包
→ 启动训练
```

重新 Pack 后必须重新分析，因为：

- packed offset 可能变化；
- 包内样本顺序可能变化；
- 数据集 fingerprint 应变化；
- 旧 Sidecar 不能默认视为仍然有效。

不要把 Ordinary 模式生成的 Sidecar 未经验证直接复制给 Packed 目录。

---

## 15. 质量分数的正确理解

`quality_score` 是同一 faceset 内的相对启发式分数，通常由以下指标组成：

- Laplacian 清晰度；
- 暗区比例；
- 高光剪切比例；
- 曝光分数；
- faceset 全局百分位归一化。

它不代表：

- 最终换脸视频的主观画质；
- 身份相似度；
- 脸型匹配度；
- 表情准确度；
- 遮挡质量；
- XSeg Mask 质量；
- 训练 Loss 大小。

低 quality score 样本只会被适度降权，不应自动删除。明显错脸、严重遮挡、错误 Align、非目标人物等问题仍应人工清理。

---

## 16. 故障排查

### 16.1 Analyzer 找不到样本

检查：

- 输入是否为 aligned 目录；
- Packed 目录是否包含有效 `faceset.pak`；
- 图片是否为项目支持的 DFL aligned 样本；
- 路径是否拼写正确；
- 当前用户是否有读取权限。

### 16.2 Analyzer 成功但训练提示 missing

检查：

- Sidecar 是否位于每一侧 aligned 根目录；
- 是否使用了自定义 `--output-file`；
- 自定义 `metadata_path` 是否正确；
- 配置是否真的放在顶层 `enhancements`；
- `training.enabled` 与 `metadata_sampling` 是否同时为 true。

### 16.3 日志显示 LOADED，但姿态采样没有效果

检查：

- yaw bucket 名称是否符合统一契约；
- Loader 的 `pose_valid` 是否至少有一部分为 true；
- yaw IDs 是否全为 `-1`；
- 实际 probabilities 是否非均匀；
- Ticket 14 的端到端测试是否通过；
- 是否误把 quality-only 变化当成 pose balance。

### 16.4 增量报告统计不可信

在 Ticket 18 完成前，增量 summary 可能受嵌套字段与旧顶层字段不一致影响。遇到统计异常时使用：

```bash
python main.py faceset-analyze --input-dir <dir> --force
```

并比较全量 Metadata 中的真实 sample records，而不是只看旧增量报告。

### 16.5 Windows 子进程训练崩溃或超时

检查：

- 是否启用了 `pose_balanced` 或 `quality_pose_balanced`；
- 是否进入 `SubprocessGenerator`；
- `WeightedIndexHostClient` 是否可在 spawn 下序列化；
- 子进程中 `_host_ref` 是否被正确移除；
- Queue 是否使用可靠的 timeout；
- Ticket 16 的 spawn 测试是否通过。

在修复前，安全回退是关闭 Metadata Sampling 并使用 legacy，而不是扩大异常捕获吞掉 worker 崩溃。

---

## 17. 发布前最小验收清单

### Analyzer

- [ ] Ordinary 全量分析通过；
- [ ] Packed 全量分析通过；
- [ ] 中文、空格、Unicode 路径通过；
- [ ] 损坏样本在非严格模式记录、严格模式失败；
- [ ] 增量新增、修改、删除计数准确；
- [ ] 强 fingerprint 真实读取内容；
- [ ] `--workers` 真实改变并行执行，或已从 CLI 移除。

### Metadata Loader

- [ ] Analyzer 输出可直接加载；
- [ ] canonical yaw / pitch bucket 100% 可识别；
- [ ] stale signature 不计入 matched；
- [ ] 重名或 sample ID collision 安全处理；
- [ ] quality、pose 和 metadata validity 分开计算；
- [ ] 所有数组 shape、dtype 和长度正确。

### Sampling

- [ ] legacy 关闭路径与基线一致；
- [ ] pose-balanced 概率非均匀且符合预期；
- [ ] quality + pose 组合概率有限、正数、和为 1；
- [ ] SRC/DST 配置按契约独立；
- [ ] optional Metadata 错误可回退；
- [ ] 核心 SampleLoader、worker、TensorFlow 错误不得被吞掉。

### Windows GPU

- [ ] `spawn` 多进程 generator 持续运行；
- [ ] FP32 + AdaBelief；
- [ ] Ordinary / Packed；
- [ ] 四种采样模式；
- [ ] 手动保存、自动保存、退出保存；
- [ ] 退出后恢复训练；
- [ ] 记录实际抽样分布、iter time 和显存；
- [ ] 无静默 fallback、死锁和 30 秒超时。

---

## 18. 安全结论

在 Ticket 14—21 验收完成前，推荐使用方式是：

```text
Faceset Analyzer：可用于数据集报告和开发验证
Metadata Sampling：仅用于修复测试，不用于正式模型结论
正式训练：继续使用 legacy_random 或 legacy_uniform_yaw
```

最终解除 Review Gate 的唯一条件是：

```text
端到端 Schema 测试 PASS
+
Windows spawn PASS
+
Windows FP32 + AdaBelief 真实训练 PASS
+
Ordinary / Packed PASS
+
Save / Exit / Resume PASS
+
文档与源码一致
```

任何单元测试数量、compileall、synthetic-only 测试或日志中的 `effective` 字样，都不能单独替代上述最终验收。