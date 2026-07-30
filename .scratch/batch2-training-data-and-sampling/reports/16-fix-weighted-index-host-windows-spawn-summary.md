# Ticket 16 — WeightedIndexHost Windows Spawn / 生命周期 实施总结

> 当前状态：**IMPLEMENTATION COMPLETE / AWAITING WAVE-1 CENTRAL REVIEW**  
> 实现者自审：`PASS`（不得自行签发 APPROVED/PASS/CLOSED）  
> Independent Review：`PENDING`  
> Base Commit：`0bb1fa094c3ddf0304eaf6cfcb9b11aac2eff400`  
> 工作分支：`codex/batch2-ticket16-windows-spawn`  
> 环境：Windows 10.0.19045 / Python 3.11.7 / start method `spawn` / CPU 16  
> `--options-json` 文档同步：**NA**（本 Ticket 未改训练配置字段）

---

## 1. 修复前复现

脚本：

```text
.scratch/batch2-training-data-and-sampling/scripts/ticket16_spawn_repro_before.py
```

修复前（旧 `WeightedIndexHostClient` 持有 `_host_ref`，Host `__getstate__` 返回 `{}`）：

```text
PRE: _host_ref WeightedIndexHost
start_method spawn
exitcode 0
child result ('err', {
  'host_ref_is_none': False,
  'host_type': 'WeightedIndexHost',
  'attrs': [],
  'has_fatal': False
}, 'AttributeError',
"'WeightedIndexHost' object has no attribute '_fatal_error'", ...)
```

根因：

1. spawn pickle 后 Host 变成空壳对象；
2. Client.multi_get 仍访问 `self._host_ref._fatal_error`；
3. Generator worker 在子进程崩溃/卡死，fallback 无法接管。

修复后同一脚本：

```text
PRE: _host_ref WeightedIndexHost
start_method spawn
exitcode 0
child result ('ok', {
  'host_ref_is_none': True,
  'host_type': None,
  ...
}, [1, 0, 0, 1])
```

---

## 2. Pickle contract

```text
WeightedIndexHost.__getstate__  -> {}   # Host 禁止跨进程
WeightedIndexHostClient.__getstate__:
  state = __dict__.copy()
  state["_host_ref"] = None
  return state
```

子进程中 `_host_ref is None` 为正常状态。

Client 跨进程只依赖：

```text
sq / cq  (multiprocessing.Queue)
_closed_event / _fatal_event  (multiprocessing.Event)
cq_id / timeouts / request_id
```

---

## 3. IPC protocol

请求：

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

- 单 Client 串行请求；
- 响应按 `request_id` 匹配，丢弃 stale response；
- **禁止** `Queue.empty()` 作为同步；统一 `queue.get(timeout=...)`。

---

## 4. 生命周期

```text
Main process:
  Host starts host_thread
  create_cli() before worker start  (monotonic client id, dedicated cq)
  SubprocessGenerator workers hold Client only

close():
  1. _closing = True
  2. sq.put(("stop",))
  3. thread.join(timeout)
  4. _closed + closed_event
  5. close queues best-effort
  6. idempotent

fatal:
  full traceback to stderr + _fatal_traceback
  fatal_event set
  ERROR response to current request if possible
  host loop exits

SampleGeneratorFace:
  self.index_host / self.ct_index_host retained
  finalize(): terminate workers -> host.close()
  __del__ only as safety net

ModelBase.finalize:
  prefer gen.finalize() for sample_generators / generator_list
```

---

## 5. 修改文件 / 函数

| 文件 | 变更 |
|---|---|
| `samplelib/sampling/weighted_index_host.py` | Host/Client 重写：Events、request_id、timeout 可配、close/fatal、spawn-safe getstate |
| `samplelib/SampleGeneratorFace.py` | 保存 index host；`finalize()` / 幂等；`__del__` 安全网 |
| `models/ModelBase.py` | `finalize()` 优先调用 generator.finalize |
| `tests/smoke/test_batch2_weighted_index_host.py` | close/fatal/timeout/stale/N&lt;batch/getstate |
| `tests/smoke/test_batch2_weighted_index_host_spawn.py` | **新增** spawn child / multi-child / close-while-spawned |
| `tests/smoke/test_batch2_generator_sampling_spawn.py` | **新增** debug=False Ordinary/Packed/Legacy |
| `tests/smoke/test_batch2_generator_sampling.py` | 补 finalize 防止残留 Host 线程 |
| `.scratch/.../scripts/ticket16_spawn_repro_before.py` | 修复前/后复现脚本 |

