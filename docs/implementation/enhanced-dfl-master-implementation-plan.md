# DeepFaceLab TF2.x 增强版总实施计划

> 文档定位：本项目增强开发的唯一实施入口（Single Source of Execution Truth）  
> 适用范围：训练正确性、训练质量、身份几何、脸型保持、Shape-aware Merge、时序稳定、兼容与人工验收  
> 原则：先修正确性，再搭扩展框架；先做最小闭环，再逐步增加算法能力。

---

## 1. 为什么需要这份总计划

项目文档最初围绕“训练增强”展开，之后逐步扩展到：

- src / dst 职责重新划分；
- Identity Appearance 与 Identity Geometry 的统一表达；
- src 脸型在训练阶段的学习；
- src 脸型在 Merge 阶段的实际保留；
- Shape-aware Mask 与视频时序稳定；
- 配置、Feature Flag、旧模型兼容和未来 UI 接入。

这些内容并不是互相独立的功能，而是一条连续链路：

```text
训练正确性
   ↓
训练扩展框架
   ↓
数据与采样增强
   ↓
身份外观与身份几何学习
   ↓
Source Shape Template
   ↓
Hybrid Landmark
   ↓
Shape-aware Warp / Mask
   ↓
Temporal Stabilization
   ↓
人工视觉验收
```

本文件负责规定实施顺序、模块依赖、阶段出口和文档阅读入口。后续开发任务应以本文件为总纲，专项文档只负责解释某一模块的细节。

---

## 2. 最终目标

在不替换 SAEHD、不破坏旧模型和旧 Merge 的前提下，形成可选增强管线：

```text
Enhanced DeepFaceLab

Training Side
├── Correctness Fixes
├── Metadata / Smart Sampling
├── Multi-objective Loss
├── Identity Geometry
└── Curriculum

Geometry Bridge
└── Source Shape Template

Merge Side
├── Hybrid Landmark
├── Piecewise Affine Warp
├── Shape-aware Mask
└── Temporal Stabilization
```

增强能力必须满足：

1. 默认关闭时保持原始行为。
2. 可按模块独立启用和回滚。
3. 旧 checkpoint、旧模型和旧 Merge 参数继续可用。
4. 开发层由代码测试保证可运行，视觉质量由人工验收。
5. 不在第一阶段引入新的大型网络、Diffusion、Transformer 或强耦合服务化改造。

---

## 3. 两个核心问题必须分开解决

### 3.1 训练侧问题

训练侧回答：

> 模型是否真正学到了完整的 src 身份，包括纹理、五官和脸型几何？

主要手段：

- 修复训练正确性问题；
- 恢复 Eyes / Mouth Priority 的真实监督；
- metadata 与采样优化；
- Identity、Geometry、Region、Boundary、Frequency 等损失扩展；
- curriculum training。

### 3.2 Merge 侧问题

Merge 侧回答：

> 即使模型学到了 src 脸型，最终回贴是否仍被 dst landmarks、Affine 和 dst mask 强制恢复为 dst 几何？

主要手段：

- Source Shape Template；
- Hybrid Landmark；
- Piecewise Affine Warp；
- Shape-aware Soft Mask；
- Temporal Stabilization。

结论：

```text
训练学会 src geometry
        ≠
最终视频保留 src geometry
```

两条路线必须分别完成，再联调形成闭环。

---

## 4. 总体实施阶段

## Stage 0：冻结基线与开发边界

### 目标

明确当前代码、兼容要求和实施范围，避免开发过程中继续扩张目标。

### 工作项

- 确认当前主分支能够启动、训练、保存、恢复和 Merge。
- 记录 Python、TensorFlow、CUDA、GPU 与模型恢复环境。
- 将所有增强能力设为默认关闭。
- 确定不改动的核心边界：SAEHD 模型格式、旧 checkpoint、旧命令入口。

### 阶段出口

- 原始流程可运行；
- 已有问题有明确记录；
- 增强功能不存在隐式默认启用。

### 主要文档

- `analysis/dfl-current-project-overview.md`
- `analysis/dfl-tf2-upgrade-analysis.md`
- `analysis/implementation-status-and-risk-matrix.md`
- `implementation/deepfacelab-source-code-audit.md`
- `implementation/deepfacelab-tf2x-source-tree-analysis.md`

---

## Stage 1：P0 训练正确性修复

### 目标

先保证现有训练逻辑正确，再叠加任何质量优化。

### 优先工作项

1. 修复 `unified_train()` 中 Eyes / Mouth Priority 使用空 mask 的问题。
2. 审计 FP16 / BF16、Loss Scaling、梯度 dtype 和 optimizer state。
3. 检查模型保存、恢复和优化器状态兼容。
4. 确认新增 loss 前后张量 shape、mask 和归一化范围一致。
5. 为关键路径补充最小 smoke test。

