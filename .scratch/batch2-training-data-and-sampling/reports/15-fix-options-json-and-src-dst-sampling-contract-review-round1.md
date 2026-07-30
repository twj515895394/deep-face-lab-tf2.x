# Ticket 15 — `--options-json`、双 Gate 与 SRC/DST Sampling 配置契约独立 Review Round 1

> Review 日期：2026-07-30  
> Review 结论：**CHANGES REQUIRED / NOT APPROVED**  
> Base Commit：`d4d0b20b91a0bdf5a06586f345f974255aa46002`  
> 被审实现 Commit：`43a3c437fee4454b54abb192727797dbbe20a4e7`  
> 工作分支：`codex/batch2-ticket15-config-contract`  
> Ticket 15 状态：**REMEDIATION REQUIRED**  
> Ticket 20：继续 `BLOCKED-BY-15+16+17`

---

## 1. 最终结论

Ticket 15 的主体方向正确，以下核心能力已经基本实现：

- `enhancements.*` 作为 Batch 2 唯一受支持的配置入口；
- `SamplingConfig defaults → flat base → src/dst override`；
- SRC/DST 独立 requested mode、metadata path 和 seed；
- 双 Gate 四组合；
- Gate 关闭时不加载 Metadata；
- 相对 `metadata_path` 按各自 faceset 解析并拒绝 `..` 逃逸；
- 扁平 sampling 向后兼容；
- options-json 权威文档更新为 v1.1。

但是，当前实现仍有 **5 项需要修复的问题**。其中前三项直接影响 Ticket 15 的验收目标：

1. 已持久化到旧模型 `data.dat` 的错误顶层 Batch 2 keys 仍会静默失效；
2. SAEHD 真实运行路径把 `config_source` 打印成 `explicit`，无法证明 base/side 来源；
3. 普通交互 Override 会删除已经保存的 `sampling.src` / `sampling.dst`；
4. side-specific validation warning 会同时污染 SRC 和 DST 日志；
5. `min_sample_weight == max_sample_weight` 被代码接受，但权威文档要求严格 `<`。

因此本轮不得签发：

```text
APPROVED
PASS
TICKET 15 CONFIG CONTRACT CLOSED
```

修复完成后必须提交新的实现 commit、更新 Summary，并进入 Round 2 独立 Review。

---

## 2. 本轮施工边界

### 2.1 允许修改

只允许围绕本报告中的 5 项问题修改：

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
docs/implementation/options-json-training-configuration-reference.md（仅实现语义变化时同步）
Ticket 15 summary / review / handoff 文档
```

不要求每个文件都修改。只修改真正需要的文件。

### 2.2 明确禁止

本轮不要顺手处理：

- Ticket 16 Windows spawn、daemon shutdown、WeightedIndexHost 生命周期；
- Ticket 17 workers、strong fingerprint、stale signature；
- Ticket 18 incremental summary；
- Ticket 19 Loss Window；
- Ticket 20 SampleLoader 核心错误分类；
- SAEHD 网络、Loss、optimizer、checkpoint；
- GUI Sampling 控件；
- 大范围配置系统重构；
- 新增第二个 JSON 文件参数；
- 改变 `--options-json` 当前“JSON 字符串”语义。

如果全量 `test_batch2_*.py` 仍然出现已知 `-1073740791` 退出码，只能记录为 `BLOCKED-BY-TICKET16`，不得在 Ticket 15 内修改 daemon/spawn 代码。

---

## 3. 必修问题 R1-01：最终 `self.options` 未统一检测错误顶层 Batch 2 keys

### 3.1 当前问题

当前检测逻辑只存在于：

```python
if self.options_json is not None and len(self.options_json) > 0:
    new_options = json.loads(self.options_json)
    misplaced = detect_misplaced_batch2_top_level_keys(new_options)
