# Batch 2：训练数据 Metadata 与 Quality / Pose Sampling 详细设计

> 文档版本：v1.0  
> 创建日期：2026-07-27  
> 设计基线：`55d4d8a4d29dc0fcc4a571d2c4f24dcdb2b7069e`  
> 当前状态：done-macos-lightweight-pending-windows (macOS 169/169 烟雾测试通过，Windows GPU 验证挂起)  
> 批次定位：承接总实施计划中的 `Batch 2：训练数据增强`  
> 训练基线：`FP32 + AdaBelief`  
> 执行原则：在不修改 SAEHD 网络、Loss、checkpoint 和 Merge 格式的前提下，交付可独立长期使用的 Metadata 分析与静态智能采样完整模块。

---

## 1. 文档目的

本文件是 Batch 2 的文件级、函数级、数据级施工说明，不是新的总体路线。

它负责回答：

1. Batch 2 交付什么完整能力，什么明确延期。
2. 普通 aligned faceset 与 Packed Faceset 如何拥有统一、稳定的样本身份。
3. Metadata Schema v1 如何定义、保存、校验、增量更新和兼容回退。
4. Faceset Analyzer 如何计算可解释的姿态、清晰度和基础质量信息。
5. Pose Sampling、Quality Sampling 与联合采样如何接入当前多进程 Generator。
6. 旧 `uniform_yaw`、旧模型、旧 faceset 和旧训练入口如何保持兼容。
7. 日志、报告、测试、性能预算、Windows FP32 验收和失败语义如何落地。
8. 每个任务修改哪些文件、依赖哪些前置、如何回退、何时才算完成。

总体实施顺序仍以：

```text
docs/implementation/enhanced-dfl-master-implementation-plan.md
```

为唯一总入口。

---

## 2. 已确认的产品决策

### 2.1 Batch 2 必须是完整品

Batch 2 完成后，用户应当可以长期执行以下闭环：

```text
分析 src / dst faceset
→ 生成并复用 Metadata sidecar
→ 选择传统或智能采样模式
→ 运行 FP32 + AdaBelief SAEHD 训练
→ 查看原始分布与实际采样分布
→ 保存、退出、恢复训练
→ Metadata 缺失或损坏时安全回退
```

以下情况不允许标记 Batch 2 完成：

- 只有 Schema，没有 Analyzer；
- Analyzer 生成文件，但训练不读取；
- 训练读取 Metadata，但采样分布没有实际变化；
- 只支持普通目录，不考虑 Packed Faceset；
- Metadata 缺失会阻断旧训练；
- 多进程 Generator 未验证；
- 关闭增强后仍改变传统采样；
- 没有用户入口、日志、报告或使用说明；
- 只有纯函数测试，没有 Windows FP32 真实训练验证记录。

### 2.2 本批次固定训练基线

```text
precision = fp32
optimizer = adabelief
```

Batch 2 的数据与采样功能不得依赖：

- Lion；
- FP16；
- BF16；
- Loss Scaling；
- GAN；
- TrueFace；
- 新增训练 Loss。

这些功能可以存在于项目中，但不属于 Batch 2 的开发目标和完成条件。

### 2.3 动态 Loss 感知采样延期

本批次只做基于图片静态属性的采样：

```text
质量
+
姿态
+
安全的随机探索
```

明确延期：

- 单图片 Loss 历史；
- LossWeightedSampler；
- 高 Loss 样本动态强化；
- 长期高 Loss 异常样本识别；
- Sampler 动态状态保存恢复；
- src / dst 单样本学习进度反馈。

该能力未来应作为独立实验批次，不得成为 Batch 3、Batch 4 或 Shape-aware Merge 的前置依赖。

### 2.4 脸型训练不在 Batch 2

Batch 2 可以产出姿态、landmark 合法性等后续几何能力所需的数据基础，但不实现：

- Shape Anchor 训练；
- Landmark / Ratio Loss；
- Identity Geometry Loss；
- Source Shape Template；
- Hybrid Landmark；
- Shape-aware Warp / Mask。

真正的脸型训练继续留在 Batch 4；Batch 5、Batch 6 分别负责几何 sidecar 与 Merge 闭环。

---

## 3. Batch 2 范围

### 3.1 本批次必须完成

```text
B2-00  冻结 Batch 2 源码、数据与性能基线
B2-01  定义稳定 Sample Identity、Dataset Fingerprint 与 Metadata Schema v1
B2-02  实现轻量 Faceset Analyzer 核心指标
B2-03  实现 Analyzer CLI、原子写入、增量更新与报告
B2-04  实现 Metadata Loader、校验、缓存和普通/Packed Faceset 兼容
B2-05  建立 Sampling Policy API 与 legacy 适配层
B2-06  实现 Pose-balanced Sampling
B2-07  实现 Quality-aware Sampling
B2-08  实现 Quality + Pose 联合采样及多进程 Index Host
B2-09  接入 Enhancement Config、SAEHD 选项、日志和安全回退
B2-10  建立单元、集成、多进程与 Windows FP32 验收
B2-11  完成兼容矩阵、使用文档、状态更新与 handoff
```

### 3.2 本批次不做

- 不修改 SAEHD 网络结构。
- 不修改 reconstruction、mask、Eyes / Mouth 或其他 Loss 公式。
- 不新增 Region / Boundary / Frequency / Identity Loss。
- 不实现 Identity Geometry 或脸型比例训练。
- 不实现动态 Loss-aware Sampling。
- 不自动删除、移动、重命名或覆盖 aligned 图片。
- 不把 Metadata 写回 DFLJPG / DFLPNG 内部数据。
- 不修改 `faceset.pak` 格式版本。
- 不修改模型权重、optimizer state、`data.dat` 核心格式或 DFM 导出格式。
- 不修改 Merge 行为。
- 不建设 Web UI、服务化 API 或大型质量评分模型。
- 不引入 ArcFace、DINO、VGG、LPIPS 等外部大型模型。

### 3.3 最终产出

```text
可复用 Metadata sidecar
+
独立 Analyzer 入口
+
legacy_random
+
legacy_uniform_yaw
+
pose_balanced
+
quality_pose_balanced
+
采样统计与质量报告
+
普通/Packed Faceset 兼容
+
失败自动回退
+
FP32 真实训练验收
```

---

## 4. 当前源码复核结论

