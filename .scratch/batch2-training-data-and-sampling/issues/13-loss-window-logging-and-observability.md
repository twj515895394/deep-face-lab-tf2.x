# 13 — 恢复训练日志区间平均 Loss，并保留单步诊断与可观测性

Status: done-macos-lightweight-pending-windows  
Type: AFK + Windows GPU  
Blocked by: `12-compatibility-docs-and-handoff.md`  
GitHub Issue: `#3`

**构建内容：** 修复当前 `mainscripts/Trainer.py` 在保存时只显示最后一个 iteration loss、导致控制台 loss 看起来反复跳动的问题；恢复旧版 DeepFaceLab 更适合观察长期趋势的“保存区间平均 loss”主显示，同时保留 last/median/count 等诊断信息。该 Ticket 只修复日志统计和可观测性，不修改 SAEHD Loss、optimizer、学习率、采样策略、模型权重或 checkpoint 格式。

---

## 1. 问题背景

Batch 1 Windows FP32 + AdaBelief 测试中观察到保存日志：

```text
[07:22:44][#128515][1091ms][0.3937][0.3001]
[07:37:25][#129227][1235ms][0.3809][0.2930]
[07:52:06][#129951][1196ms][0.4175][0.3217]
[08:07:08][#130695][1154ms][0.4431][0.2810]
[08:22:11][#131439][1116ms][0.3870][0.3259]
```

这些值会随 batch 样本难度、随机 warp、翻转、颜色增强和 SRC/DST 独立采样上下变化。当前日志容易让用户误判为：

- 模型训练发散；
- TF2.x Loss 不稳定；
- AdaBelief 异常；
- Batch 1 finite gate 或训练正确性失效。

实际上，上述日志当前展示的是最后一个 batch 的 loss，不是保存区间趋势。

---

## 2. 已确认的源码根因

当前 `mainscripts/Trainer.py` 保存日志分支使用：

```python
latest_loss = loss_history[-1]
```

并将该值赋给名为 `mean_loss` 的局部变量。变量名称与真实统计语义不一致。

当前行为等价于：

```text
保存发生
→ 读取最后一个 iteration 的 loss
→ 作为保存日志中的 SRC/DST loss 输出
```

旧版常见语义更接近：

```text
上一次保存后新增的 loss_history 区间
→ 计算 mean
→ 作为保存日志主值输出
```

因此本 Ticket 的主要问题是**日志统计口径回归与命名误导**，不是直接证明训练数值路径有问题。

---

## 3. Agent 开工前必读

1. `AGENTS.md`
2. `.handoff/current.md`
3. `.scratch/batch2-training-data-and-sampling/spec.md`
4. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
5. `.scratch/batch2-training-data-and-sampling/FINAL_AUDIT_CONTRACTS.md`
6. Ticket 11、12 summary 和 Windows 验收报告
7. `mainscripts/Trainer.py`
8. `models/ModelBase.py`：
   - `train_one_iter()`
   - `get_loss_history()`
   - `save()`
   - loss history 裁剪逻辑
   - iter 递增语义
9. Batch 1 finite gate / skipped-step 相关实现和测试
10. 旧版 TF1.x Trainer loss 统计实现，作为语义参考，不允许直接无审计复制

开工前必须记录：

```text
branch
HEAD commit
Trainer 当前保存触发路径
自动保存路径
手动保存路径
首次保存路径
loss_history 的 shape / dtype / append 时机
iter 与 loss_history 长度的当前关系
history 裁剪规则
finite-step skipped update 的记录语义
```

---

## 4. Ticket 目标

### 4.1 主目标

保存日志中的主 SRC/DST loss 改为：

```text
自上一个统计窗口起点之后新增 loss_history 的 arithmetic mean
```

### 4.2 辅助目标

同时保留：

- `last`：窗口最后一个 iteration loss；
- `median`：窗口中位数；
- `count`：窗口包含的 loss 记录数；
- 可选 `min/max`：详细诊断或结构化日志使用。

