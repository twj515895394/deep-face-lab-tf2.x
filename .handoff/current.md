# 当前项目交接入口

> 本文件是新会话、新 Agent 和后续开发者的固定入口。  
> 更新时间：2026-07-30  
> 当前分支：`codex/batch2-ticket19-loss-window`  
> 当前决策：维护者明确跳过 Batch 2 最终 Windows GPU 硬门，不再以该矩阵阻塞 Batch 3；未执行的实机验证保持 `DEFERRED / NOT EXECUTED`，不得伪写为 GPU PASS。  
> 下一会话唯一首要任务：参照 Batch 2 的详细拆分方式，完成 Batch 3 Ticket 全量拆分与施工文档，不直接开始编码。

---

## 1. 当前权威结论

```text
Batch 1：计划内实现已完成
Batch 2：计划内代码、自动测试、文档和 Review 已完成
Batch 2 Windows GPU Final Matrix：DEFERRED-BY-MAINTAINER / NOT EXECUTED
Batch 2 作为后续开发基线：APPROVED-FOR-PROGRESSION
Batch 3 设计路线：GEOMETRY-FIRST
Batch 3 Ticket 拆分：READY-TO-START
Batch 3 编码实施：必须先完成并复核 Ticket 拆分后再开始
```

必须准确理解：

```text
允许进入 Batch 3
≠
Batch 2 Windows GPU Matrix 已通过
```

维护者决定不再等待 Batch 2 的最终实机矩阵。后续由维护者在真实机器上使用；若发现训练、保存恢复、采样、资源清理或兼容问题，再提交实际日志与复现条件，按缺陷修复流程处理。

因此：

- 不再把 Ticket 21 作为 Batch 3 的阻塞条件；
- 不需要在下一会话继续准备或执行 Batch 2 GPU 验收；
- 不得把未执行的 Matrix 改写成 `PASS-WINDOWS-GPU`；
- 历史 Ticket、Summary 和验收记录保持原事实，不回写伪造结果；
- 后续文档可以将 Batch 2 标记为“维护者接受风险并允许推进”；
- 实机问题属于后续反馈修复，不再属于 Batch 3 启动前置门。

---

## 2. 最新必读入口

下一会话必须按顺序读取：

1. [本文档](current.md)
2. [增强版总实施计划](../docs/implementation/enhanced-dfl-master-implementation-plan.md)
3. [训练增强实施计划](../docs/implementation/training-enhancement-implementation-plan.md)
4. [训练质量算法路线](../docs/optimization/training-quality-algorithm-roadmap.md)
5. [src 脸型保持设计](../docs/optimization/src-face-shape-preservation-design.md)
6. [src 脸型训练与 Shape-aware Merge 联合设计](../docs/optimization/src-face-shape-training-and-shape-aware-merge-design.md)
7. [代码修改地图](../docs/implementation/deepfacelab-code-modification-map.md)
8. [配置与扩展架构](../docs/implementation/deepfacelab-config-and-extension-architecture.md)
9. [Batch 2 详细任务设计](../docs/development/batch2-training-data-and-sampling-tasks.md)
10. [Batch 2 GUI 参数接入说明](../docs/implementation/batch2-gui-parameter-integration.md)

为理解 Batch 2 的工程质量和拆分粒度，还应阅读：

- `.scratch/batch2-training-data-and-sampling/issues/`
- `.scratch/batch2-training-data-and-sampling/reports/`
- `.scratch/batch2-training-data-and-sampling/reviews/`（如存在）
- Batch 2 各 Ticket 的 Summary、Review、验收矩阵与 Handoff

重点不是复制 Batch 2 的功能，而是复制它的**任务描述精度、边界控制、测试约束和交接完整度**。

---

## 3. 统一工作分支

```text
codex/batch2-ticket19-loss-window
```

下一会话继续在该分支进行 Batch 3 的设计与 Ticket 拆分，除非维护者另行指定新分支。