### 阶段出口

- 原始训练可正常迭代；
- Eyes / Mouth Priority 的监督实际生效；
- 保存和恢复不破坏；
- 关闭增强功能时行为与原基线一致。

### 主要文档

- `optimization/training-correctness-audit.md`
- `implementation/deepfacelab-training-call-chain-analysis.md`
- `implementation/deepfacelab-code-modification-map.md`

---

## Stage 2：配置与扩展骨架

### 目标

先建立可维护的 Hook、配置与 Feature Flag，避免后续算法代码直接堆入 SAEHD 或 Merge 主文件。

### 工作项

- 建立统一 Feature Flag。
- 定义训练、Merge、运行时配置结构。
- 建立 loss hook、sampling hook、shape merge hook。
- 预留日志和运行状态输出。
- 所有新模块支持关闭和异常回退。

### 推荐目录

```text
core/
├── training/
│   ├── losses/
│   ├── sampling/
│   └── curriculum/
├── shape/
│   ├── source_shape_template.py
│   ├── hybrid_landmark.py
│   └── shape_warp.py
├── merge/
│   └── shape_merge.py
└── temporal/
    └── stabilizer.py
```

### 阶段出口

- 新功能可配置；
- 默认关闭；
- 主训练和 Merge 流程只保留稳定 Hook；
- 不因未提供新配置而改变旧行为。

### 主要文档

- `implementation/deepfacelab-config-and-extension-architecture.md`
- `implementation/deepfacelab-code-modification-map.md`

---

## Stage 3：训练数据与采样增强

### 目标

不改模型结构，先改善模型实际看到的数据分布。

### 工作项

- 样本 metadata：quality、pose、occlusion、landmark confidence、shape anchor。
- Quality Sampling。
- Pose / yaw / pitch bucket sampling。
- Shape-aware Sampling。
- 针对严重模糊、遮挡和错误 landmarks 的降权。
- 保持旧随机采样作为 fallback。

### 实施建议

第一版只实现低成本 metadata 和权重采样，不在此阶段引入复杂离线分析服务。

### 阶段出口

- 关闭时使用原采样；
- 开启时分布可记录、可复现；
- 不因 metadata 缺失导致训练中断；
- 采样逻辑不改变数据张量接口。

### 主要文档

- `optimization/training-quality-algorithm-roadmap.md`
- `optimization/src-dst-training-quality-optimization-design.md`
- `implementation/training-enhancement-implementation-plan.md`

---

## Stage 4：训练 Loss 扩展与身份表示增强

### 目标

让训练目标从单纯 reconstruction 扩展为完整身份表示。

### 推荐实施顺序

1. Region Loss / Eyes-Mouth 修复与权重统一。
2. Boundary Loss。
3. Frequency Loss。
4. Identity Appearance Loss。
5. Landmark / Shape Loss。
6. Identity Geometry Loss。

### 总目标

```text
Identity
=
Appearance
+
Geometry
```

### 注意事项

- 每个 loss 独立开关和权重。
- 新 loss 必须记录单项数值，避免总 loss 掩盖异常。
- 第一版不强制依赖大型外部识别模型。
- Geometry Loss 应围绕稳定几何比例和 landmark 关系，不直接追求大形变。

### 阶段出口

- 每个 loss 可独立启用；
- 关闭后保持基线；
- 不出现 NaN、梯度爆炸或 checkpoint 不兼容；
- 训练预览可供人工观察身份与轮廓变化。

### 主要文档

- `optimization/src-face-shape-preservation-design.md`
- `optimization/src-face-shape-training-and-shape-aware-merge-design.md`
- `implementation/training-enhancement-implementation-plan.md`
- `optimization/training-ablation-experiment-plan.md`

---

## Stage 5：Curriculum Training

### 目标

控制增强能力启用顺序，避免训练早期同时优化过多目标。

### 推荐阶段

```text
Stage A：基础 reconstruction + 强 warp
Stage B：Identity Appearance
Stage C：Identity Geometry / Shape
Stage D：Boundary / Frequency / Detail
```

### 实施要求

- 支持按 iteration 或手动阶段切换；
- 阶段状态写入 checkpoint 或训练配置；
- 恢复训练时不得错误回到初始阶段；
- 第一版优先支持显式配置，不做自动智能调度。

### 阶段出口

- 阶段切换可追踪；
- 恢复逻辑正确；
- 用户可关闭 curriculum 使用传统训练。

---

## Stage 6：Source Shape Template

### 目标

建立训练侧与 Merge 侧之间的几何桥梁。

### 产物

建议新增：

```text
model.srcshape
```

或等价的独立 sidecar artifact。

### 内容