未改：

- 采样概率算法 / SAEHD 网络 / SubprocessGenerator 主体（无需改）

---

## 6. 测试证据

命令：

```text
set PYTHONPATH=.
python -m compileall samplelib/sampling samplelib/SampleGeneratorFace.py core/joblib models/ModelBase.py
python -m unittest ^
  tests.smoke.test_batch2_weighted_cycle ^
  tests.smoke.test_batch2_weighted_index_host ^
  tests.smoke.test_batch2_weighted_index_host_spawn ^
  tests.smoke.test_batch2_generator_sampling_spawn ^
  tests.smoke.test_batch2_generator_sampling
```

结果：

```text
compileall: exit 0
Ran 26 tests in ~5.9s
OK
process EXIT=0
```

覆盖点：

| 项 | 状态 |
|---|---|
| Client getstate `_host_ref=None` | PASS |
| spawn child draw | PASS |
| multi child 4-way | PASS |
| request_id 去 stale | PASS |
| close/fatal/timeout | PASS |
| N&lt;batch / count=0 / count&lt;0 | PASS |
| debug=False Ordinary PoseBalanced | PASS |
| debug=False Packed PoseBalanced | PASS |
| legacy Generator regression | PASS |
| Host thread join after finalize | PASS |

---

## 7. Windows 状态

本机即为 Windows + `spawn`：

```text
Python 3.11.7
multiprocessing start method: spawn
CPU count: 16
branch: codex/batch2-ticket16-windows-spawn
mode: unit/smoke only
```

| 验收项 | 状态 |
|---|---|
| Host spawn smoke | PASS |
| Ordinary Generator debug=False | PASS |
| Packed Generator debug=False | PASS |
| SAEHD FP32 + AdaBelief 500 iter | **PENDING** |
| save / exit / resume 200 iter | **PENDING** |
| 训练退出无残留 worker 人工确认 | **PENDING**（unit 级已 terminate+join） |
| GPU acceptance 文档实跑 | **PENDING** |

因此 Ticket 级状态只能写：

```text
IMPLEMENTATION COMPLETE
WINDOWS-SPAWN-UNIT-PASS
PENDING-WINDOWS-SAEHD-GPU-TRAINING
AWAITING-WAVE1-CENTRAL-REVIEW
```

**不得**写 `resolved` / `APPROVED` / `PASS` / `CLOSED`。

---

## 8. 残留风险

1. **全量 Batch 2 suite 进程退出码**（历史 `-1073740791`）未在本 Ticket 全量复跑确认是否已消失；需 Wave 1 集成后 `discover -s tests/smoke -p "test_batch*.py"`。
2. **SAEHD 真训练路径**未跑；SubprocessGenerator + ModelBase.finalize 联调待 GPU 验收。
3. mplib.IndexHost 仍使用 `Queue.empty()` 与无 close；legacy 路径不在本 Ticket 范围。
4. close 后 Queue handle 已关闭，**不能**再把 Client pickle 进新进程（符合生命周期；已有 spawn-before-close 测试）。
5. 实现者不得自签 Final Review。

---

## 9. Reviewer 检查清单

- [ ] pickle contract 与 spawn child 证据
- [ ] 无 `Queue.empty()` 同步
- [ ] request_id stale 拒绝
- [ ] close 幂等 / fatal traceback / 可配置 timeout
- [ ] SampleGeneratorFace 持有 host 且 finalize 关闭
- [ ] debug=False Ordinary + Packed
- [ ] 未把采样算法/网络改坏
- [ ] 未错误签发 PASS/CLOSED
- [ ] 明确 PENDING SAEHD GPU 训练

---

## 10. 下一依赖

- Wave 1 并行：Ticket 17 / 19 可同时进行
- Wave 1 集成：`codex/batch2-wave1-integration`
- Ticket 20：`BLOCKED-BY-16+17`（等 16 实现 SHA 固定后可 provisional）