控制台默认保持紧凑，不能每次保存打印大段统计。

### 4.3 非目标

本 Ticket 不负责：

- 修改 SAEHD loss 公式；
- 修改 optimizer；
- 修改学习率；
- 修改 gradient clipping；
- 修改 finite gate；
- 修改 sample generator；
- 修改 Batch 2 weighted sampling；
- 为了让 loss 更平滑而修改训练数据；
- 重新定义 loss history 文件格式；
- 开发 TensorBoard 或完整可视化平台；
- 判断最终换脸视觉质量。

---

## 5. 核心设计原则

### 5.1 不使用全局 model iter 作为 loss_history 数组索引

禁止直接实现：

```python
window = loss_history[save_iter:iter]
```

原因：

- 模型可能从已有 checkpoint 恢复；
- loss history 可能被裁剪或降采样；
- iter 与 history 长度未来可能因 skipped-step 语义不同；
- 保存恢复后旧 session 历史仍在数组中；
- 直接按 iter 切片可能得到空窗口或错误窗口。

固定使用独立 history index：

```python
loss_window_start_index = len(model.get_loss_history())
```

窗口读取：

```python
history = model.get_loss_history()
window = history[loss_window_start_index:]
```

窗口成功消费后：

```python
loss_window_start_index = len(history)
```

### 5.2 Session 边界

Trainer 新进程启动时：

```text
loss_window_start_index = 当前已加载 history 长度
```

因此恢复模型后第一次保存只统计本次启动后新增 loss，不混入旧 session 历史。

### 5.3 保存失败不得推进窗口

只有模型保存成功后，才能推进：

```text
loss_window_start_index
```

若 `model.save()` 抛异常：

- 核心保存错误继续抛出；
- 当前窗口不得丢弃；
- 不输出伪造的“保存成功平均 loss”；
- 下一次成功保存可继续统计未消费窗口。

### 5.4 统计不改变训练状态

统计代码只能读取 loss history，不得：

- 修改 history 内容；
- 重排 history；
- 对 history 原地转换 dtype；
- 修改 iter；
- 触发额外 train step；
- 影响 save payload。

---

## 6. 推荐数据对象

建议建立纯函数和轻量数据对象，避免将统计逻辑继续散落在 Trainer 主循环。

```python
from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

@dataclass(frozen=True)
class LossWindowStats:
    count: int
    mean: Tuple[float, ...]
    median: Tuple[float, ...]
    last: Tuple[float, ...]
    minimum: Tuple[float, ...]
    maximum: Tuple[float, ...]
```

推荐纯函数：

```python
def compute_loss_window_stats(
    history,
    start_index: int,
) -> Optional[LossWindowStats]:
    ...
```

约束：

- 不导入 TensorFlow；
- 输入只读；
- 空窗口返回 `None`；
- 不返回伪造 0；
- 所有输出必须 finite；
- 维度不一致时抛出明确错误，不能静默截断；
- 支持 NumPy scalar 和普通 Python float；
- 输出转为普通 Python float，便于日志和测试。

是否将纯函数放在 `mainscripts/Trainer.py` 或单独小模块，由源码结构审计决定；禁止为一个小功能创建过度复杂的日志框架。

---

## 7. 输入契约

合法 history 示例：

```python
[
    [0.40, 0.30],
    [0.38, 0.29],
    [0.42, 0.32],
]
```

要求：

- 每条记录 loss 项数量一致；
- 每项可转换为 float；
- 所有项 finite；
- `start_index` 为整数；
- `0 <= start_index <= len(history)`。

非法输入：

```text
start_index < 0
start_index > len(history)
记录维度不一致
NaN / Inf
非数值 loss
history 结构损坏
```

处理原则：

- 统计层错误不得伪装成训练 loss；
- 默认应明确告警并保留 last 可用诊断，或直接阻止错误保存日志；
- 不允许 `except Exception: pass` 后输出 `[0.0000]`；
- 最终行为需测试冻结。

---

## 8. 输出与日志格式

