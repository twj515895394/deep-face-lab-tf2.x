# 13 — 恢复训练日志区间平均 Loss，并保留单步诊断与可观测性 总结报告

> 创建时间：2026-07-29  
> 对应 issue：`.scratch/batch2-training-data-and-sampling/issues/13-loss-window-logging-and-observability.md`  
> 状态：PASS (macOS 轻量验证 PASS, 175/175 测试通过)

---

## 1. 核心改动

1. **`samplelib/sampling/loss_stats.py`** (新增):
   - 实现无 TensorFlow 依赖的纯数据结构 `LossWindowStats` 与计算纯函数 `compute_loss_window_stats(history, start_index)`。
   - 包含 `count`、`mean`、`median`、`last`、`minimum`、`maximum`。
   - 实现数值安全校验（拒绝 NaN / Inf），校验维度一致性（如 1D float 或 2D `[src, dst]`）。
   - 空窗口或超界索引返回 `None`（不输出伪造 `0.0000` 伪 Loss）。

2. **`mainscripts/Trainer.py`** (修改):
   - 初始化 `loss_window_start_index = len(model.get_loss_history())`。
   - 在 `shared_state['after_save']` 分支计算区间 `history[loss_window_start_index:]` 的算术平均值作为保存日志打印主值。
   - 仅在保存完成后推进 `loss_window_start_index = len(loss_history)`；遇到保存异常时不丢弃窗口。

3. **`tests/smoke/test_batch2_loss_window_logging.py`** (新增):
   - 全面覆盖 1D/2D Loss 算术平均、切片偏移、Session 隔离、数值异常拦截与空窗口处理。

---

## 2. 验证结果

- **编译检查**：`./.venv/bin/python -m compileall samplelib/sampling/loss_stats.py mainscripts/Trainer.py tests/smoke/test_batch2_loss_window_logging.py` → **PASS**
- **单元测试**：`./.venv/bin/python -m unittest tests/smoke/test_batch2_loss_window_logging.py` → **PASS (6/6 PASS)**
- **全量烟雾测试套件**：`./.venv/bin/python -m unittest discover -s tests/smoke -p "test_batch*.py"` → **PASS (175/175 PASS)**
- **Windows FP32 GPU 验收**：**PENDING-WINDOWS-GPU**

---

## 3. 状态变更说明

- `.scratch/batch2-training-data-and-sampling/issues/13-loss-window-logging-and-observability.md` 状态更新为 `done-macos-lightweight-pending-windows`。
- Hand-off [.handoff/handoff-20260729-ticket13-loss-window-logging.md](file:///Users/tangwujun/Documents/trae_projects/DeepFaceLab-master/.handoff/handoff-20260729-ticket13-loss-window-logging.md) 状态更新为 `已完成`。
