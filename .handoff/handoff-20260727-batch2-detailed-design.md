# DeepFaceLab TF2.x 项目交接：Batch 2 Metadata 与 Sampling 详细设计

> 交接编号：H-011  
> 创建日期：2026-07-27  
> 仓库：`twj515895394/deep-face-lab-tf2.x`  
> 设计分支：`codex/batch2-metadata-sampling-design`  
> 基线提交：`55d4d8a4d29dc0fcc4a571d2c4f24dcdb2b7069e`  
> 本次定位：完成 Batch 2 的源码复核、产品边界、文件/函数级详细设计和 `.scratch` ticket 拆分；尚未开始运行时代码实现。

---

## 1. 本次目标

根据 Batch 1 handoff 和总实施计划，细化：

```text
Batch 2：训练数据增强
- Metadata schema
- Quality / Pose sampling
- 日志与 fallback
```

设计必须满足：

- Batch 2 完成后是可独立长期使用的完整功能，而不是半成品；
- 训练主线固定 FP32 + AdaBelief；
- 不把动态 Loss sampler、脸型训练、Lion 或低精度混入 Batch 2；
- ordinary / Packed Faceset 均可使用；
- 所有增强默认关闭，失败可回退 legacy。

---

## 2. 已完成工作

### 2.1 新增正式详细设计

```text
docs/development/batch2-training-data-and-sampling-tasks.md
```

内容包括：

- 产品完成定义与禁止范围；
- 当前 Sample / SampleLoader / Generator / IndexHost 源码事实；
- Sample Identity、Signature、Dataset Fingerprint；
- Metadata Schema v1；
- Analyzer 图片/landmark/pose/quality 设计；
- Analyzer CLI、原子存储和增量更新；
- Metadata Loader、运行时缓存和 ordinary/Packed 匹配；
- Sampling Policy API 与 legacy adapter；
- Pose/Quality/联合权重公式；
- WeightedIndexHost 与多进程 Generator 接入；
- Enhancement Config 和 SAEHD 选项；
- 日志、fallback、性能预算；
- 自动测试、Windows FP32 验收、文件级任务表；
- 推荐提交、ticket 依赖、完成/阻断条件；
- 后续 Batch 3/4/5/6 和 Future Adaptive Sampling 边界。

### 2.2 新增 Batch 2 执行包

```text
.scratch/batch2-training-data-and-sampling/
├── spec.md
├── issues/
│   ├── 01-baseline-and-fixtures.md
│   ├── 02-sample-identity-and-metadata-schema.md
│   ├── 03-lightweight-faceset-analyzer-core.md
│   ├── 04-analyzer-cli-atomic-store-and-incremental.md
│   ├── 05-metadata-loader-folder-packed-compat.md
│   ├── 06-sampling-policy-and-legacy-adapters.md
│   ├── 07-pose-balanced-sampling.md
│   ├── 08-quality-aware-weighting.md
│   ├── 09-weighted-index-host-and-generator-integration.md
│   ├── 10-config-saehd-logging-and-fallback.md
│   ├── 11-batch2-test-matrix-and-windows-acceptance.md
│   └── 12-compatibility-docs-and-handoff.md
└── reports/
    └── README.md
```

### 2.3 设计引用的核心文档

- Batch 1 详细设计；
- Enhanced DFL 总实施计划；
- Training Enhancement Implementation Plan；
- Training Quality Algorithm Roadmap；
- src/dst Training Quality Design；
- Config and Extension Architecture；
- Code Modification Map；
- Manual Quality Acceptance Standard。

### 2.4 复核的核心源码

- `samplelib/Sample.py`
- `samplelib/SampleLoader.py`
- `samplelib/SampleGeneratorFace.py`
- `samplelib/PackedFaceset.py`
- `core/mplib/__init__.py`
- `core/enhancements/config.py`
- `models/Model_SAEHD/Model.py`
- `main.py`

---

## 3. 已确定技术决策

### 3.1 Batch 2 是完整产品模块

完成后用户可以：

```text
faceset-analyze
→ 生成/更新 sidecar
→ 选择 legacy / pose / quality+pose
→ FP32 训练
→ 查看实际采样日志
→ 保存退出恢复
→ Metadata 异常时回退
```

