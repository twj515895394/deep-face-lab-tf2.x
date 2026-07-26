# DeepFaceLab TF2.x 文档总索引

> 文档版本：v2.0  
> 更新日期：2026-07-26  
> 定位：项目文档导航。实际开发顺序以统一总实施计划为准。

---

## 1. 唯一实施入口

后续进行代码开发、任务拆分、Agent 协作或进度判断时，先阅读：

- [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)

该文档已经统一串联：

```text
训练正确性
   ↓
配置与扩展框架
   ↓
数据与采样增强
   ↓
身份外观与身份几何训练
   ↓
Source Shape Template
   ↓
Hybrid Landmark
   ↓
Shape-aware Warp / Mask
   ↓
Temporal Stabilization
   ↓
开发验证与人工质量验收
```

专项文档用于解释细节，不再各自决定总体实施顺序。

---

## 2. 项目路线

```text
Phase 1：现状、TF2.x 与源码基线
                  ↓
Phase 2：训练正确性与扩展骨架
                  ↓
Phase 3：训练质量、Identity Geometry 与 Curriculum
                  ↓
Phase 4：Source Shape Template 与 Shape-aware Merge
                  ↓
Phase 5：Mask、Temporal、联调与人工验收
                  ↓
Phase 6：Linux 服务化与 UI（核心引擎稳定后）
```

当前阶段：**从文档设计进入 Phase 2 的实际代码开发准备**。

---

## 3. 推荐阅读路径

### 3.1 快速了解项目

1. [当前项目架构与升级分析](analysis/dfl-current-project-overview.md)
2. [TF2.x 升级实现分析](analysis/dfl-tf2-upgrade-analysis.md)
3. [实现状态与风险矩阵](analysis/implementation-status-and-risk-matrix.md)
4. [增强版总实施计划](implementation/enhanced-dfl-master-implementation-plan.md)

### 3.2 了解完整处理链

1. [Extract / 切脸架构分析](analysis/extraction-architecture-analysis.md)
2. [训练架构分析](analysis/training-architecture-analysis.md)
3. [Merge / 合成架构分析](analysis/merging-architecture-analysis.md)
4. [TF2.x 源码树分析](implementation/deepfacelab-tf2x-source-tree-analysis.md)

### 3.3 开始训练侧开发

1. [训练正确性审计](optimization/training-correctness-audit.md)
2. [训练调用链分析](implementation/deepfacelab-training-call-chain-analysis.md)
3. [训练质量算法路线](optimization/training-quality-algorithm-roadmap.md)
4. [src / dst 训练质量设计](optimization/src-dst-training-quality-optimization-design.md)
5. [src 脸型保持训练设计](optimization/src-face-shape-preservation-design.md)
6. [训练增强实施计划](implementation/training-enhancement-implementation-plan.md)

### 3.4 开始脸型与 Shape-aware Merge 开发

1. [src 脸型训练与 Shape-aware Merge 总设计](optimization/src-face-shape-training-and-shape-aware-merge-design.md)
2. [Shape-aware Merge 实现设计](optimization/shape-aware-merge-implementation-design.md)
3. [Merger 调用链分析](implementation/deepfacelab-merger-call-chain-analysis.md)
4. [Shape-aware Merge 实施计划](implementation/merge-shape-aware-implementation-plan.md)

### 3.5 工程接入与验收

1. [代码修改地图](implementation/deepfacelab-code-modification-map.md)
2. [源码审计](implementation/deepfacelab-source-code-audit.md)
3. [配置与扩展架构](implementation/deepfacelab-config-and-extension-architecture.md)
4. [人工质量验收与开发验证标准](implementation/manual-quality-acceptance-and-development-validation-standard.md)
5. [训练消融实验计划](optimization/training-ablation-experiment-plan.md)

### 3.6 未来 UI 与 Linux 服务化

1. [WSL2 后端与宿主机 UI 设计](design/dfl-wsl2-host-ui-design.md)

该方向保留，但在核心训练与 Merge 增强完成前不进入主要开发阶段。

---

## 4. 文档目录说明

### analysis/

描述当前真实代码、架构、调用链现状和风险，不代表未来方案已经实现。

主要文档：

- `dfl-current-project-overview.md`
- `dfl-tf2-upgrade-analysis.md`
- `implementation-status-and-risk-matrix.md`
- `extraction-architecture-analysis.md`
- `training-architecture-analysis.md`
- `merging-architecture-analysis.md`

