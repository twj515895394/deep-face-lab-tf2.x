# Batch 2 最终审计补充契约

> 状态：**MANDATORY / 开发前强制阅读**  
> 适用范围：Batch 2 Ticket 01-12  
> 审计日期：2026-07-29  
> 目的：冻结主分支合并后新增的兼容要求、算法常量、配置优先级和可量化验收条件，避免能力较弱的模型各自猜测实现。

---

## 1. 约束优先级

执行模型遇到说明不一致时，按以下顺序处理：

```text
当前源码事实
→ 本最终审计补充契约
→ 当前 Ticket
→ Batch 2 正式详细设计
→ Agent 自行判断
```

若当前源码事实与本文件冲突，必须停止编码并标记 `blocked-source-contract-mismatch`，不得自行扩大范围。

本文件不是新增 Batch 2 功能范围，只负责消除原 Ticket 中仍可能存在的歧义。

---

## 2. 主分支合并后的固定事实

Batch 2 分支已经包含主分支新增能力：

- `--options-json` 从 `main.py` 透传到 `Trainer` 和 `ModelBase`；
- `ModelBase.load_train_step_config()` 在 `on_initialize_options()` 前覆盖 `self.options`；
- 传入非空 `options_json` 时启用 silent start，并跳过已有模型的交互 override；
- 项目已加入中文路径和 UTF-8 兼容改造；
- `Sample.load_bgr()` 通过项目 `cv2ex` 路径读取普通与 Packed 样本；
- `SampleGeneratorFace` 当前含 legacy random、128 格 legacy uniform yaw、random color transfer 和 FP16 IPC 传输优化；
- Batch 2 不得破坏上述能力。

Ticket 01 必须以实际开工时 HEAD 为基线，不得继续把 2026-07-27 的设计 commit 当作运行时代码基线。

---

## 3. 全 Ticket 通用 Unicode 与文件格式契约

### 3.1 路径

所有 Ticket 必须覆盖：

- 中文目录和文件名；
- 路径中含空格；
- 非 ASCII 人名目录；
- 至少一个 emoji 或扩展 Unicode 测试名；
- Windows 路径分隔符和盘符输入；
- ordinary、person、Packed 三种样本身份。

生产代码不得通过 ASCII 编码、默认系统编码或原生 `cv2.imread/cv2.imwrite` 绕过项目 Unicode 路径能力。

### 3.2 JSON 和文本

Metadata、Report、配置示例和 summary 统一：

```python
json.dump(
    data,
    file,
    ensure_ascii=False,
    allow_nan=False,
    indent=2,
)
```

文本文件必须显式使用：

```python
encoding="utf-8"
```

要求：

- JSON 中中文路径可直接阅读，不强制转成 `\uXXXX`；
- 不允许 NaN / Infinity；
- 换行统一使用 `\n`；
- 日志可以显示路径，但不能批量打印完整私有样本列表。

---

## 4. Ticket 01 最终补充：合并后基线

Ticket 01 除原内容外，必须增加以下基线证据。

### 4.1 必跑现有回归

至少尝试执行并记录：

```bash
python -m unittest tests.test_options_json
python -m unittest tests.smoke.test_chinese_path_compatibility
python -m unittest tests.smoke.test_all_features_chinese_path
python -m unittest discover -s tests/smoke -p "test_*.py"
```

依赖缺失时只能标记 `SKIP-DEPENDENCY`，不能写 PASS。

### 4.2 Fixture 路径

ordinary 和 Packed fixture 至少各在以下环境运行一次：

```text
<temp>/批次 02 测试/人物甲/aligned
```

并增加一个包含 emoji 的文件名用于 identity/JSON 测试。真实 DFL 读取不支持的文件名场景，应在 summary 明确记录，不得静默删掉该测试。

### 4.3 `--options-json` 基线

记录当前链路：

```text
main.py
→ Trainer.main/trainerThread
→ ModelBase(options_json)
→ load_train_step_config
→ SAEHD on_initialize_options
```

Ticket 10 将依赖该基线，因此 Ticket 01 summary 必须说明：

- options JSON 的注入时机；
- silent start 行为；
- `self.options["enhancements"]` 是否可接收嵌套 mapping；
- 当前无 options JSON 时行为是否完全不变。

---

## 5. Ticket 02 最终补充：Unicode Sample Identity

### 5.1 Canonical Sample Key

在原路径规则基础上增加：

```python
unicodedata.normalize("NFC", component)
```

规范化顺序固定为：

```text
取得逻辑相对路径
→ 分隔符统一为 /
→ 移除空的和 . component
→ 拒绝绝对路径、盘符和 ..
→ 每个 component 做 NFC
→ 保留大小写
→ 使用 / 重新连接
```

