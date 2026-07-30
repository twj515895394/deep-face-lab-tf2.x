# B4-06 Batch 3 Anchor/训练派生 Candidate Adapter

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-02和Batch3最终产物；阻塞B4-07。
- 目标：把最终ShapeAnchorV1或经批准的训练派生几何摘要转换为统一`TemplateCandidate`，不从网络权重推测新几何。

## In Scope

- Adapter读取Batch3 Anchor/runtime report，校验schema、identity、fingerprint、ratio顺序和confidence。
- 明确来源`batch3_anchor`或`training_export`，保留provenance。
- 对字段缺失建立显式兼容映射；不能转换时返回reason，不猜默认正值。
- 输出与B4-05完全相同的candidate接口。

## Out/Forbidden

- 不读取encoder/decoder权重并计算embedding。
- 不修改Batch3 Anchor。
- 不把单次训练loss数值当Template geometry。
- 不绕过identity/fingerprint。
- 不直接写`.srcshape`。

## 目标代码

`core/enhancements/shape_template/training_adapter.py`，纯输入对象/文件到candidate的转换，clock和版本可注入。

## 测试

`test_batch4_training_candidate_adapter.py`覆盖最终Batch3 schema、旧草案schema拒绝/迁移、ratio顺序变化、confidence低、fingerprint stale、Unicode路径、candidate与offline接口一致、输入对象不被修改。

## 完成定义

Adapter无模型图依赖、无GPU依赖、无权重猜测；所有兼容映射有文档和测试；Summary、Review、SHA完整。
