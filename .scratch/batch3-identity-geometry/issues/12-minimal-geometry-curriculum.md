# B3-12 Minimal Geometry Curriculum

- 前置：B3-04,B3-11；P1。
- 目标：实现 `reconstruction -> geometry_ramp -> geometry_stable` 三阶段确定性权重调度。
- 输入：global iter、warmup_iters、ramp_iters、目标权重；输出 stage、progress、effective weights。
- 恢复：优先由已保存 iter 重建，不新增 optimizer slot；旧 checkpoint 缺配置时关闭。
- 修改建议：`core/enhancements/geometry/curriculum.py`；不得实现通用 multi-objective curriculum。
- 测试：边界 iter、零 ramp、恢复等价、非法配置、ratio/landmark 独立目标权重。
- 完成：状态机表、测试、Summary/Review/SHA。