开始操作前必须确认：

```bash
git branch --show-current
git rev-parse HEAD
```

代码、文档和 Ticket 事实以该分支最新 HEAD 为准。

---

## 4. 最新 Commit 锚点

### Batch 2 实施与 Review

```text
Ticket 18 implementation： 9a2c28bf2da5a5bd4182ef8731fa22c1d5b2e058
Ticket 20 implementation： 1ca7f178981c971c331108969c62f657f773000a
Wave 1 Review R4：         0742381d10ad49848c9cfba33fc72a622c567e52
Ticket 21 docs/handoff：   c53e8e1c521d3e8b9ec3260a750e32b6a2ee1abd
Ticket 18/20 Final Review：5440770c47c4415bd018d24da92ba42b2a6a8566
```

### Batch 2 GUI 文档

```text
Batch 2 GUI integration：2730deb0b6ef1949e450a4108b011ffd1b411978
```

### Geometry-first 路线调整

```text
Master plan：             b7b2ae65c4c1bddf1c7a3c2b081baeb7d532ce2a
Training implementation：0b083e19dc81210cd22564bd78366959df8ebf4e
Training roadmap：       51c3f6b294658974b1b551be9170e6381167f461
Face shape design：      e9730a99b0bb7bb51e55f7c1c3c3055fea06efab
Training/Merge design：  31e28ef3345a770ecb5b5f437642754a472e7fcd
Merge implementation：  40e0ce345657ea7acbf0db5170d13c83970cb581
Code modification map：  118109243ecb52634e7b9c2d1b27bca629c516a4
Config architecture：    6f42f7ffb893de6df48838ada771d5caf67781c6
Docs index：             c5503ef012f12fbe82446265a1d79be5d0928c68
```

当前 HEAD 以 GitHub 分支最新 Commit 或 `git rev-parse HEAD` 为准，不得只依赖本节的静态锚点。

---

## 5. Batch 2 最终状态与维护者决策

### 5.1 已完成能力

```text
Metadata Schema / Identity / Fingerprint
Faceset Analyzer ordinary + packed
quick / strong fingerprint
incremental / force-full equivalence
trusted match / stale detection / strict atomic write
legacy_random / legacy_uniform_yaw
pose_balanced / quality_pose_balanced
SRC / DST side configuration
spawn-safe WeightedIndexHost and deterministic process cleanup
optional Metadata fallback + core error propagation
Trainer loss window / save / exit / resume control flow
Unicode / 中文 / 空格路径 smoke
完整使用文档、options-json 参考、GUI 接入说明、Summary 和 Handoff
```

Batch 2 对素材的作用是分析素材并调整训练抽样概率，不修改、删除或重写 aligned 原始图片。

### 5.2 自动测试事实

```text
OS：Windows
Python：3.11.7
start method：spawn

python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
Ran 331 tests
OK
shell EXIT=0
```

该结果不等价于 GitHub CI，也不等价于真实 SAEHD GPU 长时间训练已完成。

### 5.3 未执行的环境项目

以下项目未执行，事实状态保持 `DEFERRED / NOT EXECUTED`：

```text
真实 Windows TensorFlow + CUDA SAEHD Matrix
ordinary + packed 实机训练
legacy_random / legacy_uniform_yaw 实机训练
pose_balanced / quality_pose_balanced 实机训练
连续训练 ≥500 iter
manual save / exit
resume ≥200 iter
真实 Loss Window 日志核对
训练结束资源差集
1k/10k 大规模性能与 RSS 验证
GPU / thread attribution 验证
```

### 5.4 维护者风险接受

维护者于 2026-07-30 明确决定：

```text
跳过 Batch 2 最终待确认实机验证
解除 Batch 3 启动阻塞
后续由维护者实机使用
若发现问题，再提供反馈并修复
```

因此，后续状态应写作：