- canonical landmarks；
- face width / jaw / cheek / chin ratios；
- shape anchor；
- quality 与 confidence；
- schema version。

### 原则

- 不直接改旧模型权重格式；
- artifact 缺失时自动回退传统 Merge；
- 支持版本校验和重建；
- 第一版允许由 src faceset 离线生成。

### 阶段出口

- Shape Template 可生成、保存、加载和校验；
- 不影响旧模型加载；
- 异常或缺失时安全回退。

### 主要文档

- `optimization/src-face-shape-training-and-shape-aware-merge-design.md`
- `optimization/shape-aware-merge-implementation-design.md`
- `implementation/merge-shape-aware-implementation-plan.md`

---

## Stage 7：Hybrid Landmark Engine

### 目标

将 src 身份几何与 dst 姿态、表情分离组合。

### 责任划分

```text
src：脸宽、下颌、下巴、颧骨、稳定比例

dst：姿态、眼睛开合、嘴型、表情、运动
```

### 工作项

- landmark 分区；
- canonical → dst pose 映射；
- source shape power；
- 表情保持约束；
- 极端姿态和遮挡回退。

### 阶段出口

- 输出 landmark 数量、顺序和坐标范围稳定；
- `source_shape_power = 0` 等价传统几何；
- 大角度或低置信度时可降低增强强度。

---

## Stage 8：Shape Warp 与 Shape-aware Mask

### 目标

让 Hybrid Landmark 真正作用到预测脸，并避免 mask 再次裁回 dst 轮廓。

### 第一版 Warp

```text
Piecewise Affine Warp
```

暂不优先 TPS 或网络化 warp。

### Mask 原则

- 中心身份区域优先 src；
- 轮廓边缘采用软过渡；
- 遮挡区域保持 dst；
- 不简单使用 `prd * dst` 作为唯一规则。

### 阶段出口

- Warp 可独立开关；
- 不出现空洞、三角翻转和明显越界；
- Shape Mask 与传统 mask 可切换；
- 失败时回退传统 Merge。

### 主要文档

- `analysis/merging-architecture-analysis.md`
- `implementation/deepfacelab-merger-call-chain-analysis.md`
- `optimization/shape-aware-merge-implementation-design.md`
- `implementation/merge-shape-aware-implementation-plan.md`

---

## Stage 9：Temporal Stabilization

### 目标

消除单帧几何增强在视频中的跳动。

### 工作项

- landmark smoothing；
- warp parameter smoothing；
- mask contour smoothing；
- scene cut / tracking reset；
- 极端帧 confidence gate。

### 第一版建议

优先 EMA 或 One Euro Filter，不引入复杂光流网络。

### 阶段出口

- 静态和连续运动视频不出现明显脸宽、下巴和边缘闪动；
- 场景切换时状态可重置；
- 单帧模式不强制启用时序模块。

---

## Stage 10：联调与人工验收

### 开发层验证

由 Agent、开发者或 CI 负责：

- 启动；
- 配置解析；
- Feature Flag；
- 训练迭代；
- checkpoint 保存与恢复；
- Merge 执行；
- 旧流程回归；
- 异常回退；
- 日志与错误定位。

### 效果层验收

由人工负责：

- src 身份相似度；
- src 脸型保留；
- dst 表情与姿态；
- 拉伸、错位和边缘；
- 遮挡；
- 视频抖动和闪烁；
- 参数强度的主观合理性。

### 主要文档

- `implementation/manual-quality-acceptance-and-development-validation-standard.md`
- `optimization/training-ablation-experiment-plan.md`
- `validation/training-benchmark-specification.md`（仅作为人工固定条件参考，不作为第一阶段自动评分系统）

---

## 5. 模块依赖关系

```text
P0 Correctness
      ↓
Config / Feature Flag
      ↓
Metadata & Sampling
      ↓
Loss Hook
      ↓
Identity Geometry
      ↓
Source Shape Template
      ↓
Hybrid Landmark
      ↓
Shape Warp
      ↓
Shape Mask
      ↓
Temporal Stabilization
      ↓
Manual Acceptance
```

以下模块可并行：

- 配置框架与开发 smoke tests；
- Shape Template schema 设计与训练 loss 开发；
- Merge 侧 Hook 骨架与训练侧 metadata。

以下模块不应提前：

- 未完成正确性修复前，不应叠加复杂 loss；
- 未有 Shape Template 前，不应正式实现 Hybrid Landmark；
- 未有稳定 Warp 前，不应优先做复杂时序；
- 核心链路未稳定前，不进入 UI/Linux 服务化。

---

## 6. 推荐开发批次

### Batch 1：最小安全改造

- 修复 Eyes / Mouth Priority。
- Feature Flag 与配置读取。
- 训练和 Merge smoke test。
- 旧流程回归。

