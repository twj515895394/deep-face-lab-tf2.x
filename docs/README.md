# DeepFaceLab TF2.x 文档总索引与演进大纲

> 文档版本：v1.1  
> 更新日期：2026-07-25  
> 作用：统一管理项目分析、优化设计、验证方案和未来 UI 服务化文档。

---

## 1. 文档体系目标

本目录用于回答四类问题：

1. **当前项目是什么**：当前架构、代码模块、TF2.x 升级范围和真实实现状态。
2. **下一步优化什么**：训练、切脸、Faceset、合成各链路的优化方向和优先级。
3. **如何证明优化有效**：正确性审计、Benchmark、质量评估和兼容性测试。
4. **何时进入 UI 与 Linux 服务化**：只有核心引擎稳定、配置结构化、状态可观测后才进入第三阶段。

项目总体顺序固定为：

```text
Phase 1：项目现状与 TF2.x 升级分析
                 ↓
Phase 2：核心引擎优化
  训练正确性 → Benchmark → 训练性能 → 训练质量
                 ↓
        Extract / Faceset 优化
                 ↓
             Merge 优化
                 ↓
Phase 3：Linux 后端服务化与前端 UI
```

当前最重要阶段：**Phase 2 的训练核心链路优化**。

---

## 2. 推荐阅读路径

### 2.1 快速了解项目

1. [当前项目架构与升级分析](analysis/dfl-current-project-overview.md)
2. [TF2.x 升级实现分析](analysis/dfl-tf2-upgrade-analysis.md)
3. [实现状态与风险矩阵](analysis/implementation-status-and-risk-matrix.md)

### 2.2 按完整业务流程阅读

1. [Extract / 切脸架构分析](analysis/extraction-architecture-analysis.md)
2. [训练架构分析](analysis/training-architecture-analysis.md)
3. [Merge / 合成架构分析](analysis/merging-architecture-analysis.md)

### 2.3 开始训练优化

1. [训练架构分析](analysis/training-architecture-analysis.md)
2. [实现状态与风险矩阵](analysis/implementation-status-and-risk-matrix.md)
3. [训练算法优化候选方案](design/dfl-training-algorithm-optimizations.md)
4. `optimization/training-correctness-audit.md`（下一份重点文档，待创建）
5. `validation/training-benchmark-specification.md`（待创建）

### 2.4 了解已有升级设想

1. [TF2 升级优势分析](design/dfl-tf2-upgrade-advantages-analysis.md)
2. [训练算法优化候选方案](design/dfl-training-algorithm-optimizations.md)

> 注意：`design/` 下的文档包含候选方案和预期收益，不代表功能已经完成或收益已经验证。真实实现状态以 `analysis/implementation-status-and-risk-matrix.md` 为准。

### 2.5 未来 UI 与 Linux 服务化

1. [WSL2 后端与宿主机 UI 设计](design/dfl-wsl2-host-ui-design.md)

该设计当前保留，但暂不进入主要开发阶段。

---

## 3. 当前已有文档

### 3.1 Analysis：现状与代码基线

| 文档 | 作用 | 当前状态 |
|---|---|---|
| [dfl-current-project-overview.md](analysis/dfl-current-project-overview.md) | 项目定位、模块架构、完整工作流、阶段路线 | v1.1，主总览 |
| [dfl-tf2-upgrade-analysis.md](analysis/dfl-tf2-upgrade-analysis.md) | TF2.x、CUDA、新 GPU、精度、优化器和数据管线的代码级分析 | v1.1，训练审计输入 |
| [implementation-status-and-risk-matrix.md](analysis/implementation-status-and-risk-matrix.md) | 功能状态、代码入口、风险、验证方式和优先级 | v1.0，统一状态来源 |
| [extraction-architecture-analysis.md](analysis/extraction-architecture-analysis.md) | S3FD、FAN、对齐、worker、DFLJPG 和 Faceset 链路 | v1.0，Extract 基线 |
| [training-architecture-analysis.md](analysis/training-architecture-analysis.md) | SAEHD、Leras、数据、Loss、梯度和优化器训练链路 | v1.1，训练审计输入 |
| [merging-architecture-analysis.md](analysis/merging-architecture-analysis.md) | Predictor、mask、颜色、融合、多脸和时序链路 | v1.0，Merge 基线 |

### 3.2 Design：候选设计与未来方案

| 文档 | 作用 | 使用原则 |
|---|---|---|
| [dfl-training-algorithm-optimizations.md](design/dfl-training-algorithm-optimizations.md) | 梯度检查点、采样、CBAM、FFL、LPIPS 等候选方案 | 进入开发前必须经过正确性和收益评估 |
| [dfl-tf2-upgrade-advantages-analysis.md](design/dfl-tf2-upgrade-advantages-analysis.md) | TF2 升级价值与预期收益 | 预期收益不能代替 Benchmark |
| [dfl-wsl2-host-ui-design.md](design/dfl-wsl2-host-ui-design.md) | WSL2/Linux 后端、Windows UI、HTTP/WebSocket 设计 | Phase 3 使用，当前冻结实施 |

---

## 4. 下一批计划文档

### 4.1 Phase 1 收尾

| 文件 | 目标 | 状态 |
|---|---|---|
| `analysis/configuration-and-compatibility-matrix.md` | Python、TF、CUDA、GPU、模型恢复、导出兼容矩阵 | 待创建，可与验证文档合并 |
| `analysis/phase1-known-issues.md` | 将代码审计发现整理为可执行问题清单 | 可直接并入训练正确性审计 |