```text
Batch 2 implementation：COMPLETE
Batch 2 automated/code acceptance：COMPLETE
Batch 2 final GPU matrix：DEFERRED-BY-MAINTAINER
Batch 2 progression decision：APPROVED-FOR-BATCH3
```

不得写作：

```text
PASS-WINDOWS-GPU
GPU Matrix completed
Production GPU acceptance passed
```

除非未来真实执行并补充证据。

---

## 6. Post-Batch 2 路线

调整后的批次顺序：

```text
Batch 3：Minimal Loss Hook + Identity Geometry MVP
Batch 4：Source Shape Template
Batch 5：Hybrid Landmark + Piecewise Affine Warp
Batch 6：Shape-aware Soft Mask + Temporal
Batch 7：Identity Appearance / Region / Boundary / Frequency
Batch 8：联调、A/B、默认值、GUI、兼容与文档
```

关键约束：

> Batch 3 不是完全跳过 Loss Hook，而是只实现 Identity Geometry 必需的最小 Loss 基础设施；通用外观和画质 Loss 必须后移到 Batch 7。

不得在 Batch 3 混入：

```text
Identity Appearance Loss
通用 Region Loss
Boundary Loss
Frequency Loss
大型外部身份模型
完整 Multi-objective Curriculum
自动参数搜索
Shape-aware Merge 实施
完整 GUI 接入
Linux 服务化
```

---

## 7. 下一会话的唯一首要任务

### 7.1 任务名称

```text
Batch 3：Identity Geometry 训练基础——Ticket 全量拆分与施工设计
```

### 7.2 任务性质

下一会话首先是**设计与拆票会话**，不是直接编码会话。

必须先完成：

1. Batch 3 总体详细设计；
2. Ticket 列表和依赖图；
3. 每个 Ticket 的独立 Issue 文档；
4. Master Test Matrix；
5. Review 规则；
6. Summary 模板；
7. Handoff 更新；
8. 对总计划和索引的必要同步。

完成并复核前，不应直接修改核心训练代码。

### 7.3 拆分质量要求

Batch 3 Ticket 必须达到或超过 Batch 2 的详细程度，因为后续执行模型可能较弱，必须通过文档降低误解空间和编码跑偏风险。

每个 Ticket 都必须做到：

```text
目标单一
输入明确
输出明确
修改文件明确
修改函数/类明确
禁止修改范围明确
接口契约明确
数据结构明确
默认值明确
兼容规则明确
错误语义明确
Fallback 边界明确
测试命令明确
验收条件明确
Review 检查项明确
提交边界明确
后续依赖明确
```

禁止只写：

```text
实现 Loss Hook
增加 Geometry Loss
补充测试
优化脸型
```

这类描述不足以交给弱模型执行。

---

## 8. Batch 3 功能边界

### 8.1 必须包含

```text
Minimal Loss Hook
独立 Loss 开关和权重
单项 Loss 日志
requested / effective 配置状态
shape / dtype / mask 契约
NaN / Inf 检测与错误传播
Shape Anchor 定义、生成或加载入口
Landmark / Ratio 特征定义
Identity Geometry Loss MVP
Reconstruction → Geometry Ramp → Geometry Stable
保存恢复与旧 checkpoint 兼容
Feature Flag 默认关闭
异常时安全回退基线训练
自动测试矩阵
Windows GPU Geometry A/B 验收说明
GUI 未来接入所需的配置 Schema 文档
```

### 8.2 明确不包含

```text
Identity Appearance Loss
Region Loss
Boundary Loss
Frequency Loss
Perceptual / LPIPS / VGG / DINO Loss
ArcFace 或大型外部身份网络
新 Backbone
Diffusion / Transformer
完整自动 Curriculum
自动权重搜索
Source Shape Template 正式实现
Hybrid Landmark
Piecewise Affine Warp
Shape-aware Mask
Temporal Stabilization
完整 GUI 页面实现
```

