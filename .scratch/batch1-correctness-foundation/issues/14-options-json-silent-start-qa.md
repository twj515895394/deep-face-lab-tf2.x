# 14 — 倒计时防拦截与静默启动集成

Status: open
Type: AFK
Blocked by: 13 — 后端 JSON 解析注入与选项覆写

**构建内容:** 在 `models/ModelBase.py` 中拦截防停顿倒计时提示 `ask_override()`，当检测到有效 `--options-json` 参数输入时跳过 60 秒倒计时与手动参数设置；并在真实 CLI 命令行环境中进行完整的自动化静默启动集成校验。

- [ ] 修改 `ModelBase.py` 中的 `ask_override(self)` 方法。
- [ ] 当 `self.options_json` 不为空且长度大于 0 时，输出 `io.log_info("检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。")` 并直接返回 `False`。
- [ ] 确保当传入 `options_json` 时，系统自动启用 `silent_start = True`，无需手动在 CLI 额外传参。
- [ ] 在 CLI 命令行环境中进行多参数静默启动测试：
  ```bash
  python main.py train \
    --model SAEHD \
    --training-data-src-dir /path/to/src/aligned \
    --training-data-dst-dir /path/to/dst/aligned \
    --model-dir /path/to/model \
    --silent-start \
    --options-json "{\"batch_size\":16,\"random_warp\":true,\"optimizer\":\"adabelief\",\"precision\":\"fp32\",\"gan_power\":0.1}"
  ```
- [ ] 验证控制台不再出现 `Press enter in 60 seconds to override model settings.` 停顿倒计时。
- [ ] 验证控制台日志输出包含 `✅ [GUI_OPTIONS] 成功从 --options-json 动态解析并注入了 ... 项训练超参数`。
- [ ] 验证控制台日志输出包含 `检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。`。
- [ ] 验证在无人工按键干预的情况下，模型载入 `batch_size: 16` 成功并直接进入 `train_one_iter` 训练迭代。

## 代码核心实现规格

### 文件: `models/ModelBase.py`

```python
def ask_override(self):
    # 如果提供了 options_json (GUI 模式)，跳过 60 秒倒计时与手动参数设置提示
    if self.options_json is not None and len(self.options_json) > 0:
        io.log_info("检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。")
        return False

    return self.is_training and self.iter != 0 and io.input_in_time(
        "两秒内按Enter键可进行手动配置模型参数 Press enter in 2 seconds to override model settings.", 5 if io.is_colab() else 60)
```

## 预期的终端集成日志输出

```text
Loading model_SAEHD model...
Silent start: choosed device GPU-0
✅ [GUI_OPTIONS] 成功从 --options-json 动态解析并注入了 5 项训练超参数
检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。
=========================== Model Summary ===========================
Model name              : model_SAEHD
Current iteration       : 1024
Batch_size              : 16
Random_warp             : True
Optimizer               : adabelief
Precision               : fp32
GAN_power               : 0.1
=====================================================================
Starting. Press "Enter" to stop training and save model.
[16:00:00][#001025][120ms][0.0421][0.0385]
```

## 验证与测试要点

1. **零停顿倒计时测试**：
   启动带 `--options-json` 的训练命令，使用定时器监视标准输入，断言进程在 3 秒内自动开始打印迭代日志，不等待 Enter 键。
2. **Summary 参数核对测试**：
   核对控制台打印的 `Model Summary` 中展示的 `Batch_size` 与 `Optimizer` 是否与 JSON 中传参完全吻合。

## 完成总结报告

- [ ] 完成后需在 `.scratch/batch1-correctness-foundation/reports/14-options-json-silent-start-qa-summary.md` 生成 summary 报告。
- [ ] 报告需记录命令行集成测试结果、倒计时跳过情况与日志断言截图/文字输出。
- [ ] 已在本 issue 的 `## Comments` 中追加 summary 报告路径。

## Comments

- 待开发人员或 Agent 执行完成后填写执行记录。
