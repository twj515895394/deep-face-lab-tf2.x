# DeepFaceLab TF2.x 文档总索引

> 文档版本：v2.3  
> 更新日期：2026-07-30  
> 定位：项目文档导航。总体开发顺序以统一总实施计划为准；当前事实状态以 `.handoff/current.md` 和对应验收报告为准。

---

## 1. 唯一实施入口

后续进行代码开发、任务拆分、Agent 协作或进度判断时，先阅读：

- [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)
- [最新交接入口](../.handoff/current.md)

统一路线：

```text
训练正确性与扩展骨架（Batch 1）
        ↓
Metadata / Smart Sampling（Batch 2）
        ↓
Minimal Loss Hook + Identity Geometry（Batch 3）
        ↓
Source Shape Template（Batch 4）
        ↓
Hybrid Landmark + Piecewise Affine Warp（Batch 5）
        ↓
Shape-aware Soft Mask + Temporal（Batch 6）
        ↓
Identity Appearance / Region / Boundary / Frequency（Batch 7）
        ↓
联调、A/B、默认值、GUI、兼容与文档（Batch 8）
```

关键原则：

> 不是跳过 Loss Hook，而是保留 Geometry 必需的最小 Loss 基础设施，将通用外观和画质 Loss 后移到脸型闭环稳定之后。

专项文档解释模块细节，不再各自决定总体实施顺序。

---

## 2. 当前状态

当前分支：

```text
codex/batch2-ticket19-loss-window
```

准确状态：

```text
Batch 1：计划内实现已完成
Batch 2：计划内代码、测试和文档已完成
Ticket 14—20：代码门完成
Ticket 21：Windows GPU Final Matrix PENDING
Batch 2 production sign-off：PENDING-WINDOWS-GPU
Batch 3 implementation：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```

最新自动测试记录：

```text
OS：Windows
Python：3.11.7
start method：spawn
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
Ran 331 tests
OK
```

该结果不等价于 GitHub CI PASS，也不等价于真实 Windows GPU SAEHD Matrix 已通过。

当前 Ticket 21 环境事实：

```text
acceptance Python 未安装 TensorFlow
SAEHD GPU 训练未启动
Matrix A/B 未执行
GPU Gate：NOT PASS / PENDING-WINDOWS-GPU
```

不得把 Batch 2 写成生产签发完成，不得把 Batch 3 写成已经进入正式实施。

---

## 3. 当前批次入口

### Batch 1

- [P0 正确性与扩展安全骨架详细设计](development/batch1-correctness-and-extension-foundation-tasks.md)
- [训练正确性审计](optimization/training-correctness-audit.md)

### Batch 2

- [训练数据 Metadata 与 Quality / Pose Sampling 详细设计](development/batch2-training-data-and-sampling-tasks.md)
- [Faceset Metadata 与智能采样用户指南](usage/faceset-metadata-and-sampling.md)
- [Faceset Analyzer 完整使用说明](usage/faceset-analyzer-complete-guide.md)
- [options-json 权威参考](implementation/options-json-training-configuration-reference.md)
- [Batch 2 GUI 参数接入说明](implementation/batch2-gui-parameter-integration.md)
- [最新 Handoff](../.handoff/current.md)

### 下一计划批次：Batch 3

Batch 3 尚未进入正式实施。设计边界：

```text
必须：
Minimal Loss Hook
Shape Anchor
Landmark / Ratio Loss
Identity Geometry
Minimal Geometry Curriculum
单项日志、数值保护、保存恢复和 GPU A/B

不包含：
Identity Appearance
Region
Boundary
Frequency
Full Multi-objective Curriculum
Shape-aware Merge 实施
```

Batch 3 启动条件：Ticket 21 Windows GPU Final Matrix 通过，或维护者明确记录验收豁免 / 延期策略。

---

## 4. 推荐阅读路径

### 4.1 快速了解项目

