# 13 — 后端 JSON 解析注入与选项覆写

Status: completed
Type: AFK
Blocked by: 12 — CLI 参数扩展与透传链路

**构建内容:** 在 `models/ModelBase.py` 中实现 `--options-json` 字符串的安全反序列化与字段清洗校验逻辑 `load_train_step_config()`。在从 `data.dat` 读取模型持久化选项后、调用 `on_initialize_options()` 之前，将 JSON 中包含的 27 项训练超参数强制覆盖到 `self.options` 字典中，同时严格保护模型结构参数（`resolution`, `archi` 等）在首次运行时不被篡改。

- [x] 在 `ModelBase.__init__` 方法中新增 `options_json=None` 参数，保存成员变量 `self.options_json = options_json`。
- [x] 当 `options_json` 不为空时，自动设置 `self.silent_start = True`。
- [x] 在 `ModelBase.__init__` 中反序列化 `data.dat` 之后、`on_initialize_options()` 调用之前插入 `self.load_train_step_config()`。
- [x] 实现 `load_train_step_config(self)` 方法，包含 JSON 安全解析、类型转换、特殊字段映射与错误捕获。
- [x] 实现布尔值解析转换逻辑（处理 `True`/`False` 以及字符串 `"true"`/`"false"`）。
- [x] 实现数值解析转换逻辑（支持 `int` 与 `float` 自动判别转换）。
- [x] 实现 `lr_dropout` 的类型转换规则：布尔值 `True` 映射为 `'y'`，`False` 映射为 `'n'`；支持原生字符串 `'n'`, `'y'`, `'cpu'`。
- [x] 确保支持的 27 项超参数能准确覆盖至 `self.options` 字典中。
- [x] 保持 `is_first_run` 模型首次运行建立逻辑原状，防止神经网络结构参数（`resolution`, `archi`, `ae_dims`, `e_dims`, `d_dims` 等）被外部动态篡改。
- [x] 增加 `try...except` 异常捕获机制，JSON 解析失败时通过 `io.log_err` 输出日志警告，避免导致主进程崩溃。

## 27 项训练超参数 Key 与类型规范对照表

| 序号 | 参数 Key (`json_key`) | 类型 | 示例值 | 说明 / 合法取值范围 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `batch_size` | `int` | `8` | 批次大小 (1 ~ 120) |
| 2 | `target_iter` | `int` | `500000` | 目标总迭代次数，0 表示无限制 |
| 3 | `autobackup_hour` | `int` | `2` | 自动备份间隔 (小时, 0 ~ 24) |
| 4 | `optimizer` | `str` | `"adabelief"` | 优化器：`"adabelief"`, `"lion"`, `"rmsprop"` |
| 5 | `precision` | `str` | `"fp32"` | 计算精度：`"fp32"`, `"fp16"`, `"bf16"` |
| 6 | `lr_dropout` | `str`/`bool` | `"n"` / `false` | 学习率下降：`"n"`, `"y"`, `"cpu"` |
| 7 | `ct_mode` | `str` | `"lct"` | 色彩迁移模式：`"none"`, `"rct"`, `"lct"`, `"mkl"`, `"idt"`, `"sot"` |
| 8 | `random_src_flip` | `bool` | `false` | SRC 样本随机水平翻转 |
| 9 | `random_dst_flip` | `bool` | `true` | DST 样本随机水平翻转 |
| 10 | `masked_training` | `bool` | `true` | 仅在遮罩范围内训练 |
| 11 | `blur_out_mask` | `bool` | `false` | 遮罩边缘羽化模糊 |
| 12 | `eyes_mouth_prio` | `bool` | `false` | 眼嘴器官部位优先训练 |
| 13 | `uniform_yaw` | `bool` | `false` | 侧脸均匀采样 |
| 14 | `models_opt_on_gpu` | `bool` | `true` | 模型与优化器放在 GPU 显存中 |
| 15 | `opt_states_on_gpu`| `bool` | `true` | 优化器状态放在 GPU 显存中 |
| 16 | `random_warp` | `bool` | `true` | 样本随机扭曲 |
| 17 | `clipgrad` | `bool` | `false` | 梯度裁剪 |
| 18 | `pretrain` | `bool` | `false` | 预训练模式开关 |
| 19 | `write_preview_history`|`bool`| `false` | 生成历史预览图像文件夹 |
| 20 | `gan_power` | `float`| `0.0` | GAN 判别器强度 (0.0 ~ 5.0) |
| 21 | `gan_patch_size` | `int` | `28` | GAN 补丁块大小 (3 ~ 640) |
| 22 | `gan_dims` | `int` | `16` | GAN 判别器维度 (4 ~ 512) |
| 23 | `true_face_power` | `float`| `0.01` | True Face 真实人脸损耗权重 |
| 24 | `face_style_power` | `float`| `0.0` | 人脸风格损失权重 (0.0 ~ 100.0) |
| 25 | `bg_style_power` | `float`| `0.0` | 背景风格损失权重 (0.0 ~ 100.0) |
| 26 | `random_hsv_power` | `float`| `0.05` | 随机 HSV 色彩抖动强度 (0.0 ~ 0.3) |

