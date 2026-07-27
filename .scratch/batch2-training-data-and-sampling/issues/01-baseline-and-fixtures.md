# 01 — 冻结 Batch 2 基线、测试工作区与 legacy 采样证据

Status: open
Type: AFK
Blocked by: None — 可以立即开始

**构建内容：** 在任何 Metadata 或采样代码修改前，建立可重复的源码、faceset、索引分布、Generator 输出和 Windows FP32 验收基线，防止后续只能证明“新代码能运行”，却无法证明旧行为未被破坏。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. `.scratch/batch2-training-data-and-sampling/spec.md`
3. `docs/development/batch2-training-data-and-sampling-tasks.md` 中基线、兼容和测试章节
4. `samplelib/Sample.py`
5. `samplelib/SampleLoader.py`
6. `samplelib/SampleGeneratorFace.py`
7. `samplelib/PackedFaceset.py`
8. `core/mplib/__init__.py` 中 `IndexHost`、`Index2DHost`
9. Batch 1 smoke runner、fixture 和 manifest 的现有实现

本 Ticket 是证据冻结任务。**不得先写 Metadata 或 WeightedIndexHost，再倒推基线。**

## 当前源码事实必须先确认

开工后先在 summary 草稿中记录：

- `Sample.__slots__` 当前字段；
- ordinary faceset 如何通过 DFLIMG 生成 `Sample`；
- Packed Faceset 如何恢复 `Sample` 并通过 offset 读取原始 bytes；
- `SampleGeneratorFace.__init__()` 如何选择 `IndexHost` 或 `Index2DHost`；
- `batch_func()` 最终 yield 的数组数量、顺序、shape 和 dtype；
- `eyes_mouth_prio` 对输出数量的影响；
- debug 模式与 subprocess 模式的差异；
- 现有 `Index2DHost` 是否支持 seed，以及其随机状态是否使用全局 NumPy RNG。

如果源码事实与本文不同，只记录差异，不修改生产逻辑。

## 目标

- 固定实现基线 commit、Python、平台和关键依赖。
- 建立普通目录和 Packed Faceset 小 fixture。
- 记录 `legacy_random` 与现有 `uniform_yaw` 的索引分布。
- 记录 `SampleGeneratorFace` 输出数量、shape、dtype 和多进程行为。
- 建立 Batch 2 测试入口、manifest 与报告模板。
- 把真实 Windows GPU 验收项明确留档，不在无 GPU 环境伪完成。

## 建议施工顺序

### Step 1：只建立环境记录

新增一个测试辅助函数，输出结构化信息：

```python
def collect_batch2_environment() -> dict:
    """Return branch/commit, Python, OS and optional dependency availability."""
```

不得因为 TensorFlow、cv2 或 GPU 缺失直接失败；应返回 availability 字段，并由测试决定 skip。

### Step 2：建立 synthetic fixture 生成器

fixture 必须可重复生成，建议固定随机种子。至少包含：

- 正常清晰 RGB 图；
- 高斯模糊图；
- 全黑/全白/过暗/过亮图；
- 损坏 bytes；
- 正脸、左右侧脸等固定 landmarks；
- landmarks 缺失、NaN、越界案例。

禁止提交真实人脸。生成器必须能在临时目录运行。

### Step 3：建立 ordinary fixture

使用项目现有 DFLIMG 写入/读取能力生成 aligned fixture。若现有 API 不适合 synthetic 写入：

- 优先复用 Batch 1 fixture；
- 或只为测试创建最小合法 DFLIMG；
- 不修改生产格式。

记录文件名、person_name、source_filename、landmark 数量和加载顺序。

### Step 4：建立 Packed fixture

由 ordinary fixture 使用现有 `PackedFaceset.pack/load` 生成。测试必须证明：

```text
pack
→ load
→ Sample.read_raw_file
→ Sample.load_bgr
```

