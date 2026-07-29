# Batch 2 独立代码审查、问题汇总与修复总计划

> 文档状态：REVIEW-FAILED / FIXES-REQUIRED  
> 审查日期：2026-07-29  
> 审查范围：Batch 2 Ticket 01—13、Faceset Analyzer、Metadata Loader、Sampling Runtime、WeightedIndexHost、SAEHD 接线、Loss Window、使用文档与交接文档  
> 目标读者：项目维护者、独立 Reviewer、弱模型编码 Agent、Windows GPU 验收执行者  
> 结论优先级：本文档高于此前“175/175 PASS 即视为 Batch 2 完成”的结论

---

## 1. 执行结论

Batch 2 当前不能认定为正式完成，也不应直接合并到 `main` 后用于生产训练。

现有测试证明了部分纯函数、Synthetic Fixture、主进程 Host 调用和轻量 CLI 可以运行，但没有证明以下关键链路：

```text
Analyzer
→ Metadata Sidecar
→ Runtime Loader
→ Canonical Pose / Quality Arrays
→ Sampling Policy
→ WeightedIndexHost
→ Windows spawn worker
→ SAEHD 真训练
→ Save / Exit / Resume
```

独立审查发现：

- 4 个阻断级 P0 问题；
- 5 个高优先级 P1 问题；
- 多项文档与实现不一致；
- 测试存在“模块测试通过但端到端契约断裂”的结构性盲区；
- Windows GPU 验收尚未完成；
- `.handoff/current.md` 含未解决 Git 冲突标记；
- 原综合 Review 报告对“spawn 安全”“配置可用”“Analyzer 参数生效”等结论过度乐观。

因此 Batch 2 当前建议状态：

```text
REVIEW-FAILED
FIXES-REQUIRED
LEGACY-SAFE
METADATA-SAMPLING-NOT-PRODUCTION-READY
PENDING-WINDOWS-GPU
```

Legacy 路径原则上仍可继续使用，但修复过程中必须持续回归：

- `legacy_random`；
- `legacy_uniform_yaw`；
- Metadata Sampling 总开关关闭；
- 旧模型配置加载；
- 原有 Generator 输出 shape / dtype / 顺序。

---

## 2. 核心问题总览

| 编号 | 等级 | 问题 | 用户影响 | 修复 Ticket |
|---|---|---|---|---|
| P0-01 | 阻断 | Analyzer 与 Loader 的 yaw/pitch bucket 名称不一致 | `pose_balanced` 可能静默退化为均匀采样 | 14 |
| P0-02 | 阻断 | 用户指南配置缺少顶层 `enhancements` 和 `training.enabled` | 用户按文档启动时功能不生效 | 15、21 |
| P0-03 | 阻断 | 文档宣称 `sampling.src/dst`，代码只支持扁平全局配置 | SRC/DST 独立配置被静默忽略 | 15 |
| P0-04 | 阻断 | WeightedIndexHostClient 在 Windows spawn 下携带不完整 `_host_ref` | 子进程可能 `AttributeError`、超时或训练挂起 | 16 |
| P1-01 | 高 | `--workers` 与 `--strong-fingerprint` 参数未实际使用 | 用户误以为并行和强指纹生效 | 17 |
| P1-02 | 高 | Loader 按 sample ID 计匹配，不逐样本验证 signature | 同名替换图片后可能继续使用旧元数据 | 17 |
| P1-03 | 高 | 增量汇总读取旧顶层字段，真实记录使用嵌套字段 | valid、usable、pose 分布报告失真 | 18 |
| P1-04 | 高 | Loss Window 在保存后下一轮才统计 | 窗口多包含一个未进入 checkpoint 的 batch | 19 |
| P1-05 | 高 | Fallback 捕获范围包含 SampleLoader 核心错误 | 核心数据错误可能被伪装成 Metadata optional fallback | 20 |
| D-01 | 文档 | 使用指南写成支持 SAEHD、AMP、Quick96 全量模型 | 能力范围被夸大 | 21 |
| D-02 | 文档 | 使用指南写 `--options-json` 可传文件 | 与真实入口不符 | 21 |
| D-03 | 文档 | `.handoff/current.md` 有冲突标记和互相矛盾状态 | 后续 Agent 无法判断真实 frontier | 21 |
| T-01 | 测试 | Generator 集成测试全部 `debug=True` | 完全绕过真实子进程 | 16 |
| T-02 | 测试 | Loader 测试不断言 pose bucket 真正可识别 | P0 Schema 漂移未被发现 | 14 |
| T-03 | 测试 | 增量测试手工构造旧 Schema | 测试验证了错误结构 | 18 |
| T-04 | 测试 | Loss 仅测纯函数，不测 Trainer 保存时序 | 保存边界错误未被发现 | 19 |

