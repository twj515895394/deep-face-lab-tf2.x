# Ticket 15 — `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约独立 Review Round 2 Final

> Review 日期：2026-07-30  
> Review 结论：**APPROVED / PASS**  
> Ticket 15 状态：**CONFIG CONTRACT CLOSED**  
> 首轮实现 Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> Round 1 Review Commit：`b3d7af4228e4e35c9d94ca9d9f3e7d152576b2de`  
> Round 1 前 Head：`35c42c4379aaa387c9130d4941ec6a5982217ff6`  
> Remediation Commit：`6ee5eceb2be9230f8e292364ec4a425e445c83d7`  
> 被审分支 Head：`f2428ec1f46104cca621af60b466a26dcbad2987`  
> 工作分支：`codex/batch2-ticket15-config-contract`

---

## 1. 最终结论

Round 1 指出的五项必修问题已经按限定范围完成修复，代码、测试、文档和交接状态相互一致。本轮没有发现新的 Ticket 15 阻断问题，因此正式签发：

```text
APPROVED
PASS
TICKET 15 CONFIG CONTRACT CLOSED
```

Ticket 15 只代表配置契约、双 Gate、SRC/DST 分侧配置与 SAEHD 接线通过，不代表整个 Metadata Sampling 已生产就绪。Ticket 16、17、19、20 及 Windows GPU 验收仍按各自 Ticket 独立推进。

---

## 2. Review 范围

本轮比较：

```text
35c42c4379aaa387c9130d4941ec6a5982217ff6
→ 6ee5eceb2be9230f8e292364ec4a425e445c83d7
```

以及只回填 remediation SHA 的文档提交：

```text
f2428ec1f46104cca621af60b466a26dcbad2987
```

Remediation 为单一实现提交，实际修改集中在 Ticket 15 允许范围：

```text
models/ModelBase.py
models/Model_SAEHD/Model.py
core/enhancements/__init__.py
core/enhancements/config.py
samplelib/sampling/config.py
samplelib/sampling/runtime.py
tests/test_options_json.py
tests/smoke/test_batch2_sampling_config.py
tests/smoke/test_batch2_saehd_sampling_options.py
docs/implementation/options-json-training-configuration-reference.md
Ticket 15 summary / handoff
```

没有修改 Ticket 16 daemon/spawn、Ticket 17 analyzer workers、Ticket 19 Loss Window、Ticket 20 SampleLoader 核心异常分类、SAEHD 网络/Loss/optimizer/checkpoint 或 GUI Sampling 控件。

---

## 3. Round 1 五项问题关闭证据

### R1-01 — persisted 错误顶层 Batch 2 keys 静默失效

**状态：CLOSED**

`ModelBase.load_train_step_config()` 现在先完成 options-json 注入，再无条件对最终 `self.options` 调用 misplaced-key 检测。因此以下来源都会被统一发现：

```text
旧模型 data.dat 中已持久化的错误 keys
本次 --options-json 注入的错误 keys
persisted + injected 合并后的最终 options
```

行为保持为 warning-only：不自动迁移、不删除、不重写用户配置。

测试使用真实轻量 `ModelBase.__new__()` fixture 调用 `load_train_step_config()`，覆盖：

```text
persisted keys + options_json=None
本次 options-json 错误顶层 keys
正确 enhancements 嵌套不告警
原错误配置不被自动删除
```

相关测试：`tests/test_options_json.py`。

### R1-02 — SAEHD 真实路径的 config_source 退化为 explicit

**状态：CLOSED**

`build_sampling_runtime()` 新增可选 `sampling_config_source`，并保持兼容规则：

```text
未显式传 SamplingConfig
→ Runtime 从 EnhancementConfig 解析 config 与 source

显式传 SamplingConfig + source
→ 使用调用方给出的真实 source

显式传 SamplingConfig、未传 source
→ 兼容回退为 explicit
```

SAEHD 真实接线现在分别取得并传入：

```text
src_sampling_cfg + src_config_source
dst_sampling_cfg + dst_config_source
```

因此启动日志可稳定区分：

```text
default
base
src_override / dst_override
base+src_override / base+dst_override
```

测试覆盖与 SAEHD 相同的显式 Runtime 调用形状，并断言 SRC/DST 的 `config_source` 和 requested mode 独立。

### R1-03 — 普通交互 Override 删除 sampling.src/dst

**状态：CLOSED**

新增纯 helper `apply_interactive_sampling_base_update()`：

