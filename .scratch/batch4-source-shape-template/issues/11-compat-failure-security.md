# B4-11 兼容、失败、安全与传统Merge Fallback矩阵

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-03/08/09/10；阻塞B4-12。
- 目标：冻结所有Template状态对训练/传统Merge/未来Shape Merge的行为，防止loader错误扩大为项目不可用。

## 矩阵维度

- 旧模型无Template；合法匹配；低confidence；stale fingerprint；model/source mismatch；unsupported schema；损坏/partial；权限/I/O；显式/自动来源；strict/fallback组合。

## 规则

- 旧模型/缺失/可选mismatch：Shape能力disabled，传统Merge继续并一次性日志。
- 显式路径invalid、strict模式、核心I/O错误：明确失败，不静默改选。
- Template永远不影响训练权重加载、DFM导出和传统predictor。
- JSON大小、递归深度/字段数量、数组shape有上限；拒绝路径遍历和外部引用。
- 日志不输出完整landmark数组、素材绝对路径或文件内容。
- `runtime.fallback_on_optional_error`与`strict_validation`语义必须与增强框架一致，不创建第三套全局开关。

## Forbidden

- 不使用`except Exception: return None`。
- 不把权限错误分类为not_found。
- 不接受NaN/Inf、超大数组、非UTF8。
- 不执行Template内任何代码/表达式。
- 不修改历史Batch状态。

## 测试

`test_batch4_srcshape_compat_security.py`使用参数化矩阵覆盖全部状态、zip/path traversal类输入（即使JSON不应支持）、大文件、深层unknown、symlink、Windows权限mock、传统Merge可继续标志和稳定reason。

## 完成定义

兼容/安全矩阵与代码、CLI、文档一致；所有fatal/optional边界有测试；Summary、Review、SHA完整。
