# Ticket 16 — WeightedIndexHost Windows Spawn / 生命周期独立 Review Round 1

> Review 状态：**REQUEST_CHANGES / SPAWN-CORE-FIXED / LIFECYCLE-GATE-NOT-CLOSED**  
> Review 日期：2026-07-30  
> Base：`0bb1fa094c3ddf0304eaf6cfcb9b11aac2eff400`  
> 被审实现：`f9f846ab255a97005890a4ed7b6d3740ee4119e8`  
> 集成分支：`codex/batch2-ticket19-loss-window`  
> Review 方法：独立静态源码、测试源码、Ticket 与实现侧测试记录复核。Reviewer 未在本环境重新运行 Windows/GPU 测试；GitHub 无 Actions/status check。

---

## 1. 结论

```text
REQUEST_CHANGES
SPAWN PICKLE CONTRACT: CLOSED
DEDICATED CLIENT QUEUES / REQUEST ID: CLOSED
DEBUG=FALSE ORDINARY/PACKED SMOKE: ESTABLISHED
DETERMINISTIC WORKER REAP: NOT PROVEN
FULL PROCESS EXIT / SAEHD GPU: NOT PROVEN
TICKET 16: NOT PASS / NOT CLOSED
```

本轮确实修复了原始 P0：spawn 后 Client 不再依赖空壳 Host；closed/fatal 使用共享 Event；响应按 request ID 匹配；Host 路径不再使用 `Queue.empty()`；Ordinary/Packed 的 `debug=False` Generator 测试也已建立。

但 Ticket 16 的核心不只是“能 draw”，还要求所有 worker/process/thread 确定性回收、save/exit/resume 和真实 Windows SAEHD 训练。当前实现与测试会掩盖残留 worker，因此不能签发 PASS。

---

## 2. 已确认关闭

### 2.1 Client spawn 契约

- `WeightedIndexHostClient.__getstate__()` 明确把 `_host_ref` 置为 `None`；
- worker 只依赖 Queue/Event；
- spawn child、4-way multi-child、close/fatal/timeout、stale response 均有 focused tests；
- Host 请求队列使用 `get(timeout=...)`，未使用 `Queue.empty()` 作为同步。

### 2.2 Generator 主路径

- `SampleGeneratorFace` 保留 `index_host` / `ct_index_host`；
- 非 debug 路径为每个 SubprocessGenerator 创建独立 Client；
- Ordinary、Packed、legacy regression 均增加 `debug=False` smoke。

这些内容后续返修不得回退。

---

## 3. 阻断项

## T16-R1-01 — `finalize()` 会在 join 超时后丢失仍存活进程的句柄

**等级：P0 / LIFECYCLE BLOCKER**

当前 `SampleGeneratorFace.finalize()`：

```python
if p.is_alive():
    p.terminate()
p.join(timeout=3)
...
g.p = None
```

无论 `join(timeout=3)` 后 `p.is_alive()` 是否仍为 true，都会把 `g.p=None`。

后果：

1. 仍存活 worker 的句柄被丢弃；
2. 无法继续 kill/join；
3. 后续测试和 ModelBase 都无法发现残留进程；
4. 与 Ticket 的“关闭后无残留线程/进程”失败条件直接冲突。

必须改为确定性回收：

```text
terminate
→ join(timeout)
→ 若仍存活则 kill（平台支持时）
→ 再 join(timeout)
→ 若仍存活则抛出/记录硬失败
→ 只有确认退出后才能清空句柄
```

不得用 `except: pass` + `p=None` 将失败伪装成完成。

## T16-R1-02 — 现有 Generator 测试无法证明 worker 已退出

**等级：P0 / TEST FALSE-POSITIVE**

测试在 `gen.finalize()` 后读取：

```python
p = getattr(g, "p", None)
assert p is None or not p.is_alive()
```

而实现已无条件把 `g.p=None`，所以即使 OS worker 仍存活，断言仍通过。

必须在 finalize 前保存原始 `Process` 对象列表，并在 finalize 后对这些原始句柄断言：

