# Ticket 15 — 修复 `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约 实施总结

> 当前状态：**INDEPENDENT REVIEW ROUND 1 — CHANGES REQUIRED / REMEDIATION OPEN**  
> 实现者自审：`PASS`（已被独立 Review 覆盖，不能作为关闭依据）  
> 独立 Review：`NOT APPROVED`  
> Base Commit：`d4d0b20b91a0bdf5a06586f345f974255aa46002`  
> 首轮实现 Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> Review R1 报告 Commit：`b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de`  
> 分支：`codex/batch2-ticket15-config-contract`  
> 首轮实现环境：Windows 11 / Python 3.11.7（pyenv）  
> `--options-json` 文档同步：**v1.1 已同步，但最终实现仍需 remediation 对齐**  
> 独立 Review 报告：[15-fix-options-json-and-src-dst-sampling-contract-review-round1.md](15-fix-options-json-and-src-dst-sampling-contract-review-round1.md)

---

## 1. 首轮实现的目标与调用链

```text
main.py train --options-json
→ ModelBase.load_train_step_config
   - json.loads → 顶层键注入 self.options（嵌套 enhancements 保持 dict）
   - 首轮实现：检测本次 new_options 中顶层 training/sampling/runtime 并 warning
→ Model_SAEHD.on_initialize_options
   - normalize_enhancement_config(options["enhancements"])
→ ask_override：非空 options-json → silent（不交互覆盖）
→ on_initialize
   - sampling_config_for("src"|"dst")
   - build_sampling_runtime(role, path, enh, sampling_config=side)
   - SampleGeneratorFace(..., sampling_policy=runtime.policy)
```

首轮实现试图修复：

1. 仅一份扁平 `sampling_config`，SRC/DST 共用；
2. `sampling.src` / `sampling.dst` 未解析；
3. 错误顶层 Batch 2 key 静默无效；
4. metadata 相对路径缺少逃逸保护；
5. 启动日志无法证明分侧配置。

---

## 2. 首轮实际修改

| 文件 | 首轮变更 |
|---|---|
| `samplelib/sampling/config.py` | `resolve_metadata_path`；side split/merge；unknown field warning；`with_seed` |
| `core/enhancements/config.py` | `sampling_config_for`；`sampling_config_source`；gate state；misplaced key helpers；to_dict 保留 src/dst |
| `samplelib/sampling/runtime.py` | 分侧 config；path resolve；gate warning；增强 startup log |
| `models/Model_SAEHD/Model.py` | 显式 `sampling_config_for(src/dst)` 传入 runtime |
| `models/ModelBase.py` | 本次 options-json 顶层 Batch 2 key warning；嵌套类型保持 JSON |
| `docs/implementation/options-json-training-configuration-reference.md` | v1.0 → v1.1 |
| `docs/usage/faceset-analyzer-complete-guide.md` | src/dst 标为已实现 |
| `tests/smoke/test_batch2_sampling_config.py` | 配置矩阵 |
| `tests/smoke/test_batch2_saehd_sampling_options.py` | Runtime / gate / path / seed |

---

## 3. 首轮已确认正确的主体契约

### 3.1 JSON 形状

正确路径仅：

```text
enhancements.*
```

扁平兼容：

```json
{"enhancements":{"sampling":{"mode":"pose_balanced"}}}
```

SRC/DST 都使用 base。

Side-specific：

```json
{"enhancements":{"sampling":{
  "fallback_mode":"legacy_random",
  "src":{"mode":"quality_pose_balanced"},
  "dst":{"mode":"pose_balanced"}
}}}
```

固定优先级：

```text
SamplingConfig defaults
→ flat sampling base
→ sampling.<role> override
```

缺失侧使用 base，不复制另一侧。

### 3.2 双 Gate

| enabled | metadata_sampling | Loader | Policy |
|---:|---:|---|---|
| false | false | 不加载 | legacy |
| false | true | 不加载 + gate warning | legacy |
| true | false | 不加载 | legacy |
| true | true | 按 side 加载 | requested/fallback |

### 3.3 Metadata Path

- `null` / `""` → `<faceset>/faceset_metadata.v1.json`；
- 相对路径相对各自 faceset 根目录；
- 规范化后禁止逃逸；
- `../` 逃逸抛 `ValueError`，不能伪装成 missing fallback；
- 绝对路径允许并记录；
- Unicode 路径基础能力已覆盖。

