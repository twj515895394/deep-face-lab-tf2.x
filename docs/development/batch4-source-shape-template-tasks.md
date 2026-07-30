# Batch 4：Source Shape Template（Geometry Bridge）详细任务设计

> 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`  
> 当前不允许编码。Batch 3完成后必须用最终ShapeAnchorV1、ratio/SDF定义和A/B结果重新审计、修订、独立Review。  
> 目标：把训练侧可信src geometry转换为Merge可读取、可校验、可回退的权威独立资产 `model_name.srcshape`，不修改模型权重、optimizer、DFM和传统Merge。

## 1. 批次产物

```text
ShapeAnchor / offline faceset / training-derived candidate
  -> Source Resolution Policy
  -> robust template aggregation
  -> model_name.srcshape v1
  -> atomic writer + strict loader
  -> identity/model/fingerprint/confidence validation
  -> later Batch 5 merger context
```

## 2. 非目标

- 不实现Hybrid Landmark、Piecewise Warp、Shape-aware Mask、Temporal。
- 不改变`MergeMasked`几何。
- 不将Template写入权重、`data.dat`、DFM、DFLJPG/PNG或faceset.pak。
- 不自动选择冲突来源。
- 不引入3DMM、大型身份模型或新网络。

## 3. 核心契约草案

文件：`<saved_models_path>/<model_name>.srcshape`或与现有`get_strpath_storage_for_file`一致的无歧义命名；最终命名在B4-01代码审计后冻结。

Schema至少包含：schema/generator版本、model identity、source identity、faceset fingerprint、landmark schema、canonical landmarks、固定ratio names/values、confidence/quality、sample summary、aggregation/provenance、compatible consumer版本。

加载失败只关闭Shape Merge能力，不阻止传统Merge；显式用户路径错误不得静默改选其他来源。

## 4. Ticket DAG

```text
B4-01 baseline/contracts
  ├─ B4-02 srcshape schema
  ├─ B4-03 identity/provenance
  └─ B4-04 source priority resolver
B4-02+B4-03 -> B4-05 offline builder
B4-02+B3-final -> B4-06 training candidate adapter
B4-05+B4-06 -> B4-07 aggregation/confidence
B4-02+B4-03+B4-07 -> B4-08 writer/loader/cache
B4-08 -> B4-09 model path/discovery
B4-04+B4-08+B4-09 -> B4-10 CLI/user override
B4-08+B4-10 -> B4-11 compatibility/failure/security
B4-11 -> B4-12 Windows bridge acceptance
B4-12 -> B4-13 docs/review/handoff
```

## 5. Ticket列表

| ID | 标题 |
|---|---|
| B4-01 | 真实代码/Batch3产物复核、坐标与Fixtures |
| B4-02 | `.srcshape` Schema v1与版本契约 |
| B4-03 | Model/SRC Identity、Fingerprint与Provenance |
| B4-04 | Template来源优先级与冲突Resolver |
| B4-05 | Offline Faceset Template Builder |
| B4-06 | Batch3 Anchor/训练派生Candidate Adapter |
| B4-07 | Robust Aggregation、Quality与Confidence |
| B4-08 | Atomic Writer、Loader、Cache与Invalidation |
| B4-09 | Model命名、默认路径、Discovery与生命周期 |
| B4-10 | CLI、用户显式Override与报告 |
| B4-11 | 兼容、失败、安全和Fallback矩阵 |
| B4-12 | Windows Bridge Smoke、性能与视觉验收 |
| B4-13 | 用户/GUI Schema、Review和Handoff收口 |

详细文档：`.scratch/batch4-source-shape-template/issues/`。

## 6. Revalidation Gate

开始B4-01前必须记录Batch 3最终Commit、ShapeAnchor schema、ratio顺序、confidence/fingerprint、实际保存目录、GPU/A-B状态和偏差。若与草案冲突，先更新本文件和全部受影响Ticket，再Review；不得让执行Agent自行适配。
