# B6-01 Batch 5输出复核、Mask/Temporal基线、坐标与Fixtures

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P0；阻塞B6-02/03/08。
- 目标：Batch5完成后读取最终WarpResult、coverage、QualityResult、Merge顺序和多脸生命周期，冻结Batch6所有输入；本票不实现Mask/Filter。

## 审计

- 最终Hybrid landmarks、warped image/mask、coverage、reason/metrics。
- `MergeMaskedFace`实际mask mode、resize、erode/blur、inverse affine、blend顺序。
- `InteractiveMergerSubprocessor.Frame`的prev/current/next infos、worker/prefetch/session和多脸列表。
- 帧命名/排序、scene变化和landmark list身份可用程度。

## 冻结契约

- image/mask/coverage layout、dtype、范围和坐标空间。
- face/frame/track identity可用字段；若不存在稳定track id，冻结保守禁用跨帧策略。
- mask baseline golden outputs和power/Gate off hash。
- temporal输入时间戳/帧序号语义，不用wall clock猜视频间隔。
- 单脸、多脸、检测顺序交换、scene cut、丢脸、遮挡、快速运动fixtures。

## Forbidden

不假设Batch5草案字段就是最终字段；不创建跟踪网络；不改Merge；不开始filter；不伪写视频验收。

## 测试/完成

`test_batch6_contracts.py`覆盖输入schema、mask ranges、frame ordering、face identity fixtures、baseline outputs和差异表。同步修订所有受影响Ticket并独立Review后才能签发基础票。
