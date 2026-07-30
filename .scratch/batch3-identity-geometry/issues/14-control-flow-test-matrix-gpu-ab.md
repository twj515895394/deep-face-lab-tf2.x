# B3-14 控制流、Master Matrix 与 Windows GPU A/B

- 前置：B3-13；P0。
- 目标：回归 Loss Window、manual save、exit、resume、异常资源清理；建立自动测试和 Windows GPU Geometry A/B 规约。
- 自动门：全部 Batch3 unit/smoke/integration/compat/failure/determinism；同时运行现有 `test_batch*.py` 防回归。
- GPU 矩阵：baseline off、ratio only、landmark only、combined；ordinary/packed；短 smoke 与长视觉 A/B 分开记录。
- 指标：启动配置、iter/loss、有限值、save/resume、资源差集、脸型稳定性与表情保留；人工结论必须附素材和日志。
- 未执行必须标 `NOT EXECUTED`，不得沿用 Batch2 豁免写 PASS。
- 完成：两份矩阵、执行命令、结果模板、Summary/Review/SHA。