### 3.4 Seed

- side seed 优先；
- side seed 为 `None` 时：SRC = `base_seed + 1000`；DST = `base_seed + 2000`；
- 不污染全局 NumPy RNG。

---

## 4. 首轮测试证据及正确解释

首轮 Summary 记录：

```text
Python 3.11.7
compileall core/enhancements samplelib/sampling models/Model_SAEHD ModelBase → exit 0

focused 相关单测：
  test_batch2_sampling_config
  test_batch2_saehd_sampling_options
  test_batch2_sampling_fallback
  test_batch2_sampling_logging
  test_batch1_config_defaults
→ Ran 44 / OK / shell exit 0

全量 test_batch2_*.py
→ Ran 169 / assertions OK
→ shell exit -1073740791（daemon shutdown；Ticket 16）
```

独立 Review 对证据的权威解释：

```text
focused Ticket 15 tests：PASS
full Batch 2 assertions：OK
full Batch 2 process exit：BLOCKED-BY-TICKET16
```

不得把 `Ran 169 / OK + shell exit -1073740791` 表述为“全量回归 PASS”。Ticket 15 remediation 不得顺手修改 Ticket 16 的 daemon/spawn。

---

## 5. 独立 Review Round 1 结论

结论：

```text
CHANGES REQUIRED
NOT APPROVED
TICKET 15 REMEDIATION OPEN
TICKET 20 REMAINS BLOCKED
```

完整依据见：

```text
.scratch/batch2-training-data-and-sampling/reports/
15-fix-options-json-and-src-dst-sampling-contract-review-round1.md
```

Review 认为主体配置解析方向正确，但真实调用链和持久化链路仍有 5 项缺口。

---

## 6. Round 1 必修项

### R1-01：错误顶层 key 只检测本次 `new_options`，未检测最终 `self.options`

当前问题：

- 本次 `--options-json` 中的错误顶层 keys 可以 warning；
- 已保存到旧模型 `data.dat` 的顶层 `training/sampling/runtime` 在无 options-json 启动时仍静默失效；
- 这没有覆盖旧错误文档造成的 persisted config 迁移场景。

修复要求：

```text
在 options-json 注入完成后，对最终 self.options 统一检测一次。
即使 options_json=None 也必须执行。
只 warning，不自动迁移、不删除、不重写。
```

必须使用真实 `ModelBase.load_train_step_config()` 测试，不得只测试 helper。

### R1-02：SAEHD 真实调用路径的 `config_source` 退化为 `explicit`

当前问题：

- SAEHD 外部解析 side config 后显式传入 Runtime；
- Runtime 只要收到 `sampling_config` 就记录 `config_source="explicit"`；
- 正式训练日志无法显示 `base+src_override` / `base+dst_override`；
- 当前测试绕过 SAEHD 的显式调用方式，所以未发现。

修复要求：

```text
保持 SAEHD 为 side config 解析权威入口。
Runtime 增加可选 sampling_config_source。
SAEHD 将 EnhancementConfig.sampling_config_source(role) 一并传入。
不得根据 SamplingConfig 值反向猜来源。
```

### R1-03：普通交互 Override 会删除 `sampling.src/dst`

当前问题：

```python
current_sampling_dict = self.enhancements.sampling_config.to_dict()
updated_dict["sampling"] = current_sampling_dict
```

`sampling_config` 只含 base/global，因此该替换会删除 side layout，并在后续 save 时永久持久化退化结果。

修复要求：

```text
从 self.enhancements.to_dict() 取得完整 sampling。
交互只更新 base 字段，例如 sampling["mode"]。
src/dst 原样保留。
关闭 Gate 时也保留 side config，不能删除。
不新增 GUI 或双侧交互控件。
```

### R1-04：side-specific validation warning 未按角色隔离

当前问题：

- SRC override 的 invalid mode warning 缺少 role 前缀；
- Runtime 在两侧遍历同一全局 warning list；
- 只有 SRC 配置错误时，DST 日志也可能显示同一错误。

修复要求：

```text
base warning 保持 global。
side warning 使用固定前缀 sampling.src: / sampling.dst:。
EnhancementConfig 提供 config_warnings_for(role)。
Runtime 每侧只输出 global + 本侧 warning。
```

### R1-05：`min_sample_weight == max_sample_weight` 与 v1.1 文档不一致

