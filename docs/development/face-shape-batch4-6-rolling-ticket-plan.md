# Face Shape Batch 4–6 滚动拆票与复核策略

> 状态：`ROLLING-DESIGN-POLICY`  
> 日期：2026-07-30  
> 适用批次：Batch 4 Source Shape Template、Batch 5 Hybrid Landmark + Piecewise Affine Warp、Batch 6 Shape-aware Soft Mask + Temporal

## 1. 决策

现在可以、也应该提前拆分 Batch 4–6，但这些 Issue 是详细施工草案，不是立即编码许可。

```text
现在：拆到文件/函数/数据/测试级，状态 DESIGN-DRAFT
Batch 3完成：重新审计真实Anchor/Ratio/A-B，修订并冻结Batch 4
Batch 4完成：重新审计真实.srcshape/loader，修订并冻结Batch 5
Batch 5完成：重新审计真实Hybrid/Warp/Merge顺序，修订并冻结Batch 6
```

## 2. 状态语义

- `DESIGN-DRAFT-REVALIDATE-AFTER-B3/B4/B5`：内容足够用于架构评审和前置接口保护，但禁止直接编码。
- `DOCUMENT-REVIEW-PASSED`：本批草案内部一致，不代表前置实现已经满足。
- `READY-FOR-<TICKET>`：只有完成前置批次代码审计、修订、独立Review后才能授予。

## 3. 为什么提前拆

- 保护Batch 3 Anchor字段能服务Batch 4 Template。
- 保护Batch 4 `.srcshape`能服务Batch 5 Merge。
- 保护Batch 5 Warp输出能服务Batch 6 Mask和Temporal。
- 提前识别跨批次坐标系、身份、fallback、配置和评估缺口。

## 4. 为什么不能现在冻结

真实实现可能改变：

- Schema字段、ratio定义和confidence。
- 文件命名、路径、模型生命周期。
- Merge函数插入点和数据流。
- Warp质量、性能和视觉结果。
- 多脸、场景切换、遮挡的实际约束。

因此后批Issue必须允许在前批完成后增删、合并、拆分或改依赖，但修改必须保留Review记录。

## 5. 每批Revalidation输入

### Batch 4启动前

- Batch 3最终ShapeAnchorV1和loader。
- ratio names/order、SDF/contour定义。
- Geometry A/B结果和已知局限。
- 模型保存目录、命名和权限行为。

### Batch 5启动前

- Batch 4最终`.srcshape` Schema、来源优先级和fallback。
- Template confidence和fingerprint规则。
- 实际Merge入口、MergerConfig和session兼容。

### Batch 6启动前

- Batch 5最终Hybrid Landmark、triangle topology、Warp输出和quality flags。
- MergeMasked实际执行顺序。
- 多脸/多进程和interactive session实际行为。

## 6. 弱模型执行保护

- 一次只执行一个Ticket。
- Ticket必须预先指定文件、函数、接口、默认值、错误语义和测试。
- 未决架构项单独设计票，不让编码Agent临场决定。
- 每票：实现→测试→Summary→独立Review→修复→状态同步。
- 不允许将后续批次功能提前塞进当前票。

## 7. 批次边界

```text
Batch 4：权威Geometry Bridge资产，不改Merge几何
Batch 5：Hybrid Landmark与Warp，不做Shape-aware Mask/Temporal
Batch 6：Mask与Temporal，不做Batch 7通用训练Loss
```

## 8. 当前状态

```text
Batch 3: READY-FOR-B3-01-ONLY
Batch 4: DESIGN-DRAFT-REVALIDATE-AFTER-B3
Batch 5: DESIGN-DRAFT-REVALIDATE-AFTER-B4
Batch 6: DESIGN-DRAFT-REVALIDATE-AFTER-B5
```