### design/

保存早期候选方案、TF2 升级价值和未来 UI / 服务化构想。

主要文档：

- `dfl-training-algorithm-optimizations.md`
- `dfl-tf2-upgrade-advantages-analysis.md`
- `dfl-wsl2-host-ui-design.md`

这些内容是设计输入，不自动等于当前实施优先级。

### optimization/

保存训练、脸型、Merge、性能和实验方面的专项优化方案。

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

### implementation/

保存实际施工入口、代码映射、调用链、配置架构和实施计划。

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
- `manual-quality-acceptance-and-development-validation-standard.md`

### validation/

保存固定测试条件、兼容检查和验证记录。

已有 `training-benchmark-specification.md` 可作为人工 A/B 的固定条件参考，但第一阶段不建设自动化视觉评分平台。最终视觉质量由人工验收，自动化仅负责工程正确性、回归和可运行性。

---

## 5. 训练增强与脸型合成如何衔接

最初的训练增强不是独立路线，而是 Shape-aware Merge 的前置基础。

```text
训练增强
├── 数据质量
├── Sampling
├── Region / Boundary / Frequency Loss
├── Identity Appearance
└── Identity Geometry
          ↓
Source Shape Template
          ↓
Shape-aware Merge
├── Hybrid Landmark
├── Piecewise Affine Warp
├── Shape-aware Mask
└── Temporal Stabilization
```

训练侧负责“学到 src 身份与几何”，Merge 侧负责“最终画面不再被 dst 几何完全覆盖”。只完成其中一侧，都不能完整解决脸型保持问题。

---

## 6. 当前开发优先级

### P0：立即处理

1. 修复 Eyes / Mouth Priority 实际传入空 mask 的正确性问题。
2. 审计低精度、Loss Scaling、梯度 dtype、Optimizer state 和恢复逻辑。
3. 建立 Feature Flag、配置读取与旧流程回归。
4. 补充启动、训练、保存恢复和 Merge smoke test。

### P1：训练增强 MVP

1. metadata schema。
2. quality / pose / shape-aware sampling。
3. loss hook。
4. Identity Appearance 与 Identity Geometry 实验入口。
5. curriculum 基础阶段控制。

### P2：Shape-aware Merge MVP

1. Source Shape Template sidecar。
2. Hybrid Landmark。
3. Piecewise Affine Warp。
4. Shape-aware Soft Mask。
5. 基础时序平滑与失败回退。

### P3：联调与人工验收

1. 固定素材 A/B。
2. 身份、脸型、表情、边界和时序人工判断。
3. 修订默认参数。
4. 更新兼容说明和实施状态。

### 暂缓

- 替换 SAEHD；
- Diffusion / Transformer；
- TPS 作为默认大形变方案；
- 自动化视觉质量评分系统；
- 完整 Linux 服务化与 Web UI。

---

## 7. 文档状态定义

| 状态 | 定义 |
|---|---|
| 设计阶段 | 仅有方案，尚无代码 |
| 代码骨架 | 已有类、函数或配置入口，但未进入主流程 |
| 已实现 | 存在实际代码 |
| 已接通 | 已进入主运行链路，可由参数调用 |
| 待验证 | 代码存在，但正确性或收益未确认 |
| 已验证 | 已通过工程检查或固定样例验证 |
| 存在问题 | 已确认当前实现与目标不一致 |
| 建议重构 | 技术债较大，不宜继续直接叠加 |

任一任务标记完成至少应满足：

```text
代码存在
+
进入主链路
+
默认兼容
+
基本运行验证通过
+
失败可回退
+
文档状态已更新
```

视觉算法任务还需要产出可供人工 A/B 判断的结果，但不要求 Agent 自动作出最终审美结论。

---

## 8. 文档维护规则

1. 总体实施顺序只维护在 `implementation/enhanced-dfl-master-implementation-plan.md`。
2. `docs/README.md` 只负责索引、当前优先级和导航。
3. 当前代码事实写入 `analysis/`。
4. 算法与优化细节写入 `optimization/`。
5. 实际任务、文件和调用链写入 `implementation/`。
6. 固定测试条件与结果写入 `validation/`。
7. 每完成一个开发批次，同步更新总实施计划、索引和状态矩阵。
8. 不再创建第二份并行的“总路线”文档，避免实施顺序分裂。