### 8.1 默认兼容格式

为了保持现有用户脚本和阅读习惯，保存日志主行仍保留：

```text
[time][#iter][iter_time][src_mean][dst_mean]
```

示例：

```text
[07:37:25][#129227][1235ms][0.3864][0.2941]
```

方括号中的 loss 明确表示窗口 mean。

### 8.2 诊断附加行

建议在保存日志后追加一条紧凑信息：

```text
[LossWindow] count=712 src_last=0.3809 dst_last=0.2930 src_median=0.3847 dst_median=0.2918
```

如果担心默认日志过多，可以：

- 始终输出 `count` 与 `last`；或
- 通过现有 verbose/debug 机制输出 median/min/max。

但主 mean 和窗口 count 必须可追溯。

### 8.3 禁止歧义

禁止：

```text
变量叫 mean_loss，实际存 latest_loss
```

代码变量和日志标签必须准确：

```text
window_mean
window_median
window_last
window_count
```

### 8.4 空窗口

空窗口可能出现在：

- 启动后尚未完成训练就触发保存；
- 连续保存；
- 已达到 target iter；
- preview-only 状态；
- 某些异常或 skipped-step 流程。

空窗口时：

```text
不得输出 0.0000 假 loss
不得读取 history[-1] 导致 IndexError
不得推进窗口到错误位置
```

推荐输出：

```text
[LossWindow] no new loss records since previous successful save
```

如果 history 非空，可另外显示 `last_known`，但必须明确标记不是本窗口 mean。

---

## 9. 保存时序设计

推荐流程：

```text
训练产生新 loss
→ loss_history append
→ 达到保存条件
→ 记录当前 window_end_index
→ model.save()
→ save 成功
→ 对 [start_index:window_end_index] 统计
→ 输出 mean/last/count
→ start_index = window_end_index
```

为何固定 `window_end_index`：

- 防止保存过程中未来出现异步 append；
- 明确统计窗口边界；
- 保证日志和成功保存时刻对应。

若当前 Trainer 保证同线程同步运行，仍建议保留显式 end index，减少未来维护歧义。

### 9.1 手动保存与自动保存

两条路径必须复用同一个窗口消费函数，不允许：

- 自动保存显示 mean；
- 手动保存仍显示 last；
- 首次保存走另一套 0.0 fallback。

### 9.2 首次 iteration 自动保存

当前 Trainer 可能在第一个 iteration 后触发一次保存。必须确认：

- 窗口 count 正确；
- count=1 时 mean=median=last；
- 不重复消费该记录；
- 下一窗口从新索引开始。

### 9.3 保存失败

固定：

```text
save failed
→ start_index 不变
→ 不打印成功窗口统计
→ 错误继续传播/记录
```

---

## 10. History 裁剪与降采样

`ModelBase.train_one_iter()` 当前可能在 history 过大时进行裁剪或降采样。该行为可能改变：

```text
len(loss_history)
已保存 start_index 对应的位置
```

因此开工前必须验证当前裁剪是在 append 后如何执行。

要求至少选择一种安全策略并冻结测试：

### 方案 A：窗口独立缓冲（推荐优先评估）

Trainer 维护仅包含当前 session 未消费 loss 的轻量 buffer：

```python
pending_loss_window.append(current_loss)
```

保存成功后清空。

优点：

- 不受历史裁剪影响；
- session 语义清晰。

风险：

- Trainer 当前只能通过 `get_loss_history()` 读取，可能需要最小接口；
- 不得重复存储无限历史，窗口保存后必须清空。

### 方案 B：索引重定位

如果坚持使用 history index，必须在 history 缩减时安全重定位 start index，并有明确接口通知 Trainer。

禁止通过猜测：

```python
start_index = min(start_index, len(history))
```

这种写法可能静默丢失窗口数据。

最终实现由源码审计决定，但必须覆盖超过裁剪阈值的 synthetic 测试。

---

## 11. Finite Gate 与 skipped-step 语义