```

这只能发现“本次新传入的错误 JSON”。

但是旧模型可能已经把以下错误配置保存进 `<model>_data.dat`：

```json
{
  "training": {"enabled": true, "metadata_sampling": true},
  "sampling": {"mode": "pose_balanced"}
}
```

模型启动时会先恢复：

```python
self.options = model_data["options"]
```

如果本次没有传 `--options-json`，`load_train_step_config()` 不会检测这些 persisted keys。最终 SAEHD 仍只读取：

```python
self.options["enhancements"]
```

结果是旧错误配置继续静默失效，正好没有解决 Ticket 15 的历史迁移场景。

### 3.2 必须达到的行为

无论错误 keys 来自：

- 本次 `--options-json`；
- 已保存模型 `data.dat`；
- 两者合并后的最终 options；

都必须在 `on_initialize_options()` 前对 **最终 `self.options`** 检测一次。

### 3.3 推荐最小实现

不要分别维护两套检测逻辑。推荐：

1. 保留原有 JSON 解析和注入逻辑；
2. 删除或避免仅对 `new_options` 重复告警；
3. 在 `load_train_step_config()` 末尾，对最终 `self.options` 统一调用一次 helper；
4. 检测只负责 warning，不自动迁移、不删除、不重写用户配置。

伪代码：

```python
def load_train_step_config(self):
    if self.options_json is not None and len(self.options_json) > 0:
        try:
            new_options = json.loads(self.options_json)
            # 原有注入逻辑
        except Exception as e:
            io.log_err(...)

    # 必须位于 options-json 注入之后；即使 options_json=None 也执行。
    try:
        misplaced = detect_misplaced_batch2_top_level_keys(self.options)
        if misplaced:
            io.log_info(format_misplaced_batch2_keys_warning(misplaced))
    except Exception:
        # warning helper 不得阻断 legacy 初始化
        pass
```

不要把错误顶层 `training/sampling/runtime` 自动搬进 `enhancements`，因为无法可靠判断用户意图，也会改变已保存模型。

### 3.4 必须新增测试

在真实 `ModelBase.load_train_step_config()` 轻量 fixture 上新增：

#### A. persisted options，无 options-json

```python
model.options = {
    "batch_size": 4,
    "training": {"enabled": True},
    "sampling": {"mode": "pose_balanced"},
}
model.options_json = None
model.load_train_step_config()
```

断言：

- warning 被调用一次；
- warning 包含 `training, sampling`；
- warning 包含 `Expected under "enhancements"`；
- 原 options 未被自动迁移或删除。

#### B. 本次 options-json

断言错误顶层 key 同样 warning。

#### C. 正确嵌套

```json
{"enhancements":{"training":{},"sampling":{}}}
```

不得产生 misplaced warning。

### 3.5 完成标准

只有检测最终 `self.options` 的测试通过，R1-01 才算关闭。仅测试 helper 函数本身不算关闭。

---

## 4. 必修问题 R1-02：SAEHD 真实路径丢失 `config_source`

### 4.1 当前问题

SAEHD 正确地在外部解析两侧配置：

```python
src_sampling_cfg = enh_cfg.sampling_config_for("src")
dst_sampling_cfg = enh_cfg.sampling_config_for("dst")
```

随后显式传入 Runtime：

```python
build_sampling_runtime(..., sampling_config=src_sampling_cfg)
build_sampling_runtime(..., sampling_config=dst_sampling_cfg)
```

但是 Runtime 的当前逻辑是：

```python
if sampling_config is None:
    config_source = enhancement_config.sampling_config_source(role_key)
else:
    config_source = "explicit"
```

所以真正训练时日志只能显示：

```text
[Sampling][src] config source: explicit
[Sampling][dst] config source: explicit
```

这无法证明配置来自：

- `default`；
- `base`；
- `src_override`；
- `dst_override`；
- `base+src_override`；
- `base+dst_override`。

当前测试直接让 Runtime 自己解析 EnhancementConfig，因此绕过了 SAEHD 的真实调用方式，没有发现这个问题。

### 4.2 固定设计决定

保留当前设计：

```text
SAEHD 是 side config 的解析权威入口
Runtime 消费已经解析完成的 SamplingConfig
```

不要改成 SAEHD 和 Runtime 各自重新解析一遍，也不要删除显式 `sampling_config` 接线。

### 4.3 推荐最小实现

给 Runtime 增加一个可选来源参数，例如：

```python
def build_sampling_runtime(
    ...,
    sampling_config: Optional[SamplingConfig] = None,
    sampling_config_source: Optional[str] = None,
) -> SamplingRuntime:
```

Runtime 规则：

```python
if sampling_config is None:
    sampling_cfg = enhancement_config.sampling_config_for(role_key)
    config_source = enhancement_config.sampling_config_source(role_key)