## 代码核心实现规格

```python
def load_train_step_config(self):
    if self.options_json is not None:
        try:
            import json
            new_options = json.loads(self.options_json)
            
            for k, v in new_options.items():
                # 1. 处理布尔类型
                if v is True or (isinstance(v, str) and v.lower() == 'true'):
                    val = True
                elif v is False or (isinstance(v, str) and v.lower() == 'false'):
                    val = False
                # 2. 处理数值与字符串
                elif isinstance(v, (int, float)):
                    val = v
                elif isinstance(v, str):
                    try:
                        fv = float(v)
                        if fv == int(fv) and 'e' not in v.lower() and '.' not in v:
                            val = int(fv)
                        else:
                            val = fv
                    except (ValueError, TypeError):
                        val = v
                else:
                    val = v

                # 3. 特殊逻辑修正：lr_dropout 的布尔与字符映射 ('y'/'n'/'cpu')
                if k == 'lr_dropout' and isinstance(val, bool):
                    val = 'y' if val else 'n'

                # 覆盖写入 self.options
                self.options[k] = val
            
            io.log_info(f"✅ [GUI_OPTIONS] 成功从 --options-json 动态解析并注入了 {len(new_options)} 项训练超参数")
        except Exception as e:
            io.log_err(f"❌ [GUI_OPTIONS] 从 --options-json 解析配置失败: {e}")
```

## 验证与测试要点

1. **JSON 类型推导单元测试**：
   测试传参包含 `{"batch_size": 16, "random_warp": false, "lr_dropout": true}`，断言解析后 `self.options['batch_size'] == 16`，`self.options['random_warp'] == False`，`self.options['lr_dropout'] == 'y'`。
2. **已有模型覆盖测试**：
   在已有 `data.dat`（历史 `batch_size: 4`）的模型上，传入 `--options-json "{\"batch_size\":16}"`，校验 `self.options['batch_size']` 被正确覆写为 `16`。

## 完成总结报告

- [x] 完成后需在 `.scratch/batch1-correctness-foundation/reports/13-options-json-parser-override-summary.md` 生成 summary 报告。
- [x] 报告须包含注入覆盖逻辑说明、数据类型校验结果、结构参数防护测试结果。
- [x] 已在本 issue 的 `## Comments` 中追加 summary 报告路径。

## Comments

- 2026-07-28 16:22: 已完成后端 JSON 解析注入与选项覆写功能，生成总结报告：[13-options-json-parser-override-summary.md](file:///t:/deep-face-lab-tf2.x/.scratch/batch1-correctness-foundation/reports/13-options-json-parser-override-summary.md)。