### 4.1 `Sample` 当前没有增强 Metadata

当前 `samplelib/Sample.py::Sample` 只保存：

- filename；
- face_type；
- shape；
- landmarks；
- masks；
- source_filename；
- person_name；
- pitch_yaw_roll。

没有：

- stable sample id；
- quality score；
- pose bucket；
- image / landmark validity；
- analyzer version；
- sample signature。

设计要求：Batch 2 不直接膨胀 `Sample.__slots__` 为完整 Metadata 容器。运行时只允许按需挂载最小引用或通过外部索引查询，避免扩大 `MPSharedList` 中每个对象的共享和序列化成本。

### 4.2 当前已有普通随机与 uniform yaw

`SampleGeneratorFace` 当前根据 `uniform_yaw_distribution` 选择：

```text
False → mplib.IndexHost
True  → mplib.Index2DHost
```

`IndexHost` 负责随机打乱全部索引；`Index2DHost` 先抽一个 yaw 分组，再在组内抽样。

Batch 2 必须保留这两个 legacy 实现，并通过 Sampling Policy Factory 进行适配，不得直接删除或改变其默认行为。

### 4.3 当前 yaw 分布实现不可解释

现实现把约 `[-1.2, +1.2]` 分成 128 个区间，然后均匀抽取非空区间。

问题：

- 用户无法看到 bucket 分布；
- 没有 pitch 报告；
- 没有质量过滤；
- 稀缺 bucket 中的坏图可能被高频重复；
- 不支持权重上下限和统一探索概率；
- `Index2DHost` 没有显式 seed 参数，复现能力有限。

Batch 2 不要求删除该路径，只新增可解释的新模式。

### 4.4 `SampleLoader` 同时支持目录和 Packed Faceset

加载顺序：

```text
优先 PackedFaceset.load(samples_path)
→ 不存在 faceset.pak 时读取普通图片
→ 转换为 MPSharedList
```

Packed Faceset 内：

- `sample.filename` 被保存为 basename；
- person faceset 使用 `person_name/filename`；
- 图片字节通过 offset / size 从 `faceset.pak` 读取。

因此 Metadata 不能只依赖绝对路径；稳定样本键必须同时支持：

```text
普通目录：相对路径
Packed Faceset：person_name/filename 或 filename
```

### 4.5 Enhancement Config 已预留入口

当前 `core/enhancements/config.py` 已包含：

```text
training.enabled
training.metadata_sampling
```

但只有 bool flag，没有采样模式、路径、权重或 fallback 参数。

Batch 2 应在保持 `schema_version=1` 的前提下增加可选、向后兼容的 `sampling` section。旧代码会把它作为未知 top-level extra field 保留；新代码负责解析。不得把 `training.metadata_sampling` 从 bool 改成 dict。

### 4.6 `main.py` 已有 util 和 train 入口

项目已有：

- `util --save-faceset-metadata`，用途是备份 DFL 图片内部 metadata；
- `train`；
- `sort`；
- `extract`。

Batch 2 的训练质量 Metadata 与现有“保存图片内部 metadata”不是同一概念，不能复用同名参数造成误解。

建议新增明确入口：

```bash
python main.py faceset-analyze --input-dir <aligned>
```

而不是把它命名为 `save-faceset-metadata`。

---

## 5. 用户工作流

### 5.1 传统用户

不开启 Batch 2：

```text
旧模型
+ 旧 faceset
+ 无 Metadata sidecar
+ training.metadata_sampling=False
```

期望：

- 启动参数不增加；
- 不读取或生成 sidecar；
- `uniform_yaw=False` 继续使用 `IndexHost`；
- `uniform_yaw=True` 继续使用 `Index2DHost`；
- 训练张量、Loss、保存和 Merge 行为不变。

### 5.2 新用户首次分析

```bash
python main.py faceset-analyze \
  --input-dir <aligned-dir> \
  --output-file <aligned-dir>/faceset_metadata.v1.json
```

Analyzer 应输出：

- Metadata 文件；
- 控制台摘要；
- 可选 JSON / CSV 报告；
- 失败样本列表；
- 姿态与质量分布。

### 5.3 增量更新

faceset 新增、删除或替换图片后：

```bash
python main.py faceset-analyze \
  --input-dir <aligned-dir> \
  --incremental
```

行为：

- 未变化记录复用；
- 新增或 signature 改变记录重算；
- 已删除记录从新 Metadata 中移除；
- 原文件通过临时文件和原子替换更新；
- 失败时旧 Metadata 保持完整。

### 5.4 训练选择

建议用户可见模式：

```text
legacy_random
legacy_uniform_yaw
pose_balanced
quality_pose_balanced
```

第一版不单独暴露 `quality_only` 作为主要用户选项；Quality-only 可以作为内部 policy / 测试入口，减少用户选择复杂度。

### 5.5 保存恢复

Batch 2 采样为静态策略，不维护“当前模型对每张图的学习状态”。

重新启动时：

- 重新读取同一 Metadata；
- 根据相同配置重建权重；
- 不需要把采样状态写入 optimizer checkpoint；
- 模型保存恢复不得依赖 Metadata 成功。

如果 Metadata 丢失：

```text
warning
→ fallback_mode
→ 训练继续
```

---

## 6. 推荐模块结构

```text
samplelib/
├── metadata/
│   ├── __init__.py
│   ├── schema.py
│   ├── identity.py
│   ├── fingerprint.py
│   ├── pose.py
│   ├── quality.py
│   ├── analyzer.py
│   ├── store.py
│   ├── loader.py
│   └── report.py
├── sampling/
│   ├── __init__.py
│   ├── config.py
│   ├── policies.py
│   ├── weights.py
│   ├── factory.py
│   ├── weighted_index_host.py
│   └── stats.py
├── Sample.py
├── SampleLoader.py
└── SampleGeneratorFace.py

mainscripts/
└── FacesetAnalyzer.py

core/enhancements/
└── config.py

models/Model_SAEHD/
└── Model.py

main.py
```

模块边界：

- `metadata/*` 不依赖 TensorFlow；
- `sampling/*` 不读取图片像素，只消费样本索引与 Metadata；
- `SampleGeneratorFace` 只负责调用 policy host 获取索引；
- `Model_SAEHD` 只负责解析用户选项并将配置传给 generator；
- Analyzer 不导入 SAEHD 模型；
- Metadata 文件不写入模型目录，除非用户显式指定路径。