Batch 1 曾发现 non-finite / skipped update 与 iter/loss history 语义风险。本 Ticket 不修改该机制，但必须确认统计口径。

验收需要区分：

```text
optimizer step applied
optimizer step skipped
loss record appended
iter incremented
```

要求：

- 统计窗口只对实际存在的 loss records 计算；
- `count` 表示 loss record 数，不声称等于 optimizer applied steps；
- 如果 history 中存在 skipped-step 标记或无效占位，必须按 Batch 1 最终语义处理；
- NaN/Inf 不得进入统计结果；
- 若发现 Batch 1 仍会追加伪造 0 loss，应标记 blocked，并关联正确性修复，不在本 Ticket 静默过滤掩盖。

---

## 12. 建议施工顺序

### Step 1：冻结当前行为

新增测试证明当前实现：

```text
保存时输出最后一条 loss，而不是窗口 mean
```

测试应先失败于期望的新行为。

### Step 2：提取纯统计函数

覆盖：

- count=1；
- 多条二维 loss；
- 三个及以上 loss 项；
- empty；
- invalid start；
- NaN/Inf；
- 维度不一致。

### Step 3：建立窗口生命周期

覆盖：

- 新 session 起点；
- 保存成功推进；
- 保存失败不推进；
- 连续保存空窗口；
- 首次 iteration 保存。

### Step 4：统一手动/自动保存路径

只保留一套日志统计入口。

### Step 5：处理 history 裁剪

通过 synthetic 大 history 测试验证窗口不丢失、不重复。

### Step 6：回归控制台格式

确保旧日志解析器若只读取前五段，仍可继续工作；新增诊断信息不得破坏主行。

### Step 7：Windows FP32 实测

在真实训练中验证窗口 mean 比 last 更平滑，同时 last 仍能反映 batch 波动。

### Step 8：生成 summary 和用户说明

明确：

```text
平滑的是日志统计口径，不是修改训练数值使 loss 人为平滑
```

---

## 13. 自动测试设计

建议新增：

```text
tests/smoke/test_trainer_loss_window.py
```

至少包含：

### 13.1 纯函数

- [ ] 两项 loss mean/median/last/min/max 正确；
- [ ] count=1 时所有统计相等；
- [ ] 空窗口返回 None；
- [ ] start=history len 返回 None；
- [ ] 非法负 start 抛错；
- [ ] start 越界抛错；
- [ ] 不同维度抛错；
- [ ] NaN/Inf 拒绝；
- [ ] 输入 history 不被修改；
- [ ] 输出为 Python float。

Golden case：

```python
history = [
    [0.40, 0.30],
    [0.38, 0.28],
    [0.44, 0.32],
]
```

期望：

```text
count = 3
mean = [0.4066666667, 0.30]
median = [0.40, 0.30]
last = [0.44, 0.32]
min = [0.38, 0.28]
max = [0.44, 0.32]
```

浮点容差建议 `1e-7`。

### 13.2 生命周期

- [ ] 加载已有 history 后 start=len(history)；
- [ ] 新增 3 条后只统计新 3 条；
- [ ] 成功保存后窗口推进；
- [ ] 失败保存后窗口保留；
- [ ] 连续保存不输出伪造值；
- [ ] 重启后不混入旧 session；
- [ ] 第一次训练 count=1；
- [ ] history 裁剪后无重复/遗漏。

### 13.3 日志

- [ ] 主行 loss 为 mean；
- [ ] 主行仍保持 `[time][#iter][time][src][dst]`；
- [ ] 诊断包含 count 和 last；
- [ ] 空窗口文案明确；
- [ ] 不出现误导变量/标签；
- [ ] Unicode 控制台环境不乱码。

### 13.4 回归

- [ ] Trainer 正常启动；
- [ ] 自动保存；
- [ ] 手动保存；
- [ ] save error 传播；
- [ ] target iter reached；
- [ ] debug 模式；
- [ ] no-preview；
- [ ] `--options-json` 启动不受影响；
- [ ] Batch 2 四种 sampling mode 不改变统计逻辑。

