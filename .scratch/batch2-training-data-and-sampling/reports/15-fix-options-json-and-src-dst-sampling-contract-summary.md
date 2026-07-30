# Ticket 15 — 修复 `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约 实施总结

> 当前状态：**REMEDIATION COMPLETE / AWAITING ROUND-2 INDEPENDENT REVIEW**  
> 实现者自审：`PASS`（不覆盖独立 Reviewer Gate）  
> 独立 Review R1：`CHANGES REQUIRED`（已按报告修复）  
> Base Commit：`d4d0b20b91a0bdf5a06586f345f974255aa46002`  
> 首轮实现 Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> Review R1 报告 Commit：`b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de`  
> Previous Head（R1 后）：`35c42c4379aaa387c9130d4941ec6a5982217ff6`  
> Remediation Head：`6ee5eceb2be9230f8e292364ec4a425e445c83d7`  
> 分支：`codex/batch2-ticket15-config-contract`  
> 环境：Windows 11 / Python 3.11.7（pyenv）  
> `--options-json` 文档同步：**PASS / v1.1**（min/max 严格 `<` 语义已对齐）  
> 独立 Review 报告：[15-fix-options-json-and-src-dst-sampling-contract-review-round1.md](15-fix-options-json-and-src-dst-sampling-contract-review-round1.md)

---

## 1. R1 逐项关闭

| ID | 问题 | 修复 | 证据 |
|---|---|---|---|
| R1-01 | 仅检测 new_options | `load_train_step_config` 末尾检测**最终** `self.options`；不迁移 | `tests/test_options_json.py` persisted + injected + nested |
| R1-02 | SAEHD 显式 config → `explicit` | `sampling_config_source=` 参数；SAEHD 传入 `sampling_config_source` | `test_saehd_explicit_sampling_config_preserves_config_source` |
| R1-03 | Override 删 src/dst | `apply_interactive_sampling_base_update` 只改 base mode/gates | `test_interactive_override_preserves_side_configs` |
| R1-04 | side warning 串侧 | `sampling.<role>:` 前缀 + `config_warnings_for(role)` | `test_side_warning_isolation` |
| R1-05 | min==max 被接受 | `min_weight >= max_weight` → 0.5/2.0 + warning | `test_min_max_equality_*` |

---

## 2. 实际修改函数 / 文件

| 文件 | 变更 |
|---|---|
| `models/ModelBase.py` | `load_train_step_config` 最终 options 检测 |
| `models/Model_SAEHD/Model.py` | Override 用 helper；runtime 传 `sampling_config_source` |
| `core/enhancements/config.py` | `config_warnings_for`；`apply_interactive_sampling_base_update` |
| `samplelib/sampling/config.py` | side warning 前缀；`min >= max` |
| `samplelib/sampling/runtime.py` | `sampling_config_source`；按 role 打 warning |
| `tests/test_options_json.py` | R1-01 + 避免 mock 污染真实 cv2 |
| `tests/smoke/test_batch2_sampling_config.py` | R1-03/04/05 |
| `tests/smoke/test_batch2_saehd_sampling_options.py` | R1-02 SAEHD 式接线 |
| options-json 文档 | min/max 严格 `<` 说明 |

---

## 3. 测试证据

```text
Python 3.11.7
compileall core/enhancements samplelib/sampling Model_SAEHD ModelBase → exit 0

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
→ process exit -1073740791 → BLOCKED-BY-TICKET16
  （断言通过，但测试进程退出仍被 Ticket 16 daemon shutdown 阻断）
```

**不得**将 `Ran 175 OK + shell exit -1073740791` 写成全量回归 PASS。

---

## 4. 范围外

- Ticket 16 daemon / spawn
- Ticket 17/18/19/20
- GUI、网络、Loss、optimizer
- Ticket 15 正式 PASS/CLOSED 待 Round-2 Reviewer

---

## 5. 结论

R1-01—R1-05 已在允许范围内闭环。  
**等待 Round-2 独立 Review 签发 APPROVED / PASS。**
