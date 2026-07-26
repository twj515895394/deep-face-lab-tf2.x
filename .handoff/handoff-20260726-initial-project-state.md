# DeepFaceLab TF2.x 项目交接文档（首次完整交接）

> 交接编号：H-001  
> 创建日期：2026-07-26  
> 仓库：`twj515895394/deep-face-lab-tf2.x`  
> 默认分支：`main`  
> 文档定位：供新会话、新 Agent 或后续开发者快速恢复项目上下文。  
> 最新入口：`.handoff/current.md`

---

## 1. 交接目的

本文件是项目的第一份正式交接文档，后续所有 handoff 文档应参照本结构编写。

它需要让一个不了解此前对话的新会话在较短时间内回答以下问题：

1. 这个项目是什么，当前准备解决什么问题。
2. 项目过去经历了哪些分析和设计阶段。
3. 当前代码与文档处于什么状态。
4. 已经形成了哪些关键结论，哪些结论不能再被轻易推翻。
5. 接下来应该按照什么顺序开发。
6. 哪些工作属于自动化开发验证，哪些必须由人工完成。
7. 新会话启动后首先应该阅读哪些文件、检查哪些代码、执行哪些任务。

---

## 2. 项目基本信息

### 2.1 项目定位

该仓库是 DeepFaceLab 的 TensorFlow 2.x 演进版本。当前阶段的核心目标不是重写 DeepFaceLab，也不是引入全新的换脸生成范式，而是在保留原有工作流、模型兼容性和使用习惯的基础上，对核心引擎进行增强。

当前增强方向包括：

- 训练正确性修复；
- 训练性能优化；
- 训练质量优化；
- src / dst 职责重新划分；
- Identity Appearance 与 Identity Geometry 分离；
- src 脸型学习能力增强；
- Shape-aware Merge；
- Mask 与 Temporal Stabilization；
- 未来配置化、Linux 服务化和 UI 接入。

### 2.2 当前项目阶段

当前项目已经完成较大规模的研究、架构分析和实施规划，尚未正式进入大规模代码开发。

当前阶段可定义为：

```text
研究与架构分析：基本完成
专项优化设计：基本完成
源码调用链审计：已完成第一轮
统一实施计划：已建立
开发验证标准：已建立
实际代码改造：即将开始
```

### 2.3 当前唯一实施入口

所有开发顺序以以下文档为准：

```text
docs/implementation/enhanced-dfl-master-implementation-plan.md
```

该文件是当前唯一的实施总入口。后续不应再建立平行的第二套总路线，避免训练优化、脸型优化和 Merge 优化再次分裂。

---

## 3. 项目历史演进

### 3.1 第一阶段：TF2.x 项目现状分析

最初工作主要集中在：

- 当前 DeepFaceLab TF2.x 项目的真实实现状态；
- TensorFlow 2.x、CUDA、新 GPU、低精度训练等升级情况；
- Extract、Training、Merge 三条主链路；
- 现有代码与文档中“已经设计”与“已经实现”的差异；
- 未来 Linux 后端与 UI 的可能架构。

这一阶段建立了项目现状和代码基线，主要文档位于：

```text
docs/analysis/
docs/design/
```

### 3.2 第二阶段：训练增强优化

随后重点转向训练侧，包括：

- 训练正确性；
- BF16 / FP16 与 Loss Scaling；
- Optimizer state 和断点恢复；
- 数据管线和吞吐；
- Sampling；
- Loss；
- Identity Similarity；
- Region、Boundary、Frequency 等质量目标；
- Curriculum Training。

这一阶段最初仍然偏向“提高模型训练质量”，还没有完全解决最终脸型问题。

### 3.3 第三阶段：src / dst 职责重新定义

进一步分析后，形成了新的训练职责划分：

```text
Source 主要提供：
- identity
- texture
- face shape
- stable facial proportions

Destination 主要提供：
- pose
- expression
- lighting
- motion
```

这比传统的对称重建思路更符合换脸目标。

### 3.4 第四阶段：脸型问题被拆成训练与合成两个独立瓶颈

项目中形成了一个非常重要的结论：

```text
训练是否学会 src 脸型
        ≠
最终视频是否保留 src 脸型
```

原因是当前 Merge 流程仍然主要受 dst landmarks、dst affine 空间和 dst mask 约束。

因此，脸型问题必须拆成两条独立路线：

#### Training Side