---

## 7. Sample Identity 设计

### 7.1 Stable Sample Key

定义规范化逻辑：

```python
def build_sample_key(sample, faceset_root, packed):
    if sample.person_name:
        return normalize(f"{sample.person_name}/{sample.filename}")
    return normalize(relative_or_basename(sample.filename, faceset_root, packed))
```

规范：

- 使用 `/` 作为逻辑分隔符；
- 移除 `./`；
- 不包含绝对盘符；
- Windows 大小写保持原文，但查找层提供受控 case-fold fallback；
- 禁止 `..` 越界；
- person faceset 必须包含 `person_name`。

### 7.2 Sample ID

```text
sample_id = sha256("dfl-sample-v1\0" + sample_key).hexdigest()[:32]
```

Sample ID 只表示逻辑身份，不表示内容未变化。

### 7.3 Sample Signature

普通文件：

```text
relative key
file size
mtime_ns
可选 quick hash
```

Packed Faceset：

```text
sample key
packed file size
packed file mtime_ns
sample offset
sample byte size
```

默认增量模式使用快速 signature；`--strong-fingerprint` 可计算内容 hash，但不是训练启动必需项。

### 7.4 Dataset Fingerprint

```text
sha256(
  schema identity version
  + faceset format
  + sorted(sample_id + sample_signature)
)
```

用途：

- 判断 Metadata 是否对应当前 faceset；
- 日志记录；
- 发现新增、删除、替换；
- 后续 Batch 4 / 5 复用。

Fingerprint 不用于安全认证，不应阻止 fallback。

---

## 8. Metadata Schema v1

### 8.1 文件名与格式

默认：

```text
<faceset_root>/faceset_metadata.v1.json
```

第一版选择单 JSON 文件，原因：

- 可人工查看；
- 易于版本化和原子替换；
- 普通目录与 Packed Faceset 共用；
- 不增加数据库依赖。

大规模 faceset 的压缩、SQLite 或二进制索引属于后续性能扩展，不是第一版前置。

### 8.2 顶层结构

```json
{
  "schema_version": 1,
  "analyzer_version": "1.0.0",
  "created_at": "2026-07-27T00:00:00Z",
  "updated_at": "2026-07-27T00:00:00Z",
  "faceset": {
    "format": "folder",
    "sample_count": 1000,
    "valid_sample_count": 990,
    "dataset_fingerprint": "..."
  },
  "analysis_config": {
    "pose_version": "pose-v1",
    "quality_version": "quality-v1",
    "strong_fingerprint": false
  },
  "summary": {},
  "samples": []
}
```

### 8.3 单样本字段

```json
{
  "sample_id": "...",
  "sample_key": "person/frame_0001.jpg",
  "filename": "frame_0001.jpg",
  "person_name": "person",
  "source_filename": "000001.png",
  "signature": {
    "size": 123456,
    "mtime_ns": 0,
    "offset": null
  },
  "image": {
    "valid": true,
    "width": 512,
    "height": 512,
    "channels": 3
  },
  "landmarks": {
    "present": true,
    "valid": true,
    "count": 68,
    "inside_ratio": 1.0,
    "reason": null
  },
  "pose": {
    "valid": true,
    "pitch": 0.02,
    "yaw": -0.31,
    "roll": 0.01,
    "yaw_bucket": "left_minor",
    "pitch_bucket": "level"
  },
  "quality": {
    "valid": true,
    "sharpness_raw": 123.4,
    "sharpness_score": 0.73,
    "exposure_score": 0.88,
    "quality_score": 0.79
  },
  "issues": []
}
```

### 8.4 必填与可选

必填：

- sample_id；
- sample_key；
- image.valid；
- landmarks.present / valid；
- pose.valid；
- quality.valid；
- issues。

数值不可得时用 `null`，不得写 NaN / Infinity 到 JSON。

### 8.5 Issue Codes

建议固定枚举：

```text
image_read_failed
invalid_image_shape
landmarks_missing
landmarks_count_invalid
landmarks_nonfinite
landmarks_out_of_bounds
pose_estimation_failed
quality_estimation_failed
sample_key_collision
signature_unavailable
```

日志和报告使用 code，不依赖异常字符串做机器判断。

### 8.6 Schema 兼容规则

- 缺失 `schema_version`：视为无效 Metadata，回退；
- 版本 `1`：正常读取；
- 高于支持版本：默认告警并回退；
- 未知顶层字段：保留或忽略，不影响读取；
- 未知单样本字段：忽略；
- 缺失可选字段：使用安全默认；
- 核心字段类型错误：该记录无效，不影响其他记录；
- 重复 sample_id：标记 collision，相关记录使用默认权重。

---

## 9. Faceset Analyzer 核心设计

### 9.1 输入来源

统一通过 `SampleLoader.load(SampleType.FACE, samples_path)` 获取样本，使普通目录与 Packed Faceset 走同一解析入口。

Analyzer 不应直接假设文件一定存在于磁盘路径；读取像素统一调用：

```python
sample.load_bgr()
```

### 9.2 图片合法性

检查：

- 能读取；
- dtype 可转换为 float32；
- shape 为 HWC；
- channel 可归一化到 3；
- width / height > 0；
- 数值 finite；
- 像素范围可裁剪到 `[0,1]`。

单图失败：记录 issue，继续分析其他样本。

### 9.3 Landmark 合法性

检查：

- landmarks 存在；
- shape 为 `[N,2]`；
- N 与项目支持值匹配；
- 全部 finite；
- 至少一定比例位于图片合理边界；
- 坐标范围不过度越界；
- 能调用 `LandmarksProcessor.estimate_pitch_yaw_roll`。

第一版不引入新的 landmark confidence 网络。`landmark_valid` 是工程合法性，不宣称为语义准确率评分。

### 9.4 Pose 计算

使用现有：

```python
sample.get_pitch_yaw_roll()
```

统一记录弧度值。

Yaw bucket v1：

```text
right_extreme  yaw <= -0.80
right_major   -0.80 < yaw <= -0.45
right_minor   -0.45 < yaw <= -0.20
front         -0.20 < yaw < 0.20
left_minor     0.20 <= yaw < 0.45
left_major     0.45 <= yaw < 0.80
left_extreme   yaw >= 0.80
unknown        pose invalid
```

