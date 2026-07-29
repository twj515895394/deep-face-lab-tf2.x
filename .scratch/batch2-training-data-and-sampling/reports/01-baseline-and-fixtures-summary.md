# Ticket 01 — 基线、测试工作区与 Legacy 采样证据冻结总结报告

- **修改前 Commit**: 见环境记录
- **修改后 Commit**: 见环境记录
- **更新时间**: 2026-07-29

## 测试与状态总览

- **测试状态**: PASS (macOS 轻量级验证已通过)
- **Windows GPU 真实训练验证**: PENDING-WINDOWS-GPU (已保留模板，等待 Windows GPU 环境实测)
- **Unicode / UTF-8 兼容性**: PASS
- **`--options-json` 文档同步**: NA (本 Ticket 不涉及训练参数定义变更)

## 详细修改与资产目录

1. **`tests/fixtures/batch2/manifest.example.json`**:
   - 描述 Batch 2 Fixture 与环境契约示例。

2. **`tests/fixtures/batch2/build_synthetic_fixture.py`**:
   - 不含真实人脸的合成 DFLIMG 样本生成工具，支持 Ordinary 和 Packed Faceset 生成。

3. **`tests/smoke/test_batch2_baseline.py`**:
   - 收集分支与依赖信息 (`collect_batch2_environment`)；
   - 验证 `SampleLoader` 对 Ordinary 和 Packed 格式的正确解析与读取；
   - 冻结 `IndexHost` 固定 seed 抽样序列、覆盖率契约及 `Index2DHost` 行为；
   - 冻结 `SampleGeneratorFace` 在调试模式、多进程、`eyes_mouth_prio` 为 True/False 时的数组输出数量、shape 与 dtype 契约。

4. **`.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md`**:
   - 供 Windows GPU FP32 训练使用的验收记录模板。

## 可供 Ticket 02 直接调用的 API 与 Fixtures

- **Synthetic Fixture 生成器**:
  - `tests.fixtures.batch2.build_synthetic_fixture.build_ordinary_fixture(target_dir)`
  - `tests.fixtures.batch2.build_synthetic_fixture.build_packed_fixture(ordinary_dir, pak_output_dir)`
- **环境收集工具**:
  - `tests.smoke.test_batch2_baseline.collect_batch2_environment()`
