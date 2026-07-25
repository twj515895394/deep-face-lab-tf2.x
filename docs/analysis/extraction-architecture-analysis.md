# DeepFaceLab TF2.x Extract / 切脸架构分析

> 文档版本：v1.0（代码链路基线）  
> 文档类型：Phase 1 Extract 架构分析  
> 更新日期：2026-07-25

---

## 1. 文档目标

本文档用于梳理当前项目的人脸提取、Landmark、对齐和 Faceset 输出链路，为后续以下工作提供基线：

- Extract 性能优化
- 现代检测器对照
- Landmark 与大角度侧脸优化
- 视频级时序稳定
- Faceset 质量分析
- 多 GPU 和批处理调度
- 未来 Linux 后端任务化

本文描述当前真实代码行为，不代表所有候选优化已经实现。

相关文档：

- [当前项目架构与升级分析](dfl-current-project-overview.md)
- [实现状态与风险矩阵](implementation-status-and-risk-matrix.md)
- [文档总索引](../README.md)

---

## 2. 当前 Extract 主流程

```text
输入图片/视频帧
      ↓
读取与通道归一化
      ↓
人脸框检测（S3FD）
      ↓
必要时尝试 0/90/270/180 度旋转
      ↓
Landmark 检测（FAN）
      ↓
将旋转坐标还原到原图
      ↓
根据 Landmark 计算对齐矩阵
      ↓
cv2.warpAffine 生成人脸图
      ↓
JPEG 编码
      ↓
写入 DFLJPG 元数据
      ↓
输出 Faceset
```

主要实现位于：

```text
mainscripts/Extractor.py
facelib/
DFLIMG/
core/joblib/Subprocessor.py
main.py
```

---

## 3. 代码模块地图

| 模块 | 主要代码 | 作用 |
|---|---|---|
| CLI 入口 | `main.py` | 接收输入、输出、detector、face type、workers 等参数 |
| Extract 调度 | `mainscripts/Extractor.py` | 管理检测、Landmark、final、manual 等阶段 |
| 子进程框架 | `core/joblib/Subprocessor.py` | 为 Extract worker 分发图片任务 |
| 人脸检测 | `facelib.S3FDExtractor` | 检测人脸框 |
| Landmark | `facelib.FANExtractor` | 生成 2D/3D Landmark |
| 几何对齐 | `facelib.LandmarksProcessor` | 变换矩阵、坐标转换和 hull mask |
| 图像读写 | `core.cv2ex` | OpenCV 读写封装 |
| Faceset 元数据 | `DFLIMG/DFLJPG` | 保存 face type、Landmark、来源文件和变换矩阵 |

---

## 4. ExtractSubprocessor 架构

`mainscripts/Extractor.py` 使用 `ExtractSubprocessor` 管理多进程任务。

### 4.1 Data 对象

每张输入图片对应一个数据对象，包含：

- `filepath`
- `rects`
- `rects_rotation`
- `landmarks`
- `landmarks_accurate`
- `manual`
- `force_output_path`
- `final_output_files`
- `faces_detected`

该对象会在检测、Landmark 和最终输出阶段之间传递。

### 4.2 Cli worker

每个 worker 初始化时读取：

- 处理类型
- image size
- JPEG quality
- face type
- max faces
- device index/type
- 输出目录

GPU worker 会建立对应的 Leras device config，并初始化 S3FD/FAN 模型。

### 4.3 支持的阶段

当前主要处理类型包括：

- `rects-s3fd`
- `landmarks`
- `landmarks-manual`
- `final`
- `all`

其中 `all` 会在一个 worker 流程中连续完成检测、Landmark 和最终输出。

---

## 5. 人脸框检测阶段

### 5.1 当前实现

`rects_stage` 主要逻辑：

1. 检查图片最小尺寸。
2. 按顺序尝试原图和旋转图。
3. 调用 S3FD extractor。
4. 找到人脸后停止继续旋转。
5. 根据 `max_faces_from_image` 截断结果。

### 5.2 当前优势

- 能处理部分方向错误的输入图片。
- 保留 S3FD 与原 DFL 工作流兼容性。
- 支持限制每图最大人脸数。
- 可在 GPU 或 CPU 上运行。

### 5.3 当前限制

- 一张图最多可能执行多次完整检测。
- 每张图片逐张送入 detector，缺少 Batch inference。
- S3FD 对极小脸、遮挡、大姿态和复杂多人场景并非总是最佳。
- 旋转尝试是串行流程。
- 检测置信度、框质量和失败原因缺少结构化输出。

### 5.4 后续候选方向

- S3FD Batch inference。
- SCRFD、RetinaFace 或其他现代 detector 对照。
- 多尺度和小脸策略。
- 检测置信度记录。
- 身份过滤和目标人物跟踪。
- 视频级检测复用与 tracking。

