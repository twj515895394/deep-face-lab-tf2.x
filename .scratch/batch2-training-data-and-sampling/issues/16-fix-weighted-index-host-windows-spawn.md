# Ticket 16 — 修复 WeightedIndexHost Windows Spawn、多进程生命周期与真实 Generator 链路

> 状态：OPEN / P0 BLOCKER / HIGH RISK  
> 优先级：最高  
> Blocked by：Ticket 14  
> Blocks：20、21  
> 平台要求：macOS/Linux 可做 spawn 模拟；最终必须 Windows 实机  
> 强制 Reviewer：是，施工 Agent 不得自审后直接 resolved

---

## 1. 问题背景

`WeightedIndexHostClient` 当前持有 `_host_ref`。`WeightedIndexHost.__getstate__()` 返回空字典。Windows 使用 spawn 时，Client 随 `SubprocessGenerator` 参数被 pickle，引用的 Host 可能反序列化成缺少 `_fatal_error`、`_closed` 等字段的空对象。

子进程进入：

```python
if self._host_ref and self._host_ref._fatal_error:
```

可能出现：

- `AttributeError`；
- worker 提前退出；
- 主进程等待预取数据；
- Client 30 秒超时；
- 训练看似卡死；
- fallback 无法介入，因为错误发生在 Generator 子进程。

现有测试全部绕过真实路径：

- `debug=True` 使用 `ThisThreadGenerator`；
- Host Client 只在创建 Host 的主进程调用；
- 没有 `multiprocessing.get_context("spawn")`；
- 没有 `debug=False` Generator 测试。

---

## 2. 开工前必读

1. `AGENTS.md`
2. Ticket 14 summary
3. `samplelib/sampling/weighted_index_host.py`
4. `samplelib/SampleGeneratorFace.py`
5. `core/joblib/SubprocessGenerator.py`
6. `core/mplib/*IndexHost*`
7. `models/Model_SAEHD/Model.py` Generator 创建部分
8. `tests/smoke/test_batch2_weighted_index_host.py`
9. `tests/smoke/test_batch2_generator_sampling.py`
10. `tests/smoke/test_batch2_weighted_cycle.py`
11. Windows GPU acceptance 文档

开工前必须实际写一个最小 spawn 复现脚本，记录修复前结果。

---

## 3. 固定并发契约

### 3.1 Host 所有权

- Host 只存在于训练主进程；
- Host thread 只在训练主进程运行；
- worker 只持有 Client；
- Client 不得要求访问 Host Python 对象；
- Client 可持有 multiprocessing Queue/Event 等可 pickle IPC 句柄。

### 3.2 Client pickle

必须实现明确：

```python
def __getstate__(self):
    state = self.__dict__.copy()
    state["_host_ref"] = None
    return state
```

或完全删除 `_host_ref` 的跨进程作用。

子进程中：

```text
_host_ref is None
```

必须是正常状态，不得触发 AttributeError。

### 3.3 状态传播

推荐共享：

```text
closed_event: multiprocessing.Event
fatal_event: multiprocessing.Event
```

Host：

- 正常 close 设置 closed；
- 未处理 fatal 设置 fatal，并尽力向请求方返回 ERROR；
- fatal 后不再接受 draw；
- close/fatal 都使等待 Client 在有限时间内退出。

Client：

- 发请求前检查 event；
- 使用 `cq.get(timeout=...)`；
- timeout 后再次检查 closed/fatal；
- fatal 抛 RuntimeError；
- closed 抛 RuntimeError；
- 单纯响应超时抛 TimeoutError。

### 3.4 禁止使用 `Queue.empty()` 作为同步判断

`multiprocessing.Queue.empty()` 在多进程下不可靠。必须改成：

```python
try:
    message = queue.get(timeout=...)
except queue.Empty:
    ...
```

Host thread 可使用短 timeout 或阻塞 get，并由 stop command 唤醒。

---

## 4. 请求协议

请求建议包含唯一 request ID：

```text
("draw", client_id, request_id, count)
("stats", client_id, request_id)
("stop",)
```

响应：

```text
("OK", request_id, payload)
("ERROR", request_id, error_type, error_message)
```

原因：同一 Client 若未来出现并发、超时残留响应或 stats/draw 交错，必须能拒绝错误 request 的旧响应。

本 Ticket 可保持单请求串行，但 request ID 必须测试或明确记录为何暂不需要。不得让 stale response 被下一次调用误接收。

---

## 5. 生命周期

### 5.1 create_cli

- 必须在 worker start 前创建；
- client ID 单调且不可复用；
- 每个 worker 使用独立 response queue；
- Host close 后禁止创建新 Client。

### 5.2 close

正确顺序：

1. 设置 closing 状态；
2. 发送 stop；
3. 唤醒 Host thread；
4. join 有限超时；
5. 如果 thread 未退出，记录 error；
6. 设置 closed event；
7. 关闭 Queue 资源；
8. close 幂等。

不得在 stop 被消费前就让 Host loop 因 `_closed=True` 直接跳出并遗留请求。

### 5.3 fatal

Host 对单个 draw 的异常：

- 尽量向该 Client 返回 ERROR；
- 设置 fatal event；
- 记录完整 traceback 到主进程日志；
- 不仅保存 `str(e)`；
- 不吞掉后继续生成错误 index。

### 5.4 Generator finalize

`SampleGeneratorFace` 应保存 index host 引用，以便 finalize/close。当前只保存局部 `index_host` 时，可能无法显式关闭 Host。

需要检查并修复：