说明：

- Shape Anchor 属于 Batch 3 训练几何入口；
- `model.srcshape` 或正式 Source Shape Template Sidecar 属于 Batch 4；
- Batch 3 可以定义未来 Template 所需的中间契约，但不得提前实现整个 Batch 4；
- Batch 3 的 Geometry 结果必须能够被未来 Batch 4 消费，但不能和 Merge 代码耦合。

---

## 9. 建议的 Batch 3 Ticket 主题

下一会话需要重新审计并确定最终编号，以下只作为必须覆盖的主题，不代表最终 Ticket 数量已经锁定。

建议至少覆盖：

```text
B3-T01：基线冻结、术语、Tensor/Mask/DType 契约与 Fixtures
B3-T02：Batch 3 配置 Schema、默认值、Feature Flag 与 options-json
B3-T03：Minimal Loss Hook API、注册机制与基线零影响
B3-T04：单项 Loss 结果模型、日志、requested/effective 状态
B3-T05：数值保护、NaN/Inf、错误传播与 Optional Fallback 边界
B3-T06：Shape Anchor 数据模型、身份绑定、缓存与失效规则
B3-T07：Landmark/Ratio 特征定义、归一化与有效性规则
B3-T08：Identity Geometry Loss MVP
B3-T09：SRC/DST 非对称职责与 Geometry/Expression 隔离
B3-T10：Minimal Geometry Curriculum 与恢复状态
B3-T11：SAEHD 主训练链路接入、开关和旧 Checkpoint 兼容
B3-T12：Loss Window、保存、退出、恢复与控制流回归
B3-T13：Master Smoke/Unit Matrix、确定性和异常矩阵
B3-T14：Windows GPU Geometry A/B 验收规约
B3-T15：用户/GUI 配置说明、Summary、Review 与 Handoff 收口
```

下一会话必须根据真实代码审计决定：

- 是否需要合并或拆分上述 Ticket；
- 是否要把 Anchor 生成与 Anchor Loader 分开；
- Geometry Loss 是否需要先拆为 Ratio MVP 与 Landmark MVP；
- Curriculum 是否应独立于 SAEHD 接入；
- 测试基础设施是否需要先做独立 Ticket；
- 是否需要专门 Ticket 处理旧模型恢复和 optimizer state。

不得直接照抄上面的编号开始编码。

---

## 10. 每个 Ticket 的强制模板

每份 Ticket 文档必须至少包含以下章节。

### 10.1 基本信息

```text
Ticket ID
标题
状态
优先级
前置 Ticket
阻塞 Ticket
目标分支
建议提交粒度
```

### 10.2 背景与问题

必须说明：

- 当前代码实际行为；
- 为什么需要该 Ticket；
- 它解决什么问题；
- 它不解决什么问题；
- 与前后 Ticket 的关系。

### 10.3 Scope

分别列出：

```text
In Scope
Out of Scope
Forbidden Changes
```

`Forbidden Changes` 必须具体到模块，例如：

- 不修改模型权重格式；
- 不修改 DFM 导出；
- 不改 Merge；
- 不引入外部大模型；
- 不改变增强关闭时的 Loss；
- 不吞掉核心训练异常。

### 10.4 当前代码锚点

必须列出：

```text
文件路径
类名
函数名
调用关系
当前数据 shape
当前 dtype
当前 mask 来源
当前保存恢复入口
```

不能只写目录级路径。

### 10.5 目标设计

必须包括：

- 类与函数签名；
- 配置字段；
- 数据结构；
- 输入输出；
- 默认值；
- 校验规则；
- 错误类型或错误码；
- 日志格式；
- Fallback 规则；
- requested/effective 状态；
- 与旧流程的等价条件。

### 10.6 实施步骤

按可执行顺序列出：

1. 新增或修改哪些文件；
2. 每个文件修改哪些类/函数；
3. 先写哪些测试；
4. 如何接入主链路；
5. 如何验证开关关闭时零影响；
6. 如何验证失败回退；
7. 如何验证保存恢复。

