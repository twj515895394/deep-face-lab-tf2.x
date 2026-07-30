# B4-12 Windows Geometry Bridge Smoke、性能与Consumer验收

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-11；阻塞B4-13。
- 目标：证明Template生成/保存/加载/发现可在真实Windows环境作为稳定Bridge工作；本票不评价Batch5 Warp效果。

## 自动矩阵

- ordinary/packed、quick/strong fingerprint、offline/training adapter、合法/invalid、Unicode/中文/空格、model rename/copy/delete、CLI exit code、atomic failure、cache、legacy no-template。
- 统一`python -m unittest discover -s tests/smoke -p "test_batch*.py" -q`并记录OS/Python/start method/测试数/SHA。

## Windows Smoke

1. 真实src faceset构建`.srcshape`。
2. validate/inspect报告。
3. 模型目录发现与load。
4. rename/copy后identity行为。
5. 传统Merge在Template缺失/invalid时仍启动。
6. 1k/10k metadata records构建时间、峰值RSS、文件大小。

## Consumer Contract

提供fake Batch5 consumer读取immutable template，验证canonical landmarks/ratios/confidence/identity，不实现Hybrid/Warp。consumer不应依赖provenance内部字段或文件路径。

## 状态

分别记录`AUTOMATED / WINDOWS-SMOKE / PERFORMANCE / CONSUMER-CONTRACT`。未执行写`NOT EXECUTED`；不得因Schema单测通过宣称Bridge GPU/生产通过。

## 验收

- 原子写入和读取一致。
- 旧模型/无Template传统Merge无回归。
- 性能在B4-01冻结预算内；超预算必须报告。
- consumer只使用公开Schema。
- 所有失败有reason和日志。

## 交付物

Master Matrix、Windows报告、性能表、consumer fixture、Summary、Review、SHA。