---

## 6. Landmark 阶段

### 6.1 当前实现

`landmarks_stage`：

1. 根据检测阶段记录的旋转角度旋转图像。
2. 调用 FAN extractor。
3. 必要时结合 rect detector 提高 Landmark 准确性。
4. 把 rect 和 Landmark 坐标还原到原图坐标系。

### 6.2 当前优势

- 支持普通和 HEAD 类型需要的 Landmark 模式。
- 能处理旋转输入。
- 支持手动阶段重新标注。
- 与 DFL 的对齐和 Faceset 元数据兼容。

### 6.3 当前限制

- Landmark 同样按图片和人脸串行处理。
- 缺少 Landmark 置信度和质量评分。
- 视频相邻帧没有平滑或跟踪约束。
- 大角度侧脸、遮挡和快速运动可能抖动。
- Landmark 异常时缺少自动重试策略。

### 6.4 后续候选方向

- Landmark Batch inference。
- 现代 Landmark 模型对照。
- 2D 与 3D Landmark 混合策略。
- 视频级 Landmark smoothing。
- optical flow / tracking 辅助。
- 异常点检测和自动回退。
- 输出 Landmark confidence 和稳定性分数。

---

## 7. Final 对齐与输出阶段

### 7.1 当前流程

`final_stage` 对每个检测到的人脸：

1. 根据 Landmark 和 face type 计算 `image_to_face_mat`。
2. 使用 `cv2.warpAffine` 对齐到目标分辨率。
3. 将 Landmark 转换到 face 坐标。
4. 进行检测框面积和 Landmark 区域的异常检查。
5. 输出 JPEG。
6. 重新加载 DFLJPG。
7. 写入元数据。
8. 再次保存文件。

### 7.2 写入的主要元数据

- face type
- 对齐后 Landmark
- source filename
- source rect
- source Landmark
- image-to-face matrix

### 7.3 当前性能问题

#### 图像编码和二次写入

当前流程先写 JPEG，再加载 DFLJPG、写元数据并保存，可能产生：

- 重复文件访问
- JPEG 编码成本
- DFLJPG 解析成本
- 小文件 I/O 压力

#### 逐脸 CPU Warp

每张脸分别执行：

- transform matrix
- `cv2.warpAffine`
- Landmark transform
- JPEG encode

在多脸和高分辨率视频中会增加 CPU 时间。

#### JPEG 质量与训练输入

JPEG 有利于兼容和磁盘体积，但会带来：

- 编码耗时
- 解码耗时
- 压缩伪影
- 高频细节损失

需要通过训练质量和读取性能评估是否继续作为唯一格式。

---

## 8. Manual Landmark 流程

当前提供交互式窗口进行人工人脸框和 Landmark 修正。

### 优点

- 作为自动检测失败时的兜底。
- 可以处理特殊姿态和漏检。
- 保留 DFL 原有工作方式。

### 局限

- 强依赖窗口、鼠标和键盘。
- 不适合 Linux 后端无界面运行。
- 不适合远程 UI 或任务队列。
- 自动流程与人工流程耦合在同一脚本中。

### 后续架构方向

未来不应删除人工修正，而应拆成：

```text
后端生成待修正任务
       ↓
UI 展示图片、框和 Landmark
       ↓
用户修改
       ↓
结构化结果提交后端
       ↓
继续 final 阶段
```

这属于 Phase 3，但 Phase 2 新增代码不应继续扩大终端窗口耦合。

---

## 9. Worker 与设备调度

### 9.1 当前策略

`get_devices_for_config` 会：

- GPU 模式下按每 GPU worker 数创建 worker。
- 手动 Landmark 只使用最佳设备。
- CPU 模式按 CPU 核心数创建有限 worker。
- final 阶段主要使用 CPU worker。

### 9.2 优点

- 能利用多 GPU 和多进程。
- 用户可配置 `workers_per_gpu`。
- CPU final 阶段可以并行输出。

### 9.3 风险

- 多个 worker 可能重复加载 detector 和 Landmark 模型。
- GPU 显存占用与 worker 数不是线性可控。
- 同一 GPU 多 worker 可能互相争抢计算和上下文。
- worker 数是静态参数，不根据图片分辨率、磁盘和模型耗时调整。
- 检测、Landmark、final 没有形成独立流水线队列。

### 9.4 后续方向

更合理的结构可以是：

```text
Decode Queue
    ↓
Detector Batch Worker
    ↓
Landmark Batch Worker
    ↓
Align / Encode Worker
    ↓
Metadata Writer
```

不同阶段可独立扩缩容，不必让每个 worker 加载全部模型。