---

## 3. P0 问题详细说明

## 3.1 P0-01：Pose Bucket Schema 漂移

Analyzer 当前输出 yaw：

```text
extreme_left
major_left
minor_left
center
minor_right
major_right
extreme_right
```

Analyzer 当前输出 pitch：

```text
up
level
down
```

Loader 当前识别 yaw：

```text
pitch_center_yaw_center
front
slight_left
slight_right
left
right
extreme
```

Loader 当前识别 pitch：

```text
up
center
down
```

结果：

```text
Metadata 文件成功加载
sample_id 匹配成功
status == LOADED
但 yaw_bucket_ids 保持 -1
pose_valid 保持 false
```

`PoseBalancedPolicy` 对 unknown / invalid pose 使用固定权重，最终可能得到近似等权概率。控制台仍可能显示 requested/effective 均为 `pose_balanced`，形成最危险的“静默功能失效”。

必须通过 Ticket 14：

- 建立唯一 canonical bucket 常量；
- Analyzer、Loader、Incremental、Report、Tests 共用；
- 增加真实 Analyzer → Loader → Policy 端到端测试；
- 断言概率确实非均匀；
- 禁止用“LOADED 状态”代替姿态有效性验收。

---

## 3.2 P0-02：训练配置示例不可用

真实 SAEHD 读取：

```text
self.options["enhancements"]
```

真实 Gate：

```text
enhancements.training.enabled == true
AND
enhancements.training.metadata_sampling == true
```

旧使用指南却给出：

```json
{
  "training": {"metadata_sampling": true},
  "sampling": {...}
}
```

该 JSON 会被 ModelBase 注入为未知顶层字段，但 SAEHD 不读取这些字段。用户看到训练正常启动，会误以为智能采样已启用。

修复必须覆盖：

- 权威 JSON Path；
- 双 Gate；
- silent start；
- `--force-model-name`；
- 持久化语义；
- requested/effective/fallback 日志；
- 负向测试：错误层级配置必须明确警告，不能静默忽略。

---

## 3.3 P0-03：SRC / DST 配置契约不一致

旧指南宣称支持：

```json
"sampling": {
  "src": {"mode": "pose_balanced"},
  "dst": {"mode": "legacy_random"}
}
```

实际 `SamplingConfig.from_mapping()` 只解析一份扁平配置。SAEHD 为 SRC 和 DST 传入同一个 `EnhancementConfig`，仅 seed 和默认 Metadata 路径不同。

Ticket 15 采用以下正式决策：

1. 保留旧扁平 `enhancements.sampling`，作为“同时应用于 SRC/DST”的兼容形状；
2. 新增正式 `enhancements.sampling.src` 与 `.dst`；
3. 出现 side-specific 配置时，每侧独立解析；
4. 缺失侧从扁平 base 继承；
5. side-specific 字段覆盖 base；
6. Metadata 路径相对各自 faceset 解析；
7. 不允许 `..` 逃逸到未授权父目录；
8. 启动日志必须分别输出最终解析后的完整摘要。

---

## 3.4 P0-04：Windows spawn Client 序列化风险

当前 `WeightedIndexHostClient` 保存 `_host_ref`。Host 的 `__getstate__()` 返回空字典。Windows spawn 时 Client 被 pickle，引用的 Host 也被 pickle 成缺少全部属性的空对象。

子进程调用：

```python
if self._host_ref and self._host_ref._fatal_error:
```

可能直接 `AttributeError`。

测试没有覆盖，因为：

- Generator 测试全部 `debug=True`；
- debug 路径使用当前线程；
- Host 测试只在主进程直接调用 Client；
- 未使用 `multiprocessing.get_context("spawn")`。

Ticket 16 必须：

- 明确定义 Client pickle contract；
- 子进程中 `_host_ref` 必须为 `None`；
- 使用可 pickle 的 Event/Queue 传播 closed/fatal；
- 使用阻塞 `get(timeout=...)`，不依赖 `Queue.empty()`；
- 增加真实 spawn process 测试；
- 增加 `debug=False` Generator 测试；
- 验证多 worker、close、host fatal、timeout、N<batch。

---

## 4. P1 问题详细说明

## 4.1 P1-01：Analyzer 空壳参数

`main.py` 和 `FacesetAnalyzer.main()` 接收：

```text
workers
strong_fingerprint
```

