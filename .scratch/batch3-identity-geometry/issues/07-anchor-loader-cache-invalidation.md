# B3-07 Shape Anchor 加载、路径解析、缓存、失效与安全回退

## 1. 基本信息

- Ticket ID：`B3-07`
- 状态：`BLOCKED-BY-B3-02-B3-06`
- 优先级：P0
- 前置 Ticket：B3-02、B3-06
- 阻塞 Ticket：B3-08、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

B3-06 定义 Anchor 内容，本 Ticket 定义训练启动时如何定位、加载、校验和冻结运行时快照。为避免 loss_history 通道和图结构在会话中变化，Batch 3 不做 Anchor 热重载。

Anchor 是可选增强资产：缺失或失配可以按配置回退基线，但损坏数据、核心 I/O 和严格模式必须保留明确失败语义。

## 3. Scope

### In Scope

- 定义显式路径和默认路径解析。
- 定义 loader、validation result、runtime snapshot。
- 定义 fingerprint/identity/schema/confidence 校验。
- 定义进程内只读缓存和失效键。
- 定义 strict/fallback 状态矩阵。
- 定义 startup 日志，不做 per-iter 文件检查。

### Out of Scope

- 不自动生成 Anchor；生成由独立 CLI/前置流程负责。
- 不实现 Batch 4 Template discovery。
- 不监控文件系统变化。
- 不从网络下载资产。
- 不修改原 Anchor。

### Forbidden Changes

- 禁止搜索整个磁盘。
- 禁止使用当前工作目录的相对路径作为隐式优先来源。
- 禁止发现多个 Anchor 时静默选最新文件。
- 禁止 cache key 只使用路径而不含 stat/fingerprint。
- 禁止 runtime 中热切换 effective。
- 禁止把 Anchor bytes 放入 multiprocessing worker 每个样本重复传输。

## 4. 当前代码锚点

- `core/enhancements/config.py` geometry `anchor_path`
- `models/ModelBase.py::get_model_root_path`
- `models/ModelBase.py::get_strpath_storage_for_file`
- `samplelib/metadata` loader/fingerprint helpers
- `core/pathex` 原子/路径 helper
- `models/Model_SAEHD/Model.py::on_initialize_options/on_initialize`

## 5. 路径优先级

Batch 3 训练内部 Anchor：

```text
1. enhancements.geometry.anchor_path 显式绝对或相对 saved_models_path 的路径
2. <src_faceset>/faceset_shape_anchor.v1.json
3. 未找到
```

规则：

- 显式相对路径只相对 `saved_models_path` 解析，不相对 cwd。
- 显式路径存在但无效时不得继续尝试默认路径；必须按该错误决定 fallback/fail，避免用户配置被静默忽略。
- 自动发现仅允许一个固定文件名。
- Batch 4 `.srcshape` 不属于本 Ticket 的候选来源。

## 6. Loader API

```python
@dataclass(frozen=True)
class AnchorLoadResult:
    requested_path: str | None
    resolved_path: str | None
    source: str                 # explicit|src_faceset_default|none
    anchor: ShapeAnchorV1 | None
    valid: bool
    reason: str
    warnings: tuple[str, ...]
    file_signature: tuple[int, int] | None  # size, mtime_ns
```

```python
def load_shape_anchor(
    *,
    explicit_path,
    saved_models_path,
    src_faceset_path,
    expected_fingerprint,
    min_confidence,
    strict_validation,
    fallback_on_optional_error,
) -> AnchorLoadResult:
    ...
```

## 7. 校验顺序

1. 路径解析和文件类型检查。
2. 最大文件大小限制；第一版建议 16 MiB。
3. UTF-8 JSON decode。
4. schema version/support。
5. finite/shape/ratio names。
6. role=`src`。
7. faceset fingerprint match。
8. identity/person 规则。
9. confidence threshold。
10. 构造 float32 只读 runtime arrays。

失败 reason 必须稳定：

```text
not_found
not_regular_file
file_too_large
json_decode_error
unsupported_schema
invalid_schema
identity_mismatch
fingerprint_mismatch
confidence_low
ready
```

## 8. Cache 设计

进程内 cache key：

```text
resolved absolute path
+ file size
+ mtime_ns
+ expected fingerprint
+ min confidence
+ loader schema version
```

- cache value 是不可变 `AnchorLoadResult`。
- 训练启动阶段最多加载一次。
- 测试必须支持显式 `clear_anchor_cache()`。
- cache 不是跨进程共享服务；不得引入 manager/thread。
- worker 只接收 B3-08 所需的小型 float32 arrays，不接收完整 JSON/provenance。

## 9. Fallback 矩阵

| strict_validation | fallback_on_optional_error | optional anchor failure |
|---|---|---|
| false | true | effective=false，基线继续 |
| false | false | 抛 GeometryAnchorError |
| true | true | 抛 GeometryAnchorError |
| true | false | 抛 GeometryAnchorError |

核心 I/O 错误（权限、底层读失败）默认抛出；只有明确分类为 optional 的 `not_found/mismatch/confidence_low` 可以进入表格。

## 10. 实施步骤

1. 新建 `core/enhancements/geometry/anchor_loader.py`。
2. 新建路径解析纯函数。
3. 新建 loader limits 常量。
4. 将 B3-06 schema validator 作为唯一校验来源。
5. 实现 cache 和测试清理入口。
6. 实现 runtime compact view：canonical landmarks、ratios、confidence、fingerprint，不复制样本明细。
7. 在 fake model startup 测试 requested/effective/reason；不接 SAEHD 图。
8. 输出限频 startup summary。

## 11. 测试要求

测试文件：`tests/smoke/test_batch3_anchor_loader.py`

必须覆盖：

- 显式路径优先。
- 显式无效不回落默认。
- 相对路径只相对 saved_models_path。
- Unicode/中文/空格路径。
- ordinary/packed fingerprint。
- 文件过大、目录伪装、symlink 行为（按平台明确）。
- schema/identity/fingerprint/confidence mismatch。
- 四种 strict/fallback 组合。
- cache hit、stat 改变、expected fingerprint 改变。
- runtime snapshot float32 且调用方无法原地修改缓存。
- 训练中删除文件不改变已冻结 snapshot。

命令：

```bash
python -m unittest tests.smoke.test_batch3_anchor_loader -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 12. 完成定义

- 路径优先级唯一且无隐式 cwd。
- 校验顺序、reason code、fallback 矩阵有测试。
- cache key 包含身份和文件状态。
- runtime snapshot 不热重载。
- 不读取 `.srcshape`，不修改 Merge。
- Summary、Review、SHA 齐全。

## 13. Review 检查表

- 是否静默选另一个文件？
- 是否把显式错误回退成默认发现？
- 是否存在 TOCTOU 导致训练中切换状态？
- 是否缓存可变 ndarray？
- 是否把完整 Anchor 发到每个 worker？
- 是否混入 Batch 4 discovery？

## 14. 交付物

- `core/enhancements/geometry/anchor_loader.py`
- `tests/smoke/test_batch3_anchor_loader.py`
- 路径/失败语义文档
- Summary、Review、Commit SHA
