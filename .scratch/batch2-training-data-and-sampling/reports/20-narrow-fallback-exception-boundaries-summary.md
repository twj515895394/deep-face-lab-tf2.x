# Ticket 20 — Narrow Fallback Exception Boundaries Summary

> 状态：IMPLEMENTATION COMPLETE / AWAITING REVIEW  
> 分支：`codex/batch2-ticket19-loss-window`  
> `--options-json` 文档同步：**PASS**  
> 文档版本：options-json-training-configuration-reference.md §9.1–9.2  
> 修改章节：runtime fallback / strict_validation 语义与决策矩阵

---

## 异常分类

| 类别 | 处理 |
|---|---|
| SampleLoader / empty / PermissionError / MemoryError / RuntimeError | **core raise** |
| Metadata missing/invalid/mismatch status | optional：fallback 或 raise（按 flags） |
| Metadata OSError/ValueError/JSONDecodeError | optional 窄捕获 |
| 其他 Exception from loader | **core RuntimeError**（不 fallback） |
| Policy factory ValueError | optional 可 fallback；其他异常不吞 |

## strict / fallback 矩阵

见权威文档 §9.2。`strict_validation=true` 时 optional 问题一律 raise。

## broad except 审计（runtime.py）

- 无 `except Exception: fallback`  
- SampleLoader 在 optional try 外  
- Metadata 仅窄异常 + 最终 `except Exception: raise RuntimeError`  

## 测试

```text
test_batch2_sampling_fallback：PASS
test_batch2_fallback_exception_boundaries：PASS
full test_batch*.py：Ran 327 / OK / EXIT=0
```

实现者不得签发 APPROVED/PASS/CLOSED。
