# B3-03 Minimal Loss Hook API、注册机制与基线零影响

## 1. 基本信息

- Ticket ID：`B3-03`
- 状态：`BLOCKED-BY-B3-01`
- 优先级：P0
- 前置 Ticket：B3-01
- 阻塞 Ticket：B3-04、B3-05、B3-09、B3-10、B3-13
- 目标分支：`codex/batch2-ticket19-loss-window`
- 建议提交粒度：Hook 纯接口/测试一个提交；SAEHD 尚不得接入

## 2. 背景与问题

当前 SAEHD 在 `SAEHDModel.on_initialize()` 的每 GPU 图块内直接构建 reconstruction、eyes/mouth、mask、style、GAN 等 Loss，随后生成 `gpu_G_loss` 和梯度。若 Geometry 直接硬编码到该函数，会导致：

- 后续 Loss 无法独立注册和测试；
- Feature Flag 关闭时仍可能构建额外图；
- dtype/reduction/日志规则分散；
- 弱模型容易误改 GAN、true-face 或 optimizer 路径。

本 Ticket 只建立纯 Hook API 和 registry；不得在 SAEHD 主图中调用，主链路接入属于 B3-13。

## 3. Scope

### 3.1 In Scope

- 新建最小 Loss Hook 包。
- 定义 immutable context、result 和 registry 契约。
- 定义每 GPU、每样本 Loss 的 reduction 规则。
- 定义关闭时不实例化 Hook、不构建 TensorFlow op 的规则。
- 提供 fake tensor/纯对象测试，不要求真实 GPU。

### 3.2 Out of Scope

- 不实现 ratio/contour 公式。
- 不修改 `models/Model_SAEHD/Model.py`。
- 不修改 `_unified_ops`、日志或 loss history。
- 不实现 Batch 7 的 Appearance/Region/Boundary/Frequency。

### 3.3 Forbidden Changes

- 禁止让 Hook 拥有 optimizer、save、exit、resume 控制权。
- 禁止 Hook 读取全局 mutable model 状态。
- 禁止 Hook 自行捕获并吞掉任意 Exception。
- 禁止在 Feature Flag 关闭时创建 placeholder、constant、variable 或 summary op。
- 禁止直接把 Geometry 公式写进 SAEHD 主 Loss 块。
- 禁止 registry 通过动态 import 扫描整个仓库。

## 4. 当前代码锚点

- `models/Model_SAEHD/Model.py` 每 GPU loss 构建块
- `gpu_src_loss`、`gpu_dst_loss`、`gpu_G_loss`
- `gpu_G_loss_gvs` 与 `nn.average_gv_list`
- `core/leras/nn` TensorFlow wrapper
- `core/enhancements/__init__.py`

## 5. 目标目录

```text
core/enhancements/losses/
├── __init__.py
├── contracts.py
├── registry.py
└── noop.py
```

Batch 3 具体 Geometry Hook 后续放在：

```text
core/enhancements/geometry/losses.py
```

避免把 Geometry 与通用 Loss registry 强耦合。

## 6. 冻结接口

### 6.1 Context

```python
@dataclass(frozen=True)
class LossHookContext:
    name: str
    domain: str                 # 第一版只允许 "src"
    prediction: object          # Tensor，具体语义由 hook 声明
    target: object | None
    target_mask: object | None
    supervision: Mapping[str, object]
    model_data_format: str
    precision: str
    batch_size_per_device: int
```

Context 不包含 model、optimizer、session、路径或 logger。

### 6.2 Result

```python
@dataclass(frozen=True)
class LossHookResult:
    per_sample_addition: object       # shape [device_batch]
    raw_metrics: Mapping[str, object]
    weighted_metrics: Mapping[str, object]
    active_count: object | None
    warnings: tuple[str, ...]
```

硬契约：

- `per_sample_addition` 与当前 `gpu_src_loss` 的 batch 维一致。
- Hook 不执行最终 batch mean；SAEHD 仍保留当前 per-sample loss 结构。
- 所有加入主 Loss 的张量在相加前显式 cast 到目标 loss dtype。
- metrics 不参与梯度，除非它本身也是 addition 的同一张量引用；日志侧需要 `stop_gradient` 时由实现明确处理。

### 6.3 Hook Protocol

```python
class LossHook(Protocol):
    name: str
    def build(self, context: LossHookContext, weight: float) -> LossHookResult: ...
```

### 6.4 Registry

```python
class LossHookRegistry:
    def register(self, name: str, factory: Callable[[], LossHook]) -> None: ...
    def create(self, name: str) -> LossHook: ...
    def registered_names(self) -> tuple[str, ...]: ...
```

- 重名注册必须抛 `ValueError`。
- 未知名称必须抛 `KeyError`。
- 注册顺序不得决定最终日志顺序；日志顺序由冻结常量控制。
- 第一版不提供 plugin discovery。

## 7. 零影响规则

当 Geometry 未 requested：

```text
不 import geometry loss implementation
不 create registry instance for runtime
不 create supervision placeholder
不调用 hook.build
不修改 gpu_src_loss / gpu_dst_loss
不增加 _unified_ops fetch
不改变 onTrainOneIter 返回通道
```

Noop Hook 仅用于单元测试，不得作为生产关闭路径替代 Python 分支。

## 8. 实施步骤

1. 创建 `contracts.py`，只含 dataclass/protocol 和纯校验 helper。
2. 创建 `registry.py`，实现显式注册。
3. 创建 `noop.py`，验证 reduction 和 dtype 契约。
4. 在 `__init__.py` 只导出稳定公开符号，不自动注册 Geometry。
5. 添加 shape validator：要求 addition rank=1 或可明确 reshape 为 `[batch]`；禁止标量隐式广播。
6. 添加 metric name validator：只允许小写 snake_case，避免日志键漂移。
7. 添加测试证明 disabled 调用方无需 import TensorFlow。

## 9. 测试要求

测试文件：`tests/smoke/test_batch3_loss_hook_contracts.py`

必须覆盖：

- duplicate registration。
- unknown hook。
- context domain 非 src。
- addition 标量、错误 batch 长度、错误 dtype。
- 空 metrics 和稳定排序。
- Hook 抛错时 registry 不吞异常。
- disabled factory 不被调用。
- Noop addition 全 0 且不改变基线数组。
- import 模块不初始化 TensorFlow session。

命令：

```bash
python -m unittest tests.smoke.test_batch3_loss_hook_contracts -v
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

## 10. 完成定义

- API 可由纯 Python/fake tensor 测试。
- Hook 不拥有 Trainer 控制权。
- per-sample reduction 与 SAEHD 当前 loss shape 对齐。
- 关闭时生产路径不构建任何 Hook 图。
- 未混入任何 Batch 7 Loss。
- Summary、Review 和 SHA 齐全。

## 11. Review 检查表

- 是否有 scalar 隐式广播？
- 是否把 batch mean 提前做了两次？
- 是否在 import 时初始化 TF？
- 是否吞异常？
- 是否让 Hook 访问 model/session/optimizer？
- 是否为 disabled 路径构建了 Noop 图？
- 是否存在动态扫描和不可控注册顺序？

## 12. 交付物

- `core/enhancements/losses/*`
- `tests/smoke/test_batch3_loss_hook_contracts.py`
- API 说明
- Summary、Review、Commit SHA