解决模型是否学会：

- src 脸宽；
- 下颌；
- 下巴；
- 颧骨；
- 五官比例；
- 稳定的 identity geometry。

#### Merge Side

解决最终输出是否允许：

- src geometry 进入回贴空间；
- src 脸型不被 dst mask 截断；
- dst 表情和姿态继续保留；
- 视频连续帧不出现形变抖动。

### 3.5 第五阶段：Shape-aware Merge 设计

为避免替换原 SAEHD 和原 Merge，当前方案采用扩展式架构：

```text
Prediction
    ↓
Predicted / Canonical Geometry
    ↓
Hybrid Landmark Engine
    ↓
Piecewise Affine Warp
    ↓
Shape-aware Mask
    ↓
Blend
    ↓
Temporal Stabilization
```

第一版明确采用 Piecewise Affine，而不是 TPS、大型新网络、Transformer 或 Diffusion。

### 3.6 第六阶段：统一实施路线建立

随着文档增多，原有 `docs/README.md` 已出现过时、文档状态错误和路线分裂问题。

因此已经完成：

- 更新 `docs/README.md`；
- 建立唯一实施入口；
- 将训练增强、Identity Geometry、Source Shape Template、Hybrid Landmark、Shape Warp、Mask、Temporal 和人工验收串成一条开发链路。

---

## 4. 已确认的关键技术结论

以下结论是当前项目的架构基础。新会话在没有新的代码证据或实验结果前，不应随意推翻。

### 4.1 不替换 SAEHD

第一阶段增强不以替换 SAEHD 为目标。

原因：

- 兼容风险高；
- 会扩大开发范围；
- 现阶段主要瓶颈不只是模型容量；
- Sampling、Loss、Geometry 和 Merge 仍有大量低风险提升空间。

### 4.2 Identity 必须拆分

当前统一采用：

```text
Identity
=
Appearance
+
Geometry
```

Appearance 包括：

- 眼睛；
- 鼻子；
- 嘴部；
- 肤质；
- 局部纹理。

Geometry 包括：

- 脸宽；
- 下颌；
- 下巴；
- 颧骨；
- 五官比例；
- landmark ratios。

### 4.3 训练和 Merge 必须独立增强

只改训练不能保证最终脸型迁移；只改 Merge 也不能弥补模型完全没有学习 src geometry 的问题。

最终需要：

```text
Better Training
+
Identity Geometry
+
Shape-aware Merge
+
Temporal Stabilization
```

### 4.4 Shape-aware Merge 必须可关闭

所有新能力默认关闭，关闭时必须保持原始 DeepFaceLab 行为。

需要通过：

- Feature Flag；
- Optional Pipeline；
- 独立模块；
- 缺失数据回退；
- 异常回退。

保证旧模型和旧流程继续可用。

### 4.5 第一版 Warp 采用 Piecewise Affine

原因：

- 逻辑可解释；
- OpenCV 支持成熟；
- 更容易控制局部形变；
- 易调试和回滚；
- 比 TPS 更适合当前第一版 MVP。

### 4.6 自动化负责工程正确性，人工负责视觉质量

Agent、开发者或 CI 负责：

- 项目启动；
- 配置加载；
- Feature Flag；
- 训练运行；
- 保存和恢复；
- Merge 运行；
- dtype、shape、路径、序列化；
- 新功能关闭时兼容原流程；
- 错误和回退日志。

人工负责：

- src 相似度；
- src 脸型迁移程度；
- dst 表情保持；
- 边缘自然度；
- 遮挡表现；
- 视频抖动；
- 最佳参数选择。

当前不建设完整的自动视觉评分平台。

---

## 5. 当前已识别的重要问题

### 5.1 Eyes / Mouth Priority 可能实际失效

在现有训练调用链审计中发现，`unified_train()` 可能向训练图传入：

```python
zeros_like(mask)
```

而不是真实的 eye / mouth mask。

这意味着 Eyes / Mouth Priority loss 可能没有实际生效。

该问题应作为首批 P0 正确性任务重新检查并修复。

注意：实施前必须再次基于当前分支源码确认具体文件、函数和调用参数，不能只依据历史分析直接修改。

### 5.2 当前 Swap 缺少显式身份监督

传统训练主要是：

```text
src → src reconstruction
dst → dst reconstruction
dst latent → src decoder
```

Swap 输出没有足够明确的 identity supervision，因此需要逐步加入：

