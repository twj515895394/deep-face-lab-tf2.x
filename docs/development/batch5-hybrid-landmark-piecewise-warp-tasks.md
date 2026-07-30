# Batch 5：Hybrid Landmark + Piecewise Affine Warp 详细任务设计

> 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`  
> 当前禁止编码。Batch 4完成后必须基于最终`.srcshape` Schema、loader、confidence和真实Merge入口重新审计。  
> 目标：将src稳定身份几何与dst当前pose/expression组合为Hybrid Landmark，并以可解释、可验证、可回退的Piecewise Affine Warp应用到预测脸；`source_shape_power=0`与传统Merge几何等价。

## 1. Pipeline

```text
validated .srcshape
+ current dst landmarks/pose/expression
 -> Hybrid Landmark Engine
 -> confidence/pose/occlusion gate
 -> fixed triangle topology
 -> piecewise affine warp
 -> warp quality validator
 -> MergeMasked integration
```

## 2. 非目标

- 不生成Template；Batch 4负责。
- 不做Shape-aware Mask或Temporal；Batch 6负责。
- 不做Batch 7训练Loss。
- 不改模型网络/权重/DFM。
- 不优先TPS、neural warp或3D head。

## 3. 关键契约草案

- `source_shape_power`范围`[0,1]`、默认0；0时不加载/不执行Warp或严格等价传统路径。
- Hybrid = transformed src stable geometry + dst dynamic expression offsets；禁止完整src landmarks替换dst。
- fixed 68-point topology、有限坐标、triangle area/flip/out-of-bounds/hole检查。
- 失败回退当前帧传统Merge并输出reason；不得输出部分损坏warp。

## 4. DAG与Ticket

```text
B5-01 baseline/contracts
  ├─ B5-02 config/gates
  ├─ B5-03 template merger context
  └─ B5-04 landmark regions
B5-03+B5-04 -> B5-05 pose transform
B5-04+B5-05 -> B5-06 expression offsets/hybrid
B5-03+B5-06 -> B5-07 confidence fallback
B5-01+B5-04 -> B5-08 triangle topology
B5-06+B5-08 -> B5-09 warp core
B5-07+B5-09 -> B5-10 quality validator
B5-02+B5-03+B5-10 -> B5-11 MergeMasked integration
B5-02+B5-11 -> B5-12 interactive config/session
B5-11+B5-12 -> B5-13 matrix/GPU/visual
B5-13 -> B5-14 docs/review/handoff
```

| ID | 标题 |
|---|---|
| B5-01 | Batch4/Merge真实锚点、坐标拓扑与Fixtures |
| B5-02 | Merge配置、Gate、`source_shape_power`与默认关闭 |
| B5-03 | `.srcshape` Loader接入Merger Context |
| B5-04 | Landmark分区、Stable/Dynamic契约 |
| B5-05 | Canonical Template到DST Pose变换 |
| B5-06 | DST Expression Offset与Hybrid Composition |
| B5-07 | Confidence、极端姿态、遮挡与Fallback |
| B5-08 | Fixed Triangle Topology契约 |
| B5-09 | Piecewise Affine Warp核心 |
| B5-10 | Triangle Flip/Degenerate/Hole/越界质量校验 |
| B5-11 | MergeMasked顺序接入与零强度等价 |
| B5-12 | InteractiveMerger配置、Session和Hotkeys |
| B5-13 | Unit/Integration/Visual/Performance/GPU矩阵 |
| B5-14 | 用户/GUI Schema、Review和Batch6 Handoff |

详细文档：`.scratch/batch5-hybrid-landmark-warp/issues/`。