```text
exitcode is not None
is_alive() == False
join completed
```

还应检查 `multiprocessing.active_children()` 不新增残留，并覆盖 finalize 幂等。

## T16-R1-03 — SubprocessGenerator IPC Queue 未显式关闭

**等级：P1 / RESOURCE CLEANUP**

`SampleGeneratorFace.finalize()` 只处理 `g.p`，没有显式关闭 `SubprocessGenerator.sc_queue` / `cs_queue`，也没有处理 Queue feeder thread。Ticket 16 的目标包括进程退出、线程回收和历史解释器 finalizing 阶段异常，因此 Queue 资源必须有明确 cleanup contract。

建议给 `SubprocessGenerator` 增加最小 `close()/finalize()`：

```text
terminate/kill/join worker
close sc_queue / cs_queue
必要时 cancel_join_thread 或安全 join_thread
幂等
```

然后由 `SampleGeneratorFace.finalize()` 调用该接口，不再直接操作内部 `p`。

## T16-R1-04 — Host close 超时后仍继续标记 closed 并关闭 Queue

**等级：P1 / FAILURE SEMANTICS**

`WeightedIndexHost.close()` 在 host thread 超过 join timeout 后只打印 stderr，随后仍：

```text
_closed=True
closed_event.set()
close queues
```

这可能形成“线程仍活着但资源已关闭”的状态。至少应：

- 保留 thread alive 事实；
- 返回失败或抛出明确 RuntimeError；
- 不得把 close 结果描述为成功；
- 测试注入不可立即退出的 host loop，验证有限时间失败语义。

## T16-R1-05 — Ticket 明文 Windows 验收仍未完成

**等级：P0 / ACCEPTANCE EVIDENCE**

实现侧记录明确仍缺：

```text
SAEHD FP32 + AdaBelief 500 iter
manual save / exit
resume 200 iter
无残留 worker 人工确认
完整 test_batch*.py discover 的最终 shell exit code
```

Ticket 规定上述 Windows 项未完成时不能 resolved/PASS/CLOSED。

---

## 4. 测试证据判断

已有证据：

```text
Windows / Python 3.11.7 / spawn
focused 26 tests: OK / EXIT=0
Wave 组合 focused 82 tests: OK / EXIT=0
```

这些可以证明 spawn 主链路有实质修复，但不能证明确定性回收，因为 cleanup 断言读取的是已被清空的 `g.p` 字段。

GitHub 当前无 CI status；不得描述为 CI PASS。

---

## 5. 最小返修范围

主要修改：

```text
core/joblib/SubprocessGenerator.py
samplelib/SampleGeneratorFace.py
samplelib/sampling/weighted_index_host.py（仅 close 失败语义）
models/ModelBase.py（仅确保 cleanup failure 不被静默吞掉）
tests/smoke/test_batch2_generator_sampling_spawn.py
tests/smoke/test_batch2_weighted_index_host*.py
Ticket 16 summary / current.md
```

不得修改采样概率、SAEHD 网络、Metadata contract 或 options-json。

---

## 6. Final PASS 条件

- [ ] 原始 Process 句柄在 finalize 后真实 `is_alive()==False`；
- [ ] terminate 超时有 kill/join 或明确硬失败；
- [ ] SubprocessGenerator IPC Queue 显式清理且幂等；
- [ ] Host thread join 超时不再被伪装为成功 close；
- [ ] Ordinary/Packed `debug=False` 与多 worker 回归继续通过；
- [ ] 完整 Batch 2 discover `unittest OK` 且 shell exit code 0；
- [ ] Windows SAEHD 500 iter + save/exit/resume 200 iter；
- [ ] 无残留 Python worker/thread；
- [ ] 独立 Reviewer 复核后签发 APPROVED/PASS。

---

## 7. 当前签发

```text
Ticket 16
REQUEST_CHANGES
SPAWN CORE FIXED
LIFECYCLE AND WINDOWS ACCEPTANCE OPEN
```
