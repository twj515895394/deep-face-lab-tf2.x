# Ticket 20 — 收窄 Metadata Sampling Fallback 异常边界并防止核心错误被吞没

> 状态：OPEN / P1 HIGH / HIGH RISK  
> Blocked by：Ticket 15、Ticket 16、Ticket 17  
> Blocks：21  
> 强制 Reviewer：是  
> 核心原则：Optional Metadata 可以回退，训练核心错误必须失败

---

## 1. 问题背景

当前 `build_sampling_runtime()` 将 `SampleLoader.load()` 与 `FacesetMetadataLoader.load()` 放在同一个广泛 `try/except Exception` 中。当 `fallback_on_optional_error=True` 时，以下核心错误可能被伪装成 Metadata optional fallback：

- Ordinary/Packed faceset 加载失败；
- 训练数据为空；
- 权限或文件系统错误；
- Sample 对象构建异常；
- 内存错误；
- 编程错误；
- worker/IPC 错误。

这违反 AGENTS.md 的兼容和错误传播原则。

---

## 2. 开工前必读

1. `AGENTS.md`
2. Ticket 15 summary
3. Ticket 16 summary
4. Ticket 17 summary
5. `samplelib/sampling/runtime.py`
6. `samplelib/sampling/factory.py`
7. `samplelib/metadata/loader.py`
8. `samplelib/metadata/store.py`
9. `samplelib/SampleLoader.py`
10. `samplelib/SampleGeneratorFace.py`
11. `models/Model_SAEHD/Model.py`
12. Trainer/ModelBase 异常处理
13. 相关 fallback tests

---

## 3. 异常分类契约

### 3.1 可回退的 Optional Metadata 状态

以下应通过结构化状态或受控异常进入 fallback：

```text
METADATA_FILE_NOT_FOUND
INVALID_METADATA_JSON
UNSUPPORTED_METADATA_SCHEMA
DUPLICATE_METADATA_ID
TRUSTED_MATCH_RATIO_TOO_LOW
STALE_SIGNATURE_RATIO_TOO_HIGH
POLICY_REQUIRES_METADATA
OPTIONAL_METADATA_FIELD_INVALID
```

优先返回 `RuntimeMetadata.status/fallback_reason`，不依赖异常实现普通控制流。

### 3.2 必须抛出的核心错误

```text
NO_TRAINING_SAMPLES
SAMPLE_LOADER_FAILURE
PACKED_FACESET_FAILURE
FILESYSTEM_PERMISSION_ERROR
MEMORY_ERROR
WORKER_CRASH
WEIGHTED_INDEX_HOST_FATAL
SAMPLE_PROCESSOR_FAILURE
TENSORFLOW_INIT_FAILURE
TENSORFLOW_TRAIN_FAILURE
OOM
MODEL_SAVE_FAILURE
MODEL_LOAD_FAILURE
PROGRAMMING_ERROR
```

任何核心错误不得因为 `fallback_on_optional_error=True` 而变成 legacy sampling。

### 3.3 配置错误

配置错误分两类：

- 可安全回退的 requested mode / Metadata path 不可用：按 strict 配置处理；
- 非法 path escape、错误 JSON 结构、未知 role 等调用错误：必须明确报错，不能伪装 missing。

---

## 4. 推荐异常类型

可在 Metadata 包定义窄异常：

```python
class MetadataOptionalError(Exception): ...
class MetadataFileMissingError(MetadataOptionalError): ...
class MetadataInvalidError(MetadataOptionalError): ...
class MetadataUnsupportedError(MetadataOptionalError): ...
class MetadataMatchError(MetadataOptionalError): ...
```

但普通 missing/invalid 已有状态时，不必为了异常而异常。

禁止：

```python
except Exception:
    fallback
```

允许：

```python
except MetadataOptionalError as e:
    if fallback_enabled:
        ...
    else:
        raise
```

`MemoryError`、`KeyboardInterrupt`、`SystemExit` 永远不得捕获为 optional。

---

## 5. Runtime 分段

建议流程：

### Phase A：核心 Sample 加载

```python
samples = SampleLoader.load(...)
if not samples:
    raise ValueError("No training data provided")
```

不在 Metadata optional try 中。

### Phase B：Metadata 读取与验证

```python
runtime_metadata = FacesetMetadataLoader.load(...)
```

Loader 以状态返回预期 optional 问题。只有 Metadata 专属 I/O/解析异常可转换为 optional status。

### Phase C：Policy resolve

Factory 对 Metadata 不可用返回明确 fallback resolution。Policy constructor 的未预期异常必须抛出。

### Phase D：Index host 创建

不在 Runtime optional fallback 中。Host 权重、IPC 或 worker 错误属于核心运行时错误。

---

## 6. strict 与 fallback 配置

建议决策矩阵：

| fallback_on_optional_error | strict_validation | Optional Metadata 问题 | 结果 |
|---:|---:|---|---|
| true | false | missing/invalid/mismatch | fallback + warning |
| true | true | missing/invalid/mismatch | raise validation error |
| false | false | missing/invalid/mismatch | raise |
| false | true | missing/invalid/mismatch | raise |

