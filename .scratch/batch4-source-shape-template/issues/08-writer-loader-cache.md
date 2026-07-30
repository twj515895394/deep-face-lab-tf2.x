# B4-08 Atomic Writer、Strict Loader、Cache与Invalidation

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-02/03/07；阻塞B4-09/10/11。
- 目标：交付`.srcshape`可靠保存/加载生命周期；不做来源决策或Merge。

## Writer

- 标准UTF-8 canonical JSON；同目录temp + flush/fsync（平台可用时）+ atomic replace。
- 写前完整Schema/identity/finite校验；失败不得破坏旧文件。
- 文件权限沿用目录默认，不创建宽权限。
- 返回`path/bytes/hash/replaced/warnings`，不只返回bool。

## Loader

- regular file、大小上限、UTF-8、strict JSON、schema、finite、identity/fingerprint/confidence按固定顺序。
- 输出immutable runtime template和结构化reason。
- 显式文件invalid不得改选其他路径。
- unsupported/mismatch关闭Shape能力但传统Merge可继续；核心I/O错误按B4-11矩阵传播。

## Cache

key至少含resolved path、size、mtime_ns、content hash或强校验、expected model/source/fingerprint、loader version。返回只读copy；提供测试清理。Batch 4不做文件watcher/热重载。

## Forbidden

- 不用直接`write_text`覆盖目标。
- 不在失败时删除旧文件。
- 不缓存可变ndarray。
- 不把loader warning当trusted success。
- 不读取网络URL。

## 测试

`test_batch4_srcshape_io.py`覆盖原子成功/失败注入、旧文件保留、并发读、partial JSON、过大文件、权限/I/O错误、cache hit/invalidation、Unicode、identity mismatch、immutable arrays、标准hash与Windows replace语义。

## 完成定义

事务、校验、cache和failure reason有证据；无Merge修改；Summary、Review、SHA完整。