原始 `filename/person_name` 可以作为展示字段保存，但 `sample_key` 使用 NFC canonical 值。

### 5.2 Collision

必须检测：

- 两个原始路径经 NFC 后变成同一个 key；
- 大小写不同但 case-fold 相同；
- person 目录不同但 basename 相同；
- duplicate sample ID。

NFC collision 和 case-fold collision 只能报告，不得静默合并或自动选择。

### 5.3 必须增加的测试

```text
中文/人脸 001.jpg
中文/人脸_😀.jpg
C:\数据集\人物甲\aligned\0001.jpg
NFC 与 NFD 等价名称
大小写冲突名称
ordinary → packed → same sample_key
```

Dataset fingerprint 的 canonical JSON 同样必须 UTF-8、稳定排序、`ensure_ascii=False`。

---

## 6. Ticket 03 最终补充：冻结 Analyzer v1 常量

Ticket 03 不得再自行选择阈值或权重。第一版固定以下契约，并写入 `analysis_config`。

### 6.1 Pose v1

源码返回弧度，范围约为 `[-pi/2, +pi/2]`。

Yaw 数值边界固定：

```text
yaw <= -0.80                 negative_extreme
-0.80 < yaw <= -0.45         negative_major
-0.45 < yaw <= -0.20         negative_minor
-0.20 < yaw < 0.20           front
0.20 <= yaw < 0.45           positive_minor
0.45 <= yaw < 0.80           positive_major
yaw >= 0.80                  positive_extreme
pose invalid                 unknown
```

对外最终显示为 left/right 前，必须用 fixed landmark fixture 确认项目符号。现有 legacy uniform yaw 使用 `s_yaw = -pyr[1]`，不得仅凭名称猜左右。

若 fixture 证明正负与设计名称相反：

- 数值边界不变；
- 修正 left/right 映射；
- 更新测试和 summary；
- 不修改 `get_pitch_yaw_roll()`。

Pitch 固定：

```text
pitch <= -0.25         up
-0.25 < pitch < 0.25   level
pitch >= 0.25          down
invalid                unknown
```

### 6.2 Image/Gray v1

```python
bgr = np.asarray(sample.load_bgr(), dtype=np.float32)
bgr = np.clip(bgr, 0.0, 1.0)
gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
```

不允许 ordinary 和 Packed 使用不同灰度路径。

### 6.3 Sharpness v1

```python
lap = cv2.Laplacian(gray, cv2.CV_32F)
sharpness_raw = float(np.var(lap, dtype=np.float64))
log_sharpness = np.log1p(max(sharpness_raw, 0.0))
```

全 faceset 使用 finite raw 值计算 p05/p95：

```text
sharpness_score = clip((log_value - p05) / (p95 - p05), 0, 1)
```

当有效样本少于 2 个或 `p95-p05 <= 1e-8` 时，所有有效图片的 `sharpness_score=0.5`，并记录 `sharpness_distribution_degenerate`。

### 6.4 Exposure v1

固定常量：

```text
dark_threshold = 16 / 255
bright_threshold = 239 / 255
exposure_clip_tolerance = 0.20
```

公式：

```python
dark_ratio = mean(gray <= dark_threshold)
bright_ratio = mean(gray >= bright_threshold)
exposure_penalty = clip(
    (dark_ratio + bright_ratio) / exposure_clip_tolerance,
    0.0,
    1.0,
)
exposure_score = 1.0 - exposure_penalty
```

### 6.5 Quality v1

```python
landmark_factor = 1.0 if landmark_valid else 0.5
quality_score = landmark_factor * (
    0.75 * sharpness_score
    + 0.25 * exposure_score
)
quality_score = clip(quality_score, 0.0, 1.0)
```

语义：

- image invalid：`quality.valid=False`，数值字段为 null；
- image valid + landmark invalid：`quality.valid=True`，使用 0.5 factor；
- quality 不评价身份、美观、遮挡语义或最终换脸效果。

### 6.6 Golden Tests

至少固定：

```text
全黑/全白 exposure_score = 0
无 clipping 的中灰图 exposure_score = 1
退化 sharpness 分布 sharpness_score = 0.5
landmark valid + sharpness 0.5 + exposure 1.0 → quality 0.625
landmark invalid + 同指标 → quality 0.3125
```

浮点断言使用合理容差，例如 `1e-6`。

---

## 7. Ticket 04 最终补充：CLI 与原子文件

### 7.1 CLI 参数

`--workers` 只有 Analyzer 核心真实支持多 worker 时才能注册。否则第一版：

- 不暴露假参数；或
- 显式只接受 `1`，其他值返回参数错误。

### 7.2 原子写

临时文件必须位于目标文件同一目录，名称包含唯一后缀：