- Generator 对 Host 的所有权；
- ModelBase.finalize 是否遍历正确属性；
- worker terminate 前 Host 是否仍可响应；
- 正常退出与异常退出顺序。

不得只依赖 Python `__del__`。

---

## 6. N 与 batch 边界

必须覆盖：

- N=1, batch=1；
- N=1, batch>1；
- N<batch；
- N=batch；
- N>batch；
- count=0；
- count<0；
- 极端概率；
- cycle 边界跨越；
- 重复 retry 达上限。

允许 N<batch 返回重复 index，但：

- 数量必须等于 count；
- 每个 index 合法；
- 不死循环；
- stats 记录 accepted duplicate。

---

## 7. 允许修改文件

```text
samplelib/sampling/weighted_index_host.py
samplelib/SampleGeneratorFace.py
core/joblib/SubprocessGenerator.py（只允许必要的错误传播/生命周期修复）
models/ModelBase.py::finalize（只允许资源关闭）
相关 tests
Windows acceptance 文档
```

---

## 8. 禁止范围

- 不改采样概率算法；
- 不改 SAEHD 网络；
- 不用 Manager 大对象共享概率数组；
- 不把 Metadata JSON 复制到每个 worker；
- 不取消 timeout；
- 不用无限 sleep polling；
- 不捕获 worker 错误后返回随机 legacy index；
- 不把 debug=True 当多进程验收；
- 不因为 macOS fork 通过就声明 Windows PASS；
- 不依赖 daemon 进程自动清理作为完成证据。

---

## 9. 自动测试要求

### 9.1 Client pickle unit

```python
payload = pickle.dumps(client)
restored = pickle.loads(payload)
assert restored._host_ref is None
```

Queue/Event 必须仍可用。

### 9.2 Spawn child test

必须使用顶层可 pickle 函数：

```python
def child_draw(client, out_queue):
    out_queue.put(client.multi_get(...))
```

并：

```python
ctx = multiprocessing.get_context("spawn")
```

断言：

- child exitcode=0；
- 返回 index 数量正确；
- Host stats 增加；
- 无 AttributeError。

### 9.3 多 child

至少 2—4 个 spawn child 并发请求，断言：

- 每个收到自己的响应；
- 总 draws 正确；
- 无响应串线；
- 无永久等待。

### 9.4 close/fatal

- close 后 Client 快速失败；
- close 幂等；
- Host 内注入异常后 Client 收到 RuntimeError；
- Host thread 已退出；
- Queue 不遗留阻塞。

### 9.5 timeout

使用可配置短 timeout 的测试配置，不能真的等待 30 秒。生产默认可以保持 30 秒。

### 9.6 Generator `debug=False`

真实创建 `SubprocessGenerator`：

- 使用小型 Ordinary Fixture；
- 使用 PoseBalancedPolicy；
- `debug=False`；
- generators_count 至少 2；
- 获取多个 batch；
- shape/dtype 正确；
- finalize 后子进程退出；
- Host thread 退出。

Packed 也必须覆盖至少一次。

---

## 10. Windows 实机验收

Windows 上必须记录：

```text
Python version
multiprocessing start method
CPU count
GPU
branch
commit
mode
workers
batch size
```

测试：

1. 仅 Host spawn smoke；
2. Ordinary Generator debug=False；
3. Packed Generator debug=False；
4. SAEHD FP32 + AdaBelief 至少运行 500 iter；
5. 手动 save；
6. 退出；
7. resume 再运行 200 iter；
8. 关闭时确认无残留 Python worker；
9. 检查无 30 秒 timeout；
10. 检查无静默 fallback。

Windows 未执行时状态只能：

```text
PASS-SPAWN-SIMULATION / PENDING-WINDOWS
```

不能写 resolved。

---

## 11. 测试命令

```bash
./.venv/bin/python -m compileall samplelib/sampling samplelib/SampleGeneratorFace.py core/joblib
./.venv/bin/python -m unittest tests.smoke.test_batch2_weighted_cycle
./.venv/bin/python -m unittest tests.smoke.test_batch2_weighted_index_host
./.venv/bin/python -m unittest tests.smoke.test_batch2_weighted_index_host_spawn
./.venv/bin/python -m unittest tests.smoke.test_batch2_generator_sampling_spawn
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

---

## 12. 验收标准

### macOS/Linux spawn simulation

- [ ] Client pickle 后 `_host_ref=None`；
- [ ] spawn child draw PASS；
- [ ] 多 child PASS；
- [ ] request 不串线；
- [ ] close/fatal/timeout PASS；
- [ ] N<batch PASS；
- [ ] debug=False Ordinary PASS；
- [ ] debug=False Packed PASS；
- [ ] 所有进程和 thread 被回收；
- [ ] legacy Generator 回归 PASS。

### Windows

- [ ] 真实 spawn PASS；
- [ ] SAEHD 训练 PASS；
- [ ] save/exit/resume PASS；
- [ ] 无残留 worker；
- [ ] 无死锁；
- [ ] 无静默异常。

### 失败条件

以下任一出现即 FAIL：

- child exitcode 非 0；
- 只能 debug=True 通过；
- 依赖 fork；
- 超时后继续训练；
- worker 崩溃被 fallback；
- close 后残留线程/进程；
- 通过删除 timeout 解决问题。

---

## 13. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
16-fix-weighted-index-host-windows-spawn-summary.md
```

必须包含：

- 修复前复现；
- pickle contract；
- IPC protocol；
- 生命周期图；
- 修改文件和函数；
- spawn 测试输出；
- debug=False Generator 输出；
- Ordinary/Packed 状态；
- Windows 状态；
- 残留资源检查；
- Reviewer 结论。