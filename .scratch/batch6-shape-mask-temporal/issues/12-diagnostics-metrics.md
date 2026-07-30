# B6-12 Shape Mask/Temporal Diagnostics、结构化Metrics与限频日志

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`；P1；前置B6-06/07/10；阻塞B6-13。
- 目标：让用户和A/B测试能看到Mask贡献、Temporal更新/reset和fallback原因，不通过第二次处理或大日志拖慢Merge。

## Metrics

每脸/帧可选结构化摘要：shape requested/effective/power/reason、source/existing/final mask area与overlap、coverage/occlusion、Warp quality、temporal mode/update/reset reason、raw/filtered displacement、jitter estimate、processing time。默认不保存完整map/landmarks。

## 日志

- startup输出配置、Template/track能力和effective状态一次。
- frame warning按`reason+face key+config hash`限频；批处理可输出周期aggregate。
- debug artifact只在显式debug目录，文件名脱敏且有数量/磁盘上限；默认关闭。
- 不为metrics重复执行Warp/Mask/Filter。

## 报告

定义JSONL或CSV稳定Schema，含frame index、face ordinal/安全key、metrics、reason；不得含原始绝对路径或完整生物特征数组。错误写报告不得破坏已生成视频，除非用户显式strict report。

## Forbidden

不每帧打印大数组；不保存Template/landmarks原始数据；不运行第二次Merge；不把debug默认打开；不吞核心异常。

## 测试

`test_batch6_diagnostics.py`覆盖字段顺序/schema、限频、aggregate、脱敏、debug上限、report I/O失败、multi-face、reset reason、无第二次调用spy和disabled零开销。

## 完成定义

Metrics可用于B6-13复核，隐私/性能/失败边界明确；Summary、Review、SHA完整。