```text
只修改 training.enabled
只修改 training.metadata_sampling
只修改 sampling base mode
保留完整 sampling.src
保留完整 sampling.dst
```

SAEHD 普通交互路径已改为通过该 helper 更新完整 EnhancementConfig，不再用扁平 `sampling_config.to_dict()` 覆盖整个 sampling 结构。

测试覆盖：

```text
修改 base mode 后 src/dst mode 与 seed 保留
关闭 Gate 后 src/dst 仍保留
normalize → to_dict → normalize 后 src/dst 仍存在
```

本修复没有新增 SRC/DST 双侧 GUI，符合范围限制。

### R1-04 — side validation warning 串到另一侧日志

**状态：CLOSED**

side 解析告警现在统一增加：

```text
sampling.src:
sampling.dst:
```

`EnhancementConfig.config_warnings_for(role)` 只返回当前 role 的 side warning，并把 base/global warning 保持为两侧可见。Runtime 已改为调用该 role-aware API。

测试证明：

```text
invalid src mode 只出现在 src warnings
不会出现在 dst warnings
dst requested mode 不受 invalid src 配置影响
base/global unknown field 仍对两侧可见
```

### R1-05 — min_sample_weight == max_sample_weight 被接受

**状态：CLOSED**

校验条件已从：

```text
min > max
```

改为：

```text
min >= max
```

非法时统一恢复安全默认：

```text
min_sample_weight = 0.5
max_sample_weight = 2.0
```

并产生明确 warning。测试覆盖 base equality 和 SRC side equality，且验证 side warning 不污染 DST。权威 options-json 文档仍明确要求严格 `<`，代码和文档已对齐。

---

## 4. 主体契约复核

结合首轮实现与本轮 remediation，Ticket 15 的以下主体契约保持成立：

```text
Batch 2 配置唯一合法顶层入口为 enhancements.*
默认 → flat base → sampling.src/dst override
缺失侧使用 base，不复制另一侧
SRC/DST requested mode、metadata path、seed 独立
双 Gate 四组合
Gate 关闭时不调用 SampleLoader
相对 metadata_path 按各自 faceset 解析并拒绝逃逸
绝对 metadata_path 与 Unicode 路径保持支持
side seed 优先，否则 base seed + 1000/2000
扁平 sampling 配置继续向后兼容
非空 --options-json 不再被交互覆盖
启动日志包含 gates、config_source、path、requested/effective mode、fallback、seed
```

---

## 5. 测试证据判定

实施 Summary 记录的实际 Windows 测试证据：

```text
compileall changed paths
→ exit 0

focused Ticket 15 tests
→ Ran 59 / OK / shell exit 0

full test_batch2_*.py assertions
→ Ran 175 / OK

full process exit
→ -1073740791 / BLOCKED-BY-TICKET16
```

Review 判定：

```text
Ticket 15 focused tests：PASS
Ticket 15 配置契约：PASS
全量 Batch 2 进程退出：NOT PASS / BLOCKED-BY-TICKET16
GitHub Actions：无 workflow run / 无 CI status
```

不得把 `Ran 175 / OK` 与非零进程退出合并表述为“全量 Batch 2 PASS”。该限制不阻止 Ticket 15 在 focused tests exit 0、代码契约闭环后独立关闭，但 Ticket 16 必须继续处理进程退出问题。

---

## 6. 非阻断残余与后续依赖

以下内容不是 Ticket 15 的 reopen 条件：

```text
Ticket 16 Windows spawn / daemon shutdown / WeightedIndexHost
Ticket 17 workers / strong fingerprint / stale detection
Ticket 19 Loss Window
Ticket 20 SampleLoader 错误分类与生产收口
Windows GPU 正式训练验收
GUI Sampling 控件
```

Ticket 15 通过后，Ticket 20 的依赖应更新为：

```text
BLOCKED-BY-16+17
```

Metadata Sampling 整体仍为：

```text
NOT PRODUCTION READY
```

直到剩余 Batch 2 Ticket 与 Windows GPU 验收全部完成。

---

## 7. 最终签发

```text
Ticket 15：APPROVED / PASS / CLOSED
Review Round 2：FINAL
Remediation Commit：6ee5eceb2be9230f8e292364ec4a425e445c83d7
Reviewed Head：f2428ec1f46104cca621af60b466a26dcbad2987
Ticket 20：BLOCKED-BY-16+17
Metadata Sampling：NOT PRODUCTION READY
```
