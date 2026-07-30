# Batch 5 Master Test Matrix（Rolling Draft）

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4 / NOT EXECUTED`

| Gate | 重点 |
|---|---|
| Contracts | 坐标、68点、topology、Template consumer |
| Config | Gate/power0/旧session/default |
| Hybrid | stable geometry + dynamic expression |
| Warp | identity/local deformation/coverage/determinism |
| Quality | flip/degenerate/hole/越界/fallback |
| Merge | RGB-mask顺序、旧模式、多脸、raw/superres/color |
| Interactive | hotkeys/session/prefetch stale结果 |
| Compatibility | 无Template/invalid/legacy/power0 |
| Performance | 每脸耗时、RSS、worker扩展 |
| Windows | 真实predictor/短长视频/session |
| Visual | power A/B、pose/expression/artifact |

统一自动命令：`python -m unittest discover -s tests/smoke -p "test_batch*.py" -q`。各Gate分别记录，未执行不得写PASS。
