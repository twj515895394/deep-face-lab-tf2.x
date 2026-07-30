# Ticket 15 — 修复 `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约 实施总结

> 当前状态：**APPROVED / PASS / CONFIG CONTRACT CLOSED**  
> 实现者自审：`PASS`  
> 独立 Review R1：`CHANGES REQUIRED`  
> 独立 Review R2：`APPROVED / PASS / FINAL`  
> Base Commit：`d4d0b20b91a0bdf5a06586f345f974255aa46002`  
> 首轮实现 Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> Review R1 报告 Commit：`b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de`  
> Previous Head（R1 后）：`35c42c4379aaa387c9130d4941ec6a5982217ff6`  
> Remediation Commit：`6ee5eceb2be9230f8e292364ec4a425e445c83d7`  
> Review R2 Final Commit：`4fd7d062cc817589fd964efdae3bd3e793247b68`  
> 分支：`codex/batch2-ticket15-config-contract`  
> 环境：Windows 11 / Python 3.11.7（pyenv）  
> `--options-json` 文档同步：**PASS / v1.1**  
> Final Review：[15-fix-options-json-and-src-dst-sampling-contract-review-round2-final.md](15-fix-options-json-and-src-dst-sampling-contract-review-round2-final.md)

---

## 1. 最终实现范围

Ticket 15 已完成以下配置契约：

```text
Batch 2 唯一合法配置入口：enhancements.*
SamplingConfig 默认 → flat base → sampling.src/dst override
SRC/DST requested mode、metadata path、seed 独立
双 Gate：training.enabled + training.metadata_sampling
Gate 关闭时不加载 Metadata
相对 metadata_path 按 faceset 解析并拒绝逃逸
绝对路径与 Unicode 路径支持
side seed 优先，否则 base seed +1000 / +2000
扁平 sampling 向后兼容
非空 --options-json 跳过交互覆盖
启动日志输出 gates、config source、path、mode、fallback、seed
```

---

## 2. Round 1 五项问题关闭

| ID | 问题 | 最终修复 | 证据 |
|---|---|---|---|
| R1-01 | 只检测本次 new_options | `load_train_step_config()` 末尾检测最终 `self.options`，覆盖 persisted + injected | `tests/test_options_json.py` |
| R1-02 | SAEHD 显式 config 的 source 退化为 `explicit` | Runtime 增加 `sampling_config_source`；SAEHD 分别传 src/dst source | `test_saehd_explicit_sampling_config_preserves_config_source` |
| R1-03 | 普通 Override 删除 src/dst | `apply_interactive_sampling_base_update()` 只改 base mode/gates并保留两侧 | `test_interactive_override_preserves_side_configs` |
| R1-04 | side warning 串侧 | `sampling.<role>:` 前缀 + `config_warnings_for(role)` | `test_side_warning_isolation` |
| R1-05 | min==max 被接受 | `min_weight >= max_weight` 恢复 0.5/2.0 并 warning | `test_min_max_equality_*` |

---

## 3. 实际修改函数 / 文件

| 文件 | 变更 |
|---|---|
| `models/ModelBase.py` | `load_train_step_config()` 对最终 options 做 misplaced-key warning |
| `models/Model_SAEHD/Model.py` | 交互 Override 使用保留 side 的 helper；Runtime 传真实 config source |
| `core/enhancements/__init__.py` | 导出交互更新 helper |
| `core/enhancements/config.py` | `config_warnings_for()`；`apply_interactive_sampling_base_update()` |
| `samplelib/sampling/config.py` | side warning 前缀；严格 `min < max` |
| `samplelib/sampling/runtime.py` | `sampling_config_source`；按 role 输出配置告警 |
| `tests/test_options_json.py` | persisted/injected/nested 的真实 ModelBase 调用测试 |
| `tests/smoke/test_batch2_sampling_config.py` | R1-03/04/05 测试 |
| `tests/smoke/test_batch2_saehd_sampling_options.py` | SAEHD 式显式 Runtime 接线测试 |
| options-json 权威文档 | min/max 严格 `<` 语义对齐 |

---

## 4. 测试证据

```text
Python 3.11.7
compileall core/enhancements samplelib/sampling Model_SAEHD ModelBase
→ exit 0

focused Ticket 15:
  tests.test_options_json
  tests.smoke.test_batch2_sampling_config
  tests.smoke.test_batch2_saehd_sampling_options
  tests.smoke.test_batch2_sampling_fallback
  tests.smoke.test_batch2_sampling_logging
  tests.smoke.test_batch1_config_defaults
→ Ran 59 / OK / shell exit 0

full Batch 2 assertions:
  python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
→ Ran 175 / OK
→ process exit -1073740791 / BLOCKED-BY-TICKET16

GitHub Actions：无 workflow run / 无 CI status
```

正确状态解释：

```text
Ticket 15 focused tests：PASS
Ticket 15 config contract：PASS
全量 Batch 2 process exit：NOT PASS / BLOCKED-BY-TICKET16
```

不得把 `Ran 175 / OK` 与非零进程退出合并表述为“全量 Batch 2 PASS”。

---

## 5. 独立 Review 结论

Round 2 已确认：

```text
R1-01—R1-05 全部 CLOSED
没有新的 Ticket 15 阻断项
修复未跨 Ticket 16/17/19/20
权威文档与实现语义一致
focused tests 有实际 exit 0 证据
```

最终签发：

```text
APPROVED
PASS
TICKET 15 CONFIG CONTRACT CLOSED
```

---

## 6. 后续边界

Ticket 15 关闭不代表 Metadata Sampling 整体生产就绪：

```text
Ticket 16：Windows spawn / daemon shutdown
Ticket 17：workers / fingerprint / stale detection
Ticket 19：Loss Window
Ticket 20：SampleLoader 生产收口
Windows GPU 正式训练验收
```

Ticket 20 当前依赖更新为：

```text
BLOCKED-BY-16+17
```

Metadata Sampling 继续保持：

```text
NOT PRODUCTION READY
```
