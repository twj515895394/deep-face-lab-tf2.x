# DeepFaceLab TF2.x Merge / 合成架构分析

> 文档版本：v1.0（代码链路基线）  
> 文档类型：Phase 1 Merge 架构分析  
> 更新日期：2026-07-25

---

## 1. 文档目标

本文档用于梳理当前项目从训练模型输出到最终视频帧的完整合成链路，为后续以下工作提供基线：

- Predictor 批处理和多脸推理优化
- Mask、Warp 和颜色处理优化
- CPU/GPU 任务划分
- 视频级时序稳定性
- 编解码与合成流水线
- Merge 参数自动推荐
- 未来 Linux 服务化和 UI 参数面板

本文描述当前代码行为，不代表候选优化已经开发或验证。

相关文档：

- [当前项目架构与升级分析](dfl-current-project-overview.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [文档总索引](../README.md)

---

## 2. 当前 Merge 主流程

```text
目标视频帧
   ↓
读取原始 BGR 图片
   ↓
读取该帧人脸 Landmark 列表
   ↓
逐脸计算对齐矩阵
   ↓
Warp 出目标脸
   ↓
Resize 到 predictor 输入分辨率
   ↓
调用 SAEHD predictor
   ↓
得到预测脸、预测 mask、目标 mask
   ↓
可选 Face Enhancer / Super Resolution
   ↓
选择 learned / dst / XSeg 等 Mask
   ↓
Erode / Dilate / Blur
   ↓
颜色迁移 / Histogram / Seamless Clone
   ↓
运动模糊、锐化、降噪、降质等后处理
   ↓
Warp 回原帧
   ↓
逐脸合成
   ↓
输出 RGB + Mask
   ↓
编码为最终视频
```

主要实现位于：

```text
merger/MergeMasked.py
merger/MergerConfig.py
mainscripts/Merger.py
models/Model_SAEHD/
facelib/
core/imagelib/
```

---

## 3. 代码模块地图

| 模块 | 主要代码 | 作用 |
|---|---|---|
| Merge CLI/任务入口 | `main.py`、`mainscripts/Merger.py` | 加载模型、帧信息、配置和输出任务 |
| 单帧入口 | `merger/MergeMasked.py::MergeMasked` | 读取图片，遍历该帧所有人脸，组合输出 |
| 单脸处理 | `MergeMaskedFace` | Predictor、Mask、颜色、Warp 和后处理 |
| Merge 配置 | `merger/MergerConfig.py` | mode、mask、颜色、模糊、锐化、降噪等参数 |
| Predictor | 模型提供的 predictor function | 将对齐目标脸转换为预测脸和 mask |
| XSeg | XSeg extract function | 生成预测脸或目标脸分割 mask |
| Face Enhancer | enhancer function | 可选超分辨率/增强 |
| 几何变换 | `facelib.LandmarksProcessor` | face matrix、output matrix、hull mask |
| 图像处理 | `core.imagelib`、OpenCV | 颜色迁移、histogram、blur、sharpen、denoise 等 |

---

## 4. MergeMasked 单帧调度

`MergeMasked` 的当前流程：

1. 读取目标帧。
2. 统一为 3 通道。
3. 转换为 FP32 `[0,1]` 图像。
4. 遍历 `frame_info.landmarks_list`。
5. 每张脸调用一次 `MergeMaskedFace`。
6. 收集每张脸的输出图和 merging mask。
7. 按 mask 顺序逐脸组合。
8. 将最终图像与最终 mask 拼接为 4 通道输出。

### 当前特点

- 单帧内多张脸是串行处理。
- predictor 按脸调用，通常 Batch Size 为 1。
- 每张脸完整执行 mask、warp、颜色和后处理。
- 多脸冲突通过逐层 mask 混合解决。

### 当前风险

- 多脸场景 predictor 利用率低。
- 每脸重复创建矩阵和临时数组。
- 多脸 mask 重叠时，处理顺序可能影响结果。
- 输出图和 mask 的中间副本较多。

---

## 5. 单脸几何处理

### 5.1 初始 Mask

根据目标 Landmark 生成 image hull mask：

```text
Landmark
   ↓
get_image_hull_mask
   ↓
目标脸区域 mask
```

### 5.2 变换矩阵

每张脸通常计算：

- `face_mat`
- `face_output_mat`
- `face_mask_output_mat`
- XSeg 使用的变换矩阵

这些矩阵分别用于：

- 从原帧裁出目标脸。
- 把预测脸放回原帧。
- 以不同分辨率处理 mask。
- XSeg 输入对齐。

### 5.3 Warp 和 Resize

当前大量使用：

- `cv2.warpAffine`
- `cv2.resize`
- `np.clip`

单脸可能执行多次正向和反向 Warp。

### 优化方向

- 缓存同一帧/同一 Landmark 对应矩阵。
- 避免同一数据在多个分辨率之间反复 resize。
- 合并 mask 和 RGB 的可共享 Warp。
- 评估 GPU warp 或批量几何变换。
- 记录每类 OpenCV 操作耗时。

---

## 6. Predictor 推理

### 6.1 当前调用

```text
对齐后的目标脸
      ↓
resize 到 input_size
      ↓
predictor_func(face)
      ↓
predicted face
predicted source mask
predicted destination mask
```

### 6.2 当前优势

- 与现有 SAEHD predictor 接口兼容。
- 单脸逻辑简单，错误容易隔离。
- 不要求重新设计模型导出格式。

### 6.3 当前限制

- 单次通常只推理一张脸。
- 多脸和多帧无法组成 Batch。
- GPU predictor 与 CPU 前后处理可能频繁交替等待。
- Predictor 输入准备与输出后处理没有流水化。

### 6.4 优化方向

建议改造成：

```text
Frame Decode
   ↓
收集多帧、多脸 predictor input
   ↓
Batch Predictor
   ↓
按 frame_id / face_id 分发输出
   ↓
CPU/GPU 后处理
```

需要保留：

- 单脸 fallback。
- 不同输入分辨率处理。
- 内存上限。
- 人脸顺序和帧顺序稳定。

---

## 7. Face Enhancer 与 Super Resolution

当 `super_resolution_power` 非零时：

1. predictor 输出脸进入 enhancer。
2. 输出分辨率可提高到原 predictor 的 4 倍。
3. 原预测和增强结果按 power 混合。
4. mask 同步 resize 到高分辨率。

### 优点

- 可以改善模型原生分辨率不足。
- 保留平滑混合强度。

### 风险

- enhancer 增加额外模型推理和显存。
- 与 predictor 串行执行。
- 放大后的细节未必与原帧光照和纹理一致。
- 多脸场景成本倍增。
- 高分辨率 mask 和 Warp 显著增加 CPU 开销。

### 验证要求

- 单脸/多脸耗时。
- enhancer GPU 与 predictor GPU 是否冲突。
- 输出细节、身份和伪影。
- 视频时序稳定性。
- 不同 power 的质量收益曲线。

---

## 8. Mask 体系

当前支持多种 Mask 来源：

| 类型 | 说明 |
|---|---|
| Full | 全脸区域 |
| Destination hull | 目标脸 Landmark hull |
| Learned predicted | 模型预测 source mask |
| Learned destination | 模型预测 destination mask |
| Learned 组合 | 相乘或相加 |
| XSeg predicted | 对预测脸运行 XSeg |
| XSeg destination | 对目标脸运行 XSeg |
| XSeg 组合 | learned 与 XSeg 组合 |

### 8.1 当前处理

Mask 通常经历：

```text
选择来源
  ↓
resize 到 mask sub-resolution
  ↓
padding
  ↓
erode 或 dilate
  ↓
boundary clip
  ↓
Gaussian blur
  ↓
裁回有效区域
  ↓
warp 回原帧
```

### 8.2 优点

- 参数自由度高。
- 可适应不同模型和素材。
- XSeg 能改善头发、边界和遮挡。

### 8.3 问题

- 每帧独立计算，mask 可能闪烁。
- XSeg 预测可能对 predicted 和 destination 各执行一次。
- 多次 resize、pad、morphology 和 warp。
- Erode/blur 参数依赖人工经验。
- learned mask、XSeg 和 Landmark mask 之间缺少质量评分。

### 8.4 优化方向

- Mask 时序平滑。
- XSeg Batch inference。
- Landmark/learned/XSeg 自动质量选择。
- 根据脸大小自动缩放 erode/blur。
- 缓存目标脸 XSeg。
- 将 mask 操作合并或 GPU 化。

---

## 9. 颜色迁移与直方图匹配

当前支持多种颜色处理，包括：

- Reinhard Color Transfer
- Linear Color Transfer
- MKL
- IDT
- SOT
- Mix
- Histogram Match
- Masked Histogram Match

### 优点

- 适应不同光照和肤色差异。
- 可以在 seamless 前后执行不同处理。
- 为复杂素材提供手动调节空间。

### 性能问题

- 某些颜色迁移算法计算成本较高。
- 每张脸、每帧重复计算统计量。
- SOT 等算法包含多步迭代。
- CPU NumPy/OpenCV 操作与 GPU predictor 串行。

### 质量问题

- 每帧统计独立，可能产生颜色跳动。
- 遮挡和背景像素会影响颜色统计。
- 不同 mask 模式会导致颜色参数变化。

### 优化方向

- 颜色统计的时间窗口平滑。
- 对同一 track 的参数缓存。
- 基于有效 mask 的稳健统计。
- 自动选择颜色迁移模式。
- 低变化帧复用前一帧参数。

---

## 10. Seamless Clone

当前可使用 `cv2.seamlessClone` 进行融合。

### 当前处理

- 根据 mask 计算 bounding rectangle 和中心。
- 尝试减少中心点变化造成的抖动。
- 发生非内存错误时记录并继续。
- MemoryError 会抛出，以便其他进程重处理。

### 优点

- 某些光照和边界场景融合自然。
- 保留失败降级路径。

### 问题

- CPU 成本高。
- 对 mask 形状和中心敏感。
- 可能在连续帧产生亮度和边界变化。
- 错误处理和重试机制依赖上层 Subprocessor。

### 后续方向

- 记录 seamless 成功率和耗时。
- 对短视频片段进行时序质量评估。
- 提供快速 alpha blend fallback。
- 自动判断是否适合 seamless。

---

## 11. 后处理链路

当前可选处理包括：

- Motion Blur
- Blur/Sharpen
- Median Denoise
- Bicubic Degrade
- Color Degrade

### 11.1 运动模糊

根据 `frame_info.motion_power` 和 `motion_deg` 计算核大小和方向。

风险：

- motion 信息本身的稳定性影响结果。
- 高分辨率和超分时核尺寸扩大。

### 11.2 Blur/Sharpen

用于调整预测脸与原视频清晰度差异。

风险：

- 每帧独立参数可能放大闪烁。
- 锐化可能增强模型伪影。

### 11.3 Denoise

当前 median blur 可能在循环中多次执行，并对整帧图像处理。

这可能是显著 CPU 热点。

### 11.4 Bicubic/Color Degrade

用于匹配低质量目标素材。

需要避免：

- 对整帧重复 resize。
- 多脸时对相同原帧重复执行全局处理。

### 11.5 重要优化原则

应区分：

```text
单脸局部处理
帧级全局处理
视频级时序处理
```

当前部分帧级操作位于单脸路径中，多脸时可能重复执行，应优先审计和外提。

---

## 12. 多脸组合

当前先独立生成每张脸的：

- `out_img`
- `merging_mask`

之后按顺序执行：

```text
final_img = final_img * (1 - mask) + face_img * mask
final_mask = clip(final_mask + mask)
```

### 当前问题

- 重叠区域的结果与处理顺序有关。
- 每张脸都基于原始 `img_bgr` 处理，后组合时可能出现交叉影响。
- 没有显式身份、深度和遮挡优先级。
- 多脸 predictor 和后处理完全串行。

### 后续方向

- 同帧多脸 Batch predictor。
- 根据脸面积、深度、跟踪 ID 或遮挡关系排序。
- 处理 mask 冲突。
- 避免重复帧级处理。
- 多脸场景独立 Benchmark。

---

## 13. 当前性能瓶颈

### GPU 侧

- Predictor Batch Size 1。
- XSeg 逐脸推理。
- Face Enhancer 逐脸推理。
- GPU 任务之间缺少批处理和流水线。

### CPU 侧

- 多次 `warpAffine`。
- 多次 `resize`。
- mask morphology 和 blur。
- 颜色迁移。
- seamlessClone。
- median blur、sharpen、degrade。
- 多脸逐个处理。

### 内存侧

- FP32 图像和 mask 多个临时副本。
- uint8/FP32 反复转换。
- predicted、enhanced、warped、out image 同时存在。
- 多脸 `outs` 保存所有中间输出后再组合。

### I/O 和编码侧

- 帧读取、输出写入和视频编码可能与推理串行。
- 缺少 Decode→Predict→Merge→Encode 的统一流水线。

---

## 14. 视频时序稳定性

当前 Merge 的主要质量控制以单帧为中心。

视频最终质量还取决于：

- Landmark 稳定性
- Predictor 输出稳定性
- Mask 稳定性
- 颜色参数稳定性
- sharpen/denoise 强度稳定性
- 多脸顺序稳定性
- 编码质量

### 建议增加的时序能力

- Face track ID。
- Landmark 矩阵平滑。
- Mask temporal smoothing。
- 颜色统计滑动平均。
- 预测脸特征或像素残差平滑。
- 快速运动和遮挡时的自适应权重。
- 场景切换检测，避免跨镜头平滑。

### 评估指标

- Landmark jitter。
- Mask IoU temporal consistency。
- 颜色均值/方差帧间变化。
- LPIPS/光流对齐后的时序误差。
- 人工观察的闪烁、跳色、边界抖动。

---

## 15. Merge Benchmark 建议

固定场景：

- 单人正脸
- 快速转头
- 大角度侧脸
- 手部/头发遮挡
- 强光照变化
- 多人同框
- 低分辨率素材
- 4K 高分辨率素材

记录阶段耗时：

```text
frame_decode_ms
landmark_transform_ms
predictor_ms
face_enhancer_ms
xseg_ms
mask_process_ms
color_transfer_ms
seamless_ms
postprocess_ms
multi_face_combine_ms
frame_encode_ms
```

资源指标：

- frames/s
- faces/s
- GPU utilization
- VRAM
- CPU utilization
- RAM
- 临时内存峰值
- 编解码吞吐

质量指标：

- 身份一致性
- 边界自然度
- 颜色一致性
- 细节清晰度
- 遮挡处理
- 时序闪烁
- 多脸稳定性

---

## 16. 优化优先级

### P0：正确性和稳定性

- 确认多脸组合顺序和 mask 冲突行为。
- 确认所有模式在无有效 mask 时正确回退。
- 建立失败帧和重试记录。
- 建立固定模型、固定帧的输出回归。
- 分离单脸局部处理与帧级全局处理。

### P1：性能

- Batch predictor。
- Batch XSeg。
- Batch Face Enhancer。
- Decode、Predict、Merge、Encode 流水线。
- 缓存 transform 和目标 XSeg。
- 减少 uint8/FP32 转换。
- 减少重复 warp/resize。
- 避免多脸重复执行全帧 denoise/degrade。

### P1/P2：视频质量

- Landmark 和 transform 平滑。
- Mask temporal smoothing。
- 颜色参数平滑。
- 遮挡感知融合。
- 自动参数推荐。
- 多脸深度/优先级。

### P3：Linux 与 UI

- MergeConfig 结构化。
- 参数预设和版本管理。
- 单帧/区间预览。
- 实时进度和阶段耗时。
- 失败帧回看。
- 输出对比和质量检查。

---

## 17. 建议的目标架构

中期可以演进为：

```text
Frame Decoder
      ↓
Landmark / Track Metadata
      ↓
Face Crop Batch Builder
      ↓
Batch Predictor
      ↓
Batch XSeg / Enhancer
      ↓
Per-face Local Processing
      ↓
Temporal Parameter Smoother
      ↓
Per-frame Multi-face Composer
      ↓
Frame-level Global Postprocess
      ↓
Video Encoder
```

该架构的关键点：

- GPU 推理批处理。
- CPU 和 GPU 阶段并行。
- 单脸、单帧、视频级处理职责分离。
- 保留当前参数语义和 fallback。
- 所有阶段可记录结构化指标。

---

## 18. 后续专项文档

训练和 Extract 主链路稳定后，应创建：

```text
docs/optimization/merging-optimization.md
docs/validation/merging-benchmark-specification.md
docs/validation/video-temporal-quality-evaluation.md
```

分别负责：

- Merge 性能和架构重构。
- 固定素材、模型、配置和阶段指标。
- 时序稳定性与主观质量评估。

---

## 19. 当前结论

当前 Merge 架构功能丰富，支持多种 mask、XSeg、颜色迁移、seamless、增强和后处理模式，能够覆盖复杂合成需求。

主要技术债是：

- Predictor、XSeg 和 Enhancer 逐脸调用。
- 大量 CPU OpenCV 操作串行执行。
- 多脸时可能重复执行帧级处理。
- 图像和 mask 存在多次 resize、warp 和复制。
- 缺少视频级时序平滑。
- 缺少阶段 Benchmark 和自动参数推荐。

最终优化目标不只是单帧更快，而是：

> **让 Decode、推理、Mask、融合和 Encode 形成可观测、可批处理、时序稳定的完整视频流水线。**