1. [当前项目架构与升级分析](analysis/dfl-current-project-overview.md)
2. [TF2.x 升级实现分析](analysis/dfl-tf2-upgrade-analysis.md)
3. [实现状态与风险矩阵](analysis/implementation-status-and-risk-matrix.md)
4. [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)
5. [最新交接入口](../.handoff/current.md)

### 4.2 了解完整处理链

1. [Extract / 切脸架构分析](analysis/extraction-architecture-analysis.md)
2. [训练架构分析](analysis/training-architecture-analysis.md)
3. [Merge / 合成架构分析](analysis/merging-architecture-analysis.md)
4. [TF2.x 源码树分析](implementation/deepfacelab-tf2x-source-tree-analysis.md)
5. [训练调用链分析](implementation/deepfacelab-training-call-chain-analysis.md)
6. [Merger 调用链分析](implementation/deepfacelab-merger-call-chain-analysis.md)

### 4.3 Batch 1 / Batch 2 复核

1. [Batch 1 详细设计](development/batch1-correctness-and-extension-foundation-tasks.md)
2. [Batch 2 详细设计](development/batch2-training-data-and-sampling-tasks.md)
3. [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)
4. [代码修改地图](implementation/deepfacelab-code-modification-map.md)
5. [人工质量验收与开发验证标准](implementation/manual-quality-acceptance-and-development-validation-standard.md)
6. [最新交接入口](../.handoff/current.md)

### 4.4 Batch 3：Identity Geometry 训练基础

按以下顺序阅读：

1. [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)
2. [训练增强实施计划](implementation/training-enhancement-implementation-plan.md)
3. [训练质量算法路线](optimization/training-quality-algorithm-roadmap.md)
4. [src / dst 训练质量设计](optimization/src-dst-training-quality-optimization-design.md)
5. [src 脸型保持设计](optimization/src-face-shape-preservation-design.md)
6. [训练消融实验计划](optimization/training-ablation-experiment-plan.md)
7. [代码修改地图](implementation/deepfacelab-code-modification-map.md)
8. [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)

### 4.5 Batch 4—6：脸型桥梁与 Shape-aware Merge

1. [src 脸型训练与 Shape-aware Merge 总设计](optimization/src-face-shape-training-and-shape-aware-merge-design.md)
2. [Shape-aware Merge 实现设计](optimization/shape-aware-merge-implementation-design.md)
3. [Shape-aware Merge 实施计划](implementation/merge-shape-aware-implementation-plan.md)
4. [Merger 调用链分析](implementation/deepfacelab-merger-call-chain-analysis.md)
5. [代码修改地图](implementation/deepfacelab-code-modification-map.md)
6. [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)

### 4.6 Batch 7：身份外观与画质增强

在 Batch 6 闭环稳定后，再阅读和拆分：

1. [训练质量算法路线](optimization/training-quality-algorithm-roadmap.md)
2. [src / dst 训练质量设计](optimization/src-dst-training-quality-optimization-design.md)
3. [训练增强实施计划](implementation/training-enhancement-implementation-plan.md)
4. [训练消融实验计划](optimization/training-ablation-experiment-plan.md)

目标模块：

```text
Identity Appearance
Region
Boundary
Frequency
Full Multi-objective Curriculum
```

### 4.7 工程接入与验收

1. [代码修改地图](implementation/deepfacelab-code-modification-map.md)
2. [源码审计](implementation/deepfacelab-source-code-audit.md)
3. [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)
4. [人工质量验收与开发验证标准](implementation/manual-quality-acceptance-and-development-validation-standard.md)
5. [训练 Benchmark 规范](validation/training-benchmark-specification.md)

### 4.8 未来 UI 与 Linux 服务化

1. [WSL2 后端与宿主机 UI 设计](design/dfl-wsl2-host-ui-design.md)

