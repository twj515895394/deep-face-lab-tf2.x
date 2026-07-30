# Batch 4 Master Test Matrix（Rolling Draft）

状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3 / NOT EXECUTED`

| Gate | 场景 | 必须证据 |
|---|---|---|
| Contract | Batch3最终Schema/ratio/坐标对齐 | B4-01差异表、fixtures |
| Schema | valid/invalid/unknown/high version/finite | validation tests |
| Identity | ordinary/packed/model/source/fingerprint | reason matrix |
| Resolver | explicit/default/conflict/no cwd | decision tests |
| Builder | offline/training candidate/determinism | reports/hash |
| Aggregation | outlier/confidence/low evidence | golden fixtures |
| I/O | atomic failure/cache/Unicode/permissions | fault injection |
| Lifecycle | rename/copy/delete/multi-model | model tests |
| CLI | exit codes/report/no leak | CLI tests |
| Compatibility | legacy/no-template/mismatch/security | matrix |
| Windows | real path/replace/packed/large set | environment record |
| Consumer | fake Batch5 loader contract | immutable API test |

统一自动命令：

```bash
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

记录OS、Python、start method、测试数、EXIT、Commit。Windows/性能/Consumer未执行时分别写`NOT EXECUTED`，不得合并为一个PASS。
