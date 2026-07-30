# B3-05 数值保护、错误传播与 Optional Fallback

- 前置：B3-04；P0。
- 目标：统一验证 anchor/feature/loss 的 shape、dtype、finite；明确 optional 数据回退与核心错误传播边界。
- 可回退：anchor 缺失、可选 sidecar 失效、可选几何项不可用；输出 effective=false 与 reason。
- 不可回退：OOM、MemoryError、worker crash、核心 tensor shape/dtype、checkpoint/optimizer 错误、非有限关键梯度。
- 修改：`core/enhancements/geometry/validation.py`（建议）及测试；不得宽泛 `except Exception`。
- 测试：NaN/Inf、错误类型、strict/fallback 两模式、OOM 文本识别不误判。
- 完成：错误表、测试、Summary、Review、SHA。