# 01 — 冻结 Batch 2 基线、测试工作区与 legacy 采样证据

Status: open
Type: AFK
Blocked by: None — 可以立即开始

**构建内容：** 在任何 Metadata 或采样代码修改前，建立可重复的源码、faceset、索引分布、Generator 输出和 Windows FP32 验收基线，防止后续只能证明“新代码能运行”，却无法证明旧行为未被破坏。

## 目标

- 固定实现基线 commit、Python、平台和关键依赖。
- 建立普通目录和 Packed Faceset 小 fixture。
- 记录 `legacy_random` 与现有 `uniform_yaw` 的索引分布。
- 记录 `SampleGeneratorFace` 输出数量、shape、dtype 和多进程行为。
- 建立 Batch 2 测试入口、manifest 与报告模板。
- 把真实 Windows GPU 验收项明确留档，不在无 GPU 环境伪完成。

## 详细任务

- [ ] 记录当前 Git commit、分支、Python 版本、OS、CPU 数量、TensorFlow/cv2 可用性。
- [ ] 记录 `samplelib/Sample.py`、`SampleLoader.py`、`SampleGeneratorFace.py`、`core/mplib/__init__.py` 当前行为。
- [ ] 生成不含真实人脸的 synthetic aligned fixture：清晰、模糊、过暗、过亮、坏文件、不同 pose landmarks。
- [ ] 建立普通目录 fixture，确保 DFLIMG metadata 可由现有 Loader 读取。
- [ ] 建立 Packed Faceset fixture，验证 pack/load/read_raw_file。
- [ ] 固定 sample 顺序、sample filename、person_name 和 source_filename 记录。
- [ ] 对 `IndexHost` 固定 seed 抽样，记录覆盖率和序列。
- [ ] 对现有 `Index2DHost` / uniform yaw 记录分桶和抽样分布。
- [ ] 记录 debug 单线程与 subprocess generator 输出。
- [ ] 记录 `eyes_mouth_prio=False/True` 时输出数量，确保 Batch 2 后续不改变该契约。
- [ ] 新增 `tests/fixtures/batch2/manifest.example.json`。
- [ ] 新增 Batch 2 测试 runner 或明确复用现有 smoke runner 的命令。
- [ ] 新增 `.scratch/.../reports/windows-gpu-acceptance-template.md`。

## 建议文件

- `tests/fixtures/batch2/manifest.example.json`
- `tests/smoke/test_batch2_baseline.py`
- `.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md`
- `.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md`

## 验收标准

- [ ] fixture 可重复生成，不提交私有人脸素材。
- [ ] ordinary 与 packed fixture 均能被当前 `SampleLoader` 加载。
- [ ] baseline 记录包含 legacy index 分布和 generator tensor contract。
- [ ] 测试在 Python 3.9+ 可运行；无 TensorFlow/cv2 时明确 skip，而非假成功。
- [ ] Windows GPU 尚未执行时，报告明确写 `pending-windows-gpu`。
- [ ] 后续 ticket 可以直接复用 fixture 和 manifest。

## 不在本 ticket

- 不定义正式 Metadata Schema。
- 不计算 quality score。
- 不新增采样模式。
- 不修改 SAEHD options。
- 不修改 IndexHost 生产代码。

## 完成总结报告

- [ ] 在 `.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md` 记录实际环境、命令、结果、fixture 结构、Windows 待办和差异基线。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待实现。
