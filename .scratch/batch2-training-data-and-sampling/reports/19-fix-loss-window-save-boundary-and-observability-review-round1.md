# Ticket 19 — Loss Window 保存边界、失败语义与可观测性独立 Review Round 1

> Review 状态：**REQUEST_CHANGES / TRACKER-SOUND / TRAINER-CONTROL-FLOW-NOT-CLOSED**  
> Review 日期：2026-07-30  
> Base：`c342cc56ad2fbe6402c8b0b3c64c73eaab3cbb55`  
> 被审实现：`3f7c4cb7e907021bb0ef8f5c2f1eb544fa1e1032`  
> 集成分支：`codex/batch2-ticket19-loss-window`  
> Review 方法：独立静态源码、测试源码、Ticket 与实现侧测试记录复核。Reviewer 未在本环境重新运行 Trainer/GPU 测试；GitHub 无 Actions/status check。

---

## 1. 结论

```text
REQUEST_CHANGES
LOSS WINDOW TRACKER: SOUND
SAVE FREEZE / COMMIT SEMANTICS: SOUND IN HELPER
ACTUAL TRAINER INITIAL SAVE: BROKEN
TARGET / EXIT NO-EXTRA-BATCH CONTRACT: BROKEN
SAVE FAILURE ESCAPES HELPER BUT IS SWALLOWED BY TRAINER THREAD
OBSERVABILITY FIELDS: INCOMPLETE
TESTS DO NOT EXECUTE REAL TRAINER CONTROL FLOW
TICKET 19: NOT PASS / NOT CLOSED
```

`LossWindowTracker` 和纯函数设计是本轮的有效改进：窗口独立于会被压缩的全局 history；保存前 freeze；只有 `model.save()` 返回后才 commit；空窗口不复用旧 loss。

但 Ticket 19 的核心是 Trainer 保存时序。现有测试只复制了一个 helper，没有执行真实 `trainerThread` 控制流，因此遗漏了首次保存、目标迭代、退出和异常传播问题。

---

## 2. 已确认关闭

### 2.1 窗口数据结构

- session-local buffer，resume 时为空；
- 每个成功训练迭代追加最近 loss；
- freeze 返回快照；
- save 成功后 commit；
- save 失败时 helper 内不会 commit；
- history 压缩不会改变 tracker；
- pure function 支持半开区间、empty、finite 和维度一致性。

### 2.2 立即统计

`model_save()` 在 `model.save()` 返回后立即计算并打印，不再等待下一次 `train_one_iter()`，因此旧版“保存后的 batch 混入前一 checkpoint 窗口”问题在 helper 层已经修正。

这些部分不得在返修中回退。

---

## 3. 阻断项

## T19-R1-01 — `initial_iter` 保存分支在真实 Trainer 中不可达

**等级：P0 / CONTROL-FLOW BLOCKER**

真实循环每轮先执行：

```text
3 次 CUDA graph warmup train_one_iter
+
1 次 timed train_one_iter
```

然后才检查：

```python
if model.get_iter() == 1:
    model_save(reason="initial_iter")
```

从 iter=0 启动时，第一次检查已经至少是 iter=4，因此 `initial_iter` 永远不会触发。Summary 和测试声称 first save count=1，但测试只直接调用 fake helper，没有运行上述循环。

必须明确首次保存语义并实现真实控制流，例如：

- 每次 `train_one_iter()` 后立即检查 target/first-save；或
- warmup 只在图捕获阶段使用，但不能绕过 iter=1 save；或
- 先完成第一条 loss 的保存，再继续后续 warmup。

必须增加真实 `trainerThread` harness，断言从 iter=0 启动后第一次 save 的 reason=`initial_iter`、window=1，且后续窗口不重复该 loss。

## T19-R1-02 — Target iteration 可被 warmup 批量越过

**等级：P0 / CHECKPOINT BOUNDARY**

目标判断只发生在 3+1 次训练之后。如果当前 iter 接近 target，例如 target=2，从 iter=0 可直接训练到 4 才保存，违反：

```text
当前目标迭代 loss 进入保存
不额外训练下一 batch
```

每一次 `train_one_iter()` 后都必须检查是否达到 target，并立即 freeze/save/stop；不得在目标达到后继续执行剩余 warmup/timed batch。

新增测试至少覆盖：

```text
target=1
target=2
resume iter=target-1
warmup_iters > remaining_iters
```

断言最终 iter 精确等于 target，窗口只包含实际进入该 checkpoint 的 loss。

## T19-R1-03 — 已排队的退出命令仍会先训练额外 batch

**等级：P0 / EXIT SEMANTICS**

Trainer 只在完成当轮训练和自动保存判断后才读取 `s2c`。如果 close 已在队列中，仍会先训练最多 4 个 batch，然后才执行 exit save。

Ticket 明确要求：用户退出后不训练额外 batch。必须在进入训练块前处理高优先级控制命令，或至少检查 close/save pending，再决定是否训练。

真实 harness 应在开始一轮前预放 `close`，断言：

```text
train_one_iter calls = 0
save reason = exit
window 按已有 buffer 保存
```

还应覆盖训练过程中到达的 close，冻结可定义的最近安全边界，但不能无条件再跑完整 warmup 组。

## T19-R1-04 — `model.save()` 异常最终仍被 Trainer 外层吞掉

**等级：P0 / FAILURE SEMANTICS**