- Identity Appearance；
- Identity Geometry；
- Region / Boundary；
- 可选 Frequency；
- Curriculum。

### 5.3 当前 Merge 主要受 dst geometry 控制

当前典型流程：

```text
dst frame
  ↓
dst landmarks
  ↓
affine transform
  ↓
predictor
  ↓
dst mask constraints
  ↓
blend
```

这会导致：

- src jaw 无法真正扩展；
- src face width 被 dst 对齐空间压缩；
- output_face_scale 只能做整体缩放；
- mask 交集可能重新裁回 dst 轮廓。

### 5.4 当前文档多但代码尚未开始系统落地

目前最主要的风险已经从“没有设计”转变为：

> 文档继续增加，但实际代码开发仍未启动。

因此接下来应停止继续扩展大而泛的概念设计，优先进入 Batch 1 实施。

---

## 6. 当前文档体系

### 6.1 总索引

```text
docs/README.md
```

作用：

- 项目文档导航；
- 状态定义；
- 阅读路径；
- 当前阶段和优先级。

### 6.2 唯一实施总入口

```text
docs/implementation/enhanced-dfl-master-implementation-plan.md
```

作用：

- 串联所有模块；
- 定义实施批次；
- 约束范围；
- 定义模块依赖关系；
- 防止出现平行路线。

### 6.3 核心分析文档

```text
docs/analysis/dfl-current-project-overview.md
docs/analysis/dfl-tf2-upgrade-analysis.md
docs/analysis/implementation-status-and-risk-matrix.md
docs/analysis/extraction-architecture-analysis.md
docs/analysis/training-architecture-analysis.md
docs/analysis/merging-architecture-analysis.md
```

### 6.4 训练优化设计

```text
docs/optimization/training-correctness-audit.md
docs/optimization/training-performance-optimization.md
docs/optimization/training-quality-algorithm-roadmap.md
docs/optimization/src-dst-training-quality-optimization-design.md
docs/optimization/src-face-shape-preservation-design.md
docs/optimization/training-ablation-experiment-plan.md
```

### 6.5 脸型与合成设计

```text
docs/optimization/src-face-shape-training-and-shape-aware-merge-design.md
docs/optimization/shape-aware-merge-implementation-design.md
```

### 6.6 工程实施文档

```text
docs/implementation/deepfacelab-code-modification-map.md
docs/implementation/deepfacelab-source-code-audit.md
docs/implementation/deepfacelab-tf2x-source-tree-analysis.md
docs/implementation/deepfacelab-training-call-chain-analysis.md
docs/implementation/deepfacelab-merger-call-chain-analysis.md
docs/implementation/deepfacelab-config-and-extension-architecture.md
docs/implementation/training-enhancement-implementation-plan.md
docs/implementation/merge-shape-aware-implementation-plan.md
docs/implementation/manual-quality-acceptance-and-development-validation-standard.md
```

---

## 7. 当前统一实施步骤

后续开发必须以依赖关系为主，而不是按文档创建顺序开发。

### Batch 1：P0 正确性与安全骨架

目标：保证后续增强建立在可靠基础上。

任务：

1. 再次审计 Eyes / Mouth Priority 的真实输入。
2. 检查 BF16 / FP16、Loss Scaling、梯度 dtype。
3. 检查 Optimizer state 保存和恢复。
4. 建立统一 Feature Flag 或兼容的配置入口。
5. 建立训练 smoke test。
6. 建立 Merge smoke test。
7. 确保所有增强关闭时保持原始行为。

完成标准：

- 原训练流程可以启动；
- 原模型可以加载；
- checkpoint 可以保存和恢复；
- 原 Merge 可以运行；
- 新配置缺失时不报错；
- 新功能关闭时行为不改变。

### Batch 2：Dataset Metadata 与 Sampling

任务：

- metadata schema；
- quality score；
- pose bucket；
- occlusion score；
- landmark confidence；
- shape anchor；
- quality sampling；
- pose sampling；
- shape-aware sampling；
- metadata 缺失回退。

### Batch 3：Loss Hook 与基础质量目标

任务：

- 统一 Loss Hook；
- Eyes / Mouth Priority 正确接通；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- Identity Appearance Loss；
- 各 Loss 独立日志；
- 默认权重为零或功能默认关闭。

### Batch 4：Identity Geometry 与 Curriculum

任务：

