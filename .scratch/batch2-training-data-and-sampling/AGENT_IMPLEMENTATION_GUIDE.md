# Batch 2 弱模型 / 辅助 Agent 施工执行规范

> 适用范围：`.scratch/batch2-training-data-and-sampling/issues/01-12`  
> 目标：让能力偏弱、上下文窗口较小或容易过度发挥的编码模型，也能按明确边界完成高质量实现。  
> 优先级：本文件约束低于正式详细设计，高于 Agent 自行推测。若 Ticket、详细设计和源码事实冲突，必须停止并在 summary 中记录，不能自行扩大范围。

---

## 1. 每个 Ticket 开工前必须阅读

按以下顺序读取，不允许只读当前 Ticket：

1. `.handoff/current.md`
2. `.scratch/batch2-training-data-and-sampling/spec.md`
3. `docs/development/batch2-training-data-and-sampling-tasks.md`
4. 本文件
5. 当前 Ticket
6. 当前 Ticket 的 `Blocked by` 对应 summary 报告
7. Ticket 中“必读源码”列出的生产代码和测试代码

如果前置 Ticket 没有 summary、状态不是 resolved，或实际接口和当前 Ticket 假设不一致：

```text
停止编码
→ 在当前 Ticket Comments 或 summary 草稿中记录阻断
→ 不自行重写前置模块
```

---

## 2. 固定施工流程

每个 Ticket 必须严格按下面顺序执行。

### Step A：源码事实复核

先记录：

- 当前 branch 和 commit；
- 将修改的文件；
- 现有类、函数、参数和返回值；
- 调用方与被调用方；
- 当前测试入口；
- 与 Ticket 假设不一致的地方。

禁止仅根据设计文档猜测源码。

### Step B：先补失败测试或基线证据

根据 Ticket 类型选择：

- 正确性功能：先写会失败的单元测试；
- 兼容改造：先记录旧路径基线；
- 新模块：先创建最小导入、构造和边界测试；
- 多进程改造：先验证单线程，再验证多 CLI / spawn；
- 文档任务：先核对代码默认值和真实命令。

### Step C：只建立最小接口

先创建 Ticket 明确要求的：

- 文件；
- 类；
- 函数签名；
- 数据对象；
- Enum / 状态；
- 最小安全默认值。

接口测试通过后，再填充算法。不要一次写完整大文件后再调试。

### Step D：按小步骤填充实现

推荐顺序：

```text
输入校验
→ 正常路径
→ 边界条件
→ fallback / error
→ 日志和统计
→ 性能与内存检查
```

每完成一小步就运行对应测试。

### Step E：回归旧行为

凡是改动已有文件，必须验证：

- 新功能关闭时旧分支仍执行；
- 参数缺失时旧行为不变；
- 输出数量、顺序、shape、dtype 不变；
- 异常没有被新 fallback 吞掉；
- 不生成额外必需文件；
- 不修改模型、optimizer、DFM、Merge 格式。

### Step F：生成 summary

必须按 Ticket 指定路径生成 summary，不能只在提交信息里写“done”。

---

## 3. 通用编码约束

### 3.1 Python 与依赖

- 最低 Python 3.9。
- 不使用 3.10+ 才有的语法，除非已有项目已使用并有兼容处理。
- 不新增大型依赖。
- 优先使用项目现有 NumPy、OpenCV、Pathlib、dataclass/Enum 和 unittest 风格。
- Metadata、Sampling 模块不得导入 TensorFlow。

### 3.2 范围控制

禁止：

- 顺手重构无关文件；
- 修改 SAEHD 网络或 Loss；
- 修改 optimizer；
- 修改 `faceset.pak` 格式；
- 自动删除、移动、重命名 aligned 图片；
- 引入动态 Loss sampler；
- 引入脸型 Loss、Shape Template 或 Shape-aware Merge；
- 为“代码更漂亮”改变 legacy 随机语义。

### 3.3 错误与 fallback

可选增强错误和核心训练错误必须分开。

允许 fallback：

- Metadata 文件缺失；
- Metadata JSON 损坏；
- schema 不支持；
- 匹配率不足；
- 静态权重非法；
- optional stats/logging 失败。

不得 fallback 掩盖：

- faceset 没有训练数据；
- SampleProcessor 错误；
- TensorFlow 错误；
- 模型加载/保存错误；
- 用户路径参数错误；
- 多进程 worker 持续崩溃。