Schema 或 Analyzer 单独完成不能代表 Batch 2 完成。

### 3.2 不修改原始 faceset

- Metadata 放独立 JSON sidecar；
- 不写回 DFLJPG/PNG；
- 不改 `faceset.pak` 版本；
- 不自动删除、移动或重命名图片。

### 3.3 Stable Sample Identity

- ordinary 使用相对路径；
- person/packed 使用 `person_name/filename`；
- sample_id 代表逻辑身份；
- signature 代表内容状态；
- dataset fingerprint 用于匹配和增量更新。

### 3.4 Analyzer 是轻量工具

第一版只使用现有 cv2 / NumPy / landmarks：

- 图片合法性；
- landmark 合法性；
- pitch/yaw/roll；
- pose bucket；
- Laplacian sharpness；
- 曝光；
- 基础 quality score。

不引入 ArcFace、DINO、VGG 或大型质量模型。

### 3.5 采样只调整概率

- 不乘训练 Loss；
- 不读单样本训练 Loss；
- 不产生零概率；
- 使用 pose/quality 权重、上下限和 uniform exploration。

### 3.6 多进程采用中心 WeightedIndexHost

延续当前 Host thread + CLI queues 模式；静态权重只在训练启动构建一次，不建立 GPU 反馈通道。

### 3.7 Config 向后兼容

- 保留 `training.metadata_sampling` bool；
- 新增可选 `sampling` section；
- 继续 schema v1 的向后兼容扩展；
- 旧模型不强制改写 `data.dat`；
- 旧 `uniform_yaw` 保留。

### 3.8 完成状态必须经过 Windows FP32

只有 CPU/macOS 纯函数或 mock 通过时，只能标记：

```text
done-macos-lightweight-pending-windows
```

完整 `done` 需要 48GB Blackwell Windows 环境：FP32 + AdaBelief、ordinary/Packed、多进程、fallback、save/exit/resume 和性能记录。

---

## 4. 明确延期

```text
Dynamic Loss-aware Sampling：deferred
Identity Geometry / 脸型 Loss：Batch 4
Source Shape Template：Batch 5
Shape-aware Merge：Batch 6
Lion 后续开发：paused
FP16 / BF16 正式验收：paused / experimental
Region / Boundary / Frequency / Identity Loss：Batch 3+
```

这些内容不阻断 Batch 2，也不得被任一 ticket 顺手实现。

---

## 5. 当前代码状态

```text
Batch 2 正式详细设计：已完成
Batch 2 .scratch ticket 拆分：已完成
Batch 2 运行时代码：未开始
Batch 2 自动测试：未开始
Batch 2 Windows FP32 验收：未开始
```

本次只新增设计、执行包和交接，不修改运行时代码。

---

## 6. 下一步

直接领取：

```text
.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md
```

然后严格按依赖推进：

```text
01 基线
→ 02 Identity/Schema
→ 03 Analyzer Core
→ 04 CLI/Store
→ 05 Loader
→ 06 Policy
→ 07/08 Weights
→ 09 WeightedIndexHost/Generator
→ 10 Config/SAEHD
→ 11 Windows Acceptance
→ 12 Docs/Handoff
```

不得直接从 Ticket 09 开始修改 Generator。

---

## 7. 第一轮实现注意事项

- 先固定 ordinary/Packed fixture 和 legacy 分布。
- Sample key 左右/大小写/人员子目录必须有测试。
- yaw 左右符号必须用 fixture 确认。
- Analyzer 先完成 raw metrics，再做 percentile normalization。
- 原子写入必须验证临时文件再 replace。
- Loader match ratio 低时整体回退，不错误套用 Metadata。
- WeightedIndexHost 单独提交。
- SAEHD 接入只传 policy，不改 batch tensor contract。
- 所有新增功能默认关闭。
- 核心训练异常不能被 optional fallback 吞掉。

---

## 8. 参考入口

1. `docs/development/batch2-training-data-and-sampling-tasks.md`
2. `.scratch/batch2-training-data-and-sampling/spec.md`
3. `.scratch/batch2-training-data-and-sampling/issues/01-baseline-and-fixtures.md`
4. `docs/implementation/enhanced-dfl-master-implementation-plan.md`
5. `docs/implementation/manual-quality-acceptance-and-development-validation-standard.md`
