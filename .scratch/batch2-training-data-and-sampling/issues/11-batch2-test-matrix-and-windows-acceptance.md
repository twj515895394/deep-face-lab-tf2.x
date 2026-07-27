# 11 — 建立 Batch 2 完整测试矩阵并完成 Windows FP32 验收

Status: open
Type: AFK + Windows GPU
Blocked by: `10-config-saehd-logging-and-fallback.md`

**构建内容：** 将 Schema、Analyzer、Loader、权重、WeightedIndexHost、Generator、配置和 SAEHD 组合成可重复验证矩阵；在 Windows 48GB Blackwell 环境使用 FP32 + AdaBelief 完成真实训练、保存恢复、普通/Packed、fallback 和性能记录。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 01-10 所有 summary；缺少任一前置 summary 时先标记 blocked
3. `.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md`
4. Batch 1 training/save-resume smoke 和 Windows 验收记录
5. `run_dfl.bat`、`train_dfl.bat`、Docker/Windows 当前实际启动方式
6. `models/ModelBase.py` iteration/save/load 语义
7. Ticket 10 给出的启动命令、交互答案和日志关键字

本 Ticket 主要负责验证和缺陷定位，不应顺手重构前置模块。发现缺陷时应回到对应 Ticket 范围修复并在报告中关联。

## 目标

- 自动测试证明工程和概率逻辑正确。
- Windows GPU 证明真实训练链路可长期使用。
- 明确区分“功能正确”“采样分布符合设计”“最终视觉质量人工判断”。
- 不以 macOS/CPU 轻量测试代替 Windows 真实验收。
- 每个场景保留可复查的命令、配置、日志和结果文件。

## 开工前 Gate 检查

进入 Windows 场景前必须满足：

```text
Ticket 01-10 summary 存在
+
所有适用 CPU/纯函数测试通过
+
legacy tensor contract 回归通过
+
ordinary/packed synthetic integration 通过
+
没有未解决的 Host deadlock / core error swallowing
```

若不满足，Windows 测试不得用于“边测边修所有东西”后直接标 done。

## 统一结果状态

每个测试项必须使用：

```text
PASS
FAIL
SKIP-DEPENDENCY
PENDING-WINDOWS
BLOCKED-BY-<ticket/reason>
NOT-APPLICABLE
```

禁止只写“测试过”“正常”“看起来没问题”。

## 自动测试执行顺序

### Layer 0：语法与导入

```bash
python -m compileall samplelib/metadata samplelib/sampling mainscripts/FacesetAnalyzer.py models/Model_SAEHD/Model.py
```

确认 Metadata/Sampling 模块不导入 TensorFlow。可用单独 import 测试。

### Layer 1：纯函数

- identity / sample id / path normalization；
- signature / fingerprint add-modify-delete；
- Schema roundtrip / partial / unsupported / duplicate；
- pose boundary 和左右符号；
- quality percentile、degenerate 分布、finite；
- config parse、clip、roundtrip；
- pose / quality / combined weights；
- probability normalize、uniform mix；
- resolver requested/effective/fallback。

建议统一命令：

