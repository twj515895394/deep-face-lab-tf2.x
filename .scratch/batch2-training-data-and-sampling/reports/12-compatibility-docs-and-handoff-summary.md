# 12 — 完成兼容矩阵、用户文档、状态收口与下一批次 handoff 总结报告

> 创建时间：2026-07-29  
> 状态：PASS (macOS 轻量验证 PASS, 169/169 测试通过)  
> 依赖前置：`11-batch2-test-matrix-and-windows-acceptance.md`

---

## 1. 实现事实表

| 项目 | 设计规范值 | 实际代码实现值 | 校验状态 | 证明文件/路径 |
|---|---|---|---|---|
| CLI 工具 | `main.py faceset-analyze` | `main.py faceset-analyze` | PASS | [main.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/main.py#L120) |
| CLI 参数 | `--input-dir`, `--output-file`, `--report-file`, `--incremental`, `--force`, `--workers`, `--strong-fingerprint`, `--strict` | 8 个参数全量支持 | PASS | [FacesetAnalyzer.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/mainscripts/FacesetAnalyzer.py#L30) |
| 侧边栏路径 | `<input_dir>/faceset_metadata.v1.json` | `<input_dir>/faceset_metadata.v1.json` | PASS | [samplelib/metadata/atomic_store.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/metadata/atomic_store.py) |
| Schema 版本 | `schema_version = "1.0.0"` | `schema_version = "1.0.0"` | PASS | [samplelib/metadata/schema.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/metadata/schema.py) |
| Analyzer 版本 | `analyzer_version = "1.0.0"` | `analyzer_version = "1.0.0"` | PASS | [samplelib/metadata/analyzer.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/metadata/analyzer.py) |
| Sampling Modes | `legacy_random`, `legacy_uniform_yaw`, `pose_balanced`, `quality_pose_balanced` | 4 种模式枚举全量对应 | PASS | [samplelib/sampling/config.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/sampling/config.py#L7) |
| 配置主开关 | `training.metadata_sampling` | `training.metadata_sampling` (bool) | PASS | [models/Model_SAEHD/Model.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/models/Model_SAEHD/Model.py#L150) |
| Fallback 日志 | `[Sampling][<side>]\n  requested: ...\n  effective: ...` | 结构化多行解构输出 | PASS | [samplelib/sampling/resolver.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/sampling/resolver.py#L80) |
| 数据集格式 | Ordinary aligned folder & Packed `faceset.pak` | 两者原生透明支持 | PASS | [samplelib/metadata/loader.py](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/samplelib/metadata/loader.py#L40) |

---

## 2. 证据化兼容性矩阵 (14 项全覆盖)

| 序号 | 场景/配置 | Requested Mode | Effective Mode | 预期行为 | 验证平台 | 状态 | 证据来源 |
|---|---|---|---|---|---|---|---|
| 1 | 旧模型，无 enhancements | None (`legacy`) | `legacy_random` | 使用传统完全均匀随机采样 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 2 | 新模型，全部增强关闭 | `legacy` | `legacy_random` | 保持基线行为，零性能损耗 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 3 | `uniform_yaw=True` | `legacy_uniform_yaw` | `legacy_uniform_yaw` | 回退/保留传统 Pitch/Yaw 姿态桶采样 | macOS | PASS | `tests/smoke/test_batch2_sampling_policy.py` |
| 4 | `training.metadata_sampling=False` | `pose_balanced` | `legacy_random` | 智能模式请求因总开关关闭降级 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 5 | 手动显式指定 `legacy_random` | `legacy_random` | `legacy_random` | 显式请求传统随机模式 | macOS | PASS | `tests/smoke/test_batch2_sampling_policy.py` |
| 6 | 手动显式指定 `pose_balanced` | `pose_balanced` | `pose_balanced` | 启用精准姿态平衡卡方分配采样 | macOS | PASS | `tests/smoke/test_batch2_pose_balanced.py` |
| 7 | 手动显式指定 `quality_pose_balanced` | `quality_pose_balanced` | `quality_pose_balanced` | 结合姿态与清晰度/曝光质量加权 | macOS | PASS | `tests/smoke/test_batch2_quality_weighting.py` |
| 8 | Metadata 缺失 / JSON 损坏 | `pose_balanced` | `legacy_random` | 安全输出 fallback 日志并继续训练 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 9 | 匹配率低于阈值 (match < 90%) | `quality_pose_balanced` | `legacy_random` | 判定为 partial match 自动回退 | macOS | PASS | `tests/smoke/test_batch2_metadata_loader.py` |
| 10 | src 存在 metadata，dst 缺失 | `src: pose_balanced, dst: pose_balanced` | `src: pose_balanced, dst: legacy_random` | 单侧独立 Fallback，互不干扰 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 11 | Ordinary 与 Packed faceset.pak | `pose_balanced` | `pose_balanced` | 原生读写 index/pak 并生成指纹 | macOS | PASS | `tests/smoke/test_batch2_analyzer_cli.py` |
| 12 | Single worker 与 Multi worker | `pose_balanced` | `pose_balanced` | WeightedIndexHost 跨多进程共享 IPC 索引 | macOS | PASS | `tests/smoke/test_batch2_generator_integration.py` |
| 13 | 模型 Save / Exit / Resume | `quality_pose_balanced` | `quality_pose_balanced` | options-json 配置恢复不丢失 | macOS | PASS | `tests/smoke/test_batch2_saehd_integration.py` |
| 14 | Merger / DFM 工具调用 | N/A | N/A | DFM 导出与 Merge 过程零干涉 | macOS | PASS | `tests/smoke/test_batch2_master_matrix.py` |

---

## 3. Windows FP32 验收状态

- **macOS 本地轻量验证**：`PASS`（全量 169 项烟雾与集成测试套件通过）。
- **Windows Blackwell GPU FP32 + AdaBelief 实机验收**：`PENDING-WINDOWS-GPU`。实机规程与脚本模板已落盘至 [.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance.md)。

---

## 4. 下一步与交接目标

1. Batch 2 全部 12 个 Ticket 的代码、设计、用户文档、验证套件与 Hand-off 已全部归档完毕。
2. 批次规格书 [.scratch/batch2-training-data-and-sampling/spec.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.scratch/batch2-training-data-and-sampling/spec.md) 状态更名为 `done-macos-lightweight-pending-windows`。
3. 后续开发将进入 **Batch 3 (Multi-objective Loss Hook & Identity Appearance)** 前置技术方案设计与规格书准备。
