# Issue 12: CLI 参数扩展与透传链路

## 要构建什么

在 `deep-face-lab-tf2.x` 后端的入口与调度主脚本中扩展 `--options-json` 命令行参数支持，并将其一路透传给模型构造函数。

在 `main.py` 的 `train` 解析器中添加 `--options-json` 参数，并在 `process_train()` 字典构建处提取传递至 `mainscripts/Trainer.py` 的 `main()` / `trainerThread()`，最后传入 `models.import_model(...)`。

## 验收标准

- [ ] `main.py train` 命令能接收 `--options-json` 选项。
- [ ] `mainscripts/Trainer.py` 正确将 `options_json` 透传给模型实例。
- [ ] 没有传入 `--options-json` 时，`options_json` 默认为 `None`，不影响旧的 CLI 命令行行为。

## 被阻塞于

无 - 可以立即开始