- shape anchor 表示；
- landmark ratio；
- jaw / cheek / chin / width 约束；
- Identity Geometry Loss；
- Curriculum Stage；
- 训练阶段状态保存和恢复。

### Batch 5：Source Shape Template

任务：

- 设计 sidecar artifact；
- 建议文件：`model.srcshape` 或版本化等价格式；
- canonical landmarks；
- geometry ratios；
- quality / confidence；
- schema version；
- 保存、加载、兼容、缺失回退。

### Batch 6：Shape-aware Merge MVP

任务：

- Hybrid Landmark；
- src geometry + dst pose + dst expression；
- Piecewise Affine Warp；
- source shape power；
- 原 Merge 回退；
- 静态帧和短视频可运行。

### Batch 7：Shape-aware Mask 与 Temporal

任务：

- Shape-aware Soft Mask；
- 遮挡保护；
- landmark smoothing；
- warp smoothing；
- mask contour smoothing；
- 场景切换重置；
- 多脸状态隔离。

### Batch 8：联调与人工验收

任务：

- 固定素材 A/B；
- Baseline 与增强版对比；
- 参数默认值调整；
- 故障和回退记录；
- 更新文档状态；
- 准备未来 UI / Linux API。

---

## 8. 下一会话应立即执行的工作

新会话启动后，建议严格按以下顺序推进。

### Step 1：读取上下文

首先读取：

```text
.handoff/current.md
.handoff/handoff-20260726-initial-project-state.md
docs/README.md
docs/implementation/enhanced-dfl-master-implementation-plan.md
```

### Step 2：不要立即新增更多概念设计

除非代码审计发现现有设计确实缺失，否则不要继续增加大而泛的设计文档。

### Step 3：进入 Batch 1 源码复核

重点查看：

- SAEHD 模型训练入口；
- `unified_train()` 或当前等价函数；
- sample generator 输出格式；
- eyes / mouth mask 来源和传递；
- optimizer 创建、保存与恢复；
- mixed precision 逻辑；
- Merge 入口和默认配置读取。

### Step 4：生成第一个代码任务拆分

下一份开发文档建议是：

```text
docs/development/batch1-correctness-and-extension-foundation-tasks.md
```

它应是文件级、函数级任务清单，而不是新的架构论文。

至少包含：

- 目标文件；
- 目标函数；
- 修改内容；
- 风险；
- Feature Flag；
- 回退路径；
- smoke test；
- 完成标准。

### Step 5：开始第一批代码修改

第一批代码修改建议只处理：

1. 已确认的 Eyes / Mouth Priority 问题；
2. 必需的 Feature Flag / 配置兼容骨架；
3. 对应的最小 smoke test。

不要在同一个提交中同时引入全部 Loss、Sampling 和 Shape-aware Merge。

---

## 9. 开发规则与边界

### 9.1 必须遵守

- 所有新功能默认关闭；
- 旧模型继续可加载；
- 旧配置继续可运行；
- 新 sidecar 缺失时自动回退；
- 新模块异常时允许使用传统路径；
- 每个增强模块独立开关；
- 每个阶段先保证工程正常，再交给人工评估视觉效果；
- 代码状态必须同步更新到文档。

### 9.2 第一阶段禁止范围

当前不要优先执行：

- 替换 SAEHD；
- Diffusion 换脸；
- Transformer 主干；
- TPS 作为默认 Warp；
- 全自动视觉评分平台；
- 自动决定最佳 shape power；
- 完整 Web UI；
- 大规模服务化改造；
- 与核心目标无关的外围功能。

### 9.3 提交建议

后续代码提交应尽量保持单一目的，例如：

```text
fix(training): wire real eyes and mouth masks into priority loss
feat(config): add backward-compatible enhancement feature flags
feat(training): add sample metadata schema with fallback
feat(merge): add optional source shape template loader
feat(merge): add piecewise affine shape warp behind feature flag
```

避免将训练、Merge、UI 和服务化混合在同一个提交中。

---

## 10. 当前风险

### 10.1 文档与源码可能发生偏差

现有分析基于此前源码状态。正式改代码前必须重新读取当前分支，确认：

- 文件仍存在；
- 函数名未变化；
- 调用链未变化；
- 历史问题仍可复现。

### 10.2 Geometry Loss 可能依赖额外 landmark 能力

如果训练样本中不能直接稳定获得所需 geometry 表示，应优先使用现有 DFL landmarks 和离线 metadata，而不是立即在训练图中引入大型额外网络。