该方向保留，但在核心训练和 Merge 增强稳定前不进入主要开发阶段。GUI 参数应在对应 Batch 后端 Schema 冻结后逐批接入，不能提前暴露尚未实现的未来字段。

---

## 5. 文档目录说明

### `analysis/`

描述当前真实代码、架构、调用链和风险，不代表未来方案已经实现。

主要文档：

- `dfl-current-project-overview.md`
- `dfl-tf2-upgrade-analysis.md`
- `implementation-status-and-risk-matrix.md`
- `extraction-architecture-analysis.md`
- `training-architecture-analysis.md`
- `merging-architecture-analysis.md`

### `design/`

保存早期候选方案、TF2 升级价值和未来 UI / 服务化构想。

主要文档：

- `dfl-training-algorithm-optimizations.md`
- `dfl-tf2-upgrade-advantages-analysis.md`
- `dfl-wsl2-host-ui-design.md`

这些内容是设计输入，不自动等于当前实施优先级。

### `optimization/`

保存训练、脸型、Merge、性能和实验专项方案。

主要文档：

- `training-correctness-audit.md`
- `training-performance-optimization.md`
- `training-quality-algorithm-roadmap.md`
- `extraction-optimization.md`
- `merging-optimization.md`
- `src-dst-training-quality-optimization-design.md`
- `src-face-shape-preservation-design.md`
- `src-face-shape-training-and-shape-aware-merge-design.md`
- `shape-aware-merge-implementation-design.md`
- `training-ablation-experiment-plan.md`

### `implementation/`

保存唯一总实施入口、代码映射、调用链、配置架构和模块实施计划。

主要文档：

- `enhanced-dfl-master-implementation-plan.md` —— 唯一总实施入口
- `deepfacelab-code-modification-map.md`
- `deepfacelab-source-code-audit.md`
- `deepfacelab-tf2x-source-tree-analysis.md`
- `deepfacelab-training-call-chain-analysis.md`
- `deepfacelab-merger-call-chain-analysis.md`
- `deepfacelab-config-and-extension-architecture.md`
- `training-enhancement-implementation-plan.md`
- `merge-shape-aware-implementation-plan.md`
- `batch2-gui-parameter-integration.md`
- `manual-quality-acceptance-and-development-validation-standard.md`

### `development/`

保存已经进入实际施工阶段的批次级任务文档。内容应落到目标文件、函数、修改范围、回退路径、测试和完成标准，不重复大而泛的架构设计。

当前文档：

- `batch1-correctness-and-extension-foundation-tasks.md`
- `batch2-training-data-and-sampling-tasks.md`

Batch 3 施工文档尚未创建。创建前必须先完成 Ticket 21 环境门或记录维护者批准的新验收策略。

### `usage/`

保存用户可以直接执行的操作说明：

- `faceset-metadata-and-sampling.md`
- `faceset-analyzer-complete-guide.md`

### `validation/`

保存固定测试条件、兼容检查和验证规范。

已有 `training-benchmark-specification.md` 可作为固定条件参考。第一版不建设自动化视觉评分平台：自动化负责工程正确性、回归和可运行性，最终视觉质量仍由人工验收。

### `.handoff/`

保存跨会话交接：

- `current.md` 始终指向最新 Handoff；
- 历史 Handoff 不删除；
- 每份交接明确实际文件、测试、风险和下一步。

---

## 6. 训练增强与脸型合成如何衔接

```text
Batch 2
Metadata / Sampling
        ↓
Batch 3
Minimal Loss Hook + Identity Geometry
        ↓
Batch 4
Source Shape Template
        ↓
Batch 5
Hybrid Landmark + Piecewise Affine Warp
        ↓
Batch 6
Shape-aware Soft Mask + Temporal
        ↓
Batch 7
Identity Appearance + Region + Boundary + Frequency
```

职责：

