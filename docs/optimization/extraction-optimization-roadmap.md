# DeepFaceLab TF2.x Extract / 切脸与数据处理优化路线设计

> Phase 2 优化文档：Extract Pipeline Optimization
>
> 目标：提升切脸效率、数据质量和训练输入质量，为 SAEHD 训练提供更高价值的数据基础。

---

## 1. 当前 Extract Pipeline

当前流程：

```
Video Frames
    ↓
Face Detector (S3FD)
    ↓
Landmark Detector (FAN)
    ↓
Face Alignment
    ↓
WarpAffine
    ↓
DFLJPG Metadata
    ↓
Faceset
```

核心目标：

- 更快
- 更稳定
- 更高质量
- 更适合大规模训练

---

# 2. 当前主要瓶颈

## 2.1 Detector

问题：

- S3FD 较老
- 小脸检测能力有限
- 多人场景效率不足
- Batch 推理能力有限

优化方向：

候选：

- SCRFD
- RetinaFace
- YOLO-Face

评估指标：

- AP
- FPS
- GPU Memory
- 小脸召回率

---

## 2.2 Landmark

当前重点：

- FAN 精度
- 大角度脸
- 遮挡情况下稳定性

优化方向：

- InsightFace Landmark
- 3D Landmark
- 时序 Landmark smoothing

---

# 3. Extract Pipeline 重构

当前：

```
Decode
 ↓
Detect
 ↓
Landmark
 ↓
Align
 ↓
Save
```

目标：

```
Decode Worker
      ↓
Detector Batch Queue
      ↓
Landmark Batch Queue
      ↓
Alignment Worker
      ↓
Writer Worker
```

实现流水线并行。

---

# 4. GPU 利用优化

## 当前问题

- GPU worker 数量固定
- CPU/GPU 阶段耦合
- 不同 GPU 性能无法动态调度

优化：

支持：

- GPU detection worker
- GPU landmark worker
- CPU save worker
- 自动 worker 数量调整

---

# 5. Faceset 智能化

新增 Faceset Analyzer：

分析：

- 清晰度
- 模糊程度
- 重复帧
- 姿态角度
- 遮挡比例
- 光照
- 人脸质量

流程：

```
Extract
 ↓
Analyze
 ↓
Filter
 ↓
Balance
 ↓
Training
```

---

# 6. 视频级优化

增加：

## Face Tracking

避免：

- 每帧重新检测
- Landmark 抖动

方向：

- Optical Flow
- Tracker
- Temporal smoothing

---

# 7. Faceset 存储优化

当前：

- JPG 文件
- 单文件 metadata

未来：

- Packed Faceset
- SQLite Index
- mmap 数据读取
- 缓存热数据

目标：减少训练阶段 IO。

---

# 8. Benchmark

Extract 需要独立测试：

指标：

- frames/sec
- detect FPS
- landmark FPS
- GPU utilization
- CPU utilization
- faces/hour
- quality score

---

# 9. 开发优先级

## P0

- Extract Benchmark
- Faceset Analyzer
- 数据质量评分
- Pipeline profiling

## P1

- Batch detector
- Batch landmark
- Shared memory pipeline
- Tracker

## P2

- 新检测模型
- 3D landmark
- 智能数据平衡

---

# 10. 与训练优化关系

Extract 不是独立模块。

高质量训练依赖：

```
Better Faceset
      ↓
Better Sampling
      ↓
Better Convergence
      ↓
Better Final Video Quality
```

因此 Extract 优化优先考虑数据质量，而不是单纯速度。