else:
    sampling_cfg = sampling_config
    config_source = sampling_config_source or "explicit"
```

SAEHD：

```python
src_cfg = enh_cfg.sampling_config_for("src")
src_source = enh_cfg.sampling_config_source("src")

dst_cfg = enh_cfg.sampling_config_for("dst")
dst_source = enh_cfg.sampling_config_source("dst")
```

并分别传入 Runtime。

不要让 Runtime 根据 SamplingConfig 的值反向猜来源，因为默认值和显式值可能完全相同，无法可靠判断。

### 4.4 必须新增测试

必须覆盖与 SAEHD 相同的显式调用方式：

```python
src_cfg = cfg.sampling_config_for("src")
src_source = cfg.sampling_config_source("src")
src_rt = build_sampling_runtime(
    "src",
    path,
    cfg,
    sampling_config=src_cfg,
    sampling_config_source=src_source,
)
```

输入：

```json
{
  "sampling": {
    "fallback_mode": "legacy_random",
    "src": {"mode": "quality_pose_balanced"},
    "dst": {"mode": "pose_balanced"}
  }
}
```

断言：

```text
src.startup_log["config_source"] == "base+src_override"
dst.startup_log["config_source"] == "base+dst_override"
```

并断言 requested modes 分别为：

```text
quality_pose_balanced
pose_balanced
```

### 4.5 完成标准

真实 SAEHD 显式接线路径的 startup log 能证明 base/side 来源，R1-02 才算关闭。

---

## 5. 必修问题 R1-03：交互 Override 删除 `sampling.src/dst`

### 5.1 当前问题

模型中可能已经保存：

```json
"sampling": {
  "fallback_mode": "legacy_random",
  "src": {"mode": "quality_pose_balanced"},
  "dst": {"mode": "pose_balanced"}
}
```

进入普通交互 Override 时，当前代码读取：

```python
current_sampling_dict = self.enhancements.sampling_config.to_dict()
```

`sampling_config` 只表示 base/global，不包含 `src/dst`。

随后代码执行：

```python
updated_dict["sampling"] = current_sampling_dict
```

这会把完整 sampling 替换成一份扁平 base，导致：

```text
sampling.src 被删除
sampling.dst 被删除
SRC/DST 独立配置永久退化为共享 base
后续 save() 会把退化结果持久化
```

即使用户只是进入 Override 并接受默认值，也可能发生破坏。

### 5.2 必须达到的行为

传统单一 Sampling 交互只允许修改 base 字段，不得删除 side override。

规则：

- 修改 base `mode` 时，`src/dst` 原样保留；
- 关闭双 Gate 时，side config 仍保留，只是运行时不启用；
- 以后重新打开 Gate 时，原 side config 仍可恢复生效；
- 不新增 GUI/交互式 SRC、DST 双侧编辑界面。

### 5.3 推荐最小实现

先取得完整结构：

```python
updated_dict = self.enhancements.to_dict()
sampling_dict = copy.deepcopy(updated_dict.get("sampling", {}))
```

交互默认 mode 仍从 base/global 获取：

```python
current_mode = self.enhancements.sampling_config.mode.value
```

用户选择后只改 base mode：

```python
sampling_dict["mode"] = chosen_mode
updated_dict["sampling"] = sampling_dict
```

不要再使用：

```python
updated_dict["sampling"] = self.enhancements.sampling_config.to_dict()
```

因为该表达式天然丢失 side layout。

### 5.4 必须新增测试

建议抽取一个尽量小的纯 helper 来更新交互配置，避免在测试中初始化完整 TensorFlow 模型。若不抽 helper，也必须通过轻量 stub 覆盖真实更新逻辑。

初始配置：

```json
{
  "training": {"enabled": true, "metadata_sampling": true},
  "sampling": {
    "fallback_mode": "legacy_random",
    "src": {"mode": "quality_pose_balanced", "seed": 11},
    "dst": {"mode": "pose_balanced", "seed": 22}
  }
}
```

模拟用户只修改 base mode 或关闭 Gate 后，断言：

```text
sampling.src.mode 仍为 quality_pose_balanced
sampling.src.seed 仍为 11
sampling.dst.mode 仍为 pose_balanced
sampling.dst.seed 仍为 22
```

再做 `normalize → to_dict → normalize` roundtrip，断言 side 配置仍存在。

### 5.5 完成标准

无 options-json 的普通 Override 不再破坏已保存 side config，R1-03 才算关闭。

---

## 6. 必修问题 R1-04：side warning 未按侧隔离

### 6.1 当前问题

side override 解析时，类似：

```json
"src": {"mode": "wrong_mode"}
```

可能产生没有 role 信息的 warning：

```text
Invalid sampling mode 'wrong_mode'; using legacy
```

Runtime 又在 SRC 和 DST 两侧都遍历同一份 `enhancement_config.config_warnings`，所以错误可能同时显示为：

```text
[Sampling][src] config: Invalid sampling mode ...
[Sampling][dst] config: Invalid sampling mode ...
```

实际只有 SRC 错误，却污染 DST 日志，违反分侧可观测性目标。

### 6.2 推荐最小实现

不要重写整个 validation 系统。建议：

1. base config 的 warning 保持 global；
2. 每个 side override 使用局部 warning list 解析；
3. 将 side warning 加前缀后汇总，例如：

```text
sampling.src: Invalid sampling mode 'wrong_mode'; using legacy
sampling.dst: Invalid seed 'x'; using None
```

4. `EnhancementConfig` 增加：

```python
def config_warnings_for(self, role: str) -> List[str]:
```

规则：

- global warning 对两侧都可见；
- `sampling.src:` 只对 SRC 可见；
- `sampling.dst:` 只对 DST 可见；
- 未知 role 抛 `ValueError`。

5. Runtime 使用：

```python
for warn in enhancement_config.config_warnings_for(role_key):
    io.log_info(...)
