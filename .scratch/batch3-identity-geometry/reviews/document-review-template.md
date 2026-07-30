# Batch 3 文档一致性 Review 模板

- Review 状态：PENDING
- Review 基线 SHA：
- Reviewer：

## 必查项

- [ ] 15 个 Ticket 覆盖配置、Hook、结果、错误、Anchor、特征、Loss、SRC/DST、Curriculum、集成、兼容、控制流和验收。
- [ ] DAG 无循环，B3-13 不早于所有基础契约稳定。
- [ ] 每票目标单一，文件/类/函数/测试可由执行模型判断。
- [ ] 不混入 Batch 4—7、Merge、DFM、新 Backbone 或大型外部模型。
- [ ] 所有新能力默认关闭，关闭时基线等价。
- [ ] requested/effective/reason、shape/dtype/mask、NaN/Inf、fallback 与核心错误边界明确。
- [ ] SRC 身份几何与 DST 姿态表情职责未混淆。
- [ ] 旧 checkpoint/options/optimizer 和 save/exit/resume 路径覆盖。
- [ ] GPU 未执行状态没有被写成 PASS。
- [ ] 正式文档、scratch、矩阵、索引和 handoff 一致。

## Findings

| ID | Severity | File/Ticket | Finding | Required Fix | Status |
|---|---|---|---|---|---|

## 结论

仅允许：`APPROVED`、`APPROVED-WITH-NONBLOCKING-NOTES`、`CHANGES-REQUIRED`。在 `APPROVED` 前不得开始 B3-01 编码。