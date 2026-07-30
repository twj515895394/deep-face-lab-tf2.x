# Ticket 15 — 修复 `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约 实施总结

> 状态：**IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEWER**  
> 自审：`PASS`（不覆盖独立 Reviewer Gate）  
> Base Commit：`d4d0b20b91a0bdf5a06586f345f974255aa46002`  
> 分支：`codex/batch2-ticket15-config-contract`  
> Head Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> 运行环境：Windows 11 / Python 3.11.7（pyenv）  
> `--options-json` 文档同步：**PASS**  
> 文档版本：**v1.1**  
> 修改章节：§6 总结构、§7 Gate、§8 Sampling（含 8.0 src/dst）、§13 日志、§18 变更记录

---

## 1. 问题理解与真实调用链

```text
main.py train --options-json
→ ModelBase.load_train_step_config
   - json.loads → 顶层键注入 self.options（嵌套 enhancements 保持 dict）
   - 检测顶层 training/sampling/runtime 误放并 warning
→ Model_SAEHD.on_initialize_options
   - normalize_enhancement_config(options["enhancements"])
→ ask_override：非空 options-json → silent（不交互覆盖）
→ on_initialize
   - sampling_config_for("src"|"dst")
   - build_sampling_runtime(role, path, enh, sampling_config=side)
   - SampleGeneratorFace(..., sampling_policy=runtime.policy)
```

修复前缺陷：

1. 仅一份扁平 `sampling_config`，SRC/DST 共用；
2. `sampling.src` / `sampling.dst` 未解析；
3. 错误顶层 Batch 2 key 静默无效；
4. metadata 相对路径缺少逃逸保护；
5. 启动日志无法证明分侧配置。

---

## 2. 实际修改

| 文件 | 变更 |
|---|---|
| `samplelib/sampling/config.py` | `resolve_metadata_path`；side split/merge；unknown field warning；`with_seed` |
| `core/enhancements/config.py` | `sampling_config_for`；`sampling_config_source`；gate state；misplaced key helpers；to_dict 保留 src/dst |
| `samplelib/sampling/runtime.py` | 分侧 config；path resolve；gate warning；增强 startup log |
| `models/Model_SAEHD/Model.py` | 显式 `sampling_config_for(src/dst)` 传入 runtime |
| `models/ModelBase.py` | 顶层 Batch 2 key 明确 warning；嵌套类型保持 JSON |
| `docs/implementation/options-json-training-configuration-reference.md` | v1.0 → **v1.1** |
| `docs/usage/faceset-analyzer-complete-guide.md` | src/dst 标为已实现 |
| `tests/smoke/test_batch2_sampling_config.py` | 配置矩阵 |
| `tests/smoke/test_batch2_saehd_sampling_options.py` | Runtime / gate / path / seed |

---

## 3. 契约摘要

### 3.1 JSON 形状

正确路径仅 `enhancements.*`。

扁平兼容：

```json
{"enhancements":{"sampling":{"mode":"pose_balanced"}}}
```

→ SRC/DST 同为 base。

Side-specific：

```json
{"enhancements":{"sampling":{
  "fallback_mode":"legacy_random",
  "src":{"mode":"quality_pose_balanced"},
  "dst":{"mode":"pose_balanced"}
}}}
```

优先级：默认 → base → side。缺失侧用 base，不复制另一侧。

### 3.2 双 Gate

| enabled | metadata_sampling | Loader | Policy |
|---:|---:|---|---|
| F | F | 不加载 | legacy |
| F | T | 不加载 + gate warning | legacy |
| T | F | 不加载 | legacy |
| T | T | 按 side 加载 | requested/fallback |

### 3.3 Path

- `null` → `<faceset>/faceset_metadata.v1.json`
- 相对路径禁止逃逸（`ValueError`，非 missing fallback）
- 绝对路径允许并记日志
- Unicode 目录支持

### 3.4 Seed

- side seed 优先
- 否则 `base_seed + 1000(src) / 2000(dst)`

---

## 4. 测试证据

```text
Python 3.11.7
compileall core/enhancements samplelib/sampling models/Model_SAEHD ModelBase → exit 0

相关单测：
  test_batch2_sampling_config
  test_batch2_saehd_sampling_options
  test_batch2_sampling_fallback
  test_batch2_sampling_logging
  test_batch1_config_defaults
→ Ran 44 / OK / exit 0

全量 test_batch2_*.py
→ Ran 169 / OK
→ shell exit -1073740791（daemon host 关机；Ticket 16）
```

关键断言覆盖：

- 双 Gate 4 组合
- flat / src-dst / base+override / 缺失侧
- invalid side type warning
- path escape
- gate off 不调用 SampleLoader
- SRC/DST requested_mode 独立
- 顶层 misplaced key 文案
- to_dict roundtrip 含 src/dst

---

## 5. 未完成 / 范围外

| 项 | 状态 |
|---|---|
| 独立 Reviewer APPROVED | 待签发 |
| Ticket 16 daemon exit 0 | 不在本 Ticket |
| Windows GPU / 正式生产 | PENDING |
| GUI Sampling 控件 | 禁止范围 |

---

## 6. 结论

Ticket 15 配置契约与分侧接线已在允许文件范围内落地；权威 options-json 文档同步为 v1.1。  
**最终状态以独立 Reviewer 为准。**