```

不要靠字符串包含任意 `src` / `dst` 单词做模糊过滤，使用固定前缀。

### 6.3 必须新增测试

配置：

```json
{
  "sampling": {
    "src": {"mode": "wrong_mode"},
    "dst": {"mode": "pose_balanced"}
  }
}
```

断言：

- SRC warnings 包含 `sampling.src:`；
- DST warnings 不包含该 SRC warning；
- DST requested mode 仍为 `pose_balanced`；
- base/global unknown field warning 的行为有明确测试。

### 6.4 完成标准

一侧配置错误不会让另一侧日志看起来也错误，R1-04 才算关闭。

---

## 7. 必修问题 R1-05：min/max equality 与权威文档不一致

### 7.1 当前问题

权威 options-json 文档要求：

```text
min_sample_weight < max_sample_weight
```

当前实现只拒绝：

```python
if min_weight > max_weight:
```

所以：

```json
{
  "min_sample_weight": 1.0,
  "max_sample_weight": 1.0
}
```

会被接受。

这可能把所有权重压成相同值，使智能采样退化，却没有 warning。

### 7.2 必须修复

改为：

```python
if min_weight >= max_weight:
```

继续使用安全默认：

```text
0.5 / 2.0
```

并输出 warning。

不要自动交换用户输入，因为 equality 无法通过交换解决，而且静默改值不利于排查。

### 7.3 必须新增测试

至少覆盖：

```text
min > max
min == max
base 中 equality
src override 中 equality
```

断言：

- 回到 `0.5 / 2.0`；
- warning 存在；
- SRC equality 不改变 DST 合法配置。

### 7.4 完成标准

代码、测试和 v1.1 文档对严格 `<` 完全一致，R1-05 才算关闭。

---

## 8. 必须补齐的集成测试矩阵

当前测试数量增加不等于真实调用链已闭环。修复后至少覆盖以下场景。

### 8.1 ModelBase

- persisted 错误顶层 key，无 options-json，也 warning；
- 新 options-json 错误顶层 key warning；
- 正确嵌套 enhancements 不 warning；
- 嵌套 dict 通过真实 `load_train_step_config()` 保持 mapping；
- non-empty options-json 继续跳过交互 override；
- 错误 JSON 不伪装为 Metadata missing。

### 8.2 EnhancementConfig / SamplingConfig

- empty/default；
- flat config 两侧共享；
- src/dst 独立；
- base + side override；
- 缺失侧使用 base；
- invalid side type；
- side warning 隔离；
- invalid mode；
- unknown field；
- unsupported schema；
- NaN/Inf；
- `min > max`；
- `min == max`；
- to_dict roundtrip 保留 src/dst。

### 8.3 Runtime / SAEHD 接线

- 双 Gate 四组合；
- Gate 关闭不调用 SampleLoader；
- SRC requested quality，DST requested pose；
- SAEHD 式显式 config + source 传参；
- startup log 显示 `base+src_override` / `base+dst_override`；
- SRC loaded、DST missing 时只 DST fallback；
- SRC invalid config 不改变 DST requested mode；
- side seed 优先；
- 默认 seed 使用 +1000/+2000；
- relative path 按各侧根目录；
- Unicode path；
- `..` escape 在 fallback 前抛错。

### 8.4 交互持久化

- 已保存 src/dst 配置进入 Override 后仍保留；
- Gate 关闭后 src/dst 仍保留；
- normalize/to_dict roundtrip 后仍保留；
- 后续 model save 所使用的 `self.options["enhancements"]` 不退化为 flat-only。

---

## 9. 建议执行命令

按当前 Windows Python 环境使用实际解释器，至少执行：

```text
python -m compileall core/enhancements samplelib/sampling models/Model_SAEHD models/ModelBase.py
python -m unittest tests.test_options_json
python -m unittest tests.smoke.test_batch2_sampling_config
python -m unittest tests.smoke.test_batch2_saehd_sampling_options
python -m unittest tests.smoke.test_batch2_sampling_fallback
python -m unittest tests.smoke.test_batch2_sampling_logging
python -m unittest tests.smoke.test_batch1_config_defaults
```

然后执行：

```text
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