注意：项目现有代码在 uniform yaw 中使用 `s_yaw = -pyr[1]`。实现 ticket 必须通过固定 landmarks fixture 确认左右符号语义，不能只复制文档阈值。若现有约定与上述名称相反，应修正文档和测试，不能静默产生错误标签。

Pitch bucket v1：

```text
up       pitch <= -0.25
level   -0.25 < pitch < 0.25
down     pitch >= 0.25
unknown  pose invalid
```

Pitch 第一版主要用于报告和后续扩展；`pose_balanced` 默认只对 yaw bucket 做主平衡，避免二维 bucket 稀疏。

### 9.5 Sharpness

建议基础原始指标：

```text
variance(Laplacian(grayscale))
```

要求：

- 在统一缩放或统一归一化规则下计算；
- 记录 raw value；
- 不使用一个跨所有分辨率的绝对“坏图阈值”；
- 在 faceset 内通过稳健百分位归一化为 `[0,1]`。

建议：

```text
p05 = 5th percentile(log1p(raw))
p95 = 95th percentile(log1p(raw))
sharpness_score = clip((log1p(raw)-p05)/(p95-p05), 0, 1)
```

当 `p95≈p05` 时全部回到中性分数 `0.5`，不得除零。

### 9.6 Exposure

第一版可计算：

- dark clipped ratio；
- bright clipped ratio；
- mean luminance。

建议：

```text
exposure_penalty = clip((dark_ratio + bright_ratio) / tolerance, 0, 1)
exposure_score = 1 - exposure_penalty
```

阈值和 tolerance 必须集中定义并进入 `analysis_config`，不得散落在代码里。

### 9.7 Quality Score

第一版定位为“训练采样辅助分数”，不是专业人脸质量评分。

建议：

```text
landmark_factor = 1.0 if landmark_valid else 0.5
quality_score = landmark_factor * (
    0.75 * sharpness_score
  + 0.25 * exposure_score
)
```

要求：

- 最终 `[0,1]`；
- 图片可读但 landmark 无效时不直接置零；
- image invalid 时 `quality.valid=False`；
- 权重常量集中在版本化配置；
- 报告中明确该分数不代表身份、美观或最终换脸质量。

### 9.8 两阶段分析

为获得 faceset 百分位，Analyzer 建议：

```text
Pass 1：读取、合法性、pose、raw quality metrics
Pass 2：计算全局稳健统计，生成 normalized score 与 summary
```

增量更新时：

- 复用未变化样本 raw metrics；
- 全数据集重新计算 normalized score 和 summary；
- 避免不同批次分析导致分数标尺不一致。

---

## 10. Analyzer CLI 与存储

### 10.1 CLI

建议新增：

```bash
python main.py faceset-analyze \
  --input-dir <path> \
  [--output-file <path>] \
  [--report-file <path>] \
  [--incremental] \
  [--force] \
  [--workers N] \
  [--strong-fingerprint] \
  [--strict]
```

参数语义：

- `--output-file`：默认 `<input-dir>/faceset_metadata.v1.json`；
- `--report-file`：默认同目录 `faceset_metadata_report.v1.json`；
- `--incremental`：复用 signature 未变化记录；
- `--force`：忽略旧 Metadata 全量重算；
- `--workers`：默认 `min(cpu_count, 8)`；
- `--strong-fingerprint`：计算强内容签名；
- `--strict`：任何单样本失败导致非零退出；默认非严格模式继续并报告。

### 10.2 原子写入

```text
serialize
→ write .tmp
→ flush
→ fsync（平台允许时）
→ validate temp by re-read
→ os.replace(temp, target)
```

失败：

- 删除临时文件；
- 保留旧文件；
- 返回非零退出码；
- 输出 traceback 和目标路径。

### 10.3 增量更新

匹配顺序：

```text
sample_id
→ sample_key
→ signature
```

规则：

- key 相同且 signature 相同：复用 raw record；
- key 相同但 signature 改变：重算；
- 新 key：新增；
- 旧 key 不存在：移除；
- collision：两者均标记无效，不猜测匹配。

### 10.4 报告

控制台摘要：

```text
Faceset format
Sample count
Valid / invalid count
Metadata reused / recomputed / added / removed
Yaw bucket distribution
Pitch bucket distribution
Quality min / p05 / median / p95 / max
Issue code counts
Output file
Elapsed time
```

机器报告至少包含相同字段，以及最差质量样本和失败样本的 sample_key 列表。

---

## 11. Metadata Loader

### 11.1 API

建议：

```python
metadata = FacesetMetadataLoader.load(
    samples_path,
    samples,
    metadata_path=None,
    strict=False,
)

metadata.status
metadata.dataset_fingerprint
metadata.get_by_sample(sample)
metadata.get_by_id(sample_id)
metadata.summary
metadata.warnings
```

### 11.2 状态枚举

```text
loaded
missing
unsupported_schema
invalid_file
fingerprint_mismatch
partial_match
sample_key_collision
```

### 11.3 匹配与默认值

每个运行时 sample 生成 sample_id 后查询。

缺失记录：

```text
quality_score = 1.0
pose bucket = unknown
metadata_valid = False
```

缺失记录不得被赋予零权重。

### 11.4 Fingerprint 策略

- 完全一致：正常；
- fingerprint 不一致但存在高比例 sample_id 匹配：`partial_match`，默认允许并告警；
- 匹配率低于安全阈值：按配置回退 legacy；
- strict 模式：不一致可阻止智能采样，但不应破坏传统训练入口。

默认安全阈值建议：

```text
matched_ratio >= 0.90 → 可使用匹配记录，缺失用默认
matched_ratio < 0.90  → 整体回退 legacy
```

阈值必须可配置并记录日志。

### 11.5 缓存

Metadata 每次训练启动读取一次，构建：

- `sample_id -> record` dict；
- 与运行时 sample 顺序一致的紧凑数组；
- quality score float32 array；
- yaw bucket int array；
- validity bool array。

Generator 子进程不重复解析 JSON。

---

## 12. Sampling Policy API

### 12.1 统一接口

```python
class SamplingPolicy:
    def build_index_host(self, samples, metadata, seed=None): ...
    def describe(self) -> dict: ...
    def validate(self) -> list[str]: ...
```

Factory：

```python
create_sampling_policy(config, legacy_uniform_yaw)
```

### 12.2 模式

