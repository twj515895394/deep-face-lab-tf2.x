# 12 — CLI 参数扩展与透传链路

Status: open
Type: AFK
Blocked by: None — 可以立即开始

**构建内容:** 在 `deep-face-lab-tf2.x` 后端的入口与调度主脚本中扩展 `--options-json` 命令行参数支持，并将其一路透传给 Trainer 线程与 ModelBase 构造函数，为 GUI 图形客户端静默透传训练超参数提供 CLI 合约接口。

- [ ] 在 `main.py` 的 `train` 子解析器 (`subparsers.add_parser("train")`) 中添加 `--options-json` 命令行参数定义。
- [ ] 在 `main.py` 的 `process_train(arguments)` 函数的 `kwargs` 字典中添加 `'options_json': arguments.options_json`。
- [ ] 在 `mainscripts/Trainer.py` 中修改 `trainerThread` 函数形参签名，增加 `options_json=None` 默认形参。
- [ ] 在 `mainscripts/Trainer.py` 中修改 `main()` 函数形参签名，支持接收 `options_json` 形参。
- [ ] 在 `mainscripts/Trainer.py` 中实例化模型 `models.import_model(model_class_name)(...)` 时，将 `options_json=options_json` 显式透传给模型构造函数。
- [ ] 确保在没有传入 `--options-json` 时，系统维持 `options_json=None` 默认行为，与原有命令行交互 100% 兼容。

## 代码修改详细规格

### 1. 文件: `main.py`
* 在 `p = subparsers.add_parser("train", help="Trainer")` 下添加：
  ```python
  p.add_argument('--options-json', default=None, dest="options_json", help="config training params in json format")
  ```
* 在 `process_train(arguments)` 函数内：
  ```python
  kwargs = {
      'model_class_name'         : arguments.model_name,
      'saved_models_path'        : Path(arguments.model_dir),
      ...
      'options_json'             : arguments.options_json,
  }
  ```

### 2. 文件: `mainscripts/Trainer.py`
* 修改 `trainerThread` 签名并透传至模型构造：
  ```python
  def trainerThread (s2c, c2s, e,
                      ...
                      options_json=None,
                      **kwargs):
      ...
      model = models.import_model(model_class_name)(
                  ...
                  options_json=options_json,
                  debug=debug)
  ```

## 验证与测试要点

1. **命令行参数解析校验**：
   运行 `python main.py train --help`，验证输出包含 `--options-json OPTIONS_JSON` 参数帮助说明。
2. **后向兼容性测试**：
   不带 `--options-json` 参数启动原训练命令，验证程序正常运行无报错。

## 完成总结报告

- [ ] 本 issue 涉及 CLI 参数变更，完成后需在 `.scratch/batch1-correctness-foundation/reports/12-cli-options-json-arg-summary.md` 生成 summary 报告。
- [ ] summary 报告需包含新增/修改接口、输入参数变更、人工验证建议、技术验证结果、风险与注意事项。
- [ ] 已在本 issue 的 `## Comments` 中追加 summary 报告路径和生成时间。

## Comments

- 待开发人员或 Agent 执行完成后填写执行记录。
