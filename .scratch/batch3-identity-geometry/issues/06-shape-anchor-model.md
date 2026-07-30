# B3-06 Shape Anchor 数据模型、生成契约与身份绑定

## 1. 基本信息

- Ticket ID：`B3-06`
- 状态：`BLOCKED-BY-B3-01`
- 优先级：P0
- 前置 Ticket：B3-01
- 阻塞 Ticket：B3-07、B3-08、Batch 4 Template 设计
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

Batch 3 需要一个稳定的 src 身份几何参考，但不能提前实现 Batch 4 的 `model_name.srcshape` Geometry Bridge。两者职责必须分开：

- Batch 3 Shape Anchor：训练内部参考资产，证明 src faceset 的 canonical geometry 可稳定生成和验证。
- Batch 4 Source Shape Template：面向 Merge 的正式、可发现、可版本化桥接资产。

Batch 3 Anchor 必须复用 Batch 2 的 sample identity、faceset fingerprint 和 ordinary/packed 兼容规则，不得新建绝对路径身份体系。

## 3. Scope

### In Scope

- 定义 `ShapeAnchorV1` 数据类和 JSON schema。
- 定义候选样本、canonical landmarks、ratio vector、confidence、provenance。
- 定义普通/Packed faceset 的身份和 fingerprint 绑定。
- 定义确定性聚合输入输出契约。
- 定义 Batch 4 可消费但不承诺 Merge API 的中间字段。

### Out of Scope

- 不实现 `.srcshape`。
- 不实现 Merge 自动发现。
- 不写入模型权重、optimizer 或 `data.dat` 核心格式。
- 不实现大型 embedding、3DMM 或身份网络。
- 不允许多 identity 聚合成一个 Anchor。

### Forbidden Changes

- 禁止使用绝对文件路径作为稳定 sample identity。
- 禁止把 Anchor 嵌入 DFLJPG/DFLPNG 或 `faceset.pak`。
- 禁止使用 NaN/Inf JSON。
- 禁止只保存一个总体 confidence 而不保存样本统计和过滤原因。
- 禁止把 Batch 3 Anchor 文件命名为 `.srcshape`。
- 禁止把单张用户指定图片无校验地作为 Anchor。

## 4. 当前代码锚点

- `samplelib/metadata/identity.py::normalize_sample_path`
- `samplelib/metadata/identity.py::build_sample_key`
- `samplelib/metadata/identity.py::build_sample_id`
- `samplelib/metadata/fingerprint.py::SampleSignature`
- `samplelib/metadata/fingerprint.py::build_signature_from_sample`
- `samplelib/metadata/schema.py::MetadataValidationIssue`
- `samplelib/metadata/schema.py::sanitize_finite_json`
- `facelib/LandmarksProcessor.py::get_transform_mat`
- `facelib/LandmarksProcessor.py::transform_points`
- Batch 2 metadata loader/analyzer 的 fingerprint 实现

## 5. 目标目录与文件

```text
core/enhancements/geometry/
├── anchor_schema.py
├── anchor_builder.py
├── canonical.py
└── ratios.py
```

默认训练内部资产名：

```text
faceset_shape_anchor.v1.json
```

默认位置由 B3-07 冻结；本 Ticket 只定义内容，不定义自动发现优先级。

## 6. ShapeAnchorV1 Schema

```json
{
  "schema_version": 1,
  "generator_version": "batch3-anchor-v1",
  "identity_namespace": "dfl-faceset-v1",
  "source_identity": {
    "role": "src",
    "person_name": null
  },
  "faceset_fingerprint": {
    "mode": "quick",
    "value": "...",
    "sample_count": 0
  },
  "landmark_schema": "dlib-68",
  "canonical_landmarks": [[0.0, 0.0]],
  "ratio_names": [
    "face_width_over_height",
    "jaw_width_over_face_width",
    "chin_length_over_face_height",
    "cheek_width_over_face_width",
    "eye_distance_over_face_width",
    "nose_width_over_face_width"
  ],
  "ratio_values": [0.0],
  "confidence": 0.0,
  "sample_summary": {
    "input_count": 0,
    "valid_count": 0,
    "selected_count": 0,
    "rejected_by_reason": {}
  },
  "aggregation": {
    "method": "median",
    "trim_fraction": 0.0,
    "canonicalization": "face-aligned-v1"
  },
  "provenance": {
    "metadata_schema_version": 1,
    "created_at_utc": "...",
    "source": "offline_faceset"
  }
}
```