但当前：

- 没有 worker executor；
- 没有进程池；
- 没有线程池；
- 没有按参数改变执行路径；
- strong fingerprint 没有读取完整样本字节；
- signature 的 `quick_hash` 也没有被填充。

Ticket 17 必须满足二选一原则：

```text
真正实现 + 测试 + 文档
OR
删除 CLI 参数 + 删除文档承诺
```

不允许继续保留“接受但无效”的参数。

---

## 4.2 P1-02：Stale Metadata 仍被视为匹配

Loader 当前匹配主要依赖：

```text
sample_key → sample_id
```

图片内容变化但文件名不变时：

- sample ID 不变；
- matched count 仍增加；
- dataset fingerprint 即使变化，也可能只进入 PARTIAL_MATCH；
- matched ratio 仍为 100%；
- PARTIAL_MATCH 仍可能被视为可采样。

正确契约：

```text
sample_id 匹配
AND
record.signature 与 current signature 匹配
才算 trusted match
```

必须单独统计：

- id matched；
- signature matched；
- stale signature；
- missing record；
- duplicate / collision；
- trusted ratio。

采样可用性必须基于 trusted ratio，而不是 key ratio。

---

## 4.3 P1-03：Incremental Summary 读取错误字段

真实记录：

```text
image.valid
landmarks.valid
pose.valid
pose.yaw_bucket
pose.pitch_bucket
quality_raw.valid
quality.quality_score
```

增量汇总读取：

```text
valid
usable_for_sampling
pose_bucket_yaw
pose_bucket_pitch
```

测试也使用旧顶层字段，导致错误实现被测试固化。

Ticket 18 必须：

- 使用公共 record accessor；
- 基于真实 Analyzer 输出构建增量测试；
- 新增、修改、删除后对比全量重算结果；
- summary 与 Metadata samples 进行离线重算一致性检查；
- Report 不得自行维护第二套字段解释。

---

## 4.4 P1-04：Loss Window Save Boundary 错位

当前保存流程：

```text
model.save()
→ after_save = true
→ 下一次 train_one_iter()
→ 统计 loss_history[start:]
```

窗口多包含保存后的一个 batch。该 batch 不属于刚刚写入的 checkpoint。

正确流程：

```text
freeze end_index = len(loss_history)
→ model.save()
→ 只有 save 成功才统计 [start_index:end_index]
→ 输出日志
→ start_index = end_index
```

保存失败：

- 不得消费窗口；
- 不得更新 start index；
- 不得输出“保存成功窗口”；
- 原异常不得吞掉。

同一实现必须覆盖：

- 首次 iter 1 保存；
- 自动保存；
- 手动保存；
- 目标迭代保存；
- 退出保存；
- 连续保存但没有新 batch；
- 恢复训练后不混入旧 history。

---

## 4.5 P1-05：Fallback 边界过宽

当前 Metadata Sampling Runtime 将：

```text
SampleLoader.load
+
FacesetMetadataLoader.load
```

放在同一个广泛 `try/except Exception` 中。

这会把以下核心错误也误判为 optional Metadata 错误：

- faceset 无法加载；
- Packed 数据损坏；
- Sample 对象构建错误；
- 权限错误；
- 内存错误；
- 编程错误。

Ticket 20 必须建立异常分类：

### 允许 fallback

- Metadata 文件不存在；
- JSON 解析失败；
- 不支持 Schema；
- trusted ratio 不足；
- Metadata 内局部非有限值被安全中和；
- requested policy 因 Metadata 不可用而降级。

### 必须抛出

- 无训练样本；
- SampleLoader / PackedFaceset 核心异常；
- SampleProcessor 异常；
- worker 持续崩溃；
- TensorFlow 初始化或训练异常；
- OOM；
- 模型保存加载异常；
- 未预期编程错误。

---

## 5. 文档与交接问题

## 5.1 模型支持范围夸大

当前运行时接线只在 `models/Model_SAEHD/Model.py`。文档不得宣称 AMP、Quick96 或全量模型已支持，除非这些模型有独立接线和测试。

## 5.2 `--options-json` 文件支持错误

当前入口接收 JSON 字符串，不接受 JSON 文件路径。所有示例必须与权威参数文档一致。

## 5.3 `.handoff/current.md` 冲突标记

必须删除：

```text
<<<<<<<
=======
>>>>>>>
```

并形成唯一状态：

```text
Batch 2 Review remediation in progress
Tickets 14—21 open
Windows GPU pending
Batch 3 blocked until Batch 2 remediation closes
```