Phase 1 的主架构文档已经覆盖 Extract、Training 和 Merge，不建议继续无限扩写现状文档。后续以专项审计和验证为主。

### 4.2 Phase 2：训练正确性和性能

| 文件 | 目标 | 优先级 |
|---|---|---|
| `optimization/training-correctness-audit.md` | 审计 BF16/FP16、Loss Scaling、Lion、Optimizer state、梯度与恢复 | P0，下一份 |
| `validation/training-benchmark-specification.md` | 固定数据集、配置、指标和测试流程 | P0 |
| `optimization/training-performance-optimization.md` | 计算图、显存、数据管线、多 GPU 优化 | P1 |
| `optimization/training-quality-algorithm-roadmap.md` | 采样、Loss、网络结构、时序一致性实验路线 | P1 |
| `validation/model-quality-evaluation.md` | 单帧质量、身份、几何、时序稳定性评估 | P1 |
| `validation/compatibility-test-matrix.md` | 模型保存、恢复、旧模型和导出回归测试 | P1 |

### 4.3 Phase 2：Extract、Faceset 和 Merge

| 文件 | 目标 | 状态 |
|---|---|---|
| `optimization/extraction-optimization.md` | 检测、Landmark、批处理和流水线优化 | 待训练链路稳定后创建 |
| `optimization/faceset-intelligence-design.md` | 去重、清晰度、姿态、遮挡、身份和采样分析 | 待创建 |
| `validation/extraction-benchmark-specification.md` | 固定 Extract 数据集、速度和质量指标 | 待创建 |
| `optimization/merging-optimization.md` | Batch 推理、GPU 后处理、时序平滑和编码流水线 | 待创建 |
| `validation/video-temporal-quality-evaluation.md` | 闪烁、颜色跳变、mask 和 Landmark 稳定性 | 待创建 |

### 4.4 Phase 3：Linux 服务化和 UI

| 文件 | 目标 | 状态 |
|---|---|---|
| `future/dfl-linux-service-architecture.md` | 将 DFL 核心能力改造成结构化服务 | 暂不启动 |
| `future/dfl-ui-product-design.md` | 工作区、任务、训练监控、预览和参数管理 | 暂不启动 |
| `future/dfl-engine-api-contract.md` | TrainingConfig、ExtractConfig、MergeConfig 和事件协议 | Phase 2 后期准备 |

---

## 5. 文档状态定义

为了避免“写进设计文档”被误认为“已经实现”，项目统一使用以下状态：

| 状态 | 定义 |
|---|---|
| 已实现 | 存在实际代码 |
| 已接通 | 已进入主运行链路，可被参数或流程调用 |
| 已验证 | 有自动测试、Benchmark 或固定样例验证结果 |
| 待验证 | 代码存在，但正确性或收益尚未证明 |
| 存在问题 | 已确认实现与目标、算法或数值逻辑不一致 |
| 代码骨架 | 有类、函数或配置入口，但主流程未使用 |
| 设计阶段 | 仅存在设计说明，尚未开发 |
| 建议重构 | 当前实现技术债较大，不适合继续叠加功能 |

所有分析文档应尽量同时标明：

```text
功能状态 + 代码入口 + 已知风险 + 验证方法 + 后续动作
```

---

## 6. 当前阶段进度

### Phase 1：项目现状与 TF2.x 升级分析

```text
状态：主体完成，进入收尾
项目总览：已完成 v1.1
TF2.x 实现分析：已完成 v1.1
训练架构分析：已完成 v1.1
Extract 架构分析：已完成 v1.0
Merge 架构分析：已完成 v1.0
实现状态与风险矩阵：已完成 v1.0
兼容性矩阵：尚未建立
建议完成度：约 75%
```

### Phase 2：核心引擎优化

```text
状态：准备完成，即将正式启动
训练架构和风险基线：已建立
训练正确性审计：下一份文档
Benchmark：尚未建立
性能和质量优化：尚未进入开发验证
```

### Phase 3：Linux 与 UI

```text
状态：设计保留，实施冻结
启动条件：训练、Extract、Merge 核心链路稳定并通过验证
```

---

## 7. 当前最高优先级

当前不应优先增加更多界面或外围功能。推荐顺序：

1. 创建并完成 `training-correctness-audit.md`。
2. 修正 BF16、Loss Scaling、Lion、Optimizer state、低精度梯度等 P0 风险。
3. 建立统一训练 Benchmark。
4. 开始训练吞吐、显存和数据管线优化。
5. 再进行采样、Loss 和网络结构实验。
6. 训练稳定后进入 Extract/Faceset 和 Merge 专项优化。
7. 最后进行 Linux 服务化和 UI 联通。

---

## 8. 文档维护约定

- `analysis/`：描述当前真实代码，不写未经验证的收益结论。
- `design/`：描述候选方案，必须标记前提、风险和验证方法。
- `optimization/`：描述准备开发或正在开发的优化方案。
- `validation/`：保存测试规范、指标定义和验证结论。
- `future/`：保存尚未进入实施阶段的服务化和 UI 方案。
- 重大代码改造前，先更新对应设计和验证文档。
- 功能完成后，将状态从“设计阶段/待验证”更新为“已实现/已验证”。