- Sampling 决定模型看到哪些素材；
- Geometry Loss 决定模型学习哪些稳定 src 比例；
- Shape Template 保存权威 src 几何；
- Hybrid Landmark / Warp 将几何应用到 Merge；
- Shape Mask 保留并软化轮廓；
- Temporal 保持视频连续性；
- Batch 7 再改善外观、局部、边缘和高频细节。

只完成训练或只完成 Merge，都不能完整解决脸型保持。

---

## 7. 当前开发优先级

### P0：完成 Batch 2 环境门

- Windows TensorFlow + CUDA 环境；
- SAEHD FP32 + AdaBelief；
- Ordinary / Packed；
- 4 种 Sampling 模式；
- ≥500 iter；
- Manual Save / Exit；
- Resume ≥200 iter；
- SRC / DST Side Config；
- Fallback；
- Loss Window；
- 资源差集。

### P1：Batch 3 设计与实施

环境门通过后：

1. 冻结 Batch 3 非目标；
2. 拆分 Minimal Loss Hook Ticket；
3. 拆分 Shape Anchor Ticket；
4. 拆分 Landmark / Ratio Loss Ticket；
5. 拆分 Geometry Curriculum Ticket；
6. 建立 Windows GPU Geometry A/B Matrix；
7. 验证保存恢复和旧 checkpoint。

### P2：Batch 4—6 脸型闭环

1. Source Shape Template；
2. Hybrid Landmark；
3. Piecewise Affine Warp；
4. Shape-aware Soft Mask；
5. Occlusion Fallback；
6. Temporal Stabilization。

### P3：Batch 7 通用画质增强

1. Identity Appearance；
2. Region；
3. Boundary；
4. Frequency；
5. Full Multi-objective Curriculum。

### P4：Batch 8 收口

- 固定素材 A/B；
- 默认参数和预设；
- 性能与兼容；
- GUI；
- 用户文档和状态矩阵。

### 暂缓

- 替换 SAEHD；
- Diffusion / Transformer；
- TPS 作为默认大形变方案；
- 自动化视觉质量评分系统；
- 自动参数搜索；
- 完整 Linux 服务化与 Web UI。

---

## 8. 文档状态定义

| 状态 | 定义 |
|---|---|
| 设计阶段 | 仅有方案，尚无代码 |
| 详细设计完成 | 已形成文件级、函数级任务、测试与验收标准，尚未施工 |
| 代码骨架 | 已有类、函数或配置入口，但未进入主流程 |
| 已实现 | 存在实际代码 |
| 已接通 | 已进入主运行链路，可由参数调用 |
| 待验证 | 代码存在，但正确性或收益未确认 |
| 已验证 | 已通过工程检查或固定样例验证 |
| 存在问题 | 已确认当前实现与目标不一致 |
| 建议重构 | 技术债较大，不宜继续直接叠加 |

任一任务标记完成至少满足：

```text
代码存在
+
进入主链路
+
默认兼容
+
基本运行或环境验证通过
+
失败可回退
+
文档状态已更新
```

视觉算法还需要可供人工 A/B 判断的结果。Agent 不得自动宣称最终审美或视觉质量达标。

---

## 9. 文档维护规则

1. 总体实施顺序只维护在 `implementation/enhanced-dfl-master-implementation-plan.md`；
2. `docs/README.md` 只负责索引、当前优先级和导航；
3. 当前代码事实写入 `analysis/`；
4. 算法细节写入 `optimization/`；
5. 模块架构、调用链和实施计划写入 `implementation/`；
6. 当前批次的文件级、函数级施工任务写入 `development/`；
7. 固定测试条件与结果写入 `validation/` 或 `.scratch/.../reports/`；
8. 跨会话状态写入 `.handoff/current.md`；
9. 每次正式启动或完成一个 Batch，同步更新总计划、索引、状态矩阵和 Handoff；
10. 历史 Ticket、Summary 和验收报告不因未来路线调整而重写；
11. 不创建第二份并行总路线，避免实施顺序分裂。