## 5.4 原 Review 报告状态

原 `batch2-comprehensive-code-review.md` 不应删除，但必须在顶部追加 superseded / invalidated 说明，指向本文档。不得保留“完全符合”“可直接 done”而无补充声明。

---

## 6. 修复 Ticket 拆分

| Ticket | 标题 | 依赖 | 是否适合弱模型 |
|---|---|---|---|
| 14 | 统一 Metadata Bucket Schema 与端到端契约 | 无 | 是，必须严格按常量和测试施工 |
| 15 | 修复 options-json、双 Gate 与 SRC/DST 配置契约 | 14 | 是，但必须先复核真实配置链 |
| 16 | 修复 WeightedIndexHost Windows spawn | 14 | 高风险，弱模型完成后必须强模型 Review |
| 17 | 实现 workers、强指纹和 stale signature 检测 | 14 | 中高风险，拆小步骤执行 |
| 18 | 修复增量汇总与报告 Schema | 14、17 | 是 |
| 19 | 修复 Loss Window 保存边界 | 无 | 是，但必须测试 Trainer 时序 |
| 20 | 收窄 fallback 异常边界 | 15、16、17 | 高风险，必须独立 Review |
| 21 | 文档、交接和 Windows GPU 最终验收 | 14—20 | 不允许只做文档后直接 done |

推荐顺序：

```text
14
├── 15
├── 16
└── 17
     ↓
18

19 可与 14—18 独立进行

15 + 16 + 17
     ↓
20

14—20 全部完成
     ↓
21
```

不建议同时让同一个弱模型处理：

- Ticket 16 与 Ticket 20；
- Ticket 17 与 Ticket 18；
- Ticket 14 与 Ticket 15；
- Ticket 21 与任何尚未完成的代码 Ticket。

---

## 7. 修复阶段通用开发约束

所有 Ticket 必须遵守：

1. 所有增强默认关闭；
2. 不修改 SAEHD 网络或 Loss 公式；
3. 不修改 checkpoint、optimizer、DFM、Merge 或 `faceset.pak` 格式；
4. 不引入大型外部模型；
5. 路径支持中文、空格、Unicode；
6. 文本 UTF-8；
7. JSON `ensure_ascii=False`、`allow_nan=False`；
8. Windows 以 spawn 为准；
9. 不使用 `Queue.empty()` 作为可靠同步依据；
10. 不吞核心训练异常；
11. 不用 fallback 掩盖测试失败；
12. 不以测试数量替代测试覆盖；
13. 不得手工构造与真实 Analyzer 不同的虚假测试 Schema；
14. 新增配置必须同步权威 `--options-json` 文档；
15. 每个 Ticket 单独提交 summary。

---

## 8. 测试分层

## 8.1 Layer 0：纯函数

- canonical bucket assignment；
- alias / invalid bucket handling；
- signature compare；
- weight / probability finite；
- Loss Window start/end slicing；
- config inheritance；
- exception classification。

## 8.2 Layer 1：组件

- Analyzer 单样本；
- Metadata Schema；
- Loader compact arrays；
- Sampling Policy；
- WeightedCycleSampler；
- Atomic Store；
- Report recompute。

## 8.3 Layer 2：端到端 CPU

必须真实执行：

```text
build fixture
→ Analyzer
→ write Sidecar
→ Loader
→ Policy
→ Host
→ draw
```

断言：

- pose valid 非零；
- bucket IDs 正确；
- trusted ratio 正确；
- probabilities 非均匀；
- empirical distribution 接近 expected；
- Ordinary / Packed 都覆盖。

## 8.4 Layer 3：spawn

使用：

```python
multiprocessing.get_context("spawn")
```

覆盖：

- Client pickle；
- child multi_get；
- 多 child；
- host close；
- fatal event；
- timeout；
- N<batch；
- debug=False Generator。

## 8.5 Layer 4：SAEHD CPU/初始化

- `--options-json` 注入；
- 双 Gate；
- SRC/DST config；
- startup logs；
- legacy disabled path；
- fallback strictness。

## 8.6 Layer 5：Windows GPU

固定：

```text
Windows
FP32
AdaBelief
SAEHD
ordinary + packed
```

覆盖四种 mode、两侧配置、保存恢复、统计和性能。

---

## 9. 最终验收门槛

Batch 2 只有同时满足以下条件，才能恢复 `done`：

### 9.1 自动测试