```bash
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

若测试模块包含 GPU/Windows 条件，必须明确 skip reason。

### Layer 2：Analyzer / Store

- synthetic 清晰/模糊/曝光/坏文件；
- invalid landmarks；
- ordinary / packed 指标一致；
- full analyze；
- incremental all reuse；
- add/modify/delete；
- atomic write failure 保留旧文件；
- report issue counts 与 sample list；
- workers=1 和多 worker；
- CLI exit code。

必须保存一份 ordinary 和 packed 的示例 Metadata/Report 到临时测试产物目录或报告摘录，不提交用户私有数据。

### Layer 3：Loader

- full match；
- missing / invalid / unsupported；
- partial 95% / 50%；
- collision / extra records；
- ordinary / packed / person faceset；
- runtime compact arrays dtype、shape、内存；
- src/dst 单侧状态不同。

### Layer 4：Host / 分布

- fixed seed deterministic；
- 不同 seed；
- 多 CLI 并发；
- N=1、N<batch、N>>batch；
- batch duplicate retry；
- invalid probabilities；
- 长时间 draw 无死锁；
- pose imbalance simulation；
- quality + pose conflict；
- 每样本非零覆盖；
- close/fatal error propagation。

分布测试报告至少记录：

```text
expected probability
actual frequency
absolute error
max error
sample count/draw count
seed
```

### Layer 5：Generator

- debug 单线程；
- generators_count=1；
- generators_count>1；
- ordinary / packed；
- src/dst 不同 policy；
- eyes_mouth False/True；
- random_ct；
- output count/shape/dtype 与 baseline；
- worker error propagation 和正常退出；
- Windows spawn。

对 tensor contract 使用 Ticket 01 冻结的结构作为 expected，不要重新定义 expected。

## Windows GPU 固定基线

```text
GPU: RTX PRO 5000 Blackwell 48GB
precision: fp32
optimizer: adabelief
GAN: off
TrueFace: off
style loss: off for first acceptance
small/known resolution and batch
fixed src/dst test workspace
```

实际硬件、驱动、CUDA、TensorFlow、容器/宿主版本必须记录，不允许只写“Windows 已通过”。

## Windows 工作区准备

建议使用独立测试工作区，不直接操作长期主模型：

```text
batch2-acceptance/
├─ data_src/aligned
├─ data_dst/aligned
├─ data_src_packed/aligned
├─ data_dst_packed/aligned
├─ model_legacy_baseline
├─ model_pose
├─ model_quality_pose
├─ logs
└─ reports
```

要求：

- src/dst 至少覆盖正脸和侧脸；
- 保留一份固定副本用于所有场景；
- 每个模式使用独立模型目录或由同一干净 checkpoint 复制；
- 不在同一模型目录反复切换多个模式后声称可比较；
- 所有路径、命令和模型起点记录在 manifest，不提交私有素材。

## Windows 场景执行协议

每个场景都按固定顺序：

```text
准备/复制干净模型目录
→ 记录配置和 Metadata 状态
→ 启动并截取 startup sampling log
→ warmup 若干 iter
→ 记录稳定窗口 iter time/loss/资源
→ 保存
→ 完全退出进程
→ 重新启动
→ 继续训练
→ 收集实际 sampling stats
→ 标记 PASS/FAIL
```

不能只启动 1 iter 就判定“可长期使用”。小规模验收建议至少：

- warmup 20-50 iter；
- 稳定记录 100-300 iter；
- save/exit/resume 后继续 50-100 iter。

实际步数受环境限制时必须记录，不得隐瞒。

## Windows 场景

### W1 Legacy Random

- [ ] 功能关闭。
- [ ] 启动、训练、保存、退出、恢复。
- [ ] requested/effective 日志符合 master off/legacy。
- [ ] 记录 loss、iter time、GPU/CPU 内存。
- [ ] tensor contract 与 Ticket 01 baseline 一致。

### W2 Legacy Uniform Yaw

- [ ] 现有 uniform_yaw 行为可用。
- [ ] 输出 contract 与 W1 相同。
- [ ] 新配置关闭时不读取 Metadata。
- [ ] 与 Batch 1/旧行为无明显启动回归。

### W3 Pose Balanced

- [ ] src/dst Metadata 完整。
- [ ] effective mode 正确。
- [ ] 实际侧脸抽样比例高于原始分布且受限。
- [ ] loss finite、训练稳定。
- [ ] src/dst bucket stats 分开。

### W4 Quality + Pose

- [ ] quality/pose 权重和日志正确。
- [ ] 低质量样本仍有抽样记录。
- [ ] uniform exploration 可观察。
- [ ] 训练稳定。
- [ ] probability/weight min/max 与启动日志一致。

### W5 单侧 Metadata 缺失

- [ ] src 智能、dst fallback 或反向。
- [ ] 两侧日志分开。
- [ ] 训练继续。
- [ ] effective mode 不串用。

### W6 损坏与不匹配

依次独立测试，不要一次同时破坏多个条件：

- [ ] invalid JSON；
- [ ] unsupported schema；
- [ ] fingerprint mismatch；
- [ ] partial match above threshold；
- [ ] partial match below threshold；
- [ ] invalid probabilities（通过测试注入或 controlled fixture）；
- [ ] effective fallback 正确；
- [ ] 核心错误仍抛出。

### W7 Packed Faceset

- [ ] Analyzer 无需解包。
- [ ] Loader 正确匹配。
- [ ] ordinary/packed 对应样本 key 一致。
- [ ] 多进程训练、保存恢复。
- [ ] 不修改 faceset.pak。

### W8 Save / Exit / Resume

- [ ] 智能模式训练若干 iter。
- [ ] 保存并完全退出进程，不只是关闭 preview。
- [ ] 重新加载模型和 Metadata。
- [ ] model/optimizer iter 连续。
- [ ] sampling requested/effective 一致。
- [ ] sampler draw state 不要求连续，但日志说明重建。
- [ ] Metadata 丢失时可 legacy 恢复。
- [ ] Metadata 恢复后可再次启用智能模式。

### W9 Performance

记录：

- [ ] Analyzer samples/sec 和峰值 RSS。
- [ ] Metadata JSON 大小。
- [ ] Metadata load/build time。
- [ ] WeightedIndexHost build time。
- [ ] Generator samples/sec。
- [ ] legacy 与 weighted 稳定 iter time。
- [ ] CPU 使用率、内存和 GPU 显存。
- [ ] 启动额外耗时。
- [ ] stats logging 开销。

不预先拍脑袋写死阈值；先跑 baseline，再在 summary 中给出：

```text
absolute value
delta vs W1
percentage delta
是否可接受
依据
```

## 资源记录建议

每个 Windows 场景至少记录：

```text
start time/end time
model name/path alias
resolution/batch/architecture
sample counts
workers
precision/optimizer
average iter time after warmup
p50/p95 iter time（能取得时）
process RSS
GPU VRAM
loss finite
sampling stats snapshot
save duration
reload duration
```

## 人工数据检查

- [ ] 随机抽查 pose 标签。
- [ ] 抽查低/中/高 quality 样本。
- [ ] 检查稀缺侧脸是否被适度提升。
- [ ] 检查低质量样本未完全消失。
- [ ] 检查报告是否足够指导人工清理 faceset。

人工检查只判断 Metadata/采样是否合理，不在本 Ticket 宣称换脸最终质量提升。

## 缺陷处理规则

发现问题时：

- Schema/identity → 回 Ticket 02；
- Analyzer/quality → 回 Ticket 03/04；
- Loader mismatch → 回 Ticket 05；
- mode/fallback → 回 Ticket 06/10；
- pose/quality 公式 → 回 Ticket 07/08；
- deadlock/Generator contract → 回 Ticket 09；
- 文档问题 → 留 Ticket 12。

修复提交必须说明关联场景，修复后重跑受影响场景和 legacy baseline。

## 阻断条件

任一命中，Batch 2 不得标记 done：

- 任一模式导致训练卡死或 worker 无法退出；
- 关闭功能与 legacy contract 不一致；
- Metadata 错配到错误样本；
- src/dst 权重串用；
- 权重产生零概率、NaN 或 Inf；
- fallback 吞掉训练核心异常；
- save/resume 受影响；
- Packed 必须解包才能训练；
- 仅完成自动测试却宣称 Windows GPU 完成；
- Windows 只启动未完成真实 save/exit/resume；
- 性能回退严重但没有数据和结论。

## 禁止捷径与常见错误

- 不允许用 synthetic TensorFlow 图代替真实 SAEHD Windows 训练。
- 不允许用普通目录结果推断 Packed 已通过。
- 不允许同一模型目录先跑 W1 再跑 W3 后直接比较 loss/速度。
- 不允许把 macOS/Linux subprocess 结果写成 Windows spawn PASS。
- 不允许只截取 startup 日志，不收集实际 draw stats。
- 不允许只看 loss 降低判断采样策略正确。
- 不允许为了完成验收临时关闭失败测试而不记录。
- 不允许直接在 Ticket 11 做无关架构重构。
- 不允许遗漏硬件、驱动、CUDA、TensorFlow 和容器版本。

## 验收标准

- [ ] 所有适用自动测试通过。
- [ ] 所有 Windows W1-W9 有结果或明确阻断记录。
- [ ] FP32 + AdaBelief 主线稳定。
- [ ] legacy 开关关闭行为不变。
- [ ] new mode 真实改变采样分布。
- [ ] 保存恢复和 fallback 可长期使用。
- [ ] 性能回退有数据和结论。
- [ ] 每个 PASS 都能追溯到命令、日志或报告证据。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/11-batch2-test-matrix-and-windows-acceptance-summary.md`。
- [ ] 单独生成/更新 `reports/windows-gpu-acceptance.md`，包含命令、环境、日志摘要、资源数据和未完成项。
- [ ] 提供一张 W1-W9 状态表。
- [ ] 列出所有修复回流到哪个 Ticket、对应 commit 和重跑结果。
- [ ] 给 Ticket 12 明确哪些功能可写成正式可用、哪些只能写 pending/known limitation。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建。此 ticket 未完成前 Batch 2 不得标记 done。
- 2026-07-27：补充弱模型 Gate、统一状态、固定执行协议、场景证据、缺陷回流和禁止捷径。