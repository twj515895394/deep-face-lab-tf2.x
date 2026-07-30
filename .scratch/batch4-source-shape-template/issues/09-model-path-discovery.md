# B4-09 Model命名、默认路径、Discovery与生命周期

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-08；阻塞B4-10/11。
- 目标：把Template与当前模型目录/逻辑模型名安全关联，并向未来Merger提供只读发现结果；不改变Merge算法。

## 代码锚点

`ModelBase.get_model_name/get_model_root_path/get_strpath_storage_for_file`、模型rename/delete流程、`get_MergerConfig`调用链、Merger启动参数。

## 设计

- 默认文件名必须沿用真实模型命名约定，避免`model_name.srcshape`与`<model>_SAEHD_srcshape`歧义；B4-01后冻结一个helper `get_source_shape_template_path(model)`。
- 模型rename时，Template应与同前缀资产一起rename；delete时按现有模型资产规则处理并有测试。
- copy模型目录后identity校验决定是否trusted，不仅看路径。
- 向Merger暴露`TemplateDiscoveryResult`，只含path/source/exists/reason；内容加载仍由B4-08。
- 缺失Template不产生fatal，传统Merge继续。

## Forbidden

- 不修改权重/`data.dat`。
- 不递归扫描saved_models_path。
- 不按最新mtime猜模型。
- 不在predictor函数中每帧发现文件。
- 不改变旧模型选择/rename/delete交互语义。

## 测试

`test_batch4_template_model_lifecycle.py`覆盖新/旧模型、空格/中文模型名、rename/delete/copy、多个模型并存、默认路径、缺失、同名冲突、只发现固定文件和每会话一次发现。

## 完成定义

唯一命名helper、lifecycle和discovery结果有测试；无Merge行为变化；Summary、Review、SHA完整。
