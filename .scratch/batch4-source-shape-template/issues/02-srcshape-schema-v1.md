# B4-02 `.srcshape` Schema v1、版本、有限JSON与Consumer契约

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-01；阻塞B4-05/06/08。
- 目标：定义Batch 5可读取的权威Geometry Bridge资产，不实现来源选择或Merge。

## 目标Schema

至少冻结：`schema_version`、`generator_version`、`consumer_min_version`、`model_identity`、`source_identity`、`faceset_fingerprint`、`landmark_schema`、`canonical_space`、`canonical_landmarks[68,2]`、`ratio_names/values`、`confidence`、`quality`、`sample_summary`、`aggregation`、`provenance`、`created_at_utc`。

## 规则

- UTF-8标准JSON；禁止NaN/Inf；数组float32语义。
- ratio名称和顺序必须与最终Batch3契约一致。
- unknown字段可保留roundtrip，但不得影响旧consumer。
- 更高unsupported schema必须拒绝Shape能力并允许传统Merge。
- 必填字段缺失、点数/shape错误、identity空、confidence越界均invalid。
- 文件不得包含绝对用户素材路径、原图、landmark样本明细或隐私数据。

## 目标文件

`core/enhancements/shape_template/schema.py`和`contracts.py`；复用共享finite JSON helper，不复制第二套规则。

## Forbidden

- 不写权重/data.dat/DFM。
- 不把内部Batch3 Anchor直接改扩展名伪装Template。
- 不实现自动迁移未知未来版本。
- 不把consumer-specific Merge缓存写入Schema。

## 测试

`tests/smoke/test_batch4_srcshape_schema.py`覆盖合法最小/完整文档、unknown字段、旧/高版本、NaN/Inf、68点、ratio顺序、Unicode、标准JSON严格序列化、隐私路径拒绝和byte-stable canonical serialization（clock可注入）。

## 完成定义

Schema/validation/serialization/consumer contract均有测试、示例、Summary、Review和SHA；B4-01差异已吸收。