`model_save()` 本身没有捕获 save 异常，这是正确的；但异常会进入 `trainerThread` 最外层：

```python
except Exception as e:
    print(...)
    traceback.print_exc()
    model.finalize()
...
c2s.put({'op': 'close'})
```

异常没有继续传播给调用者，也没有结构化发送 fatal/error；UI 只收到普通 close。Ticket 要求原异常不得吞掉，特别是退出保存失败不能被 finalize 掩盖。

必须建立明确失败通道：

- 测试/非 GUI 调用可以重新抛出；或
- 向主线程发送 `{'op':'error', ...}` 并保留 traceback/cause；
- 不得把 save failure 等同于正常 close；
- loss window 在失败后仍未消费（在模型被终止前可观察/重试）。

必须测试 manual、scheduled、target、exit save failure 的一致语义。

## T19-R1-05 — 日志缺少 Ticket 要求的起止边界

**等级：P1 / OBSERVABILITY CONTRACT**

当前日志只有：

```text
reason / iter / window count / stats
```

没有 start/end iter 或 history/session window indices。Ticket 明确要求至少记录 start/end iter 或 indices，以便离线核对 checkpoint 窗口。

Tracker 应维护 session sequence/iter 边界，或 append 时同时存 iter。日志示例：

```text
[Save][scheduled] iter=12000 window=1000 range=11001..12000
```

恢复会话要明确 session start，空窗口也应显示边界。

## T19-R1-06 — `_record_train_loss()` broad except 会静默丢窗口数据

**等级：P1 / SILENT OBSERVABILITY LOSS**

当前任何 tracker/history 读取异常都被 `except Exception: pass` 吞掉。窗口统计虽然不能破坏核心训练，但完全静默会导致保存成功却少统计 batch。

应至少：

- 捕获预期类型；
- 记录 bounded warning；
- 标记 tracker degraded；
- 保存日志明确 `window_incomplete`；
- 不得继续输出看似完整的窗口统计。

## T19-R1-07 — FakeModel 测试镜像 helper，不是 Trainer integration

**等级：P0 / TEST FALSE-CONFIDENCE**

`test_batch2_trainer_save_window.py` 自己定义 `_model_save_helper()`，它复制理想语义，却没有调用 `trainerThread` 的嵌套 `model_save`、warmup、queue、target、preview 或 outer exception。

因此以下声称的覆盖并不成立：

```text
initial iter real path
target no extra batch
exit no extra batch
preview only after successful save
save error propagation through trainer
```

必须将保存控制抽取为可直接测试的模块级 state/controller，或构造真实 `trainerThread` harness 注入 FakeModel 和 queues。测试不得再只验证复制的 helper。

## T19-R1-08 — 完整回归证据缺失

**等级：P1 / ACCEPTANCE EVIDENCE**

实现侧只记录 Ticket19 focused 20 tests，以及 Wave focused 82 tests。Ticket 要求完整 `test_batch*.py` discover 与 shell exit code；当前没有。

---

## 4. 额外控制流问题

### 4.1 `is_reached_goal` 被闭包捕获

`model_save()` 读取外层 `is_reached_goal`。在 target 分支中调用 save 时它仍为 false，之后才设 true；这次可保存。但达到目标后的 manual/exit save 会直接 no-op。是否允许目标后再保存空窗/退出 checkpoint 必须冻结并测试，不能仅以“与旧逻辑一致”略过。

### 4.2 `save_iter` 已无实际作用

变量仍初始化但不再参与窗口范围，应删除或用于真实边界日志，避免误导。

---

## 5. 测试证据判断

已有：

```text
Ticket 19 focused: Ran 20 / OK / EXIT=0
Wave focused: Ran 82 / OK / EXIT=0
```

这些只证明 tracker/pure helper，不能证明真实 Trainer 保存时序。GitHub 无 CI status，不能宣称 CI PASS。

---

## 6. 最小返修范围

```text
mainscripts/Trainer.py
samplelib/sampling/loss_stats.py（仅 tracker 边界/状态）
tests/smoke/test_batch2_trainer_save_window.py
tests/smoke/test_batch2_loss_window_logging.py
Ticket 19 summary / current.md
```

不得修改 Loss 公式、optimizer、checkpoint 格式、采样概率或 preview history 数据结构。

建议将 Trainer 保存状态机抽成模块级小对象/函数，避免继续测试嵌套闭包的复制品。

---

## 7. Final PASS 条件

- [ ] iter=0 真实路径触发 initial save，window=1；
- [ ] target 精确停止，不因 warmup 越过；
- [ ] close pending 不训练额外 batch；
- [ ] manual/scheduled/target/exit save failure 有结构化错误且不伪装正常 close；
- [ ] save failure 不消费窗口；
- [ ] preview 只在成功保存后发送；
- [ ] 日志包含 reason、count、start/end range、mean/median/last/min/max；
- [ ] tracker degradation 不静默；
- [ ] 测试执行真实 Trainer controller/control flow，而非复制 helper；
- [ ] 完整相关 smoke + shell exit code 0；
- [ ] 独立 Reviewer 复核签发 APPROVED/PASS。

---

## 8. 当前签发

```text
Ticket 19
REQUEST_CHANGES
TRACKER FOUNDATION ACCEPTED
ACTUAL TRAINER SAVE CONTROL FLOW OPEN
```
