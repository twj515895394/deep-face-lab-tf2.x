# DeepFaceLab TF2.x 增强版总实施计划

> 文档定位：本项目增强开发的唯一实施入口（Single Source of Execution Truth）  
> 适用范围：训练正确性、训练数据与采样、身份几何、脸型保持、Shape-aware Merge、通用画质增强、时序稳定、兼容与人工验收  
> 核心原则：先修正确性，再搭扩展骨架；先完成脸型闭环，再叠加通用画质 Loss。  
> 路线调整日期：2026-07-30

---

## 1. 当前状态与文档约束

当前事实状态：

```text
Batch 1：已完成计划内实现与轻量复核
Batch 2：计划内代码、测试和文档已完成
Batch 2 production sign-off：PENDING-WINDOWS-GPU
Batch 3：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```

Batch 2 的真实 Windows GPU SAEHD 验收尚未完成。在验收通过或维护者明确修改验收策略前：

- 不得把 Batch 2 写成生产签发完成；
- 不得把 Windows GPU Matrix 写成 PASS；
- 不得启动未经授权的 Batch 3 正式实施；
- 可以完成 Batch 3 之后的设计收口、Ticket 拆分和验收矩阵准备。

本文只维护未来开发顺序，不改变 Batch 1、Batch 2 已形成的历史 Ticket、Summary 和验收记录。

---

## 2. 为什么调整 Batch 3 之后的顺序

原路线将以下通用训练增强安排在脸型需求之前：

```text
Region Loss
Boundary Loss
Frequency Loss
Identity Appearance Loss
```

这些能力有助于局部质量、纹理、边缘和身份外观，但不能直接闭合当前最核心的问题：

```text
五官和纹理可以接近 src
但脸宽、下颌、下巴和外轮廓仍明显接近 dst
```

脸型需求又不能完全跳过 Loss Hook，因为 Identity Geometry、Landmark / Ratio Loss 本身需要稳定的 Loss 注册、配置、日志和异常保护。因此本次调整采用以下原则：

> 保留几何训练必需的最小 Loss Hook，将通用外观与画质 Loss 后移。

调整后的主线：

```text
训练正确性
   ↓
配置与扩展骨架
   ↓
Metadata / Smart Sampling
   ↓
最小 Loss Hook + Identity Geometry
   ↓
Source Shape Template
   ↓
Hybrid Landmark + Piecewise Affine Warp
   ↓
Shape-aware Mask + Temporal Stabilization
   ↓
Identity Appearance / Region / Boundary / Frequency
   ↓
联调、A/B、默认值与文档收口
```

这不是降低通用 Loss 的价值，而是把项目最具差异化的“src 脸型保留闭环”提前验证。

---

## 3. 最终目标

在不替换 SAEHD、不破坏旧模型和旧 Merge 的前提下，形成可选增强管线：

```text
Enhanced DeepFaceLab

Training Side
├── Correctness Fixes
├── Metadata / Smart Sampling
├── Minimal Loss Hook
├── Identity Geometry
├── Identity Appearance / Detail Losses
└── Curriculum

Geometry Bridge
└── Source Shape Template

Merge Side
├── Hybrid Landmark
├── Piecewise Affine Warp
├── Shape-aware Soft Mask
└── Temporal Stabilization
```

增强能力必须满足：

1. 默认关闭时保持原始行为；
2. 可按模块独立启用和回滚；
3. 旧 checkpoint、旧模型、旧 DFM 和旧 Merge 参数继续可用；
4. 新 sidecar 缺失、损坏或版本不支持时能够安全回退；
5. 开发层由自动测试和环境测试保证可运行；
6. 视觉效果由固定条件下的人工 A/B 验收；
7. 第一版不引入大型新网络、Diffusion、Transformer 或强耦合服务化改造。

---

## 4. 两个核心问题必须分别解决

### 4.1 训练侧

训练侧回答：

> 模型是否真正学到了完整的 src 身份，包括外观与稳定几何？

训练侧主要负责：

- 正确性和数值稳定；
- Metadata 与智能采样；
- Shape Anchor；
- Landmark / Ratio Loss；
- Identity Geometry；
- 后续 Identity Appearance、Region、Boundary、Frequency；
- Curriculum Training。

### 4.2 Merge 侧

Merge 侧回答：

> 即使模型学到了 src geometry，最终回贴是否仍被 dst landmarks、单一 Affine 和 dst mask 强制恢复为 dst 几何？

