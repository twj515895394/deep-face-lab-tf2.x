# B3-08 可微 Geometry Supervision 输入、Aligned Landmark、Ratio 与 SDF 契约

## 1. 基本信息

- Ticket ID：`B3-08`
- 状态：`BLOCKED-BY-B3-01-B3-07`
- 优先级：P0
- 前置 Ticket：B3-01、B3-07
- 阻塞 Ticket：B3-09、B3-10、B3-11、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 独立 Review 结论

当前 SAEHD 没有 landmark prediction head，也没有可微 landmark detector。离线/样本 landmarks 只能作为监督目标，不能直接代表模型预测并产生有效坐标梯度。

因此 Batch 3 冻结以下可行路线：

```text
样本 landmark / Shape Anchor
        ↓  CPU/Generator 生成目标
Aligned Landmark + Ratio Target + Stable Contour SDF
        ↓  feed 到 TF 图
现有可微预测 src mask 的 soft geometry observable
        ↓
Ratio Loss + Contour/SDF Loss
```

第一版不实现“预测 landmark 坐标与目标 landmark 坐标直接相减”。任何编码 Agent 不得临时引入 landmark 网络。

## 3. Scope

### In Scope

- 新增与 target image/mask 完全对齐的 landmark 输出/内部 helper。
- 定义 68 点 flip remap。
- 定义固定 ratio target 和 validity。
- 定义 stable contour/region target 与 SDF 生成。
- 定义 compact worker payload 和 generator 输出顺序。
- 定义只对 src 样本生成训练 Geometry supervision。

### Out of Scope

- 不新增模型 landmark head。
- 不调用外部 landmark 模型处理预测图。
- 不生成 dst->src Hybrid Landmark；该能力属于 Batch 5。
- 不修改 Sample 对象存储结构。
- 不对 non-rigid warped input 生成监督。

### Forbidden Changes

- 禁止直接复用当前 `LANDMARKS_ARRAY` 并声称已与 target 对齐。
- 禁止对 landmarks 应用 non-rigid random warp。
- 禁止忘记 flip 后的 68 点语义重排。
- 禁止把 Python dict 作为 batch 输出，避免 worker stacking/IPC 不确定。
- 禁止将完整 Anchor JSON 每样本复制。
- 禁止使用 NaN 表示无效。

## 4. 当前代码锚点

- `samplelib/SampleProcessor.py::SampleProcessor.SampleType`
- `samplelib/SampleProcessor.py::SampleProcessor.process`
- `SampleProcessor` 当前 `LANDMARKS_ARRAY` 分支
- `core/imagelib/warp.py::gen_warp_params` 中 `rmat/flip`
- `core/imagelib/warp.py::warp_by_params`
- `facelib/LandmarksProcessor.py::get_transform_mat`
- `facelib/LandmarksProcessor.py::transform_points`
- `models/Model_SAEHD/Model.py` `_base_src_types/_base_dst_types`

## 5. 目标输出类型

建议新增，不改变 legacy `LANDMARKS_ARRAY=4`：

```python
ALIGNED_LANDMARKS_ARRAY = 7
GEOMETRY_TARGET_MAP = 8
GEOMETRY_RATIO_TARGET = 9
GEOMETRY_VALIDITY = 10
```

编号在实现前确认没有冲突；一旦提交即冻结。

### 5.1 ALIGNED_LANDMARKS_ARRAY

```text
shape: [68,2]
dtype: float32
coordinate: target canvas pixel 或 normalized，最终统一为 normalized [0,1]
face alignment: 与 target image 相同
random affine: 应用
flip: 应用坐标和 68 点 remap
non-rigid warp: 不应用
```

### 5.2 GEOMETRY_TARGET_MAP

建议两通道：

```text
shape: [resolution,resolution,2]
channel 0: normalized stable contour signed/unsigned distance target
channel 1: stable geometry region weight mask
layout: 最终按 data_format 转为 NHWC/NCHW
```

SDF 范围冻结为 `[-1,1]`；0 为目标轮廓。region mask 范围 `[0,1]`。

稳定区域第一版：

- jaw 0..16；
- chin 邻域 5..11；
- cheek/outer face 2..14；
- 鼻梁中心仅用于 canonical 稳定参考，不作为强 contour；
- eyes、brows、mouth 不进入 stable contour loss。

### 5.3 GEOMETRY_RATIO_TARGET

```text
shape: [R*2]
前 R: ratio target values
后 R: ratio validity
R 固定为 6
```

ratio target 优先来自 Shape Anchor。只有样本满足 frontal pose/confidence 条件时 ratio validity 才为 1；侧脸样本不得把 anchor frontal ratio 满权重强加到预测 mask。

