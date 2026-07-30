# Batch 6 Shape-aware Soft Mask + Temporal 设计状态

```text
Ticket count: 14
Detailed drafting: COMPLETE-DRAFT
Document review: PENDING-AFTER-B5
Coding: BLOCKED-BY-BATCH5-AND-REVALIDATION
First future ticket: B6-01
Tests/Windows/Visual: NOT EXECUTED
```

边界：只做Shape-aware Soft Mask和Temporal；不重做Template/Warp，不做Batch7通用训练Loss。Batch5完成后必须先B6-01真实审计并修订，尤其关注WarpResult、mask顺序、worker乱序和多脸identity。
