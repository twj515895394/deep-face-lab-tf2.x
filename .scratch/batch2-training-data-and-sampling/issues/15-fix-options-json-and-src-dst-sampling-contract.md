# Ticket 15 — 修复 `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约

> 状态：OPEN / P0 BLOCKER  
> 优先级：最高  
> Blocked by：Ticket 14  
> Blocks：20、21  
> 可否并行：可与 Ticket 16、17 并行，但不得由同一弱模型同时施工  
> 强制文档同步：是

---

## 1. 问题背景

当前使用指南给出的配置层级错误，真实 SAEHD 只读取顶层：

```text
options["enhancements"]
```

智能采样还要求两个 Gate 同时为 true：

```text
enhancements.training.enabled
enhancements.training.metadata_sampling
```

此外，文档宣称支持：

```text
enhancements.sampling.src
enhancements.sampling.dst
```

但代码只解析一份扁平 `enhancements.sampling`，SRC 和 DST 共用同一 `SamplingConfig`。

本 Ticket 必须建立稳定、向后兼容、可测试的配置契约，并禁止错误层级配置静默失效。

---

## 2. 开工前必读

1. `AGENTS.md`
2. `docs/implementation/options-json-training-configuration-reference.md`
3. `.scratch/batch2-training-data-and-sampling/reports/batch2-independent-code-review-and-remediation-plan.md`
4. Ticket 14 summary
5. `models/ModelBase.py::load_train_step_config`
6. `models/Model_SAEHD/Model.py::on_initialize_options`
7. `models/Model_SAEHD/Model.py::on_initialize`
8. `core/enhancements/config.py`
9. `samplelib/sampling/config.py`
10. `samplelib/sampling/runtime.py`
11. `samplelib/sampling/factory.py`
12. `main.py::process_train`
13. 相关 tests

开工前必须画出真实调用链，禁止只按旧文档改代码。

---

## 3. 固定配置形状

### 3.1 顶层

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {},
    "runtime": {}
  }
}
```

`training`、`sampling` 或 `runtime` 出现在 `enhancements` 外时，不属于受支持配置。

### 3.2 兼容扁平 Sampling

旧扁平形状继续支持，并同时应用于 SRC/DST：

```json
{
  "enhancements": {
    "sampling": {
      "mode": "pose_balanced",
      "uniform_mix": 0.1
    }
  }
}
```

### 3.3 正式 side-specific Sampling

```json
{
  "enhancements": {
    "sampling": {
      "src": {
        "mode": "quality_pose_balanced"
      },
      "dst": {
        "mode": "pose_balanced"
      }
    }
  }
}
```

### 3.4 Base + override

允许 base 字段与 side-specific 同时存在：

```json
{
  "enhancements": {
    "sampling": {
      "fallback_mode": "legacy_random",
      "uniform_mix": 0.1,
      "min_metadata_match_ratio": 0.9,
      "src": {
        "mode": "quality_pose_balanced",
        "quality_strength": 0.7
      },
      "dst": {
        "mode": "pose_balanced"
      }
    }
  }
}
```

解析优先级：

```text
SamplingConfig 默认值
→ sampling 扁平 base
→ sampling.<role> override
```

### 3.5 缺失侧

- 只有 `src` 时，DST 使用 base；
- 没有 base 时，DST 使用默认 `legacy`；
- 不允许 SRC 配置自动复制为 DST；
- 不允许因为一侧 Metadata 错误改变另一侧 requested mode。

---

## 4. 建议 API

`EnhancementConfig` 至少提供：

```python
def sampling_config_for(self, role: str) -> SamplingConfig:
    ...
```

role 只允许：

```text
src
dst
```

未知 role 必须抛 `ValueError`，不得默认当 dst。

保留：

```python
@property
def sampling_config(self) -> SamplingConfig:
```

仅用于旧调用兼容，语义明确为 base/global config。新运行时必须调用 `sampling_config_for(role)`。

---

## 5. 双 Gate 契约

只有：

```text
training.enabled == true
AND
training.metadata_sampling == true
```

才允许加载 Metadata。

决策表：

| enabled | metadata_sampling | Loader | Policy |
|---:|---:|---|---|
| false | false | 不加载 | legacy |
| false | true | 不加载，并记录 gate warning | legacy |
| true | false | 不加载 | legacy |
| true | true | 按 side config 加载 | requested/fallback |

错误配置：

```json
{"training":{"metadata_sampling":true}}
```

如果位于 enhancements 外，必须在启动日志中明确输出：

```text
Unsupported top-level Batch 2 config keys detected: training, sampling.
Expected under "enhancements".
```

不得静默忽略。

---

## 6. Metadata Path 解析

`metadata_path=null`：

```text
<src faceset>/faceset_metadata.v1.json
<dst faceset>/faceset_metadata.v1.json
```

相对路径：

- 相对各自 faceset 根目录解析；
- 支持中文、空格、Unicode；
- 规范化后不得逃逸出 faceset 根目录；
- `../` 逃逸必须拒绝并触发配置错误，不得 fallback 为 missing；
- 绝对路径允许，但必须显式记录 resolved path；
- 日志不得批量泄露样本文件清单。

推荐独立纯函数：

```python
resolve_metadata_path(samples_path, configured_path)
```

---

## 7. SamplingConfig 校验

必须覆盖：

- mode 枚举；
- fallback mode 仅允许 legacy modes；
- finite float；
- min/max weight 顺序；
- uniform mix 0..1；
- strength 0..1；
- match ratio 0..1；
- seed int/None；
- log interval 最小值；
- 未知字段 warning；
- `src`/`dst` mapping 类型。

错误 side mapping：

```json
"src": "pose_balanced"
```

必须产生明确 validation warning/error，不能当空配置继续。

---

## 8. SAEHD 接线

`Model_SAEHD.on_initialize()` 必须分别：

```python
src_cfg = enhancements.sampling_config_for("src")
dst_cfg = enhancements.sampling_config_for("dst")
```

并传给各自 Runtime。

不得在 `build_sampling_runtime()` 内部再次读取同一全局 config 后猜 role。

建议修改签名：

```python
build_sampling_runtime(
    role,
    samples_path,
    enhancement_config,
    sampling_config=None,
    ...
)
```

或由 runtime 内调用 `sampling_config_for(role)`，但只能有一个权威入口。

SRC/DST seed：

- 显式 side seed 优先；
- side seed 为 None 时从 base model seed 派生；
- SRC/DST offset 不同；
- 不污染全局 RNG。

---

## 9. 启动日志

每侧至少输出：

```text
[Sampling][src]
  gates: training.enabled=true, metadata_sampling=true
  requested: quality_pose_balanced
  effective: quality_pose_balanced
  config source: base+src_override
  metadata path: ...
  metadata status: loaded
  trusted match: 1000/1000 (100.0%)
  fallback: none
