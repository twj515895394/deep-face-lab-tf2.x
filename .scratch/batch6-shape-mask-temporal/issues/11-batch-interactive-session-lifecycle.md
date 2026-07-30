# B6-11 Batch/Interactive/Session/Worker Temporal生命周期与顺序保证

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；前置B6-02/07/09/10；阻塞B6-13。
- 目标：把Mask/Temporal接入实际批处理与InteractiveMerger，保证帧顺序、state所有权、prefetch和session恢复正确；不改变filter数学。

## 核心设计风险

`InteractiveMergerSubprocessor`可并行prefetch多个帧，Temporal却依赖严格时间顺序。不得让worker各自持有不一致state或乱序更新。

## 生命周期草案

- Temporal state由主进程/有序协调层单一拥有；worker执行无状态Mask/Warp或接收已冻结参数。
- 若必须在worker滤波，process_count需限制为1或建立有序提交队列；最终方案在B6-01真实性能审计后冻结。
- 结果只有在frame cfg/hash仍匹配且前序状态版本一致时提交。
- rewind/重新处理帧必须重建或从安全checkpoint重放state；第一版可在rewind时清空并从目标起点禁用/重算，禁止继续旧未来state。
- session pickle不信任runtime filter对象；恢复时根据frames_done、model/template/config和输出完整性决定reset/replay。
- noninteractive批处理按frame index顺序，scene cut reset。

## Forbidden

不在多个worker独立更新同一face；不接受乱序结果覆盖state；不pickle完整mask/frame；不跨session复用未经验证state；不因Temporal降低核心异常等级。

## 测试

`test_batch6_temporal_lifecycle.py`覆盖process_count1/4、乱序完成、stale cfg/result、rewind、prev/next、session恢复、模型iter变化、Template/config变化、close/error、state cleanup和batch/interactive等价。

## 完成定义

state owner、顺序、rewind/session语义有测试；无竞态或跨任务泄漏；Summary、Review、SHA完整。