Merge 侧主要负责：

- Source Shape Template；
- Hybrid Landmark；
- Piecewise Affine Warp；
- Shape-aware Soft Mask；
- 遮挡与低置信度回退；
- Temporal Stabilization。

核心结论：

```text
训练学会 src geometry
        ≠
最终视频保留 src geometry
```

只有训练侧和 Merge 侧都完成，才形成真正的脸型闭环。

---

## 5. 总体实施阶段

## Stage 0：冻结基线与开发边界

### 目标

明确当前代码、兼容要求和实施范围，避免开发过程中继续扩张目标。

### 工作项

- 确认原始启动、训练、保存、恢复和 Merge 链路；
- 记录 Python、TensorFlow、CUDA、GPU 与模型恢复环境；
- 所有增强能力默认关闭；
- 不改变 SAEHD 模型格式、旧 checkpoint、DFM 和旧命令入口。

### 阶段出口

- 原始流程可运行；
- 已知问题有记录；
- 增强功能不存在隐式默认启用。

---

## Stage 1：P0 训练正确性修复

### 目标

保证现有训练逻辑正确，再增加任何质量或几何优化。

### 工作项

- 修复 Eyes / Mouth Priority 的真实监督链路；
- 审计 FP16 / BF16、Loss Scaling、梯度 dtype 和 optimizer state；
- 验证保存、退出、恢复和优化器状态；
- 检查新增 Loss 前后的 shape、mask、dtype 和归一化范围；
- 为关键路径建立 smoke test。

### 阶段出口

- 原始训练正常迭代；
- 保存恢复不破坏；
- 关闭增强时保持基线；
- 核心异常保持原始失败语义。

---

## Stage 2：配置与扩展骨架

### 目标

建立统一配置、Feature Flag 和稳定 Hook，避免后续算法直接堆入 SAEHD 或 Merger 主文件。

### 工作项

- 统一训练、Merge 和 Runtime 配置；
- Loss、Sampling、Shape Merge 和 Temporal Hook；
- 独立开关、权重、状态日志和异常回退；
- 未提供新配置时保持旧行为；
- 为 GUI 和未来服务化提供稳定配置边界。

### 推荐模块

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
│   ├── shape_merge.py
│   └── shape_mask.py
└── temporal/
    └── stabilizer.py