核心错误无论配置为何都 raise。

当前 `strict_validation` 若未真正接入，本 Ticket 必须接入并同步权威文档。

---

## 7. SRC/DST 隔离

允许：

```text
SRC Metadata invalid → SRC fallback
DST Metadata valid → DST 继续 requested mode
```

不允许：

```text
SRC SampleLoader core failure → SRC fallback + DST 继续训练
```

训练任一侧核心数据失败必须阻止模型初始化。

每侧日志必须包含：

- role；
- requested/effective；
- optional status；
- fallback reason；
- strict/fallback flags；
- 不能只打印 exception string。

---

## 8. Loader 内部边界

`FacesetMetadataLoader.load()` 允许处理：

- Metadata 文件不存在；
- JSON parse；
- Schema；
- record validation；
- trusted match；
- stale；
- duplicate。

不应处理：

- 重新加载全部训练 samples；
- SampleProcessor；
- Host 创建；
- TensorFlow；
- 模型保存。

Loader 收到的 samples 应由 Runtime 核心阶段提供，避免重复 SampleLoader 并扩大异常范围。

---

## 9. Factory 边界

`SamplingPolicyFactory.resolve()` 可处理：

- Gate off；
- legacy modes；
- Metadata unavailable；
- requested mode 注册；
- configured fallback mode。

不应捕获：

- Policy constructor bug；
- array length mismatch；
- NaN probabilities；
- Host creation error；
- programmer typo。

这些必须在构建/验证阶段失败。

---

## 10. 允许修改文件

```text
samplelib/sampling/runtime.py
samplelib/sampling/factory.py
samplelib/metadata/loader.py
samplelib/metadata/store.py（仅异常类型）
core/enhancements/config.py（strict 配置）
models/Model_SAEHD/Model.py（初始化传播）
相关 tests
权威 options-json 文档
使用文档
```

---

## 11. 禁止范围

- 不用 broad except 修复测试；
- 不把核心错误改成 warning；
- 不自动删除坏样本；
- 不在 worker 崩溃后切 legacy 继续；
- 不吞 OOM；
- 不吞 save/load；
- 不修改网络或 Loss；
- 不让 strict 名义存在但无效果；
- 不把错误 path escape 当 missing；
- 不让一侧 optional 问题污染另一侧。

---

## 12. 必须新增测试

### Optional 状态

- Metadata missing；
- invalid JSON；
- unsupported schema；
- partial trusted match；
- low trusted match；
- duplicate；
- stale；
- fallback true/false；
- strict true/false。

### 核心异常注入

Mock `SampleLoader.load` 分别抛：

- ValueError；
- PermissionError；
- MemoryError；
- RuntimeError；
- custom packed failure。

全部必须传播，不能返回 fallback Runtime。

### Policy/Host

- Policy array mismatch；
- NaN weight；
- Host fatal；
- worker fatal；
- timeout。

全部核心失败。

### SRC/DST

- SRC optional、DST valid；
- DST optional、SRC valid；
- SRC core failure；
- DST core failure；
- 两侧 optional；
- 两侧 strict。

### Integration

SAEHD 初始化时：

- optional fallback 可启动；
- core failure 不进入 Generator；
- 日志正确；
- 旧 legacy Gate off 不加载 Metadata。

---

## 13. 测试命令

```bash
./.venv/bin/python -m compileall samplelib/sampling samplelib/metadata core/enhancements models/Model_SAEHD
./.venv/bin/python -m unittest tests.smoke.test_batch2_sampling_fallback
./.venv/bin/python -m unittest tests.smoke.test_batch2_fallback_exception_boundaries
./.venv/bin/python -m unittest tests.smoke.test_batch2_saehd_sampling_options
./.venv/bin/python -m unittest tests.smoke.test_batch2_weighted_index_host_spawn
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

---

## 14. 验收标准

- [ ] SampleLoader 在 optional try 外；
- [ ] expected Metadata 问题使用状态/窄异常；
- [ ] 无 broad `except Exception -> fallback`；
- [ ] MemoryError/OOM/core errors 传播；
- [ ] strict_validation 真正生效；
- [ ] fallback_on_optional_error 真正生效；
- [ ] SRC/DST optional 隔离；
- [ ] 任一侧 core failure 阻止初始化；
- [ ] Host/worker fatal 不 fallback；
- [ ] 日志结构化；
- [ ] 权威配置文档同步；
- [ ] 全量回归通过。

Reviewer 必须全文搜索新增和修改文件中的：

```text
except Exception
except:
```

每处都要说明为何安全。未说明不得 resolved。

---

## 15. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
20-narrow-fallback-exception-boundaries-summary.md
```

必须记录：

- 异常分类表；
- strict/fallback 矩阵；
- broad except 审计；
- 核心异常注入结果；
- SRC/DST 隔离；
- Host/worker 传播；
- 文档同步；
- 全量测试；
- Reviewer 结论。