- [ ] 所有原 Batch 1 / Batch 2 回归通过；
- [ ] Analyzer → Loader → Policy 端到端通过；
- [ ] canonical bucket 契约通过；
- [ ] stale signature 测试通过；
- [ ] incremental 与 full recompute 一致；
- [ ] spawn process 测试通过；
- [ ] debug=False Generator 测试通过；
- [ ] Trainer save-boundary 测试通过；
- [ ] fallback 分类测试通过；
- [ ] Unicode 路径通过。

### 9.2 Windows GPU

- [ ] legacy_random 训练；
- [ ] legacy_uniform_yaw 训练；
- [ ] pose_balanced 训练；
- [ ] quality_pose_balanced 训练；
- [ ] Ordinary；
- [ ] Packed；
- [ ] SRC/DST 同模式；
- [ ] SRC/DST 不同模式；
- [ ] Metadata missing fallback；
- [ ] Metadata invalid fallback；
- [ ] stale signature fallback；
- [ ] manual save；
- [ ] auto save；
- [ ] exit save；
- [ ] resume；
- [ ] 无死锁；
- [ ] 无静默 worker 崩溃；
- [ ] 记录 iter time、显存和采样统计。

### 9.3 文档

- [ ] Analyzer 独立使用说明；
- [ ] `--options-json` 权威文档；
- [ ] 兼容指南；
- [ ] Windows 验收报告；
- [ ] 所有 Ticket summary；
- [ ] 最新 handoff；
- [ ] `current.md` 无冲突；
- [ ] 原错误 Review 报告有 superseded 标记。

---

## 10. 弱模型施工规则

每次只提供：

```text
AGENTS.md
+
spec.md
+
本总计划
+
当前 Ticket
+
Blocked by 对应 summary
+
Ticket 指定源码
```

弱模型必须先输出“源码事实复核”，至少回答：

1. 当前函数实际读取哪些字段；
2. 当前测试是否走真实路径；
3. 当前数据结构与 Ticket 假设是否一致；
4. 哪些异常属于 optional；
5. 哪些行为必须保持 legacy；
6. 将修改哪些文件；
7. 哪些文件明确不修改。

施工时：

- 一次只改一个逻辑层；
- 每步运行对应测试；
- 失败不得扩大 try/except；
- 不允许通过修改测试期望来迎合错误实现；
- 测试 Fixture 必须由真实 Analyzer 输出驱动；
- 最后必须生成 summary。

高风险 Ticket 16、20 完成后，必须由强模型或人工再次 Review，不得由原施工模型自审后直接 resolved。

---

## 11. 完成状态定义

允许状态：

```text
OPEN
IN-PROGRESS
BLOCKED-BY-XX
PASS-MACOS-LIGHTWEIGHT
PENDING-WINDOWS
FAIL
RESOLVED
```

禁止使用模糊状态：

```text
基本完成
应该可用
测试看起来没问题
理论支持 Windows
大概率不会有问题
```

`RESOLVED` 必须有：

- commit SHA；
- 修改文件；
- 测试命令；
- 原始输出摘要；
- 未执行项；
- Windows 状态；
- summary 文档；
- Reviewer 结论。

---

## 12. 当前安全使用建议

在 Ticket 14—21 完成前：

```text
Analyzer：允许用于报告和开发调试
Metadata Sidecar：允许生成和检查
pose_balanced：不用于正式训练结论
quality_pose_balanced：不用于正式训练结论
Windows 多进程：未验收
正式训练：使用 legacy_random / legacy_uniform_yaw
```

不得因为训练没有崩溃，就认定智能采样正确。智能采样的验收对象是“实际抽样分布和端到端数据契约”，不是“代码成功启动”。

---

## 13. 关闭本 Review Gate 的最终判定模板

```text
Batch 2 Independent Remediation Final Decision

Ticket 14: PASS / FAIL
Ticket 15: PASS / FAIL
Ticket 16: PASS / FAIL
Ticket 17: PASS / FAIL
Ticket 18: PASS / FAIL
Ticket 19: PASS / FAIL
Ticket 20: PASS / FAIL
Ticket 21: PASS / FAIL

Legacy regression: PASS / FAIL
Analyzer → Loader → Policy E2E: PASS / FAIL
Windows spawn: PASS / FAIL
Windows FP32 + AdaBelief: PASS / FAIL
Ordinary: PASS / FAIL
Packed: PASS / FAIL
Save / Exit / Resume: PASS / FAIL
Docs consistency: PASS / FAIL

Final status:
- done
- pending-windows
- fixes-required
- blocked
```

只要任一 P0、Windows spawn、真实 GPU 训练、保存恢复或文档一致性为 FAIL，就不得签发正式 `done`。