推荐命令：

```bash
python -m compileall mainscripts/Trainer.py tests/smoke/test_trainer_loss_window.py
python -m unittest tests.smoke.test_trainer_loss_window
python -m unittest discover -s tests/smoke -p "test_batch1_*.py"
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

---

## 14. Windows GPU 验收

环境：

```text
Windows
RTX PRO 5000 Blackwell 48GB
FP32
AdaBelief
固定 checkpoint
固定 src/dst faceset
固定 batch / resolution / workers
```

### W1 恢复训练

- [ ] 加载已有 100k+ iter 模型；
- [ ] 启动后第一次保存不统计旧 history；
- [ ] count 与本 session 实际新增记录一致；
- [ ] iter 连续；
- [ ] save/resume 正常。

### W2 自动保存窗口

至少观察 3 个自动保存窗口：

- [ ] 每个窗口 count > 0；
- [ ] mean、median、last 均 finite；
- [ ] mean 与离线重算一致；
- [ ] last 与窗口最后记录一致；
- [ ] 窗口不重叠、不遗漏。

### W3 手动保存

- [ ] 手动保存使用相同统计语义；
- [ ] 手动保存后下一自动保存从新窗口开始；
- [ ] 连续手动保存空窗口不输出 0 loss。

### W4 波动展示

对至少 3 个窗口记录：

```text
src mean / median / last
src std（离线可算）
dst mean / median / last
dst std
count
```

要求：

- mean 通常比 last 的跨窗口噪声更低；
- 不要求每个窗口 mean 单调下降；
- 不把“平滑”定义为强制单调；
- 若训练真实发散，mean 仍应忠实显示上升。

### W5 保存失败注入

通过测试替身或可控方式模拟 save failure：

- [ ] 错误不被吞；
- [ ] 窗口不推进；
- [ ] 恢复后下一次成功保存包含之前未消费记录。

### W6 性能

统计逻辑开销要求：

```text
保存时统计耗时 < 100 ms，或 < 保存总耗时的 1%
训练 iteration 热路径新增开销不可测或 <= 0.5%
```

如果采用 pending buffer，每 iteration 只允许 O(loss_dim) 追加，不允许扫描历史。

---

## 15. 验收标准

### 功能正确性

- [ ] 保存日志主 SRC/DST 值是窗口 arithmetic mean；
- [ ] last 值单独标记并可追溯；
- [ ] count 准确；
- [ ] mean 与离线 NumPy 重算在 `1e-7` 容差内；
- [ ] 不要求 mean 单调下降；
- [ ] 真实异常趋势不会被平滑机制隐藏。

### 生命周期

- [ ] 新 session 不混入旧 history；
- [ ] 成功保存才消费窗口；
- [ ] 保存失败不消费；
- [ ] 手动/自动保存统一；
- [ ] 空窗口不输出 0.0；
- [ ] 首次 iteration 保存正确；
- [ ] history 裁剪不导致遗漏或重复。

### 兼容性

- [ ] 不修改 loss 公式；
- [ ] 不修改 optimizer/学习率；
- [ ] 不修改 model iter；
- [ ] 不修改 checkpoint/data.dat 格式；
- [ ] 不修改 preview loss history 数据；
- [ ] 不修改 Batch 2 sampling probability；
- [ ] 不影响 `--options-json`；
- [ ] 旧主日志前五段格式保持兼容。

### 可观测性

- [ ] 变量命名不再把 latest 叫 mean；
- [ ] mean/last/count 语义在文档中明确；
- [ ] Windows 报告包含至少 3 个窗口；
- [ ] 用户文档说明单 batch 波动正常；
- [ ] summary 明确此次修复只改变展示口径。

---

## 16. 阻断条件

任一命中不得标记 resolved：

- 为获得平滑日志修改训练 loss 或 optimizer；
- 直接用全局 iter 切 history，未处理恢复/裁剪；
- 保存失败仍推进窗口；
- 空窗口输出 `[0.0000]`；
- last 继续以 mean 名义展示；
- mean 与离线计算不一致；
- history 被原地修改；
- save/resume 后窗口混入旧 session；
- 只通过纯函数测试，没有真实 Trainer 路径测试；
- Windows 只启动未观察多个保存窗口；
- 将“更平滑”错误写成“必须单调下降”。

---

## 17. 禁止捷径与常见错误

- 不要用固定最近 N 条替代“自上次成功保存以来”的窗口，除非另行设计并记录。
- 不要用 EMA 代替 arithmetic mean；EMA 可作为未来显示选项，但不是本 Ticket 主口径。
- 不要为了兼容旧格式只显示 last。
- 不要假设 `iter == len(loss_history)`。
- 不要在 save 前推进 start index。
- 不要在异常时清空 pending buffer。
- 不要将 NaN/Inf 静默转为 0。
- 不要因 Batch 2 weighted sampling 增加波动就改变统计公式。
- 不要在本 Ticket 顺手增加 TensorBoard、大型 CSV 系统或 UI 图表。

---

## 18. 文档与交接更新

完成时至少更新：

- [ ] 本 Ticket 状态；
- [ ] `.scratch/batch2-training-data-and-sampling/spec.md`；
- [ ] `.handoff/current.md`；
- [ ] Batch 2 最终 handoff；
- [ ] 用户训练日志说明；
- [ ] Windows 验收报告；
- [ ] 如新增 `--options-json` 参数，必须同步权威参数文档；默认方案不新增参数则标 NA。

建议不新增训练参数。若确有必要增加日志模式参数，必须单独说明默认值、兼容性和持久化影响。

---

## 19. 完成总结报告

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/13-loss-window-logging-and-observability-summary.md
```