可以工作。测试结束清理临时文件，不触发交互式删除确认；必要时在测试辅助层隔离交互，不修改 pack 格式。

### Step 5：冻结 legacy 索引证据

为 `IndexHost` 使用固定 seed，至少记录：

- 前 100 个索引序列；
- 一个完整 epoch 的覆盖率；
- 是否出现 epoch 内重复；
- 相同 seed 是否一致。

对 `Index2DHost` 记录：

- 输入 bucket；
- 抽样次数；
- 每 bucket draw 数；
- 是否可固定 seed；
- 当前不可确定性作为 baseline 事实记录，不得在本 Ticket 修复。

### Step 6：冻结 Generator tensor contract

对以下组合记录数组数量、shape、dtype：

```text
debug=True / False
eyes_mouth_prio=False / True
uniform_yaw=False / True
generators_count=1 / >1（平台允许时）
ordinary / packed
```

测试只比较 contract，不比较随机像素完全一致。

### Step 7：建立 manifest 和 Windows 模板

`manifest.example.json` 只放占位路径，不提交用户绝对路径。Windows 模板必须预留：

- GPU/驱动/CUDA/TensorFlow；
- FP32 + AdaBelief；
- ordinary/packed；
- generator worker 数；
- iter time、CPU/RAM、VRAM；
- save/exit/resume。

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
- `tests/fixtures/batch2/build_synthetic_fixture.py`
- `tests/smoke/test_batch2_baseline.py`
- `.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md`
- `.scratch/batch2-training-data-and-sampling/reports/windows-gpu-acceptance-template.md`

## 最小测试命令

```bash
python -m compileall tests/fixtures/batch2 tests/smoke/test_batch2_baseline.py
python -m unittest tests.smoke.test_batch2_baseline
```

若项目 smoke runner 已存在，再运行：

```bash
python tests/smoke/run_smoke.py
```

实际命令不同必须在 summary 中写出，不得虚构成功。

## 禁止捷径与常见错误

- 不允许用普通 PNG 代替合法 DFLIMG 后声称 `SampleLoader` ordinary 已通过。
- 不允许手工构造 `Sample` 后跳过 PackedFaceset 真正的 pack/load 路径。
- 不允许把 TensorFlow/cv2 import 失败包装为 PASS；只能 SKIP。
- 不允许修改 `Index2DHost` 以获得更漂亮的 baseline。
- 不允许提交 fixture 二进制大文件、私有人脸或用户绝对路径。
- 不允许把 macOS 单线程测试写成 Windows spawn 已验证。

## 验收标准

- [ ] fixture 可重复生成，不提交私有人脸素材。
- [ ] ordinary 与 packed fixture 均能被当前 `SampleLoader` 加载。
- [ ] baseline 记录包含 legacy index 分布和 generator tensor contract。
- [ ] 测试在 Python 3.9+ 可运行；无 TensorFlow/cv2 时明确 skip，而非假成功。
- [ ] Windows GPU 尚未执行时，报告明确写 `pending-windows-gpu`。
- [ ] 后续 ticket 可以直接复用 fixture 和 manifest。
- [ ] summary 明确列出可供 Ticket 02 依赖的 fixture 路径和 helper API。

## 不在本 ticket

- 不定义正式 Metadata Schema。
- 不计算 quality score。
- 不新增采样模式。
- 不修改 SAEHD options。
- 不修改 IndexHost 生产代码。

## 完成总结报告

- [ ] 在 `.scratch/batch2-training-data-and-sampling/reports/01-baseline-and-fixtures-summary.md` 记录实际环境、命令、结果、fixture 结构、Windows 待办和差异基线。
- [ ] 明确标出 PASS / SKIP / PENDING-WINDOWS / FAIL。
- [ ] 列出 Ticket 02 可以直接调用的 fixture/helper，不要求下一模型重新猜测。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待实现。
- 2026-07-27：补充弱模型施工顺序、源码事实检查、测试命令和禁止捷径。