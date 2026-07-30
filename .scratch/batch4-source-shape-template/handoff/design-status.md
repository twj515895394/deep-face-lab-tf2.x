# Batch 4 Source Shape Template 设计状态

```text
Ticket count: 13
Drafting: COMPLETE
Detailed weak-model issues: COMPLETE-DRAFT
Document review: PENDING-AFTER-B3
Coding: BLOCKED-BY-BATCH3-AND-REVALIDATION
First future ticket: B4-01
Tests/GPU/Windows: NOT EXECUTED
```

不得直接执行B4-02及后续。Batch3完成后先读取最终产物，执行B4-01差异审计，修订全部受影响Issue并做独立Review。Batch4边界是`.srcshape` Geometry Bridge；不实现Hybrid Landmark、Warp、Mask或Temporal。