```text
legacy_random
legacy_uniform_yaw
pose_balanced
quality_pose_balanced
```

映射规则：

- `training.metadata_sampling=False`：忽略新模式，使用 legacy；
- `mode=legacy` 或缺失：根据旧 `uniform_yaw` 选择；
- `legacy_random`：强制 `IndexHost`；
- `legacy_uniform_yaw`：强制当前 `Index2DHost`；
- `pose_balanced`：需要 Metadata pose；
- `quality_pose_balanced`：需要 Metadata pose + quality；
- 依赖不满足：使用 `fallback_mode`。

### 12.3 Seed

新增 policy 必须支持显式 seed：

- 单元测试可复现；
- 相同 seed、相同 sample 顺序、相同权重产生相同索引序列；
- 默认训练可继续使用随机 seed；
- legacy 模式不强制改变历史随机语义。

---

## 13. Pose-balanced Sampling

### 13.1 目标

缓解正脸过量和侧脸不足，同时避免极少 bucket 被无限重复。

### 13.2 Bucket 权重

对有效 yaw bucket 统计数量 `count_b`。

建议：

```text
reference = median(non_empty_bucket_counts)
raw_bucket_weight_b = (reference / max(count_b, 1)) ** balance_strength
bucket_weight_b = clip(raw_bucket_weight_b, 0.5, 2.0)
```

默认：

```text
balance_strength = 0.5
```

这比完全逆频率更保守。

### 13.3 Unknown bucket

- unknown 样本不能删除；
- 默认 bucket weight = 0.75；
- quality_pose 模式再由质量权重调整；
- unknown 占比过高时告警并建议重新分析。

### 13.4 Empty bucket

空 bucket 不参与抽样，不触发除零，也不死循环。

### 13.5 与 legacy uniform yaw 的区别

`legacy_uniform_yaw`：尽量均匀抽取细粒度 yaw 区间。

`pose_balanced`：

- 使用 7 个可解释 yaw bucket；
- 平衡强度可控；
- 有权重上限；
- 有 Metadata 质量基础；
- 输出实际分布统计；
- 支持 seed。

两者都保留，由用户选择。

---

## 14. Quality-aware Sampling

### 14.1 原则

- 只调整被抽中的概率；
- 不修改反向传播 Loss；
- 不自动删除样本；
- 不允许任何可读样本永久零概率；
- 低质量样本仍保留一定训练机会，以覆盖真实模糊、光照和压缩场景。

### 14.2 Quality 权重

给定 `q∈[0,1]`：

```text
smooth_q = q*q*(3-2*q)
quality_weight = 1 + quality_strength * (2*smooth_q - 1)
```

默认：

```text
quality_strength = 0.5
```

得到大致范围 `[0.5, 1.5]`。

对无效或缺失 Metadata：

```text
quality_weight = 1.0
```

不能把 unknown 当低质量。

### 14.3 强制边界

配置允许范围：

```text
min_sample_weight >= 0.25
max_sample_weight <= 3.0
```

默认：

```text
min_sample_weight = 0.5
max_sample_weight = 2.0
```

### 14.4 权重归一化

```text
weights = clip(weights, min, max)
weights = weights / mean(weights)
weights = clip(weights, min, max)
```

全零、NaN、Inf、负数：整体回退 uniform weights，并记录原因。

---

## 15. Quality + Pose 联合采样

### 15.1 组合

```text
combined_weight_i = pose_weight(bucket_i) * quality_weight(q_i)
```

然后归一化和裁剪。

### 15.2 Uniform Exploration

为防止分布过度收缩：

```text
p_final = (1 - uniform_mix) * p_weighted + uniform_mix * (1/N)
```

默认：

```text
uniform_mix = 0.10
```

范围建议 `[0.05, 0.30]`。

### 15.3 质量与姿态冲突

典型场景：稀缺大侧脸质量较低。

设计要求：

- pose 权重和 quality 权重均有上限；
- 不允许 quality 直接清除整个 bucket；
- report 输出每个 bucket 的质量分布；
- 若某 bucket 全部低质量，仍保留 uniform exploration；
- 用户可减小 quality_strength，而不关闭 pose balance。

---

## 16. WeightedIndexHost 与多进程

### 16.1 新 Host

建议新增：

```python
class WeightedIndexHost:
    def __init__(self, weights, rnd_seed=None, cycle_size=None): ...
    def create_cli(self): ...
```

继续采用当前 Host 线程 + 多个 CLI queue 的模式，使所有 Generator 子进程从一个中心状态获取索引。

### 16.2 抽样算法

第一版建议“预生成 weighted cycle”：

1. 根据 `p_final` 生成一个长度为 `cycle_size` 的索引序列；
2. 使用带 replacement 的 `RandomState.choice`；
3. 打乱 cycle；
4. 多进程请求按顺序消费；
5. cycle 用尽后生成下一轮。

默认：

```text
cycle_size = max(sample_count, 4096)
```

原因：

- 避免每个 `multi_get` 都调用昂贵概率采样；
- 中心 Host 保证不同子进程共享同一分布；
- seed 可复现；
- 统计容易。

### 16.3 重复控制

同一个 batch 内尽量避免重复索引：

- 当 `sample_count >= batch_size` 时进行有限重采样；
- 达到重试上限后允许重复，避免死循环；
- 极小 faceset 必须正常工作。

### 16.4 生命周期

Batch 2 为静态权重：

- 训练启动时构建一次；
- 不从 GPU loss 回传；
- 不在运行中动态改变；
- 用户更改配置后重启训练重建。

这显著降低并发和保存恢复复杂度。

### 16.5 统计

Host 维护轻量计数：

- total_draws；
- per bucket draws；
- quality quantile draws；
- duplicate retry count；
- fallback count。

统计读取不得阻塞主采样线程。

---

## 17. Config 设计

### 17.1 Enhancement Config

保持：

```json
{
  "training": {
    "enabled": false,
    "metadata_sampling": false
  }
}
```

新增可选 top-level section：

```json
{
  "sampling": {
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
}
```

### 17.2 Schema 兼容

本次是添加可选 section，可继续使用 `schema_version=1`。

要求修改 `EnhancementConfig`：

- 解析和保存 `sampling` mapping；
- 严格枚举 mode；
- 数值类型安全转换与裁剪；
- 未知字段忽略或保留；
- 旧 config 不含 sampling 时生成运行时默认，但不强制改写旧 `data.dat`；
- 高版本 schema 仍保持全部增强关闭策略。

