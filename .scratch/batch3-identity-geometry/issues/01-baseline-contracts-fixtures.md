# B3-01 基线冻结、术语、Tensor/Mask/DType 契约与 Fixtures

## 1. 基本信息

- Ticket ID：`B3-01`
- 状态：`READY-AFTER-DOCUMENT-REVIEW`
- 优先级：P0
- 前置 Ticket：无
- 阻塞 Ticket：B3-02、B3-03、B3-06、B3-08
- 目标分支：`codex/batch2-ticket19-loss-window`
- 建议提交粒度：1 个代码/测试提交 + 1 个 Summary/Review 提交

## 2. 背景与问题

Batch 3 会同时触及 SAEHD 图构建、SampleProcessor 输出、增强配置和训练日志。当前代码存在以下必须先冻结的事实：

1. `models/Model_SAEHD/Model.py` 的训练输入是 NHWC/NCHW 取决于 `nn.data_format` 的图张量，当前固定输入仅有图像、full mask 和可选 eyes/mouth mask。
2. `SampleProcessor.SampleType.LANDMARKS_ARRAY` 已存在，但当前只把原始 landmarks 按原图宽高归一化；它没有应用 `face_type` 对齐矩阵、随机 affine、flip，也没有与 target 图像输出保证同一坐标系。
3. target 图像和 target mask 使用 `warp=False, transform=True`；几何监督必须与 target 路径对齐，不能与 non-rigid warped input 混用。
4. `gpu_pred_src_srcm` 是现有可微预测 mask；Batch 3 不新增 landmark head，也不允许把离线 landmark 检测器结果误称为可微预测 landmark。
5. `ModelBase.loss_history` 要求每次迭代通道维度稳定；配置改变导致历史维度变化必须禁止或明确迁移。

本 Ticket 只冻结基线和测试夹具，不实现 Geometry Loss。

## 3. Scope

### 3.1 In Scope

- 记录 Batch 3 开始前的代码、配置和自动测试基线。
- 冻结术语：Anchor、Canonical Landmark、Aligned Landmark、Geometry Target、Geometry Observable、Validity Mask、requested/effective。
- 冻结图像、mask、landmark、ratio、SDF/soft contour 的 shape 与 dtype。
- 建立纯 NumPy fixtures 和轻量 fake tensor/fake model fixtures。
- 建立“Feature Flag 全关时零影响”的基线快照测试。
- 建立 `LANDMARKS_ARRAY` 现状测试，防止后续错误假设其已对齐。

### 3.2 Out of Scope

- 不修改 SAEHD Loss。
- 不生成 Shape Anchor。
- 不新增训练 placeholder。
- 不修改 Merge、DFM 导出、模型权重或 optimizer。
- 不执行 GPU 效果验收。

### 3.3 Forbidden Changes

- 禁止重构无关的 SampleProcessor 图像增强路径。
- 禁止改变现有 `LANDMARKS_ARRAY` 的 legacy 行为而没有显式兼容开关或新 SampleType。
- 禁止把 NCHW/NHWC 在文档中写死为单一格式；必须由 `nn.data_format` 决定。
- 禁止使用 float64 作为新几何默认 dtype。
- 禁止把离线检测得到的 landmark 当作可反向传播的预测 landmark。

## 4. 当前代码锚点

- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize_options`
- `models/Model_SAEHD/Model.py::SAEHDModel.on_initialize`
- `models/Model_SAEHD/Model.py::_unpack_training_samples`
- `models/Model_SAEHD/Model.py::_unpack_unified_train_result`
- `models/Model_SAEHD/Model.py::SAEHDModel.onTrainOneIter`
- `samplelib/SampleProcessor.py::SampleProcessor.SampleType`
- `samplelib/SampleProcessor.py::SampleProcessor.process`
- `core/imagelib/warp.py::gen_warp_params`
- `core/imagelib/warp.py::warp_by_params`
- `facelib/LandmarksProcessor.py::transform_points`
- `facelib/LandmarksProcessor.py::get_transform_mat`
- `models/ModelBase.py::ModelBase.train_one_iter`
- `samplelib/sampling/loss_stats.py::LossWindowTracker`

## 5. 冻结契约

### 5.1 图像与 mask

```text
image: float32 或当前 precision 对应图 dtype
logical layout: batch + spatial + channel
channel: BGR=3, mask=1
value range: [0, 1]
non-finite: invalid，禁止进入 optimizer
```

### 5.2 Aligned Landmarks

```text
shape: [batch, 68, 2]
dtype: float32
coordinate: target face canvas normalized [0, 1]
transform source: 与 target image/mask 相同的 face alignment + random affine + flip
non-rigid warp: 禁止应用
invalid sentinel: 不使用 NaN；使用独立 validity tensor
```

### 5.3 Ratio Target

```text
shape: [batch, R]
dtype: float32
R 第一版固定，不允许运行时变长
validity: [batch, R] float32 或 bool
reduction: 先 feature，再 sample，再 batch；必须在 B3-09 冻结
```

### 5.4 Geometry SDF / Soft Contour

```text
shape: 与预测 src mask 同 layout、单通道
dtype: float32
value range: 在生成器端规范化到 [-1, 1] 或 [0, 1]，由 B3-08 唯一冻结
validity: [batch, 1]，无效样本的加权贡献严格为 0
```

### 5.5 Loss History

- Geometry 关闭时 `onTrainOneIter()` 仍只返回 `src_loss`、`dst_loss`。
- Geometry 开启后新增通道顺序必须固定并由常量定义。
- 同一训练会话中不得通过热修改配置改变 loss 通道数。

## 6. 实施步骤

1. 新建 `tests/smoke/test_batch3_contracts.py`。
2. 新建 `tests/fixtures/batch3_geometry_fixtures.py`，仅放确定性小数组和 factory，不放真实用户素材。
3. 为 `SampleProcessor.LANDMARKS_ARRAY` 添加现状回归：证明其当前不应用 target affine/flip。
4. 为 target image/mask 的共享随机 affine 建立固定 seed fixture。
5. 建立 layout 转换 fixture，覆盖 NHWC/NCHW。
6. 建立 float16/bfloat16 输入、float32 几何统计输出契约测试；无 TensorFlow 环境时使用纯函数模拟。
7. 建立非有限输入、空 validity、零有效样本测试。
8. 记录基线命令、测试数量、HEAD 和未执行 GPU 项。

## 7. 测试要求

### Unit/Smoke

- `test_batch3_contracts.py::test_legacy_landmarks_array_is_not_target_aligned`
- `test_batch3_contracts.py::test_aligned_landmark_contract_shape_dtype`
- `test_batch3_contracts.py::test_geometry_validity_never_uses_nan_sentinel`
- `test_batch3_contracts.py::test_nhwc_nchw_roundtrip`
- `test_batch3_contracts.py::test_disabled_loss_channel_contract_is_two`
- `test_batch3_contracts.py::test_empty_valid_batch_reduces_to_zero`

### 命令

```bash
python -m unittest tests.smoke.test_batch3_contracts -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 8. 完成定义

- 术语、shape、dtype、坐标系和 validity 规则均有测试。
- 已明确 `LANDMARKS_ARRAY` 不能直接用于目标对齐监督。
- Fixtures 不依赖 GPU、用户数据或外部模型。
- Feature Flag 全关时 loss 通道契约保持旧行为。
- Summary、Review、Commit SHA 和未执行项目齐全。

## 9. Review 检查表

- 是否错误修改了 legacy SampleType？
- 是否混淆 warped input 与 target coordinate？
- 是否把非可微数据描述为可微预测？
- 是否使用了 NaN 作为正常 validity 编码？
- 是否遗漏 NCHW？
- 是否让 loss history 通道数在会话中变化？

## 10. 交付物

- `tests/smoke/test_batch3_contracts.py`
- `tests/fixtures/batch3_geometry_fixtures.py`
- 基线记录与测试输出
- Ticket Summary
- 独立 Review
- Commit SHA