### 5.4 GEOMETRY_VALIDITY

```text
shape: [3]
[anchor_valid, contour_valid, ratio_valid]
dtype: float32
value: 0 or 1
```

更细 feature validity 位于 ratio target 后半部分。

## 6. Aligned Landmark 算法顺序

1. 验证 68 点和有限性。
2. 若 `face_type != sample_face_type`，使用 `get_transform_mat(sample_landmarks, resolution, face_type)` 并 `transform_points`。
3. 否则按原图宽高缩放到 resolution。
4. 若 output opts `transform=True`，应用同一个 `warp_params['rmat']`。
5. 若 flip：执行 `x = resolution - 1 - x`，再用冻结的 68 点 mirror index map 重排。
6. 除以 `resolution-1` 得 normalized `[0,1]`。
7. 越界超过容许阈值则该样本 invalid；只允许轻微数值 clip。

必须使用与 target image/mask 相同的 `rnd_seed_shift`，测试逐像素/点验证。

## 7. SDF/Contour 生成

- 输入使用 aligned landmarks。
- 使用固定线段拓扑画 1px stable contour。
- 生成 inside/outside distance transform 并按 resolution 规范化。
- region mask 在 jaw/cheek/chin 周边给权重，动态表情区域为 0。
- SDF 生成在 CPU/worker，输出必须有限 float32。
- 相同 landmarks/resolution 生成 byte-level 相同结果。
- 空轮廓、翻转后自交、严重越界时 contour_valid=0。

## 8. Worker Payload

传给 `SampleGeneratorFace` 的只读 compact config：

```python
GeometrySupervisionSpec(
    canonical_anchor_landmarks: tuple,
    anchor_ratios: tuple,
    min_sample_confidence: float,
    frontal_yaw_limit_deg: float,
    resolution: int,
    data_format: str,
)
```

- 不传 provenance/sample_summary/path。
- 必须可 pickle/spawn。
- workers_count 改变不影响输出。

## 9. 实施步骤

1. 新建 `core/enhancements/geometry/supervision.py`，含 mirror map、alignment、SDF、ratio packing 纯函数。
2. 为 SampleType 增加新枚举，不改 legacy 4。
3. 在 `SampleProcessor.process` 增加新分支，复用同一 `warp_params`。
4. 只在 Geometry runtime effective 时把新 output types 追加到 `_base_src_types`；DST 列表保持基线。
5. 先建立纯 SampleProcessor tests，再做 spawn generator tests。
6. 定义 `_unpack_training_samples` 的未来输出数量，但实际 SAEHD 接入留给 B3-13。

## 10. 测试要求

测试文件：

- `tests/smoke/test_batch3_aligned_landmarks.py`
- `tests/smoke/test_batch3_geometry_supervision.py`
- `tests/smoke/test_batch3_geometry_generator_spawn.py`

必须覆盖：

- legacy LANDMARKS_ARRAY 行为不变。
- face_type alignment。
- random affine 与 target image 对齐。
- flip 坐标 + semantic remap。
- random_warp 开启时 supervision 仍只跟 target transform。
- NHWC/NCHW。
- jaw/cheek/chin region，eyes/mouth 权重为 0。
- SDF finite/range/determinism。
- frontal ratio valid、侧脸 ratio invalid。
- anchor compact payload spawn-safe。
- ordinary/packed、Unicode 路径。
- Geometry disabled 时 generator 输出数量完全不变。

命令：

```bash
python -m unittest tests.smoke.test_batch3_aligned_landmarks -v
python -m unittest tests.smoke.test_batch3_geometry_supervision -v
python -m unittest tests.smoke.test_batch3_geometry_generator_spawn -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 11. 完成定义

- 已解决“监督 landmark 非可微”的设计缺口。
- 新 supervision 与 target 图像坐标严格一致。
- 不引入预测 landmark 网络。
- disabled 时输出和 IPC 带宽保持基线。
- spawn、flip、layout、determinism 有证据。
- Summary、Review、SHA 齐全。

## 12. Review 检查表

- 是否误用 legacy LANDMARKS_ARRAY？
- 是否应用了 non-rigid warp？
- flip 是否只翻坐标未重排语义？
- 是否给侧脸使用满权重 frontal ratio？
- 是否把完整 JSON 发给 worker？
- 是否在 DST generator 增加无用输出？

## 13. 交付物

- `core/enhancements/geometry/supervision.py`
- `samplelib/SampleProcessor.py` 最小扩展
- 三个 smoke tests
- 输出 shape/order 文档
- Summary、Review、Commit SHA