### 17.3 Legacy `uniform_yaw`

兼容优先级：

```text
metadata_sampling=False
  → uniform_yaw=True ? legacy_uniform_yaw : legacy_random

metadata_sampling=True and sampling.mode=legacy
  → 同上

metadata_sampling=True and explicit new mode
  → 使用新模式
```

不得静默把旧 `uniform_yaw` 改成 False。

### 17.4 用户选项

新模型或用户 `override` 时可以询问：

```text
Enable metadata sampling? [y/N]
Sampling mode [legacy/pose_balanced/quality_pose_balanced]
Metadata file [auto]
```

高级数值默认不在普通交互逐项询问，先使用保守默认；通过 config 或后续 UI 调整。

---

## 18. SAEHD 与 Generator 接入

### 18.1 `Model_SAEHD/Model.py`

在 `on_initialize_options()`：

- 读取 EnhancementConfig；
- 解析 SamplingConfig；
- 保持旧模型不自动改写；
- 输出 requested mode。

在 `on_initialize()` / generator 构造：

- 为 src 和 dst 分别加载 Metadata；
- 允许 src、dst Metadata 状态不同；
- 为 src、dst 分别创建 policy；
- 传入 `SampleGeneratorFace`。

### 18.2 src / dst 独立

即使使用同一种模式，src 和 dst 必须分别计算：

- dataset fingerprint；
- bucket count；
- quality percentiles；
- sample weights；
- fallback reason；
- sampling statistics。

不得将 src 权重应用到 dst。

### 18.3 `SampleGeneratorFace`

建议新增参数：

```python
sampling_policy=None
sampling_metadata=None
sampling_seed=None
sampling_role=None
```

兼容：

- 未提供 policy 时执行当前代码；
- legacy policy 调用现有 IndexHost / Index2DHost；
- new policy 返回 WeightedIndexHost；
- 输出训练 tensor 数量与顺序不变；
- 不把 sample_id 添加到训练 batch 输出。

最后一条是本批次与未来动态 Loss sampler 的边界：Batch 2 不修改 SAEHD batch tensor contract。

---

## 19. 日志与可观测性

### 19.1 启动日志

src / dst 分别输出：

```text
Sampling role: src
Requested mode: quality_pose_balanced
Effective mode: quality_pose_balanced
Faceset format: packed
Samples: 18420
Metadata: loaded 18420 / 18420
Dataset fingerprint: ...
Pose buckets: ...
Quality p05/median/p95: ...
Weight min/mean/max: ...
Uniform mix: 0.10
Fallback: none
```

### 19.2 周期日志

每 `log_interval_draws`：

- 实际抽样 bucket 分布；
- Metadata valid / fallback 抽样数；
- quality quantile 分布；
- 重复重试；
- sampling throughput。

### 19.3 日志级别

- 正常摘要：info；
- 部分缺失、fingerprint mismatch、fallback：warning；
- strict 模式无法满足：error；
- 每样本详细信息只写 report，不刷训练控制台。

---

## 20. Fallback 与错误语义

### 20.1 默认策略

Batch 2 是可选增强：

```text
可选模块失败
→ 明确 warning
→ 回退传统采样
→ 训练继续
```

但以下错误不能伪装成 fallback：

- 训练图片本身完全不存在；
- SampleLoader 无数据；
- Generator 处理 tensor 失败；
- TensorFlow 训练错误。

这些仍按现有训练异常语义抛出。

### 20.2 Fallback 表

| 场景 | 默认行为 |
|---|---|
| Metadata 文件不存在 | fallback_mode |
| JSON 解析失败 | fallback_mode |
| schema 不支持 | fallback_mode |
| match ratio 低于阈值 | fallback_mode |
| 部分记录缺失但比例可接受 | 缺失记录中性权重 |
| 权重含 NaN / Inf / 负数 | 整体回退 uniform weights 或 legacy |
| 所有权重为零 | legacy_random |
| 空 pose bucket | 忽略空 bucket |
| Analyzer 单图失败 | 记录并继续 |
| Analyzer 输出写入失败 | 保留旧文件并非零退出 |
| strict_validation=True | 按配置阻止智能采样并报告，不破坏 legacy 入口 |

### 20.3 Fallback 记录

必须记录：

```text
requested_mode
effective_mode
fallback_reason
metadata_status
matched_ratio
```

---

## 21. Packed Faceset 兼容

### 21.1 Analyzer

- 使用 `PackedFaceset.load` 经 SampleLoader 获取 sample；
- 使用 `sample.read_raw_file()` / `load_bgr()`；
- sample_key 为 `person_name/filename` 或 filename；
- 不解包、不重写 `faceset.pak`。

### 21.2 Metadata 位置

默认 sidecar 仍放在 faceset 根目录：

```text
aligned/
├── faceset.pak
└── faceset_metadata.v1.json
```

### 21.3 Packed 更新

如果重新 pack：

- fingerprint 变化；
- sample keys 相同且 signature 可匹配时可增量复用；
- offset 改变但图片逻辑身份相同，需要按 key 再判断内容 signature；
- 无法安全确认时重算，不错误复用。

### 21.4 性能

Packed Analyzer 必须按样本流式读取，不把所有原始图片字节永久保存在内存。

---

## 22. 性能预算

### 22.1 Analyzer

需要记录：

- 总耗时；
- 图片/秒；
- 峰值 RSS；
- 复用率；
- 普通与 Packed 差异。

第一版不写死绝对速度门槛，但不得出现：

- 随样本数平方增长；
- 所有图片同时驻留内存；
- 每张图重复加载多次；
- 多进程无法退出；
- Windows spawn 下重复启动主程序。

### 22.2 训练启动

Metadata JSON 解析和权重构建只执行一次。

目标：对常见 faceset，额外启动时间应可观察、可接受，且不影响 GPU 训练每 iter 主路径。

### 22.3 训练迭代

WeightedIndexHost 只替代索引分发，目标是稳定训练后 iter time 相对 legacy 不产生显著回退。实际阈值由 Windows 基线测量后固化。

---

## 23. 测试设计

### 23.1 Layer 1：纯函数

不依赖 cv2 / TensorFlow：

