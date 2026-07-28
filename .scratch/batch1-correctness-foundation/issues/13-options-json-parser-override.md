# Issue 13: 后端 JSON 解析注入与选项覆写

## 要构建什么

在 `models/ModelBase.py` 中实现 `load_train_step_config()`，解析 `--options-json` 传入的 JSON 字符串并安全注入覆盖 `self.options` 字典。

包含处理布尔值、数值格式及 `lr_dropout` 特殊值映射（如 `true` -> `'y'`, `false` -> `'n'`），并在 `self.on_initialize_options()` 调用前生效。同时保留 `is_first_run` 首次运行建模型时的结构配置防护逻辑。

## 验收标准

- [ ] `load_train_step_config()` 能正确解析 JSON 格式并映射 27 项超参。
- [ ] 解析后的值能成功覆盖由 `data.dat` 读取到的旧 `self.options` 选项。
- [ ] 首次运行模型（`is_first_run`）时，结构参数（如 `resolution`, `archi`）不受影响，仍按原流程进行初始化。
- [ ] 解析异常时能输出日志告警，不导致主进程直接崩溃。

## 被阻塞于

- [Issue 12: CLI 参数扩展与透传链路](file:///t:/deep-face-lab-tf2.x/.scratch/batch1-correctness-foundation/issues/12-cli-options-json-arg.md)