```

---

## Stage 3：训练数据与采样增强（Batch 2）

### 目标

不改变模型结构，先改善模型实际看到的数据分布。

### 已实现主能力

- Metadata Schema、Identity 和 Fingerprint；
- Ordinary / Person / Packed Faceset Analyzer；
- Quick / Strong Fingerprint；
- Full / Incremental / Force；
- trusted match、stale detection 和 strict atomic write；
- `legacy_random`、`legacy_uniform_yaw`；
- `pose_balanced`、`quality_pose_balanced`；
- SRC / DST 独立采样配置；
- WeightedIndexHost 和 spawn 生命周期；
- Optional Metadata fallback 与核心错误传播；
- Trainer loss window、save、exit、resume 控制。

### 阶段出口

计划内代码、测试和文档已完成；生产签发仍等待真实 Windows GPU Matrix。

---

## Stage 4：最小 Loss Hook 与 Identity Geometry MVP（新 Batch 3）

### 目标

建立脸型训练必需的最小 Loss 基础设施，并优先验证 src Identity Geometry 是否可以被稳定学习。

### 4.1 最小 Loss Hook

必须实现：

- Loss 注册、调用和汇总；
- 每个 Loss 的独立开关与权重；
- 单项 Loss 数值日志；
- NaN / Inf 和非有限梯度保护；
- dtype、shape 和 mask 契约；
- 默认关闭和旧 checkpoint 兼容；
- 保存恢复后开关、权重和阶段状态一致。

本阶段不要求实现完整的通用画质 Loss 集合。

### 4.2 Shape Anchor

从 src faceset 中选择或聚合：

- Landmark 可信；
- 接近正脸；
- 清晰度较高；
- 遮挡较少；
- 表情相对稳定；

的样本，形成 Identity Geometry Anchor。

### 4.3 Landmark / Ratio Loss

优先约束稳定比例，而不是复制某一帧的绝对坐标：

- face width / face height；
- jaw width；
- chin length；
- cheek ratio；
- eye distance / face width；
- nose width / face width。

### 4.4 src / dst 几何职责

```text
src：脸宽、下颌、下巴、颧骨、稳定五官比例
dst：yaw、pitch、roll、眼睛开合、嘴型、表情和运动
```

Geometry Loss 不得强行把 src 的姿态和静态表情复制到 dst。

### 4.5 最小 Curriculum

第一版只需要：

```text
阶段 A：传统 Reconstruction
阶段 B：Geometry Loss 逐步升权
阶段 C：Geometry 权重稳定
```

暂不在这一批加入完整 Appearance / Boundary / Frequency 阶段。

### 阶段出口

- Loss Hook 可扩展但保持最小；
- Geometry Loss 可独立关闭；
- `geometry_weight = 0` 等价基线；
- 不出现 NaN、梯度爆炸和 checkpoint 不兼容；
- 可输出固定条件下的 Geometry A/B 预览与指标；
- 为 Source Shape Template 提供可信几何数据。

---

## Stage 5：Source Shape Template（新 Batch 4）

### 目标

建立训练侧和 Merge 侧之间的几何桥梁。

### 产物

建议使用独立 sidecar：

```text
model.srcshape
```

### 内容

- canonical landmarks；
- face width / jaw / cheek / chin ratios；
- shape anchor；
- quality 与 confidence；
- source identity / faceset fingerprint；
- schema version 和 generator version。

### 原则

- 不修改旧模型权重格式；
- 支持生成、保存、加载、校验和重建；
- artifact 缺失或异常时回退传统 Merge；
- 第一版允许由 src faceset 离线生成；
- 训练产生的数据与离线生成结果需要定义权威优先级。

### 阶段出口

- Shape Template 生命周期完整；
- 不影响旧模型加载；
- 版本、身份和 faceset 不匹配时不得静默使用。

---

## Stage 6：Shape-aware Merge MVP（新 Batch 5）

### 目标

在 Merge 阶段真正应用 src Identity Geometry，同时保留 dst 姿态和表情。

### 6.1 Hybrid Landmark

```text
Hybrid Landmark
=
src Identity Geometry
+ dst Pose
+ dst Expression Offset
```

工作项：

- Landmark 分区；
- canonical → dst pose 映射；
- `source_shape_power`；
- 表情保持约束；
- 大角度、遮挡和低置信度回退。

### 6.2 Piecewise Affine Warp

第一版采用 Piecewise Affine，不优先使用 TPS 或网络化 Warp。

必须保证：

- 三角拓扑稳定；
- 不出现三角翻转、空洞和明显越界；
- Warp 可独立关闭；
- `source_shape_power = 0` 等价传统几何；
- 失败时回退传统 Merge。

### 阶段出口

- src 脸宽、下颌和下巴趋势能够进入最终预测回贴；
- dst 姿态和表情保持；
- 旧 Merge 路径始终可用。

---

## Stage 7：Shape-aware Mask 与 Temporal（新 Batch 6）

### 目标

避免 Mask 把脸型重新裁回 dst 轮廓，并消除逐帧几何增强的跳动。

### 7.1 Shape-aware Soft Mask

原则：

- 中心身份区域优先 src；
- 外轮廓使用软过渡；
- 遮挡区域保持 dst；
- 不把 `predicted_mask * dst_mask` 作为唯一规则；
- Shape Mask 与传统 Mask 可切换。

### 7.2 遮挡与置信度回退

需要处理：

- 手、头发、眼镜、麦克风等遮挡；
- 极端侧脸；
- Landmark 低置信度；
- Shape Template 低置信度；
- Warp 质量异常。

### 7.3 Temporal Stabilization

第一版优先：

- Landmark EMA / One Euro Filter；
- Warp 参数平滑；
- Mask contour 平滑；
- `source_shape_power` 平滑；
- Scene Cut / Tracking Reset；
- 单帧模式不强制启用时序模块。

### 阶段出口

- 不出现明显脸宽、下巴和边缘闪动；
- 场景切换能够重置状态；
- 遮挡和异常帧能够降级或回退。

---

## Stage 8：身份外观与通用画质 Loss（新 Batch 7）

### 目标

在脸型训练、几何桥梁、Warp、Mask 和 Temporal 闭环稳定后，再增加通用身份外观和画质优化。

### 工作项

- Identity Appearance Loss；
- Region Loss；
- Boundary Loss；
- Frequency Loss；
- 完整 Multi-objective Curriculum；
- 单项 Loss 指标与消融实验。

### 推荐实施顺序

1. Identity Appearance Loss；
2. Region Loss；
3. Boundary Loss；
4. Frequency Loss；
5. 完整 Curriculum 与组合权重。

### 原则

- 每个 Loss 独立开关和权重；
- 不强制依赖大型外部识别模型；
- 不允许总 Loss 掩盖单项异常；
- 逐项 A/B，不一次性启用全部目标；
- 以已稳定的 Geometry / Shape Merge 作为固定基线。

### 阶段出口

- 能明确区分每个 Loss 的收益、性能成本和副作用；
- 不破坏脸型保持、表情保持和视频稳定；
- 完整关闭后保持上一批稳定基线。

---

## Stage 9：联调与人工验收（Batch 8）

### 开发层验证

- 配置解析和 Feature Flag；
- 训练迭代；
- 单项 Loss；
- checkpoint 保存与恢复；
- Shape Template 生命周期；
- Merge、Warp、Mask 和 Temporal；
- 旧流程回归；
- 异常回退和资源清理；
- 日志与错误定位。

### 效果层验收

- src 身份外观；
- src 脸型和骨相保留；
- dst 姿态和表情；
- 拉伸、错位、空洞和边缘；
- 遮挡；
- 视频抖动和闪烁；
- 参数强度的主观合理性；
- 性能、显存和训练速度变化。

### 收口产物

- 固定 A/B 样例；
- 参数默认值和推荐预设；
- 兼容与回退说明；
- GUI 参数接入说明；
- 状态矩阵和用户文档；
- 已知限制和后续实验列表。

---

## 6. 模块依赖关系

```text
P0 Correctness
      ↓
