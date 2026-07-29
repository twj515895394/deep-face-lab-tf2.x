# Task Plan: Batch 2 Ticket 06 — Sampling Policy API & Legacy Adapters

- [x] Step 1: 创建 `samplelib/sampling/config.py` (SamplingMode & SamplingConfig 安全转换)
- [x] Step 2: 创建 `tests/smoke/test_batch2_sampling_config.py` 并验证
- [x] Step 3: 创建 `samplelib/sampling/policies.py` (SamplingPolicy, LegacyRandomPolicy, LegacyUniformYawPolicy)
- [x] Step 4: 创建 `tests/smoke/test_batch2_legacy_sampling_adapters.py` 并验证
- [x] Step 5: 创建 `samplelib/sampling/factory.py` (SamplingResolution & SamplingPolicyFactory.resolve 8种决断矩阵)
- [x] Step 6: 创建 `tests/smoke/test_batch2_sampling_factory.py` 并验证
- [x] Step 7: 运行全套烟雾测试 `./.venv/bin/python -m unittest discover -s tests/smoke -p "test_*.py"` 确保 100% 通过
- [x] Step 8: 编写 06 研发总结报告与交接文档

Status: PASS