### 3.4 数值安全

所有外部或配置数值必须：

```text
parse
→ finite check
→ range clip / reject
→ explicit fallback reason
```

禁止把 NaN / Inf 写入 JSON、概率或权重数组。

### 3.5 多进程安全

- Windows 使用 spawn；入口必须受 `if __name__ == "__main__"` 或现有 main 入口保护。
- 不在 worker 中重复读取大 JSON。
- 不把不可 pickle 对象传给 subprocess。
- queue 请求必须有明确响应，不能出现永久等待。
- 小 faceset、异常 worker 和进程退出都必须有测试。

### 3.6 确定性

- 新采样逻辑使用独立 `np.random.RandomState(seed)`。
- 不污染 NumPy 全局随机状态。
- 同输入、同配置、同 seed 的纯函数和 Host 测试必须可复现。
- legacy 未指定 seed 时不得强制改变历史行为。

---

## 4. 接口设计要求

所有新增公共对象至少需要：

- 类型明确的构造参数；
- 安全默认值；
- `validate()` 或等价校验；
- `to_dict()` / `from_mapping()`（配置或 Schema 对象）；
- 结构化状态或 reason，而不是只返回 `None`；
- 单元测试覆盖正常、缺失、错误类型和边界值。

不要使用裸 dict 在多个模块间传递复杂状态。优先定义轻量 dataclass、NamedTuple 或明确类。

---

## 5. 测试执行要求

每个 Ticket 至少执行：

```bash
python -m compileall <本 ticket 修改的 Python 文件或目录>
python -m unittest <本 ticket 对应测试模块>
```

若仓库已有 Batch 1/2 smoke runner，应同时执行相关 runner。

测试必须区分：

- PASS：实际执行并通过；
- SKIP：依赖缺失且有明确原因；
- PENDING：只能在 Windows GPU 执行；
- FAIL：实际失败，不能包装成 warning 后声称完成。

禁止使用大范围 `except Exception: pass` 让测试假成功。

---

## 6. 每个 Ticket 的提交原则

- 一个 Ticket 建议一个主提交或少量逻辑清晰的提交。
- 高风险 Ticket 不与其他 Ticket 混合提交。
- 不提交真实人脸、模型权重、用户绝对路径或大体积临时文件。
- 测试 fixture 必须 synthetic 或可重复生成。
- 提交前检查 `git diff --stat` 和 `git diff`，确认没有无关修改。

推荐提交信息：

```text
feat(batch2): ...
fix(batch2): ...
test(batch2): ...
docs(batch2): ...
```

---

## 7. Summary 固定模板

每个 summary 至少包含：

```markdown
# Ticket XX 完成总结

## 1. 状态
- resolved / blocked / pending-windows

## 2. 基线
- branch
- commit before
- commit after
- Python / OS

## 3. 实际修改
- 文件
- 类 / 函数
- 接口变化

## 4. 关键实现决策
- 正常路径
- fallback
- 兼容策略

## 5. 测试
- 命令
- PASS / SKIP / PENDING / FAIL
- 关键输出

## 6. 旧行为回归
- 新功能关闭
- legacy 输出契约
- 普通 / Packed

## 7. 未完成与风险
- Windows / GPU 项
- 性能项
- 已知限制

## 8. 下一 Ticket 使用说明
- 可依赖接口
- 不可依赖的内部实现
```

---

## 8. 必须停止并上报的情况

出现以下任一情况不得自行扩大方案：

- 详细设计要求的现有函数不存在或语义不同；
- 前置 Ticket 接口缺失；
- 必须修改 SAEHD Loss 才能完成当前 Ticket；
- 必须修改 `faceset.pak` 格式；
- ordinary 与 packed 无法使用同一 sample identity；
- 为通过测试必须吞掉核心错误；
- Windows spawn 无法复现或无法安全退出；
- legacy 行为无法在测试中保持。

正确行为是记录 `blocked`、证据和最小建议，不是擅自重构全项目。

---

## 9. 完成定义

一个 Ticket 只有同时满足以下条件才算 resolved：

```text
源码事实复核完成
+
实现严格在范围内
+
对应测试实际通过
+
旧行为回归有证据
+
summary 已生成
+
Windows/GPU 未执行项明确标记
```

只写代码、只通过导入、只生成文档、只在 macOS 运行，均不能替代 Ticket 明确要求的完整证据。