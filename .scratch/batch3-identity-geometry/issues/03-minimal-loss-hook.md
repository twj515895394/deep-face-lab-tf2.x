# B3-03 Minimal Loss Hook API 与零影响

- 状态：BLOCKED-BY-B3-01；P0；前置 B3-01。
- 目标：在 `core/enhancements/` 建立纯组合式 loss hook API，输入命名 tensor/context，输出附加 loss 列表；未注册或关闭时返回空结果。
- 接口必须包含 name、raw_value、weighted_value、weight、finite、effective、reason；注册顺序确定且可测试。
- 禁止直接接 SAEHD、修改 optimizer、改变旧 loss 表达式、捕获核心 TensorFlow 异常。
- 测试：空 registry 零影响、顺序、重复名、disabled hook、异常传播、float32 保持。
- 完成：API 文档、unit/smoke、基线等价断言、Summary/Review/SHA。