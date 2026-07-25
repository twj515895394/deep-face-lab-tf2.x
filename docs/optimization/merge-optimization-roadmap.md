# Merge / 合成链路优化路线设计

> Phase 2 优化路线文档
>
> 目标：系统分析 DeepFaceLab 合成阶段的性能、质量和架构演进方向，为后续代码改造提供设计依据。

## 1. 当前 Merge Pipeline

当前合成流程：

```
Video Decode
    ↓
Face Detection / Landmark
    ↓
Face Transform
    ↓
Model Predictor
    ↓
Mask Generation
    ↓
Color Transfer
    ↓
Face Blending
    ↓
Post Processing
    ↓
Video Encode
```

核心目标：

- 提升推理吞吐
- 降低 CPU 瓶颈
- 提升视频时序稳定性
- 减少边缘融合痕迹
- 提高多人场景稳定性

---

# 2. 当前架构问题分析

## 2.1 逐帧处理模型

当前大量流程类似：

```
Frame
 ↓
Face
 ↓
Predict
 ↓
Merge
 ↓
Next Frame
```

问题：

- GPU 等待 CPU
- 无法充分利用 Batch 推理
- 视频解码与推理无法流水线执行

---

# 3. 推理性能优化

## 3.1 Batch Predictor

当前：

```
Face1 → GPU
Face2 → GPU
Face3 → GPU
```

优化：

```
Face1
Face2
Face3

 ↓

Batch Tensor

 ↓

GPU Inference
```

收益：

- 提高 GPU 利用率
- 降低 kernel launch 开销

风险：

- 显存增加
- 多人脸排序需要稳定

---

## 3.2 推理流水线

目标架构：

```
Decode Worker
      ↓
Frame Queue
      ↓
Predict Worker
      ↓
Merge Worker
      ↓
Encode Worker
```

减少：

- IO 等待
- GPU idle

---

# 4. Mask 优化路线

## 4.1 当前 Mask 来源

包括：

- Learned Mask
- XSeg Mask
- FAN Mask
- Blur Mask

需要统一评估：

- 边缘质量
- 遮挡处理
- 稳定性

---

## 4.2 Mask 时序稳定

视频场景中重点解决：

- mask 闪烁
- 边缘跳动
- 快速运动破碎

候选方案：

- Optical Flow Warp
- Temporal Filtering
- Landmark Motion Compensation

---

# 5. Color Transfer 优化

当前颜色迁移：

- Histogram Matching
- Reinhard
- Linear Transfer

问题：

- 每帧独立计算
- 光照变化导致颜色跳变

优化方向：

- Temporal Color Cache
- 光照估计
- 视频级颜色模型

---

# 6. Blend 融合优化

重点：

## Seamless Clone

优点：

- 自动融合

问题：

- CPU 消耗高
- 多脸场景慢

---

## GPU Blend

研究方向：

- CUDA Alpha Blend
- GPU Warp
- GPU Mask Processing

目标：

减少 OpenCV CPU 操作。

---

# 7. Face Enhancer 优化

包括：

- Super Resolution
- Face Enhancement
- Sharpen

优化方向：

- 按区域启用
- Batch enhancer
- GPU pipeline
- 避免重复 resize

---

# 8. 多脸场景优化

当前问题：

- 人脸排序变化
- 身份匹配错误
- 多人遮挡复杂

方向：

- Face Tracking
- Identity Tracking
- Temporal Association

---

# 9. 视频时序质量优化

最终评价不能只看单帧。

重点指标：

- Identity consistency
- Landmark stability
- Color stability
- Mask stability
- Motion consistency

候选：

- Optical Flow Constraint
- Temporal Loss
- Frame-to-frame Consistency

---

# 10. Benchmark 设计

Merge 需要独立测试：

## 性能

- frames/sec
- inference time
- GPU utilization
- CPU utilization
- encode time

## 质量

- 单帧质量
- 视频闪烁
- 边缘融合
- 身份保持

---

# 11. 优先级规划

## P0

- Merge Pipeline Profiling
- Predictor Batch 化分析
- Decode/Encode 流水线
- Mask 时序稳定

## P1

- GPU Blend
- GPU Warp
- Temporal Color
- Face Tracking

## P2

- 视频级模型增强
- Temporal Neural Merge
- 新型融合网络

---

# 12. Phase 2 完成标准

Merge 优化完成需要满足：

1. 性能指标可量化
2. 单帧质量提升可验证
3. 视频稳定性提升可观察
4. 不破坏旧模型兼容
5. 为未来 UI 服务化提供结构化接口
