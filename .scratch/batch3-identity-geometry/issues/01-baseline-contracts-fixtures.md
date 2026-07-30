# B3-01 基线冻结、契约与 Fixtures

- 状态：READY-AFTER-DOC-REVIEW；优先级：P0；前置：无；阻塞：B3-02/B3-03/B3-06。
- 目标：记录当前 SAEHD loss/feed/save 调用链，冻结 NHWC、batch、mask、float32 统计和非有限值规则，建立纯 NumPy fixtures。
- 修改：仅 `tests/smoke/` fixtures、Batch3 文档；不得修改训练实现。
- 锚点：`models/Model_SAEHD/Model.py::_unpack_training_samples`、`_validate_eyes_mouth_mask`、`SAEHDModel`；`models/ModelBase.py` 保存恢复入口。
- 输出：baseline snapshot、shape/dtype/mask contract、valid/invalid landmark/ratio fixtures、旧行为断言。
- 测试：新增 `tests/smoke/test_batch3_contracts.py`，覆盖 shape、dtype、mask、NaN/Inf、空 batch、默认关闭。
- 完成：测试命令与结果、Summary、Review、SHA 齐全；不声称 GPU PASS。