必须包含：

1. 根因与源码位置；
2. 修改前后日志示例；
3. 窗口生命周期图；
4. mean/median/last/count 接口；
5. history 裁剪处理方案；
6. 保存失败处理；
7. 自动测试命令和结果；
8. Windows 三个以上窗口的原始数据；
9. 离线重算对照；
10. 性能开销；
11. 未完成项与风险；
12. 明确说明训练数值路径未修改。

最终审计合规表：

```markdown
## 最终审计契约合规

| 项目 | 状态 | 证据 |
|---|---|---|
| Loss 窗口 mean | PASS/FAIL | 测试与日志 |
| last/count 可追溯 | PASS/FAIL | 日志 |
| save/resume session 边界 | PASS/PENDING | 测试/Windows |
| history 裁剪 | PASS/FAIL | synthetic 测试 |
| save failure 不消费窗口 | PASS/FAIL | 测试 |
| legacy 日志兼容 | PASS/FAIL | parser/格式测试 |
| --options-json 文档同步 | NA/PASS | 默认不新增参数 |
| Windows GPU | PASS/PENDING | 报告 |
| 性能门槛 | PASS/PENDING | 数据 |
```

---

## 20. 执行顺序说明

默认依赖：

```text
Ticket 12
↓
Ticket 13
↓
Batch 2 最终收口
```

理由：

- 不打断正在进行的 Batch 2 核心 Metadata/Sampling 开发；
- 在最终收口前修复日志可观测性；
- Ticket 13 可复用 Ticket 11 Windows 环境与数据；
- 修复后应补跑至少 W1 legacy_random 与一个 weighted mode，证明采样模式只影响 loss 分布，不影响统计语义。

若 Ticket 11 验收过程中日志口径严重妨碍判断，可提前实现 Ticket 13，但仍必须：

- 独立提交；
- 独立 summary；
- 不与 Ticket 09/10 大改混合；
- 完成自身自动测试和 Windows 证据。

---

## Comments

- 2026-07-29：根据 Batch 1 Windows FP32 实测发现，当前 Trainer 保存日志展示最后一个 iteration loss，造成相比旧版 TF1.x 明显跳动；新增独立 Ticket 13，在 Batch 2 末尾修复统计口径和可观测性。