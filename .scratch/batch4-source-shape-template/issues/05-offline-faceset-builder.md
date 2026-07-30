# B4-05 Offline Faceset Source Shape Template Builder

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-02/03；阻塞B4-07。
- 目标：从ordinary或Packed src faceset离线生成符合`.srcshape` Schema的candidate，不依赖训练模型或GPU。

## 输入/输出

输入：src faceset path、metadata/landmarks、fingerprint mode、阈值、可注入clock。输出：`TemplateCandidate`或结构化失败报告；本票不直接写最终文件。

## 流程

```text
SampleLoader ordinary/packed
-> stable sample identity/fingerprint
-> landmark/quality/pose/occlusion校验
-> canonical normalize
-> fixed ratio提取
-> candidate records + reject report
```

必须复用Batch3最终canonical/ratio helper，禁止复制不同公式。按sample_id排序保证determinism；不修改/移动/写回aligned素材。

## 失败/边界

- 无样本、无有效landmark、混合identity、metadata stale、packed读取失败分别返回稳定reason。
- 核心I/O/decoder错误传播；可选metadata缺失是否fallback到DFL landmark由B4-01最终冻结并记录source quality降级。
- 大faceset采用流式/有界内存，不把全部图片驻留。

## 目标代码

`core/enhancements/shape_template/offline_builder.py`及独立CLI adapter（CLI本体可在B4-10接入）。

## Forbidden

- 不读取模型权重。
- 不生成`.srcshape`最终文件。
- 不使用外部身份模型。
- 不自动删除低质量素材。

## 测试

`test_batch4_offline_template_builder.py`覆盖ordinary/packed等价、Unicode、候选过滤、顺序determinism、1k synthetic records内存预算、stale metadata、混合identity、无有效候选和失败报告。

## 完成定义

candidate和报告可被B4-07消费；无素材修改；性能/兼容测试、Summary、Review、SHA完整。