状态：已完成 macOS 轻量实现与复核。Windows GPU 真实训练、保存恢复、Merge 质量与 FP16/BF16 稳定性仍待补证。

### Batch 2：训练数据增强

- metadata schema。
- quality / pose sampling。
- 日志与 fallback。

### Batch 3：Loss Hook

- Region / Boundary / Frequency。
- Identity Appearance。
- 单项 loss 日志。

### Batch 4：Identity Geometry

- Shape anchor。
- Landmark / ratio loss。
- Curriculum 阶段。

### Batch 5：Shape Bridge

- Source Shape Template 生成、保存、加载。
- schema version 与 fallback。

### Batch 6：Shape-aware Merge MVP

- Hybrid Landmark。
- Piecewise Affine Warp。
- source shape power。
- 独立开关。

### Batch 7：Mask 与 Temporal

- Shape-aware Soft Mask。
- 遮挡回退。
- landmark / warp / mask smoothing。

### Batch 8：联调与文档收口

- 人工 A/B 样例。
- 参数默认值修订。
- 兼容说明。
- 更新状态矩阵与用户使用说明。

---

## 7. 第一版 MVP 范围

第一版必须完成：

1. P0 训练正确性修复。
2. Feature Flag 和兼容回退。
3. 简单 metadata 与 weighted sampling。
4. Loss Hook 与至少一个 Identity Geometry 实验入口。
5. Source Shape Template sidecar。
6. Hybrid Landmark。
7. Piecewise Affine Warp。
8. Shape-aware Soft Mask。
9. 基础 EMA 时序平滑。
10. 开发 smoke test 与人工验收说明。

第一版明确不做：

- 替换 SAEHD；
- 大规模新网络；
- Diffusion / Transformer；
- 自动化视觉质量评分平台；
- 自动选择最佳参数；
- 完整 Web UI 与任务服务化；
- TPS 大形变作为默认方案。

---

## 8. 每个任务的完成定义

任一开发任务只有同时满足以下条件才可标记完成：

```text
代码存在
+
已接入主链路
+
默认关闭或兼容默认值
+
基本运行验证通过
+
失败可回退
+
文档状态已更新
```

视觉算法任务还需要：

```text
已输出可供人工 A/B 判断的结果
```

但不要求 Agent 自动判断“效果是否达到最终标准”。

---

## 9. 文档角色与阅读顺序

### 唯一实施入口

1. `implementation/enhanced-dfl-master-implementation-plan.md`（本文）

### 了解当前代码

2. `analysis/dfl-current-project-overview.md`
3. `analysis/training-architecture-analysis.md`
4. `analysis/merging-architecture-analysis.md`
5. `implementation/deepfacelab-training-call-chain-analysis.md`
6. `implementation/deepfacelab-merger-call-chain-analysis.md`

### 训练专项

7. `optimization/training-correctness-audit.md`
8. `optimization/training-quality-algorithm-roadmap.md`
9. `optimization/src-dst-training-quality-optimization-design.md`
10. `optimization/src-face-shape-preservation-design.md`
11. `implementation/training-enhancement-implementation-plan.md`

### Shape-aware Merge 专项

12. `optimization/src-face-shape-training-and-shape-aware-merge-design.md`
13. `optimization/shape-aware-merge-implementation-design.md`
14. `implementation/merge-shape-aware-implementation-plan.md`

### 工程与验证

15. `implementation/deepfacelab-config-and-extension-architecture.md`
16. `implementation/deepfacelab-code-modification-map.md`
17. `implementation/manual-quality-acceptance-and-development-validation-standard.md`

---

## 10. 后续文档维护规则

- 本文只维护总阶段、依赖、优先级和完成状态。
- 专项算法细节继续写入 `optimization/`。
- 实际文件、类、函数和任务拆分写入 `implementation/`。
- 当前代码事实写入 `analysis/`。
- 人工验收、固定条件和结果记录写入 `validation/`。
- 某专项方案与本文冲突时，以本文的实施顺序和兼容原则为准。
- 每完成一个 Batch，应同步更新本文和 `docs/README.md`，不再创建第二份总路线。

---

## 11. 当前建议启动点

Batch 1 的 macOS 轻量实现与复核已经完成，后续不应继续把 Batch 1 当作未开工任务。

当前建议从以下顺序开始：

```text
1. 将 Windows GPU 验证清单转成可执行 checklist
2. 建立 Batch 2 ticket 边界
3. Metadata / Sampling MVP
4. Loss Hook MVP
5. Identity Geometry MVP
6. Source Shape Template
7. Shape-aware Merge MVP
8. Temporal
9. 人工验收与参数调整
```

这条顺序同时覆盖最初的训练增强目标和后续的脸型训练、合成优化目标，是后续 Codex、Claude 或人工开发任务拆分的统一依据。
