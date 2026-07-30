# B3-07 Anchor 加载、缓存、失效与回退

- 前置：B3-02,B3-06；P0。
- 目标：实现显式路径加载、单进程缓存、fingerprint/version/layout 失效与 requested/effective 状态。
- 原子读取；不得自动重写 aligned 数据；不得在 worker 中重复解析。
- 缺失/陈旧在 fallback 模式关闭 geometry；strict 模式抛专用错误。核心 IO/OOM 不得吞掉。
- 测试：ordinary/packed identity、Unicode/空格路径、stale、损坏、缓存命中和进程边界。
- 完成：loader API、失效表、测试、Summary/Review/SHA。