- sample key normalization；
- sample id 稳定性；
- signature；
- dataset fingerprint；
- schema parse / roundtrip；
- bucket boundary；
- quality normalization；
- weight clipping / normalization；
- fallback config；
- deterministic index sequence。

### 23.2 Layer 2：小型图片 fixture

使用 synthetic 或仓库生成图片：

- 清晰图；
- 模糊图；
- 过暗 / 过亮图；
- invalid bytes；
- landmarks 缺失 / 非 finite / 越界；
- 不同 yaw fixture。

检查 Analyzer 输出字段、issues、报告和原子写入。

### 23.3 Layer 3：普通 / Packed Faceset

构造极小 faceset：

- 普通目录分析；
- pack 后分析；
- 两者 sample key、pose、quality 在容差内一致；
- incremental add / modify / delete；
- 旧 Metadata 不被写坏；
- Packed 无需解包。

### 23.4 Layer 4：Sampling 分布

固定 seed 抽取足够多索引：

- legacy_random 保持所有样本覆盖；
- pose_balanced 提高稀缺 bucket 占比；
- quality_pose 不会让低质量样本归零；
- uniform_mix 生效；
- empty / unknown bucket 正常；
- 权重异常回退；
- 单进程与多 CLI 共享 Host；
- batch 内重复控制不死循环。

统计测试使用容差区间，不要求随机频率逐项完全等于理论值。

### 23.5 Layer 5：Generator 集成

- debug 单线程；
- 1 个 subprocess；
- 多个 subprocess；
- ordinary / packed；
- src / dst 不同模式；
- output tensor 数量、shape、dtype 与 legacy 一致；
- Eyes / Mouth 开关输出不受影响；
- generator 可正常关闭。

### 23.6 Layer 6：Windows GPU FP32

固定：

```text
precision = fp32
optimizer = adabelief
GAN = 0
TrueFace = 0
small resolution
small batch
```

场景：

1. legacy_random 基线；
2. legacy_uniform_yaw；
3. pose_balanced；
4. quality_pose_balanced；
5. src Metadata 正常、dst 缺失；
6. Metadata 损坏 fallback；
7. 普通 faceset；
8. Packed Faceset；
9. 保存、退出、恢复；
10. 运行至少一个可观察窗口并比较 iter time。

检查：

- 能启动和持续训练；
- loss finite；
- optimizer / model iteration 正常；
- 保存恢复不受影响；
- requested / effective mode 正确；
- 实际采样统计符合预期；
- fallback 不掩盖训练错误；
- 关闭功能时与 legacy 基线一致。

### 23.7 人工数据验收

Batch 2 不要求判断最终换脸质量显著提高，但负责人需要检查：

- Analyzer 标为低质量的样本是否大体合理；
- 左右姿态标签是否正确；
- 稀缺姿态实际出现比例是否提高；
- 没有把所有模糊或特殊场景完全排除；
- 用户报告能帮助清理 faceset，但程序不自动删除。

---

## 24. 测试 Fixture 与结果记录

建议新增：

```text
tests/fixtures/batch2/
├── manifest.example.json
├── metadata_v1_minimal.json
├── metadata_v1_partial.json
├── metadata_v1_unsupported.json
└── generated/  # 测试运行时创建，不提交真实人脸
```

Manifest：

```json
{
  "src_dir": "<absolute path>",
  "dst_dir": "<absolute path>",
  "packed_src_dir": "<absolute path or null>",
  "model_dir": "<absolute path>",
  "sampling_modes": [
    "legacy_random",
    "legacy_uniform_yaw",
    "pose_balanced",
    "quality_pose_balanced"
  ]
}
```

Windows 验收结果建议写入：

```text
.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md
```

---

## 25. 文件级任务清单

| ID | 文件 | 函数 / 类 | 修改内容 | 风险 | 回退 |
|---|---|---|---|---|---|
| B2-01 | `samplelib/metadata/schema.py` | 新模块 | Schema v1、校验、序列化 | 中 | 不加载 sidecar |
| B2-01 | `samplelib/metadata/identity.py` | 新模块 | sample key / id | 中 | legacy index |
| B2-01 | `samplelib/metadata/fingerprint.py` | 新模块 | signature / dataset fingerprint | 中 | 忽略 fingerprint |
| B2-02 | `samplelib/metadata/pose.py` | 新模块 | pose bucket | 中 | unknown bucket |
| B2-02 | `samplelib/metadata/quality.py` | 新模块 | sharpness / exposure / quality | 中 | 中性质量权重 |
| B2-02 | `samplelib/metadata/analyzer.py` | 新模块 | 两阶段分析 | 中 | 不生成 Metadata |
| B2-03 | `samplelib/metadata/store.py` | 新模块 | 原子保存 / 增量更新 | 高 | 保留旧文件 |
| B2-03 | `samplelib/metadata/report.py` | 新模块 | 摘要和 issue 报告 | 低 | 仅控制台日志 |
| B2-03 | `mainscripts/FacesetAnalyzer.py` | 新入口 | CLI 执行层 | 低 | 不影响 train |
| B2-03 | `main.py` | parser | `faceset-analyze` 命令 | 低 | 删除可选命令 |
| B2-04 | `samplelib/metadata/loader.py` | 新模块 | 读取、匹配、状态、缓存 | 高 | fallback legacy |
| B2-04 | `samplelib/SampleLoader.py` | load 周边 | 暴露格式/样本信息辅助 | 中 | 原加载路径 |
| B2-05 | `samplelib/sampling/config.py` | 新模块 | SamplingConfig | 中 | legacy defaults |
| B2-05 | `samplelib/sampling/policies.py` | 新模块 | policy interface / legacy adapter | 中 | 直接旧分支 |
| B2-05 | `samplelib/sampling/factory.py` | 新模块 | requested/effective mode | 中 | legacy factory |
| B2-06 | `samplelib/sampling/weights.py` | pose functions | bucket weights | 中 | uniform weights |
| B2-07 | `samplelib/sampling/weights.py` | quality functions | quality weights | 中 | 中性权重 |
| B2-08 | `samplelib/sampling/weighted_index_host.py` | 新 Host | 中央加权索引分发 | 高 | IndexHost / Index2DHost |
| B2-08 | `samplelib/SampleGeneratorFace.py` | `__init__` | policy Host 接入 | 高 | 无 policy 走旧代码 |
| B2-08 | `samplelib/sampling/stats.py` | 新模块 | 实际抽样统计 | 低 | 关闭周期统计 |
| B2-09 | `core/enhancements/config.py` | config parse | sampling section | 中 | 缺失使用默认 |
| B2-09 | `models/Model_SAEHD/Model.py` | options/generator | src/dst 配置与日志 | 高 | metadata_sampling=False |
| B2-10 | `tests/smoke/*` | tests | 全分层测试 | 低 | 测试不影响运行时 |
| B2-11 | `docs/*` / `.handoff/*` | 文档 | 使用说明、矩阵、交接 | 低 | 不删除历史 |

