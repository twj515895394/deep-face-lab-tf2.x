# Ticket 18 / 20 独立 Review 与 Batch 2 完成状态

> Review 日期：2026-07-30  
> 工作分支：`codex/batch2-ticket19-loss-window`  
> 被审 Head：`c53e8e1c521d3e8b9ec3260a750e32b6a2ee1abd`  
> 方法：独立静态源码、测试源码、Ticket 冻结规约、Summary 与实现侧 Windows smoke 证据复核。GitHub 无 Actions/status check；Reviewer 未重新执行 Windows GPU SAEHD 矩阵。

---

## 1. Verdict

```text
Ticket 18：APPROVED / PASS / CLOSED
Ticket 20：APPROVED / PASS / CLOSED

Ticket 21：IMPLEMENTATION + DOCS COMPLETE
           FINAL WINDOWS GPU ACCEPTANCE PENDING
           NOT CLOSED

Batch 2：ALL PLANNED CODE/DOC IMPLEMENTATION COMPLETE
         CODE GATES COMPLETE
         FINAL PRODUCTION SIGN-OFF PENDING WINDOWS GPU
         NOT YET BATCH2 DONE
```

“全部 Ticket 完成”在当前仓库中应准确理解为：

```text
所有计划内代码、测试、Summary、使用文档和 handoff 均已实现；
仅 Ticket 21 的真实 Windows GPU 最终环境矩阵尚未执行。
```

不得把未执行的 GPU 训练写成 `PASS-WINDOWS-GPU`。

---

## 2. Ticket 18 Review

### 2.1 已确认实现

```text
full / incremental 共用 build_canonical_summary
summary 使用公共 record accessors
reused / newly analyzed record 深拷贝
removed record 不进入结果
重复 sample_key / sample_id 明确失败
Pass 2 对最终 faceset 全量重新归一化
Report 以 Metadata.summary 为聚合事实源
增量运行计数独立记录
SampleLoader cache 在 Analyzer 扫描前失效
```

### 2.2 等价性测试

`test_batch2_incremental_full_equivalence.py` 使用真实 Analyzer 生成的嵌套 record，覆盖：

```text
no-change incremental
add one sample
same-name modify：recomputed=1 / reused=N-1
remove one sample
Packed no-change
Unicode directory
incremental 与 force-full 的 schema / fingerprint / sample order /
signature / pose / quality / normalization / summary 精确比较
```

允许差异仅限 created_at / elapsed / timing 等运行字段，浮点使用明确 tolerance。

### 2.3 Ticket 18 签发

```text
APPROVED / PASS / CLOSED
```

未发现阻止 Ticket 21 继续的代码契约缺陷。

---

## 3. Ticket 20 Review

### 3.1 已确认实现

```text
Phase A：SampleLoader 在 optional Metadata try 外
空 faceset 与 SampleLoader 核心异常直接传播
Phase B：Metadata optional 状态按 fallback/strict 矩阵处理
MemoryError / KeyboardInterrupt / SystemExit 明确传播
未分类 Exception 转为 core RuntimeError，不进入 legacy fallback
Phase C：Policy resolve 仅对受控 ValueError 允许 optional fallback
其他 Policy / Host / worker 异常不 broad-catch
strict_validation 已真实接入
SRC / DST 分侧构建与日志保持隔离
options-json §9.1–9.2 已同步
```

### 3.2 测试证据

新增边界测试覆盖：

```text
missing Metadata：fallback true / false
strict=true 即使 fallback=true 也 raise
SampleLoader ValueError / PermissionError / MemoryError / RuntimeError 传播
empty samples 传播
SRC/DST optional 隔离
SRC core failure 不得 fallback
```

实现侧完整冻结测试记录：

```text
Windows / Python 3.11.7 / spawn
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
Ran 331 tests
OK
shell EXIT=0
```

### 3.3 非阻断硬化建议

当前 Metadata loader 调用边界仍按内建异常类型区分部分 optional parse/record 问题。后续可引入 `MetadataOptionalError` 子类进一步收窄，但现有作用域只包围 Metadata loader，SampleLoader 已在外部，MemoryError 与未分类异常也不会静默回退；未发现必须阻止本 Ticket 签发的实际失败路径。

### 3.4 Ticket 20 签发

```text
APPROVED / PASS / CLOSED
```

---

## 4. Ticket 21 与 Batch 2 最终状态

Ticket 21 的文档、Handoff、权威使用说明、旧 Review superseded 标记和验收模板已经实施。

但 `windows-gpu-acceptance.md` 当前明确记录：

```text
acceptance Python 无 TensorFlow
SAEHD GPU 训练未启动
Matrix A/B 未执行
Ticket 21 GPU gate：NOT PASS
```

因此当前只能签发：

```text
ALL-TICKET-IMPLEMENTATION-COMPLETE
TICKET21-FINAL-ENV-VALIDATION-PENDING
BATCH2-CODE-COMPLETE
BATCH2-NOT-PRODUCTION-SIGNED
```

完成真实 Windows GPU 矩阵或由维护者明确修改/豁免 Ticket 21 的硬性验收规约后，才能进一步签发：

```text
Ticket 21：PASS / CLOSED
Batch 2：DONE
允许合入 main
允许正式启动 Batch 3
```

---

## 5. Current Gate

```text
Ticket 14：PASS / CLOSED
Ticket 15：PASS / CLOSED
Ticket 16：PASS-CODE / ENV VALIDATION DEFERRED
Ticket 17：PASS-CODE / PERF VALIDATION DEFERRED
Ticket 18：PASS / CLOSED
Ticket 19：PASS / CLOSED
Ticket 20：PASS / CLOSED
Ticket 21：IMPLEMENTATION COMPLETE / WINDOWS GPU PENDING / NOT CLOSED

Batch 2 implementation：COMPLETE
Batch 2 production sign-off：PENDING-WINDOWS-GPU
Batch 3：BLOCKED-BY-BATCH2-FINAL-SIGN-OFF
```