每一步必须可以由独立 Agent 判断是否完成。

### 10.7 测试要求

必须分别列出：

```text
Unit Tests
Smoke Tests
Integration Tests
Compatibility Tests
Failure Tests
Determinism Tests
GPU/Environment Deferred Tests
```

每项至少说明：

- 测试文件名；
- 测试函数或场景；
- 输入；
- 预期输出；
- 失败时说明什么问题；
- 可执行命令。

### 10.8 完成定义

必须使用可核验条件，例如：

```text
代码存在
进入主链路
Feature Flag 默认关闭
关闭时基线结果不变
单项日志可见
NaN/Inf 不被静默吞掉
旧 checkpoint 可加载
自动测试通过
Summary 已生成
独立 Review 已完成
Handoff 已更新
```

不得用“效果更好”“基本可用”作为唯一完成标准。

### 10.9 Review 检查表

至少检查：

- 是否越界进入后续 Batch；
- 是否改变旧行为；
- 是否重复创建配置来源；
- 是否存在隐式默认启用；
- 是否吞异常；
- 是否破坏 dtype/shape；
- 是否把 SRC/DST 职责混淆；
- 是否将 Geometry 与 Expression 强耦合；
- 是否有未测试的保存恢复路径；
- 文档和代码是否一致。

### 10.10 交付物

明确列出：

```text
代码文件
测试文件
Issue/Ticket 文档
Summary
Review 报告
配置说明
用户说明
Handoff 更新
Commit SHA
```

---

## 11. Batch 3 拆分文档建议目录

下一会话应参照 Batch 2 创建独立工作区，建议：

```text
.scratch/batch3-identity-geometry/
├── README.md
├── plan.md
├── issues/
│   ├── 01-....md
│   ├── 02-....md
│   └── ...
├── reports/
│   ├── master-test-matrix.md
│   ├── windows-gpu-geometry-acceptance.md
│   └── ...
├── reviews/
│   └── ...
└── handoff/
    └── ...
```

同时更新或新增正式文档：

```text
docs/development/batch3-identity-geometry-tasks.md
```

正式文档负责稳定的批次级施工设计；`.scratch` 负责逐 Ticket 执行、Summary、Review 和动态状态。

若仓库现有 Batch 2 目录结构不同，必须先读取真实结构并对齐，不得凭空创建第二套风格。

---

## 12. Batch 3 拆分过程

下一会话建议按以下顺序执行。

### Step 1：代码审计

审计：

```text
models/Model_SAEHD/
models/ModelBase.py
core/enhancements/
samplelib/metadata/
samplelib/sampling/
trainer / loss window / save controller 相关代码
现有 tests/smoke/
现有 options-json 解析与配置合并代码
```

输出当前调用链和可插入点，不得基于旧设计文档假设代码尚未变化。

### Step 2：复用 Batch 2 拆分方法

读取 Batch 2：

- 总设计文档；
- Ticket 文件；
- Summary；
- Review；
- Master Matrix；
- Handoff。

提炼其固定模板和质量门，形成 Batch 3 的模板。

### Step 3：确定 Ticket DAG

要求：

- 每个 Ticket 有单一职责；
- 前置依赖明确；
- 可并行项明确；
- 不允许循环依赖；
- 测试基础设施必须在依赖它的实现之前；
- 主链路接入不能早于 API、配置和契约稳定。

### Step 4：编写批次总设计

必须包含：

```text
目标
非目标
术语
架构图
调用链
配置 Schema
数据 Schema
Loss Hook 契约
Anchor 契约
Geometry 特征定义
错误/Fallback 边界
保存恢复策略
Ticket DAG
测试矩阵
GPU 验收矩阵
兼容矩阵
完成定义
```

### Step 5：逐 Ticket 编写

