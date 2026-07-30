# B3-04 Loss 结果、日志与 requested/effective

- 前置：B3-02,B3-03；P0。
- 目标：定义统一 `LossTermResult` 与启动/迭代日志，区分 requested、effective、weight、raw、weighted、fallback_reason。
- 修改：`core/enhancements/` 新结果模型和格式化器；测试。不得接 SAEHD。
- 日志不得逐样本刷屏；关闭项默认不进入每 iter 明细，但启动摘要必须可见。
- 测试：稳定字段顺序、None/disabled/fallback/finite、序列化与中文路径。
- 完成：日志样例、测试、Summary、Review、SHA。