```text
.faceset_metadata.v1.json.<pid>.<random>.tmp
```

固定顺序：

```text
UTF-8 serialize
→ flush
→ fsync（平台支持）
→ close
→ 从 temp 重新读取并 Schema validate
→ 可选生成单一 .bak
→ os.replace(temp, target)
→ 清理 temp
```

JSON 必须 `ensure_ascii=False, allow_nan=False`。

### 7.3 Unicode 验收

必须在中文和空格目录执行完整 CLI：

```bash
python main.py faceset-analyze --input-dir "<temp>/批次 02 测试/aligned"
```

控制台、Metadata、Report 和 backup 路径都必须正确。

---

## 8. Ticket 05 最终补充：Loader 状态优先级

`RuntimeMetadata` 增加明确字段：

```python
usable_for_sampling: bool
matched_count: int
missing_count: int
extra_count: int
collision_count: int
fallback_reason: Optional[str]
```

状态决策优先级固定：

```text
文件不存在                    MISSING / usable=False
JSON 或顶层结构损坏           INVALID_FILE / usable=False
schema 过高                  UNSUPPORTED_SCHEMA / usable=False
未解决 identity collision    SAMPLE_KEY_COLLISION / usable=False
fingerprint 相同且完整合法    LOADED / usable=True
fingerprint 不同、ratio 达标  PARTIAL_MATCH / usable=True
ratio 低于阈值                FINGERPRINT_MISMATCH / usable=False
```

要求：

- 上层只读取 `usable_for_sampling`，不得重新解释 status 文本；
- partial 中缺失记录使用中性值；
- `strict=True` 可使 partial 不可用，但不能阻止 legacy 训练；
- `matched_ratio` 在 N=0 时不得除零，N=0 仍由核心 no-data 路径处理。

---

## 9. Ticket 06 最终补充：Config 和 Master Gate

Sampling 配置最终持久化位置固定为：

```python
self.options["enhancements"] = {
    "schema_version": 1,
    "training": {
        "enabled": bool,
        "metadata_sampling": bool,
        ...
    },
    "sampling": {...},
    "runtime": {...},
}
```

智能采样 master 的有效条件是：

```text
training.enabled == True
AND
training.metadata_sampling == True
```

只设置 `metadata_sampling=True` 但 `training.enabled=False` 时，必须保持 legacy。

`SamplingConfig` 只实现一套解析；`EnhancementConfig` 持有它，不复制数值默认和校验。

---

## 10. Ticket 07 最终补充：Pose Weight 输出语义

为避免归一化后突破 bucket 上限，Ticket 07 的输出语义固定为：

- `sample_weights` 是未经 sample-mean 归一化的正权重；
- 每个已知 bucket 权重保持在 `[min_bucket_weight,max_bucket_weight]`；
- unknown 使用固定正权重；
- 理论概率由 `sample_weights / sum(sample_weights)` 计算；
- Ticket 08 负责组合后的 normalize/clip。

Golden case：

```text
bucket counts = [80, 20, 5]
reference = 20
strength = 0.5
bucket weights = [0.5, 1.0, 2.0]
weighted bucket mass = [40, 20, 10]
expected bucket shares = [4/7, 2/7, 1/7]
```

强度为 0 时所有 sample weight 为 1。

---

## 11. Ticket 08 最终补充：Quality Golden Values

当 `quality_strength=0.5`：

```text
q                0       0.25      0.5      0.75      1
smooth_q         0       0.15625   0.5      0.84375   1
quality_weight   0.5     0.65625   1.0      1.34375   1.5
```

组合固定顺序：

```text
pose * quality
→ validate finite/positive
→ clip(min,max)
→ divide by sample mean
→ clip(min,max)
→ validate
→ normalize by sum to probability
→ uniform mix
→ final sum normalization
```

第二次 clip 后不再为了强制 mean=1 无限迭代。最终概率才必须 sum≈1。

---

## 12. Ticket 09 最终补充：Host 确定性和验收

### 12.1 Cycle Size

默认固定：

```python
cycle_size = explicit_value or min(max(N, 4096), 65536)
```

必须记录 cycle 内存和构建耗时。

### 12.2 确定性边界

保证：

- 同 probabilities、seed、单一相同请求序列 → 相同结果；
- 多 CLI 下，按 Host 实际接收请求的顺序可复现；
- 不保证不同 OS 调度下 worker 身份对应到完全相同 batch 序列。

文档不得宣称跨任意并发调度逐 batch 完全一致。

### 12.3 Lifecycle

建议默认：

```text
client poll interval: 0.1s
client operation timeout: 30s
close join timeout: 5s
```

超时必须包含 host fatal/closed 状态和请求类型，不能返回空 indexes。

### 12.4 分布验收

