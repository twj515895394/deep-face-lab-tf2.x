# AGENTS.md — DeepFaceLab TF2.x 研发与 Agent 执行规范

> 适用范围：本仓库全部代码、测试、文档和自动化 Agent。  
> Python 基线：最低 3.9。  
> 原则：先保护 legacy 正确性，再增加默认关闭、可观测、可回退的增强能力。

## 1. 开工前

1. 阅读 `.handoff/current.md`。
2. 阅读当前批次 `spec.md`、详细设计、当前 Ticket 和所有前置 summary。
3. 读取 Ticket 指定的真实源码，不能仅按文档猜测。
4. 记录当前 branch、commit、测试环境和将修改的文件。
5. 前置接口缺失或源码与设计冲突时标记 blocked，不自行扩大范围。

## 2. Unicode、中文路径与文件 I/O

所有功能必须原生支持中文、空格和非 ASCII 路径。

- 路径使用 `pathlib.Path` 或 Unicode `str`。
- 图像路径读写优先使用项目 `core.cv2ex` 能力，不直接新增原生 `cv2.imread/cv2.imwrite` 路径调用。
- 文本文件显式 `encoding="utf-8"`。
- JSON 使用 `ensure_ascii=False` 和 `allow_nan=False`。
- 不依赖 Windows ANSI 代码页。
- 测试至少覆盖中文目录、空格目录和一个扩展 Unicode 文件名。
- 日志可以显示必要路径，但不得批量泄露用户完整样本清单。

## 3. 向后兼容

新增能力必须默认关闭，并满足：

- 旧模型和旧配置可加载；
- 新字段缺失时不改变 legacy 行为；
- 不修改模型权重、optimizer、DFM、Merge 或 `faceset.pak` 格式，除非独立设计明确批准；
- optional 增强失败可以回退，但不得吞掉训练数据为空、SampleProcessor、TensorFlow、模型保存加载和 worker 持续崩溃等核心错误；
- 关闭新增功能时，输出数量、顺序、shape 和 dtype 与基线一致。

## 4. 范围控制

禁止顺手实现当前 Ticket 之外的内容，尤其是：

- SAEHD 网络或 Loss 改造；
- 动态 Loss-aware Sampling；
- Identity Geometry / 脸型 Loss；
- Source Shape Template；
- Shape-aware Merge；
- Lion 或 FP16/BF16 正式路线扩展；
- UI、服务化或大范围无关重构。

## 5. 测试与完成状态

至少执行：

```bash
python -m compileall <changed paths>
python -m unittest <relevant tests>
```

状态必须使用明确证据：

- `PASS`：实际运行并通过；
- `SKIP-DEPENDENCY`：依赖缺失且有原因；
- `PENDING-WINDOWS`：只能在 Windows 环境验证；
- `FAIL`：实际失败；
- `BLOCKED-BY-*`：被前置问题阻断。

只通过语法检查、测试全部 skip、只完成接口或只生成文档，均不能写 resolved。

## 6. 多进程与数值安全

- Windows 以 spawn 为准；进程入口必须安全。
- queue/client 不得永久等待，必须有 fatal/closed/timeout 语义。
- 不把大 JSON 或不可 pickle 对象传入每个 worker。
- 新随机逻辑使用独立 RNG，不污染全局 NumPy 状态。
- 权重、概率、配置和 JSON 不允许 NaN/Inf。
- 极小数据集、空数据、N<batch 和 worker 退出必须有测试。

## 7. `--options-json`

仓库已支持从 CLI 向 `ModelBase` 注入训练配置。后续新增训练配置必须考虑：

- 无 `--options-json` 时旧交互行为不变；
- 非空 `--options-json` 时不应再次用交互覆盖显式值；
- 已保存配置、options JSON 和交互输入的优先级必须写入测试；
- 嵌套配置必须保持 JSON 类型，不自行转换成不可兼容字符串；
- 损坏 options JSON 不得被伪装成普通 optional Metadata 缺失。

## 8. Batch 2 特别入口

Batch 2 开发还必须阅读：

1. `.scratch/batch2-training-data-and-sampling/spec.md`
2. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
3. `.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md`
4. 当前 Ticket 与前置 summary

`FINAL_AUDIT_CONTRACTS.md` 冻结 Unicode、Analyzer v1、配置优先级、采样数值和量化验收门槛，不能跳过。

## 9. Summary 与交接

每个 Ticket 完成后必须生成指定 summary，记录：

- 修改前后 commit；
- 实际文件、类、函数和接口；
- 命令和测试状态；
- legacy 回归；
- Unicode/UTF-8 验证；
- Windows/GPU 待办；
- 风险和下一 Ticket 可依赖接口。

重要阶段结束时新建时间戳 handoff，并更新 `.handoff/current.md`；历史 handoff 不删除。