---

## 26. 推荐开发顺序

### Step 1：数据契约

```text
B2-00
→ B2-01
→ B2-02
```

先证明对同一 faceset 能稳定、可解释地生成 Metadata。

### Step 2：正式 Analyzer 产品闭环

```text
B2-03
→ B2-04
```

此时用户已经能独立分析和复用 Metadata，但训练尚不改变采样。

### Step 3：采样纯逻辑

```text
B2-05
→ B2-06
→ B2-07
```

所有公式、边界和 fallback 先通过纯函数与统计测试。

### Step 4：多进程接入

```text
B2-08
→ B2-09
```

这是 Batch 2 运行时风险最高的阶段，不得与 Analyzer 大改混在同一个提交。

### Step 5：完整验收

```text
B2-10
→ B2-11
```

必须补 Windows FP32 真实训练记录后，才能标记 `done`。

---

## 27. 推荐提交拆分

```text
test(batch2): add metadata and sampling fixtures
feat(metadata): add sample identity and schema v1
feat(metadata): add lightweight faceset analyzer
feat(cli): add faceset-analyze command and atomic reports
feat(metadata): load and validate folder and packed sidecars
refactor(sampling): add policy interface with legacy adapters
feat(sampling): add pose-balanced weights
feat(sampling): add quality-aware weights
feat(sampling): add weighted multiprocess index host
feat(saehd): wire optional metadata sampling with safe fallback
test(batch2): add generator and distribution integration coverage
docs(batch2): add compatibility matrix and Windows acceptance handoff
```

禁止把所有 Batch 2 功能压成一个提交。

---

## 28. Ticket 依赖

```text
B2-00
  ↓
B2-01
  ↓
B2-02
  ↓
B2-03 ─────→ B2-04
               ↓
B2-05
  ├──→ B2-06
  └──→ B2-07
          ↓
        B2-08
          ↓
        B2-09
          ↓
        B2-10
          ↓
        B2-11
```

B2-06 与 B2-07 可在 B2-05 后并行。

---

## 29. 完成定义

Batch 2 只有同时满足以下条件才可标记完成：

```text
Schema v1 稳定
+
普通/Packed Analyzer 可运行
+
原子保存与增量更新可恢复
+
Metadata Loader 可校验和回退
+
Pose / Quality 权重纯函数通过
+
WeightedIndexHost 多进程通过
+
训练主链路实际使用新采样
+
开关关闭时 legacy 行为不变
+
Windows FP32 + AdaBelief 训练通过
+
保存退出恢复通过
+
日志、报告和用户说明完整
```

### 29.1 非阻断项

不阻断 Batch 2：

- 动态 Loss sampler；
- 自动坏图删除；
- 大型质量模型；
- 最终换脸质量显著提升；
- Identity Geometry；
- Shape-aware Merge；
- FP16 / BF16；
- Lion。

### 29.2 阻断条件

任一发生则不得完成：

- Metadata 会覆盖或损坏原图片 / faceset.pak；
- 关闭增强仍改变 legacy 抽样；
- 智能模式导致部分样本永久零概率；
- Metadata 异常会阻止传统训练；
- 普通与 Packed sample key 大量错配；
- 多进程索引重复、卡死或进程无法退出；
- src / dst 权重串用；
- Generator tensor contract 改变；
- 保存恢复受影响；
- Windows FP32 真实训练未记录却标记完成。

---

## 30. Batch 2 完成后的稳定接口

后续 Batch 3 / 4 可以依赖：

- `sample_id`；
- `sample_key`；
- dataset fingerprint；
- yaw / pitch；
- pose bucket；
- landmark validity；
- static quality score；
- Sampling Policy Factory；
- WeightedIndexHost；
- sampling report。

后续不得依赖尚未实现的单样本动态 Loss 状态。

---

## 31. 后续扩展边界

### 31.1 Batch 3

可以复用 Metadata 和 policy hook，但主要新增 Loss Hook；不得反过来修改 Batch 2 Schema 语义。

### 31.2 Batch 4

可以新增：

- shape anchor candidate；
- landmark ratio metadata；
- geometry sampling mode。

新增字段应为 Schema 的向后兼容扩展或新 schema version。

### 31.3 Future Adaptive Sampling

动态 Loss 感知采样必须独立设计：

- sample id 与 GPU per-sample loss 对齐；
- src / dst 独立状态；
- EMA、探索、异常衰减；
- 多进程反馈；
- sampler state 保存恢复。

它不得修改 Batch 2 已交付的静态 Metadata 文件；动态状态属于模型目录。

---

## 32. 实施前检查清单

开始 B2-01 前：

- [ ] 确认工作分支和基线 commit。
- [ ] 确认 Batch 1 Windows FP32 当前可训练状态和已知未完成项。
- [ ] 固定普通与 Packed 小 faceset fixture。
- [ ] 记录 legacy_random / uniform_yaw 的索引分布与 generator shape。
- [ ] 确认 Windows spawn、多进程和路径大小写行为。
- [ ] 确认 Metadata 命名不与现有 `save-faceset-metadata` 混淆。
- [ ] 确认所有新增功能默认关闭。
- [ ] 确认动态 Loss sampler、脸型 Loss、Lion 和低精度不进入提交。

---

## 33. 结论

Batch 2 的目标不是做一个庞大的智能训练系统，而是交付一个边界清晰、可复用、可回退的数据与采样基础设施：

```text
用户可理解的 faceset 报告
+
稳定的 Metadata sidecar
+
保守的姿态和质量加权
+
不破坏旧训练的多进程接入
```

完成后，即使后续暂时不开发动态 Loss 采样、Identity Geometry 或 Shape-aware Merge，Batch 2 仍然是一套可以独立长期使用的正式功能。