# Batch 6：Shape-aware Soft Mask + Temporal 详细任务设计

> 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B5`  
> 当前禁止编码。Batch 5完成后必须基于最终Hybrid/Warp/Quality/Merge顺序和多脸进程行为重新审计。  
> 目标：利用已验证的warped src contour/coverage构造Shape-aware Soft Mask，并对几何/Mask参数做逐脸时序稳定；默认关闭，失败回退Batch5或传统Merge。

## 1. Pipeline

```text
Batch5 WarpResult/Quality + predicted/dst/XSeg masks
 -> warped contour support map
 -> source contour soft mask
 -> confidence/occlusion composition
 -> existing erode/blur/color/blend

per-face geometry/mask measurements
 -> temporal state
 -> EMA / One Euro
 -> scene-cut/tracking-lost reset
 -> stable parameters/output
```

## 2. 非目标

- 不重新生成Template或Hybrid/Warp。
- 不实现Batch7训练Boundary/Frequency/Appearance Loss。
- 不引入大型视频跟踪网络。
- 不修改模型权重/DFM。
- 不保证实时服务化/UI。

## 3. 核心规则

- `shape_aware_mask=false`、`temporal_stabilization=false`默认。
- Mask组合必须保留现有predicted/dst/XSeg语义，并明确插入顺序。
- Temporal state按face/track隔离，场景切换/跟踪丢失/模型或config变化重置。
- 缺失可靠track identity时宁可禁用跨帧平滑，不跨脸污染。
- 任何invalid Warp/Mask状态回退到Batch5/传统路径。

## 4. DAG/Tickets

```text
B6-01 baseline/contracts
  ├─ B6-02 config/gates
  ├─ B6-03 contour support
  └─ B6-08 temporal state identity
B6-03 -> B6-04 source soft mask
B6-02+B6-04 -> B6-05 hybrid mask composition
B6-05 -> B6-06 occlusion/confidence fallback
B6-05+B6-06 -> B6-07 MergeMasked order integration
B6-08 -> B6-09 EMA/OneEuro
B6-08+B6-09 -> B6-10 reset/multi-face isolation
B6-07+B6-10 -> B6-11 batch/interactive/session lifecycle
B6-07+B6-10 -> B6-12 diagnostics/metrics
B6-11+B6-12 -> B6-13 matrix/GPU/visual
B6-13 -> B6-14 docs/review/handoff
```

| ID | 标题 |
|---|---|
| B6-01 | Batch5输出、Mask/Temporal契约与Fixtures |
| B6-02 | 配置Schema、Gate、默认关闭与模式 |
| B6-03 | Warped Contour Support/Coverage Map |
| B6-04 | Source Contour Soft Mask生成 |
| B6-05 | Predicted/DST/XSeg与Shape Mask组合 |
| B6-06 | Occlusion、Confidence与Fallback |
| B6-07 | MergeMasked Mask顺序接入与零影响 |
| B6-08 | Per-face/Track Temporal State与身份 |
| B6-09 | EMA与One Euro Filter |
| B6-10 | Scene Cut、Tracking Lost、Reset与多脸隔离 |
| B6-11 | Batch/Interactive/Session/Parallel生命周期 |
| B6-12 | Temporal/Mask Diagnostics与Metrics |
| B6-13 | Regression/Performance/Visual/Windows矩阵 |
| B6-14 | 用户/GUI Schema、Review与后续Handoff |

详细文档：`.scratch/batch6-shape-mask-temporal/issues/`。