记录必须区分：

```text
focused Ticket 15 tests: Ran N / OK / shell exit 0
full Batch 2 assertions: Ran N / OK
full Batch 2 process exit: 0 或 BLOCKED-BY-TICKET16
```

禁止把：

```text
Ran N / OK + shell exit -1073740791
```

写成“全量回归 PASS”。可以写“断言通过，但进程退出被 Ticket 16 阻断”。

---

## 10. 修复提交要求

修复 Agent 必须提交：

1. 一个只包含 Ticket 15 remediation 的实现 commit；
2. 更新后的 Ticket 15 Summary；
3. 完整 Base / Previous Head / New Head SHA；
4. 实际修改函数列表；
5. focused tests 的真实 Ran N、OK/FAIL、shell exit；
6. full Batch 2 的 assertions 与 process exit 分开记录；
7. 本报告 R1-01 至 R1-05 的逐项关闭证据；
8. 未完成 Windows GPU / Ticket 16 项继续明确标记范围外。

推荐 commit message：

```text
fix(sampling): address Ticket 15 review findings
```

不要把多个 Ticket 混入同一 commit。

---

## 11. Round 2 Reviewer 验收清单

只有以下全部满足，Round 2 才可以考虑 PASS：

- [ ] 最终 `self.options` 检测 persisted + injected 错误顶层 keys；
- [ ] 正确嵌套 enhancements 无误报；
- [ ] SAEHD 真实显式接线保留准确 config source；
- [ ] startup log 可证明 SRC/DST 来源和 requested mode；
- [ ] 普通 Override 不删除 src/dst；
- [ ] side warning 不污染另一侧；
- [ ] `min >= max` 均回安全默认并 warning；
- [ ] SRC loaded / DST fallback 独立性测试；
- [ ] SRC invalid / DST valid 独立性测试；
- [ ] focused Ticket 15 tests exit 0；
- [ ] Summary 不再把非零 shell exit 写成全量回归 PASS；
- [ ] options-json v1.1 文档与最终实现一致；
- [ ] Ticket 16/17/19/20 未被顺手修改。

满足后可签发：

```text
APPROVED
PASS
TICKET 15 CONFIG CONTRACT CLOSED
```

在此之前维持：

```text
CHANGES REQUIRED
TICKET 15 REMEDIATION OPEN
TICKET 20 BLOCKED
METADATA SAMPLING NOT PRODUCTION READY
```