每个 Ticket 使用第 10 节模板，细化到文件、类、函数和测试命令。

### Step 6：独立一致性 Review

在开始编码前，至少进行一次文档级独立 Review，检查：

- Ticket 是否覆盖完整；
- Ticket 是否互相重叠；
- 是否混入 Batch 4—7；
- 是否缺失配置、日志、错误、测试、保存恢复；
- 是否适合较弱模型按文档独立执行；
- 是否存在模糊词或需要自行猜测的设计。

### Step 7：更新 Handoff

拆分完成后更新本文，记录：

- Batch 3 Ticket 数量；
- Ticket 列表；
- 依赖关系；
- 正式施工入口；
- 第一个可执行 Ticket；
- Review 结果；
- Commit SHA。

---

## 13. 弱模型执行保护规则

后续 Ticket 是给能力较弱的模型执行，因此必须使用以下保护规则。

### 13.1 不允许模型自行做重大设计选择

Ticket 必须预先决定：

- 使用哪个文件；
- 新类放在哪里；
- 配置字段名称；
- 默认值；
- 数据 shape；
- dtype；
- 错误语义；
- 测试文件；
- 回退行为。

若确实存在未决策项，必须单独创建设计 Ticket，不得让编码 Ticket 临场决定。

### 13.2 一次只执行一个 Ticket

不得让弱模型一次实现：

```text
Loss Hook + Anchor + Geometry Loss + Curriculum + SAEHD 接入
```

每个 Ticket 完成后必须：

1. 运行指定测试；
2. 输出 Summary；
3. 独立 Review；
4. 修复 Review；
5. 更新状态；
6. 再开始下一个 Ticket。

### 13.3 禁止扩大 Scope

Ticket 中必须明确：

```text
Do not refactor unrelated code
Do not rename public options without migration
Do not add Batch 7 losses
Do not modify Merge
Do not change checkpoint format
Do not swallow core errors
Do not claim GPU validation without evidence
```

### 13.4 证据优先

每个完成声明必须附：

- Commit SHA；
- 测试命令；
- 测试结果；
- 变更文件；
- 未执行项目；
- 已知风险。

---

## 14. Batch 3 关键技术约束

### 14.1 默认关闭

所有 Batch 3 能力必须默认关闭。未提供新配置时，旧训练行为保持不变。

### 14.2 单一配置来源

DFL 核心配置是默认值唯一来源。GUI 或外部调用只传用户启用或修改的字段。

### 14.3 SRC/DST 职责

```text
SRC：身份几何、脸宽、下颌、下巴、颧骨、稳定比例
DST：姿态、表情、眼睛开合、嘴型、运动属性
```

Geometry Loss 不得把 DST 的表情静态化，也不得要求 SRC/DST Landmark 逐帧一一配对。

### 14.4 Loss Hook 零影响

当全部新 Loss 关闭时：

- 总 Loss 与旧基线等价；
- 不新增隐式正则项；
- 不改变梯度；
- 不改变保存恢复；
- 不改变训练采样；
- 不改变 Merge。

### 14.5 错误边界

可以回退的仅限可选增强数据或可选 Geometry 模块错误；以下错误不得吞掉：

```text
核心 SampleLoader 错误
OOM / MemoryError
worker 崩溃
核心 Tensor shape 错误
核心 dtype 错误
checkpoint 损坏
optimizer state 不兼容
非有限梯度导致的关键训练失败
```

### 14.6 保存恢复

必须明确：

- Curriculum 当前阶段保存在哪里；
- Geometry Ramp 状态如何恢复；
- 新配置是否写入 checkpoint 或 sidecar；
- 旧 checkpoint 缺字段时如何默认；
- 新 checkpoint 在关闭增强时是否仍能恢复；
- optimizer slot 是否受影响。

---

## 15. 实机验证策略

### Batch 2

维护者已决定不再把最终 GPU Matrix 作为阻塞门。未来发现问题再反馈修复。

