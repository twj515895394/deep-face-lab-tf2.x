# PRD-12: DeepFaceLab 后端 `--options-json` 训练超参数静默透传

## 问题陈述

在 DFL GUI 图形客户端中，用户已经在 UI 界面配置好了所有 20+ 项训练超参数（如 `batch_size`、`random_warp`、`optimizer`、`gan_power` 等）。

然而当前 DFL 后端在启动训练时存在以下痛点：
1. 弹出 `Press enter in 60 seconds to override model settings.` 倒计时停顿，阻碍 GUI 自动化静默启动体验；
2. 会自动加载旧模型文件中已保存的历史旧参数，忽略 GUI 传入的新配置。

## 解决方案

在 `deep-face-lab-tf2.x` 后端引入 `--options-json` 参数与配套解析覆盖逻辑。后端在启动训练时自动解析传入的 JSON 字符串并动态注入/覆盖 `self.options` 字典，同时拦截 `ask_override` 倒计时，实现零倒计时停顿、自动覆盖已有超参、全自动化静默启动训练的能力。

## 用户故事

1. 作为 DFL GUI 用户，我希望在 UI 配置好超参数并点击开始训练后，后端能直接静默开始训练，无需等待 60 秒倒计时或手动在控制台按 Enter。
2. 作为 DFL GUI 用户，我希望在界面修改 `batch_size` 或 `gan_power` 等超参后重新训练同一模型时，后端能立即生效最新超参，而不是继续使用旧模型文件中保存的旧值。
3. 作为 DFL GUI 客户端，我希望通过单条 `--options-json` 结构化字符串，向后端精确透传全部 27 项训练超参及数据类型。
4. 作为后端开发者，我希望模型首次新建（`is_first_run`）时仍保持原来的模型结构交互配置（如 `resolution` 与 `archi`），防止外部误改不可变的模型神经网络结构。

## 实现决策

- **命令行参数扩展**：在 `main.py` 的 `train` 子命令中添加 `--options-json` 命令行参数。
- **参数透传链路**：在 `mainscripts/Trainer.py` 中增加 `options_json` 形参并传递给模型构造函数。
- **动态解析与覆盖**：在 `models/ModelBase.py` 中新增 `load_train_step_config()` 方法，在反序列化 `data.dat` 之后、执行 `on_initialize_options()` 之前，将 JSON 字典安全解析并覆盖到 `self.options` 字典中（含布尔、数值及 `lr_dropout` 特殊类型转换）。
- **倒计时防拦截**：重写 `ModelBase.py` 中的 `ask_override()` 方法，当检测到 `options_json` 存在且非空时直接返回 `False`，跳过 60 秒倒计时。
- **模型结构隔离**：保持模型首次运行 `is_first_run` 逻辑不变，严禁通过 `--options-json` 修改模型结构架构参数（如 `resolution`, `archi`, `ae_dims` 等）。

## 测试决策

- **测试范围**：只测试外部传入 JSON 参数后的覆盖行为与跳过倒计时行为，不修改/测试 DFL 内部模型底层算法细节。
- **关键测试点**：
  1. CLI 命令行参数解析测试（传递转义的 JSON 字符串）。
  2. `self.options` 字典覆盖测试（核对解析后与传入 JSON 的字段一致性）。
  3. 倒计时跳过测试（验证控制台无 60 秒等待日志，直接打印跳过提示并进入训练）。

## 超出范围

- 不改变模型首次建模型时的网络结构配置（`resolution`, `archi` 等保持控制台原生逻辑）。
- 不包含 GUI 前端的 Vue 界面改动（仅针对后端响应逻辑与交互改进）。

## 进一步说明

支持的标准超参包含 27 项：`batch_size`, `target_iter`, `autobackup_hour`, `optimizer`, `precision`, `lr_dropout`, `ct_mode`, `random_src_flip`, `random_dst_flip`, `masked_training`, `blur_out_mask`, `eyes_mouth_prio`, `uniform_yaw`, `models_opt_on_gpu`, `opt_states_on_gpu`, `random_warp`, `clipgrad`, `pretrain`, `write_preview_history`, `gan_power`, `gan_patch_size`, `gan_dims`, `true_face_power`, `face_style_power`, `bg_style_power`, `random_hsv_power`。