```

Gate 关闭时：

```text
[Sampling][src]
  gates: disabled
  requested: legacy
  effective: legacy_random
  metadata: not loaded
```

日志必须能证明实际使用的 side config，不得只输出 policy class。

---

## 10. 允许修改文件

```text
core/enhancements/config.py
samplelib/sampling/config.py
samplelib/sampling/runtime.py
samplelib/sampling/factory.py
models/Model_SAEHD/Model.py
models/ModelBase.py（仅错误顶层 Batch 2 key 警告）
docs/implementation/options-json-training-configuration-reference.md
docs/usage/faceset-analyzer-complete-guide.md
相关 tests
```

---

## 11. 禁止范围

- 不修改网络、Loss、optimizer；
- 不新增 JSON 文件参数；
- 不改变 `--options-json` 当前字符串语义；
- 不自动迁移并重写用户 JSON 文件；
- 不因为配置错误吞掉 ModelBase 初始化异常；
- 不让 side-specific config 破坏旧 flat config；
- 不让非空 JSON 再进入交互覆盖；
- 不顺手实现 GUI。

---

## 12. 必须新增测试

### 12.1 配置解析矩阵

- 无 enhancements；
- 空 enhancements；
- 双 Gate 4 组合；
- flat config 同时应用两侧；
- src/dst 独立；
- base + override；
- 缺失一侧；
- invalid side type；
- invalid mode；
- unknown field；
- unsupported schema；
- finite validation；
- min/max reversal；
- Unicode metadata path；
- `..` path escape。

### 12.2 Runtime

- SRC requested quality、DST requested pose；
- SRC loaded、DST missing 时仅 DST fallback；
- SRC invalid config 不改变 DST；
- Gate off 不调用 SampleLoader；
- flat legacy compatibility；
- seeds 独立。

### 12.3 ModelBase/SAEHD

- 正确嵌套注入；
- 错误顶层 key 明确 warning；
- non-empty options JSON 不被交互覆盖；
- 现有模型持久化 roundtrip；
- `--force-model-name` 文档一致；
- model summary 显示最终 enhancements。

---

## 13. 测试命令

```bash
./.venv/bin/python -m compileall core/enhancements samplelib/sampling models/Model_SAEHD
./.venv/bin/python -m unittest tests.smoke.test_batch2_sampling_config
./.venv/bin/python -m unittest tests.smoke.test_batch2_saehd_sampling_options
./.venv/bin/python -m unittest tests.smoke.test_batch2_sampling_fallback
./.venv/bin/python -m unittest tests.smoke.test_options_json_training
./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"
```

如测试文件名不同，应在 summary 记录真实命令。

---

## 14. 验收标准

- [ ] 正确 JSON Path 只有 `enhancements.*`；
- [ ] 双 Gate 4 组合全部通过；
- [ ] flat config 向后兼容；
- [ ] src/dst 正式生效；
- [ ] base + override 优先级固定；
- [ ] 一侧 fallback 不影响另一侧；
- [ ] relative path 不能逃逸；
- [ ] 错误顶层 key 有明确 warning；
- [ ] startup log 可证明每侧最终配置；
- [ ] 权威 options-json 文档同步；
- [ ] Analyzer 使用说明同步；
- [ ] 全量回归通过。

不得用“JSON 成功解析”作为功能生效证据，必须断言 `src_runtime.resolution.requested_mode` 与 `dst_runtime...` 分别符合输入。

---

## 15. Summary 要求

生成：

```text
.scratch/batch2-training-data-and-sampling/reports/
15-fix-options-json-and-src-dst-sampling-contract-summary.md
```

必须记录：

- 最终 JSON Schema 示例；
- flat compatibility；
- side inheritance 规则；
- Gate 矩阵；
- path 规则；
- 实际修改函数；
- 测试矩阵结果；
- `--options-json` 文档版本与章节；
- legacy 回归；
- 未完成 Windows 项；
- Reviewer 结论。