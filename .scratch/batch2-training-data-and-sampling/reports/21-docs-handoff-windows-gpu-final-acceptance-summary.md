# Ticket 21 — 文档 / Handoff / Windows GPU 最终验收 Summary

> 实现侧状态：**PARTIAL / NOT RESOLVED**  
> 日期：2026-07-30  
> 分支：`codex/batch2-ticket19-loss-window`  
> 实现者不得签发 Batch 2 DONE

---

## 1. 前置 summary 检查

| Ticket | Summary 文件 | 状态 |
|---:|---|---|
| 14 | 存在 | CLOSED（历史独立 Review） |
| 15 | 存在 | CLOSED |
| 16 | 存在 | PASS-CODE |
| 17 | 存在 | PASS-CODE |
| 18 | 存在 | IMPL awaiting review |
| 19 | 存在 | CLOSED |
| 20 | 存在 | IMPL awaiting review |

前置：**满足开工文档条件**；**不满足** GPU 关闭条件。

---

## 2. 本 Ticket 已完成（文档 / 交接）

1. 标记历史综合 Review 为 **SUPERSEDED**  
   `reports/batch2-comprehensive-code-review.md`
2. 更新使用说明与状态  
   - `docs/usage/faceset-analyzer-complete-guide.md`（workers/strong/exit codes/中文路径）  
   - `docs/usage/faceset-metadata-and-sampling.md`（现状表）
3. 更新 Windows 验收记录为诚实 **PENDING-WINDOWS-GPU**  
   `reports/windows-gpu-acceptance.md`
4. 刷新 `.handoff/current.md` 与本 summary
5. 记录本机探测：Python 3.11.7 **无 TensorFlow**，无法跑 SAEHD 矩阵

---

## 3. 明确未完成（阻断 resolved）

```text
Matrix A/B SAEHD FP32 + AdaBelief ≥500 iter
manual save / exit / resume ≥200
GPU 显存 / iter time 量化
生产签发 Batch 2 DONE
合入 main
```

标签：

```text
ENV-VALIDATION-DEFERRED
PENDING-WINDOWS-GPU
```

---

## 4. 代码侧 smoke 证据

```text
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
→ Ran 331 / OK / EXIT=0（实现侧，2026-07-30）
```

含 Ticket 18 等价性、Ticket 20 fallback 边界、Unicode 路径。

---

## 5. --options-json

Ticket 21 本体无新增训练参数。  
Ticket 20 已同步 §9.1–9.2（fallback/strict）。  
本 Ticket 文档同步：**PASS（引用已同步章节）**

---

## 6. Verdict

```text
Ticket 21：NOT RESOLVED / PARTIAL
Docs/Handoff：UPDATED
Windows GPU：PENDING
Batch 2：NOT DONE
禁止合入 main
```

下一步：独立 Review 18/20 → 有 GPU 的机器补 SAEHD 矩阵 → 再审 Ticket 21。