权威文档要求：

```text
min_sample_weight < max_sample_weight
```

代码当前只拒绝 `min > max`， equality 会被接受。

修复要求：

```python
if min_weight >= max_weight:
    # warning + safe defaults 0.5 / 2.0
```

必须覆盖 base equality 和 side equality，且一侧非法不得改变另一侧。

---

## 7. remediation 范围

允许围绕 R1-01—R1-05 修改：

```text
models/ModelBase.py
models/Model_SAEHD/Model.py
core/enhancements/config.py
samplelib/sampling/config.py
samplelib/sampling/runtime.py
tests/test_options_json.py
tests/smoke/test_batch2_sampling_config.py
tests/smoke/test_batch2_saehd_sampling_options.py
tests/smoke/test_batch2_sampling_fallback.py
tests/smoke/test_batch2_sampling_logging.py
必要的 options-json v1.1 文档同步
Ticket 15 summary / review / handoff
```

明确禁止顺手修改：

```text
Ticket 16 Windows spawn / daemon / WeightedIndexHost 生命周期
Ticket 17 workers / strong fingerprint / stale signature
Ticket 18 incremental summary
Ticket 19 Loss Window
Ticket 20 SampleLoader 核心异常分类
SAEHD 网络 / Loss / optimizer / checkpoint
GUI Sampling 控件
大范围配置架构重构
```

---

## 8. remediation 必须新增或加强的测试

### ModelBase

- persisted 错误顶层 key，无 options-json，也 warning；
- injected 错误顶层 key warning；
- 正确嵌套 enhancements 不误报；
- 嵌套 dict 经过真实 `load_train_step_config()` 保持 mapping；
- non-empty options-json 继续跳过 override。

### Config

- side warning 隔离；
- invalid side type；
- invalid mode；
- unknown field；
- NaN/Inf；
- `min > max`；
- `min == max`；
- base equality；
- side equality；
- roundtrip 保留 src/dst。

### Runtime / SAEHD 式接线

- 显式传入 side config + source；
- SRC `base+src_override`；
- DST `base+dst_override`；
- SRC requested quality / DST requested pose；
- SRC loaded / DST missing 只 DST fallback；
- SRC invalid config 不改变 DST；
- side seed 与派生 seed；
- Gate off 不调用 SampleLoader；
- Unicode path 与 escape。

### 交互持久化

- Override 后 src/dst mode 和 seed 仍存在；
- 关闭 Gate 后 src/dst 仍存在；
- normalize/to_dict roundtrip 后仍存在；
- 最终 `self.options["enhancements"]` 不退化为 flat-only。

---

## 9. remediation 建议测试命令

```text
python -m compileall core/enhancements samplelib/sampling models/Model_SAEHD models/ModelBase.py
python -m unittest tests.test_options_json
python -m unittest tests.smoke.test_batch2_sampling_config
python -m unittest tests.smoke.test_batch2_saehd_sampling_options
python -m unittest tests.smoke.test_batch2_sampling_fallback
python -m unittest tests.smoke.test_batch2_sampling_logging
python -m unittest tests.smoke.test_batch1_config_defaults
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

结果必须分别记录：

```text
focused Ticket 15 tests: Ran N / OK / shell exit 0
full Batch 2 assertions: Ran N / OK or FAIL
full Batch 2 process exit: 0 or BLOCKED-BY-TICKET16
```

---

## 10. 下一提交要求

修复 Agent 必须生成一个只包含 Ticket 15 remediation 的 commit，推荐：

```text
fix(sampling): address Ticket 15 review findings
```

并在本 Summary 中补充：

```text
Previous Head SHA
New Head SHA
R1-01—R1-05 逐项关闭证据
实际修改函数
focused tests Ran N / result / exit
full assertions / process exit 分开记录
未修改 Ticket 16/17/19/20 的范围声明
```

完成后请求 Round 2 独立 Review。

---

## 11. 当前最终状态

```text
Ticket 15：CHANGES REQUIRED / REMEDIATION OPEN
Ticket 20：BLOCKED
Metadata Sampling：NOT PRODUCTION READY
Windows GPU：PENDING
```

只有 Round 2 独立 Reviewer 确认全部关闭后，才允许写：

```text
APPROVED
PASS
TICKET 15 CONFIG CONTRACT CLOSED
```
