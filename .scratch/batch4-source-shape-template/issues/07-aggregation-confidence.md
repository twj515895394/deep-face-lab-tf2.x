# B4-07 Robust Aggregation、Quality、Confidence与Candidate选择

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-05/06；阻塞B4-08。
- 目标：将一个或多个同identity candidate聚合为唯一Template payload；不决定路径和写入。

## 冻结原则

- 只聚合同一model/source identity和compatible fingerprint的candidate。
- 来源冲突先由B4-04解决；本票不暗中按confidence覆盖显式选择。
- canonical landmarks与ratio使用robust median/trimmed mean；具体策略、trim和离群阈值由B4-01 fixtures冻结。
- confidence综合有效样本量、离散度、landmark confidence、pose覆盖、来源可信度；每个分量可解释并输出。
- quality与confidence分开：quality描述输入，confidence描述Template可用可信度。

## API

`aggregate_template_candidates(candidates, policy) -> TemplateAggregationResult`，含payload、component_scores、rejected candidates、warnings、reason；输入顺序不得影响结果。

## 边界

- 单candidate允许但confidence需反映证据不足。
- fingerprint/ratio schema不一致必须拒绝聚合。
- 输出landmarks/ratios重新交叉校验，禁止各自独立聚合后不一致。
- 不自动外推缺失ratio，不使用NaN。

## Forbidden

- 不写文件、不缓存、不访问Merge。
- 不训练模型或做视觉检测。
- 不使用不可解释黑盒总分。
- 不因高confidence忽略identity mismatch。

## 测试

`test_batch4_template_aggregation.py`覆盖顺序determinism、outlier、单candidate、多来源、相同/冲突fingerprint、置信度单调性、低样本、landmark/ratio一致性、float32 finite和固定golden fixtures。

## 完成定义

聚合公式、阈值、component scores和拒绝原因全部可测试；输出符合B4-02；Summary、Review、SHA完整。