### 10.3 Shape-aware Merge 会遇到遮挡和侧脸问题

MVP 应优先覆盖：

- 正脸；
- 轻中度转头；
- 普通表情；
- 低遮挡。

强遮挡、大侧脸和极端表情应通过回退和降低 shape power 处理，而不是第一版强行解决。

### 10.4 Temporal 状态必须按人脸隔离

多脸视频中不能共用同一组 smoothing state。未来实现必须考虑 face track 或至少稳定的人脸索引。

### 10.5 人工测试结果尚未产生

当前所有预期收益都仍属于设计目标，不能写成已经验证的事实。

---

## 11. 项目完成标准

### 11.1 工程层完成标准

- 新旧配置兼容；
- 原训练流程正常；
- 原 Merge 流程正常；
- 所有新模块可独立关闭；
- checkpoint 保存和恢复正常；
- Source Shape Template 可版本化保存和加载；
- Shape-aware Merge 有传统路径回退；
- smoke test 可重复执行；
- 无明显 dtype、shape、路径、序列化错误。

### 11.2 人工效果层完成标准

由项目负责人基于固定素材评估：

- src 身份是否更明显；
- src 脸型是否改善；
- dst 表情和姿态是否正常；
- 边缘是否自然；
- 遮挡是否合理；
- 连续帧是否稳定；
- 参数调节是否符合预期；
- 相比 Baseline 是否值得保留。

---

## 12. Handoff 文档维护规范

后续每次重要阶段结束、任务中断或切换新会话时，应新增一份 handoff 文件。

### 12.1 文件命名

建议：

```text
.handoff/handoff-YYYYMMDD-HHMMSS-brief-topic.md
```

例如：

```text
.handoff/handoff-20260730-221500-batch1-correctness-fixes.md
```

### 12.2 current.md

`.handoff/current.md` 始终指向最新 handoff。

更新 handoff 时：

1. 新建带时间戳的 handoff；
2. 更新 `.handoff/current.md`；
3. 不删除历史 handoff；
4. 在新 handoff 中引用上一份 handoff；
5. 明确本次新增、修改、未完成和下一步。

### 12.3 后续 handoff 必须包含的章节

至少包含：

1. 基本信息；
2. 本次会话目标；
3. 已完成工作；
4. 实际修改文件；
5. 关键技术决策；
6. 代码当前状态；
7. 测试与验证结果；
8. 未完成事项；
9. 已知问题与风险；
10. 下一步明确任务；
11. 新会话启动顺序；
12. 相关提交与文档链接。

### 12.4 禁止写法

不要只写：

- “继续优化训练”；
- “后续完善 Merge”；
- “还有一些问题”；
- “代码基本完成”。

必须具体说明：

- 哪个文件；
- 哪个函数；
- 哪个开关；
- 哪个问题；
- 当前状态；
- 如何复现；
- 下一步做什么；
- 完成标准是什么。

---

## 13. 相关提交

当前最近的文档整理提交包括：

```text
4000822db726accb238c66d9ae339072c4cad0e9
更新 docs/README.md，建立新的统一索引和阶段路线

817f12b608c92f32e2149524a889078c50b6d4ef
新增 enhanced-dfl-master-implementation-plan.md

86c4713f100362e208eeaa564cb86ebb9f323341
新增人工质量验收与开发验证标准

f90fe86e966b187b8703355dd2807fc5274298b6
新增 Shape-aware Merge 实施计划

1495c8702f1a8476f1bf5b862323048e0fc45802
新增训练增强实施计划
```

---

## 14. 最终交接结论

项目已经从单纯的训练增强研究，演进为一套完整的 DeepFaceLab 核心引擎增强方案：

```text
训练正确性
+
数据和 Sampling
+
Identity Appearance
+
Identity Geometry
+
Source Shape Template
+
Shape-aware Merge
+
Mask
+
Temporal Stabilization
```

当前最重要的事情不是继续增加设计文档，而是：

```text
重新核对当前源码
        ↓
拆分 Batch 1 文件级任务
        ↓
修复 P0 正确性问题
        ↓
建立兼容的扩展骨架
        ↓
开始小步代码开发
```

新会话应从 `.handoff/current.md` 开始读取，并以 `docs/implementation/enhanced-dfl-master-implementation-plan.md` 作为实施主线。