# Batch 4 Source Shape Template 执行计划

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`。当前禁止编码。

## 执行规则

1. Batch 3签发后先执行B4-01重新审计，不得直接B4-02。
2. 一次一票；每票实现、测试、Summary、独立Review、修复、Handoff后再推进。
3. `.srcshape`是独立Geometry Bridge，不进入权重/optimizer/data.dat/DFM。
4. 所有Merge增强默认关闭；缺失/无效Template回退传统Merge。
5. 显式用户来源失败不得静默选择其他来源。
6. B4不修改`MergeMasked`几何，只交付可供B5消费的资产和loader契约。

## Waves

- Wave 0：B4-01 Revalidation。
- Wave 1：B4-02/03/04 Schema、Identity、Resolver。
- Wave 2：B4-05/06 Candidate来源。
- Wave 3：B4-07/08 聚合与生命周期。
- Wave 4：B4-09/10 模型接入和用户入口。
- Wave 5：B4-11/12 兼容与验收。
- Wave 6：B4-13收口。

## 完成门

Code、Automated、Windows Bridge Smoke、Consumer Contract四个状态分别记录；未执行不得写PASS。Batch 5启动前必须再次读取最终`.srcshape`实现和Review报告。