---

## 10. 当前 Extract 数据流问题

### 10.1 图片重复读取

在分阶段执行 rects、Landmark 和 final 时，同一图片可能被多次读取。

### 10.2 模型和数据耦合

一个 worker 同时承担：

- TensorFlow 模型推理
- OpenCV 图像处理
- 文件 I/O
- 元数据写入

不利于精确定位瓶颈。

### 10.3 缺少 Batch

Detector 和 Landmark 没有统一 Batch 调度，GPU 利用率可能不足。

### 10.4 缺少时序信息

视频帧被当作独立图片处理，未利用：

- 相邻帧同一身份
- 框位置连续性
- Landmark 连续性
- 检测结果复用

### 10.5 缺少质量观测

目前 Faceset 输出后，仍需要人工判断：

- 是否模糊
- 是否重复
- 是否错误身份
- 是否遮挡
- 是否过曝/欠曝
- 姿态是否均衡

这使低质量数据直接进入训练的概率较高。

---

## 11. Faceset Analyzer 的必要性

Extract 后建议增加独立流程：

```text
Extract
   ↓
Analyze
   ↓
Filter
   ↓
Deduplicate
   ↓
Identity Check
   ↓
Pose / Expression / Occlusion Balance
   ↓
Pack
   ↓
Training
```

### 建议分析维度

- 清晰度
- 分辨率与有效脸面积
- 人脸检测置信度
- Landmark 置信度
- 姿态角
- 表情
- 遮挡
- 光照
- 颜色分布
- 重复帧
- 相似帧
- 身份一致性
- 边界裁切
- JPEG 伪影

### 建议输出

每张脸生成结构化元数据：

```json
{
  "filename": "000123_0.jpg",
  "sharpness": 0.82,
  "yaw": 34.2,
  "pitch": -6.1,
  "occlusion": 0.18,
  "identity_score": 0.94,
  "duplicate_group": "dup-018",
  "quality_status": "usable"
}
```

该数据后续可以直接服务于智能采样器。

---

## 12. Extract Benchmark 建议

需要固定数据集：

- 单人正脸视频
- 快速运动视频
- 大角度侧脸
- 低光与噪声
- 多人场景
- 小脸和远景
- 遮挡场景

记录：

| 阶段 | 指标 |
|---|---|
| Decode | frames/s、decode time |
| Detector | images/s、recall、false positive |
| Landmark | faces/s、失败率、抖动 |
| Align | faces/s、warp time |
| Encode | faces/s、写入 MB/s |
| Overall | frames/s、faces/s、总耗时 |
| Resource | GPU 利用率、VRAM、CPU、RAM、磁盘 I/O |

质量指标：

- 人脸检出率
- 错检率
- Landmark 失败率
- 对齐稳定性
- 相邻帧中心点和角度抖动
- 人工修正比例

---

## 13. 优化优先级

### P0：正确性与数据质量

- 保证 DFLJPG 元数据完整。
- 建立 Landmark/对齐异常检测。
- 建立 Extract 输出质量报告。
- 验证多 worker 不产生重复、遗漏或损坏文件。

### P1：性能

- Detector Batch inference。
- Landmark Batch inference。
- Decode、推理、final 分阶段流水线。
- 减少图片重复读取。
- 减少 JPEG 二次写入。
- 自适应 worker 和队列深度。

### P1/P2：质量

- 现代 detector 对照。
- 现代 Landmark 对照。
- 时序平滑。
- 视频 tracking。
- Faceset Analyzer。
- 智能去重和身份过滤。

### P3：UI 与服务化

- 人工修正任务化。
- Web/桌面 UI Landmark 编辑器。
- Extract 任务进度和错误列表。
- Faceset 质量面板。

---

## 14. 后续专项文档

训练核心链路稳定后，应创建：

```text
docs/optimization/extraction-optimization.md
docs/optimization/faceset-intelligence-design.md
docs/validation/extraction-benchmark-specification.md
```

这些文档分别负责：

- Extract 性能与调度
- Faceset 质量分析和采样数据
- 固定数据集和验证指标

---

## 15. 当前结论

当前 Extract 架构保留了成熟、可工作的 S3FD + FAN + DFLJPG 流程，并已支持多进程和多 GPU worker。

主要技术债是：

- detector 和 Landmark 缺少 Batch inference。
- 处理阶段耦合在 worker 内。
- 视频时序信息没有利用。
- final 阶段有较多 CPU Warp、JPEG 和文件 I/O。
- Faceset 输出后缺少自动质量管理。

因此 Extract 优化的最终目标不应只是“切得更快”，而应同时做到：

> **更快、更稳、更少人工修正，并为训练采样提供高质量结构化数据。**
