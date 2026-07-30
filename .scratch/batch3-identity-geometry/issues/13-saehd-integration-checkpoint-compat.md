# B3-13 SAEHD 主链路与 Checkpoint 兼容

- 前置：B3-02～B3-12 全部完成并 Review；P0。
- 目标：把稳定的 Hook/Geometry/Curriculum 接入 `models/Model_SAEHD/Model.py`，保持关闭时图、总 loss、梯度和 optimizer 行为等价。
- 锚点：`SAEHDModel.on_initialize_options`、graph loss 构建、`onTrainOneIter`、loss 返回与启动日志；保存恢复通过 ModelBase 既有入口。
- 必须：单项 loss 可观测；requested/effective 可见；旧 checkpoint 缺字段默认关闭；optimizer slot 不新增非必要状态。
- 禁止：改权重文件格式、DFM、Merge、采样、网络结构、宽泛异常回退。
- 测试：flag-off baseline、flag-on graph、旧 options/checkpoint fixture、save/exit/resume、non-finite propagation。
- 完成：集成 diff 受限、测试、Summary、独立 Review/SHA。