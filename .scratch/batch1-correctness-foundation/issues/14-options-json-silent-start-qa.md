# Issue 14: 倒计时防拦截与静默启动集成

## 要构建什么

在 `models/ModelBase.py` 中拦截倒计时提示，并在 CLI 中进行完整的静默启动集成测试。

重写 `ask_override()` 方法，当检测到 `options_json` 存在且非空时直接返回 `False`，跳过 60 秒倒计时。通过真实命令行传递含参数 JSON 运行 `train` 命令，验证无倒计时停顿并正确输出 `✅ [GUI_OPTIONS]` 解析日志。

## 验收标准

- [ ] 传入 `options_json` 时，终端不再出现 `Press enter in 60 seconds to override model settings.` 倒计时停顿。
- [ ] 终端正确打印 `✅ [GUI_OPTIONS]` 解析提示日志。
- [ ] 能在无需人工交互的情况下直接自动进入训练迭代。

## 被阻塞于

- [Issue 13: 后端 JSON 解析注入与选项覆写](file:///t:/deep-face-lab-tf2.x/.scratch/batch1-correctness-foundation/issues/13-options-json-parser-override.md)