Config / Feature Flag
      ↓
Metadata & Sampling
      ↓
Minimal Loss Hook
      ↓
Identity Geometry
      ↓
Source Shape Template
      ↓
Hybrid Landmark
      ↓
Piecewise Affine Warp
      ↓
Shape-aware Mask
      ↓
Temporal Stabilization
      ↓
Appearance / Region / Boundary / Frequency
      ↓
Manual Acceptance
```

允许提前并行的设计工作：

- Batch 3 Ticket、配置 Schema 和验收矩阵；
- Source Shape Template Schema 草案；
- Merge Hook 的接口审计；
- GPU A/B 素材和固定条件准备。

不得提前的实施：

- 未完成正确性和 Batch 2 环境门，不正式进入 Batch 3；
- 未建立最小 Loss Hook，不实现 Geometry Loss 主链路；
- 未有可信 Shape Template，不正式实现 Hybrid Landmark；
- 未有稳定 Warp，不优先实现复杂 Mask 或 Temporal；
- 未完成脸型闭环，不批量叠加通用画质 Loss；
- 核心链路未稳定前，不进入完整 UI / Linux 服务化。

---

## 7. 推荐开发批次

### Batch 1：最小安全改造

- Eyes / Mouth Priority；
- Feature Flag 与配置读取；
- 训练和 Merge smoke test；
- 旧流程回归。

状态：计划内实现已完成；历史环境验证事实以对应交接和报告为准。

### Batch 2：训练数据与采样增强

- Faceset Metadata；
- Quality / Pose Sampling；
- SRC / DST 独立策略；
- 日志、Fallback 和 Trainer Control。

状态：代码、测试和文档完成；生产签发等待 Windows GPU Final Matrix。

### Batch 3：Identity Geometry 训练基础

- 最小 Loss Hook；
- Shape Anchor；
- Landmark / Ratio Loss；
- Identity Geometry；
- 最小 Geometry Curriculum；
- 单项 Loss 日志和兼容验证。

### Batch 4：Shape Bridge

- Source Shape Template 生成、保存、加载；
- Schema、Identity / Faceset 校验；
- 重建与 Fallback。

### Batch 5：Shape-aware Merge MVP

- Hybrid Landmark；
- Piecewise Affine Warp；
- `source_shape_power`；
- 独立开关与低置信度回退。

### Batch 6：Mask 与 Temporal

- Shape-aware Soft Mask；
- 遮挡回退；
- Landmark / Warp / Mask / Shape Power 平滑；
- Scene Cut Reset。

### Batch 7：身份外观与画质增强

- Identity Appearance；
- Region；
- Boundary；
- Frequency；
- 完整 Multi-objective Curriculum。

### Batch 8：联调与文档收口

- 人工 A/B；
- 参数默认值和预设；
- 性能与兼容验收；
- GUI 接入；
- 状态矩阵和用户文档。

---

## 8. 第一版 MVP 范围

第一版必须完成：

1. P0 训练正确性修复；
2. Feature Flag、配置和兼容回退；
3. Metadata 与 Weighted Sampling；
4. 最小 Loss Hook；
5. 至少一个 Identity Geometry / Ratio Loss 实验入口；
6. Source Shape Template Sidecar；
7. Hybrid Landmark；
8. Piecewise Affine Warp；
9. Shape-aware Soft Mask；
10. 基础 Temporal Smoothing；
11. 开发 smoke test 和人工验收说明。

第一版明确不要求：

- 全量 Identity Appearance / Region / Boundary / Frequency 同时完成；
- 替换 SAEHD；
- 大规模新网络；
- Diffusion / Transformer；
- 自动化视觉质量评分平台；
- 自动选择最佳参数；
- 完整 Web UI 与任务服务化；
- TPS 大形变作为默认方案。

---

## 9. 每个任务的完成定义

任一开发任务只有同时满足以下条件才可标记完成：

```text
代码存在
+
接入主链路
+
默认关闭或兼容默认值
+
自动或环境验证通过
+
失败可回退
+
状态和文档已更新
```

视觉算法任务还必须：

```text
输出可供人工 A/B 判断的结果
```

Agent 可以验证工程事实，但不得代替人工宣称主观视觉质量已经达到最终标准。

---

## 10. 文档角色与阅读顺序

### 唯一实施入口

1. `implementation/enhanced-dfl-master-implementation-plan.md`（本文）

### 当前状态

2. `.handoff/current.md`
3. Batch 对应 Ticket、Summary 和验收报告

### 训练专项

4. `implementation/training-enhancement-implementation-plan.md`
5. `optimization/training-quality-algorithm-roadmap.md`
6. `optimization/src-dst-training-quality-optimization-design.md`
7. `optimization/src-face-shape-preservation-design.md`
8. `optimization/training-ablation-experiment-plan.md`

### Shape-aware Merge 专项

9. `optimization/src-face-shape-training-and-shape-aware-merge-design.md`
10. `optimization/shape-aware-merge-implementation-design.md`
11. `implementation/merge-shape-aware-implementation-plan.md`

### 工程与验证

12. `implementation/deepfacelab-config-and-extension-architecture.md`
13. `implementation/deepfacelab-code-modification-map.md`
14. `implementation/manual-quality-acceptance-and-development-validation-standard.md`
15. `validation/training-benchmark-specification.md`

---

## 11. 文档维护规则

- 本文维护总阶段、依赖、优先级和当前 Frontier；
- 专项算法细节写入 `optimization/`；
- 文件、类、函数和任务拆分写入 `implementation/`；
- 当前代码事实写入 `analysis/`；
- 验收条件和结果写入 `validation/` 或 `.scratch/.../reports/`；
- 历史 Ticket 和 Summary 不因未来路线调整而重写；
- 专项方案与本文冲突时，以本文的顺序和兼容原则为准；
- 每次正式启动或完成一个 Batch，必须同步更新本文、Handoff 和必要索引。

---

## 12. 当前 Frontier

```text
当前开发 Frontier：无剩余 Batch 2 计划内代码 Ticket
当前验收 Frontier：Ticket 21 Windows GPU Final Matrix
Batch 2 implementation：COMPLETE
Batch 2 production sign-off：PENDING-WINDOWS-GPU
Next planned batch：Batch 3 Identity Geometry 训练基础
Batch 3 implementation：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```

Batch 2 最终签发后，下一步应按以下顺序执行：

```text
1. 冻结 Batch 3 需求和非目标
2. 拆分最小 Loss Hook / Shape Anchor / Ratio Loss / Geometry Curriculum Ticket
3. 建立 Windows GPU Geometry A/B Matrix
4. 实施最小 Loss Hook
5. 实施 Identity Geometry MVP
6. 进入 Source Shape Template
7. 进入 Shape-aware Merge MVP
8. 完成 Mask / Temporal
9. 最后叠加通用画质 Loss
```

这条顺序是后续 Codex、Claude 或人工开发任务拆分的统一依据。