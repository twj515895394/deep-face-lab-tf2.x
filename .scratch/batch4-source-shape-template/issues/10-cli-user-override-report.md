# B4-10 CLI、用户显式Override、生成/校验报告与Exit Code

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P1；前置B4-04/08/09；阻塞B4-11/12。
- 目标：提供可脚本化的Template生成、校验、检查和显式路径入口，不建立完整GUI。

## 命令草案

```text
build-srcshape --src <faceset> --output <path> [--model-dir]
validate-srcshape --template <path> [--src] [--model-dir]
inspect-srcshape --template <path> --json-report <path>
```

具体入口应对齐仓库现有main/CLI风格，B4-01后冻结。

## 契约

- 默认dry validation先完成再写；`--force`只允许替换合法目标，仍使用atomic writer。
- stdout简洁，机器报告结构化JSON；敏感绝对素材路径默认脱敏。
- Exit code稳定：0成功、2用户输入/config、3validation/mismatch、4I/O、5内部错误。
- 显式template路径具有最高优先级；invalid不得回落。
- 报告包含来源、fingerprint、sample/reject统计、confidence component、hash和未执行项。

## Forbidden

- 不启动训练或Merge。
- 不自动下载/检测新landmark模型。
- 不覆盖原aligned素材。
- 不把GUI默认值复制进CLI。
- 不在失败时返回0。

## 测试

`test_batch4_srcshape_cli.py`覆盖参数、exit code、ordinary/packed、Unicode、已存在文件、force、invalid input、report schema、stdout不泄露、显式路径和mock I/O失败。

## 完成定义

命令可自动化、错误可区分、报告可复核；用户文档和options/GUI未来映射完成；Summary、Review、SHA完整。