### Batch 3

Ticket 拆分时仍必须设计 Windows GPU Geometry A/B Matrix，但它属于 Batch 3 自身的效果与环境验证，不应复制 Batch 2 已被豁免的阻塞逻辑。

建议将 Batch 3 验证分为：

```text
Code Gate
Automated Test Gate
Short GPU Smoke Gate
Long GPU / Visual A-B Gate
```

是否把长时间 GPU / 人工视觉验收设为后续批次阻塞门，应由维护者在 Batch 3 Ticket 设计阶段明确决定，不得由执行模型自行假设。

---

## 16. 文档维护规则

1. 总体顺序以 `docs/implementation/enhanced-dfl-master-implementation-plan.md` 为准；
2. 当前跨会话事实以本文为准；
3. Batch 3 正式施工设计写入 `docs/development/`；
4. 动态 Ticket、Summary、Review 和矩阵写入 `.scratch/batch3-identity-geometry/`；
5. 不修改历史 Batch 2 报告以伪造 GPU PASS；
6. 维护者豁免决策写在当前 Handoff 和后续 Batch 3 计划中；
7. 每完成一个 Ticket，同步状态、Summary、Review 和 Handoff；
8. 任何未执行环境项目必须标注 deferred、not executed 或 pending；
9. 不创建第二份互相冲突的总路线；
10. 设计文档和真实代码冲突时，先审计代码并更新设计，不得让执行模型自行猜测。

---

## 17. 当前 Frontier

```text
开发 Frontier：Batch 3 Ticket 全量拆分与施工设计
Batch 2 implementation：COMPLETE
Batch 2 automated/code acceptance：COMPLETE
Batch 2 Windows GPU Final Matrix：DEFERRED-BY-MAINTAINER
Batch 2 progression：APPROVED-FOR-BATCH3
Batch 3 route：GEOMETRY-FIRST
Batch 3 ticket planning：READY-TO-START
Batch 3 coding：WAITING-FOR-TICKET-DESIGN-AND-REVIEW
```

---

## 18. 下一会话完成标准

下一会话只有同时满足以下条件，才算完成 Batch 3 Ticket 拆分：

```text
完成当前代码审计
完成 Batch 2 拆分方法复盘
建立 Batch 3 正式施工总文档
建立完整 Ticket DAG
每个 Ticket 都有独立详细文档
每个 Ticket 细化到文件/类/函数/测试
明确 In Scope / Out of Scope / Forbidden Changes
建立 Master Test Matrix
建立 Windows GPU Geometry A/B 规约
建立 Summary 与 Review 模板
完成至少一次独立文档 Review
修复 Review 发现的问题
更新 docs/README.md
更新总实施计划中的当前状态（如必要）
更新本文并记录所有 Commit SHA
明确第一个可执行编码 Ticket
```

在这些工作完成前，不应宣称 Batch 3 已进入编码实施阶段。

---

## 19. 新 Agent 接手指令

新会话开始后应直接执行：

1. 读取本文；
2. 确认分支和 HEAD；
3. 读取第 2 节列出的权威文档；
4. 审计 Batch 2 的真实 Ticket 目录结构和文档模板；
5. 审计 Batch 3 涉及的真实代码路径；
6. 输出 Batch 3 Ticket 拆分方案；
7. 创建完整详细文档；
8. 做独立一致性 Review；
9. 修订后提交；
10. 更新本文，留下第一个可执行 Ticket。

不得：

- 继续等待 Batch 2 GPU 验收；
- 把 Batch 2 未执行矩阵写成 PASS；
- 未拆 Ticket 就开始编码；
- 把 Batch 7 通用 Loss 混入 Batch 3；
- 只写概略 Ticket；
- 把重大设计决定留给后续弱模型；
- 修改 Merge 或 checkpoint 格式；
- 省略测试、回退、兼容和 Review 要求。