硬约束：

- `canonical_landmarks` 精确为 `[68,2]`、float32 语义、有限、推荐范围 `[0,1]`。
- `ratio_names` 顺序固定；`ratio_values` 长度必须一致。
- JSON 序列化使用标准有限数值；不得输出 `NaN`。
- confidence 范围 `[0,1]`。
- `valid_count <= input_count`，`selected_count <= valid_count`。
- `role` 第一版只允许 `src`。

## 7. 候选与聚合契约

候选输入：

```python
@dataclass(frozen=True)
class ShapeAnchorCandidate:
    sample_id: str
    sample_key: str
    canonical_landmarks: np.ndarray  # [68,2] float32
    ratio_values: np.ndarray         # [R] float32
    quality_score: float
    landmark_confidence: float
    yaw: float
    pitch: float
    occlusion_score: float | None
```

最低过滤：

- landmarks 存在且 68 点。
- 全部有限。
- canonical transform 可逆且非退化。
- pose/quality/confidence 达到配置阈值。
- ratio 分母大于 epsilon。
- sample identity 与当前 src faceset 一致。

聚合：

1. 先对每个候选 canonical normalize。
2. 对固定 ratio 逐项做 robust outlier 过滤。
3. 第一版使用 coordinate-wise median；trimmed mean 只作为可测试替代，不自动选择。
4. 输出聚合后 ratio 并重新计算一致性。
5. confidence 必须综合样本数、分布离散度、landmark confidence 和 pose 覆盖；公式由本 Ticket 测试固定。

## 8. 与 Batch 4 的边界

Batch 3 必须保证以下字段可被 Batch 4读取：

```text
schema_version
generator_version
source_identity
faceset_fingerprint
canonical_landmarks
ratio_names/ratio_values
confidence
sample_summary
```

但 Batch 3 不定义：

- 模型名绑定；
- Merge discovery；
- 用户显式 Template 优先级；
- `.srcshape` 生命周期；
- Hybrid Landmark。

## 9. 实施步骤

1. 建立 dataclass 和纯 schema validation。
2. 复用 `sanitize_finite_json` 或提取共享有限 JSON helper；不得复制不同规则。
3. 建立 canonicalization helper，输入原图 landmarks 和 face type，输出 `[68,2]`。
4. 建立固定 ratio 定义和索引常量。
5. 建立 candidate validator 和 reject reason enum。
6. 建立 deterministic median aggregator；固定输入排序按 `sample_id`，避免并行遍历顺序影响结果。
7. 建立 confidence 纯函数。
8. 生成/读取逻辑分离；本票不做缓存。

## 10. 测试要求

测试文件：

- `tests/smoke/test_batch3_shape_anchor_schema.py`
- `tests/smoke/test_batch3_shape_anchor_builder.py`

必须覆盖：

- ordinary 与 packed 使用相同 canonical sample identity。
- Unicode、中文、空格路径。
- 68 点 shape、错误点数、非有限、退化 transform。
- 候选顺序打乱后 Anchor byte-level canonical JSON 一致（时间字段除外，应可注入 clock）。
- median/outlier/filter reason。
- sample count 不足。
- fingerprint mismatch。
- JSON 不产生 NaN/Inf。
- 多 identity 混合必须拒绝。
- 不创建 `.srcshape`。

命令：

```bash
python -m unittest tests.smoke.test_batch3_shape_anchor_schema -v
python -m unittest tests.smoke.test_batch3_shape_anchor_builder -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- Schema、ratio 顺序、identity/fingerprint 规则已冻结。
- 生成确定性有证据。
- ordinary/packed/Unicode 兼容。
- 不修改原图、pak、checkpoint 或 Merge。
- 与 Batch 4 边界明确。
- Summary、Review、SHA 齐全。

## 12. Review 检查表

- 是否误用绝对路径？
- 是否把 Batch 4 `.srcshape` 提前实现？
- 是否允许 NaN JSON？
- 是否因遍历顺序产生不同 Anchor？
- 是否遗漏 ratio 名称顺序？
- 是否混入 DST identity？

## 13. 交付物

- `core/enhancements/geometry/anchor_schema.py`
- `anchor_builder.py`、`canonical.py`、`ratios.py`
- 两个 smoke tests
- Schema 示例
- Summary、Review、Commit SHA