固定 seed，draws 至少 100000。对 bucket/quantile 聚合概率：

```text
allowed_error = max(
    0.01,
    5 * sqrt(p * (1-p) / draws)
)
```

要求 `abs(actual-p) <= allowed_error`。极小概率项主要验证方向、finite 和非零，不做不合理的逐样本窄阈值。

---

## 13. Ticket 10 最终补充：`--options-json` 与配置优先级

### 13.1 数据来源优先级

固定为：

```text
内建默认
→ 已保存 data.dat options
→ --options-json 显式覆盖
→ 交互输入（仅没有 non-interactive override 时）
```

非空 `options_json` 启动时，不得再次用 sampling prompt 覆盖注入值。

### 13.2 GUI/静默启动 JSON 形状

正确示例：

```json
{
  "enhancements": {
    "schema_version": 1,
    "training": {
      "enabled": true,
      "metadata_sampling": true
    },
    "sampling": {
      "mode": "quality_pose_balanced",
      "metadata_path": null,
      "fallback_mode": "legacy_random",
      "pose_balance_strength": 0.5,
      "quality_strength": 0.5,
      "uniform_mix": 0.1,
      "min_sample_weight": 0.5,
      "max_sample_weight": 2.0,
      "min_metadata_match_ratio": 0.9,
      "seed": 12345,
      "log_interval_draws": 10000
    }
  }
}
```

禁止把 `sampling` 错放为 `self.options` 的独立顶层键。

### 13.3 必须增加的测试

- 无 `--options-json`：旧交互行为不变；
- 现有模型 + options JSON：无倒计时、无 sampling prompt、配置生效；
- options JSON 中 `training.enabled=false`：即使 metadata_sampling=true 仍 legacy；
- options JSON 嵌套 sampling mapping roundtrip；
- 中文 metadata_path；
- 旧模型无 enhancements；
- options JSON 损坏仍按当前 ModelBase 错误语义处理，不伪装成 Metadata missing；
- 保存恢复后 requested/effective 一致。

---

## 14. Ticket 11 最终补充：量化验收门槛

### 14.1 Legacy Off

在相同 checkpoint、数据、batch 和 worker 条件下，与 W1 baseline 比较：

```text
median iter time regression <= 3%
p95 iter time regression <= 5%
```

超出时先重复测量；仍超出则 FAIL 或明确阻断，不能只写“可接受”。

### 14.2 Weighted Mode

第一版工程验收门槛：

```text
median iter time regression <= 5%
p95 iter time regression <= 10%
generator samples/sec regression <= 10%
```

超出门槛不一定否定算法价值，但 Batch 2 不得直接标记完整 done，必须有原因、profile 和处理结论。

### 14.3 Host 热路径

在验收机器、常用 batch size 下记录：

```text
multi_get p95 <= 5 ms
stats snapshot p95 <= 5 ms
close 后 5 s 内退出
```

### 14.4 Startup

记录 Metadata load、policy build 和 Host build。新增启动耗时超过：

```text
max(5 seconds, W1 startup time * 20%)
```

必须分析并给出结论。

### 14.5 验收证据

每个性能结论至少基于 3 次运行或 3 个稳定窗口，报告 median，不以单次最好结果作为 PASS。

---

## 15. Ticket 12 最终补充：用户文档

最终用户文档必须同时包含：

- 交互式启用示例；
- `--options-json` 静默启动示例；
- `enhancements.training.enabled` 与 `metadata_sampling` 双 gate 说明；
- 中文/Unicode 路径示例；
- JSON/Report UTF-8 说明；
- ordinary/person/Packed 区别；
- sampler draw state 不持久化；
- 性能验收结果；
- fallback reason 对照；
- 明确动态 Loss sampler 和脸型训练未实现。

---

## 16. 每个 Ticket Summary 新增合规表

每个 Ticket summary 末尾增加：

```markdown
## 最终审计契约合规

| 项目 | 状态 | 证据 |
|---|---|---|
| Unicode/UTF-8 | PASS/SKIP/NA | 命令或测试 |
| 算法/接口固定值 | PASS/NA | 测试 |
| --options-json 兼容 | PASS/NA | 测试 |
| legacy 关闭路径 | PASS | 测试 |
| Windows/GPU | PASS/PENDING/NA | 报告 |
| 性能门槛 | PASS/PENDING/NA | 数据 |
```

没有证据的项目不得写 PASS。

---

## 17. 最终判断

完成本补充后，Ticket 01-08 可交给能力偏弱模型逐个开发。Ticket 09、10 即使由弱模型实现，也必须由较强模型或人工做独立 code review。Ticket 11 必须在真实 Windows GPU 环境执行，不能交由纯代码模型根据日志模板自行宣称完成。
