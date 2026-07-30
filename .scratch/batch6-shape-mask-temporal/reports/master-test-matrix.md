# Batch 6 Master Test Matrix（Rolling Draft）

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5 / NOT EXECUTED`

| Gate | 重点 |
|---|---|
| Contracts | Batch5 Warp/coverage/quality、mask坐标、face identity |
| Config | Mask/Temporal独立Gate、旧session、zero path |
| Support/Mask | contour、coverage、softness、mask modes/XSeg |
| Fallback | occlusion/confidence/invalid Warp/area |
| Merge | 插入顺序、RGB-mask、raw/superres/color、多脸 |
| State | track identity、容量、无跨任务泄漏 |
| Filters | EMA/OneEuro数学、dt/fps、finite |
| Reset | scene cut/gap/lost/config/hash/multi-face |
| Lifecycle | worker乱序、prefetch、rewind、session |
| Diagnostics | metrics/限频/脱敏/零额外处理 |
| Performance | fps/RSS/state/buffer/zero overhead |
| Windows/Visual | 长短视频、遮挡、闪切、多脸、lag/ghosting |

统一自动命令：`python -m unittest discover -s tests/smoke -p "test_batch*.py" -q`。各Gate分别记录，未执行不得写PASS。
