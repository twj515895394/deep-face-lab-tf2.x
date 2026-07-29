# PRD-12: DeepFaceLab 后端 `--options-json` 训练超参数静默透传

> **文档目标**：本文档为 `deep-face-lab-tf2.x` 代码库提供精确的修改规格与设计指导，使其原生支持通过 `--options-json` 命令行参数静默传入训练超参 JSON 字符串，实现 **零倒计时停顿、自动覆盖已有超参、全自动化静默启动训练** 的能力。

---

## 一、 背景与总体流程

在图形化客户端 (DFL GUI) 中，用户已经在 UI 界面配置好了所有 20+ 项训练超参数（如 `batch_size`、`random_warp`、`optimizer`、`gan_power` 等）。

为了避免 DFL 在启动训练时出现以下阻碍自动化体验的问题：
1. 弹出 `Press enter in 60 seconds to override model settings.` 倒计时停顿；
2. 忽略 UI 传入的新配置，直接加载旧模型文件中已保存的旧参数；

我们需要在 `deep-face-lab-tf2.x` 中引入 `--options-json` 参数与配套逻辑。

---

## 二、 命令行 CLI 交互规范

执行训练时的 CLI 命令形式如下：

```bash
python main.py train \
  --model SAEHD \
  --training-data-src-dir /path/to/src/aligned \
  --training-data-dst-dir /path/to/dst/aligned \
  --model-dir /path/to/models/model-name \
  --silent-start \
  --options-json "{\"batch_size\":8,\"target_iter\":500000,\"autobackup_hour\":2,\"optimizer\":\"adabelief\",\"precision\":\"fp32\",\"lr_dropout\":\"n\",\"ct_mode\":\"lct\",\"random_src_flip\":false,\"random_dst_flip\":true,\"masked_training\":true,\"blur_out_mask\":false,\"eyes_mouth_prio\":false,\"uniform_yaw\":false,\"models_opt_on_gpu\":true,\"random_warp\":true,\"clipgrad\":false,\"pretrain\":false,\"opt_states_on_gpu\":true,\"write_preview_history\":false,\"gan_power\":0.0,\"gan_patch_size\":28,\"gan_dims\":16,\"true_face_power\":0.01,\"face_style_power\":0.0,\"bg_style_power\":0.0,\"random_hsv_power\":0.05}"
```

---

## 三、 超参数字典与数据类型对照表 (27 项参数)

`--options-json` 中传入的 JSON 对象应包含以下字段，后台解析时需保证正确的数据类型映射：

| 序号 | 参数 Key (`json_key`) | 类型 | 示例值 | DFL 内部合法范围 / 选项说明 |
| :--- | :--- | :--- | :--- | :--- |
| 1 | `batch_size` | `int` | `8` | 批次大小 (1 ~ 120) |
| 2 | `target_iter` | `int` | `500000` | 目标总迭代次数，0 表示无限制 |
| 3 | `autobackup_hour` | `int` | `2` | 自动备份时间间隔 (小时, 0 ~ 24) |
| 4 | `optimizer` | `str` | `"adabelief"` | 优化器：`"adabelief"`, `"lion"`, `"rmsprop"` |
| 5 | `precision` | `str` | `"fp32"` | 计算精度：`"fp32"`, `"fp16"`, `"bf16"` |
| 6 | `lr_dropout` | `str`/`bool` | `"n"` / `false` | 学习率下降：`"n"`(关闭), `"y"`(GPU开启), `"cpu"`(CPU开启) |
| 7 | `ct_mode` | `str` | `"lct"` | 色彩迁移模式：`"none"`, `"rct"`, `"lct"`, `"mkl"`, `"idt"`, `"sot"` |
| 8 | `random_src_flip` | `bool` | `false` | SRC 样本随机翻转 |
| 9 | `random_dst_flip` | `bool` | `true` | DST 样本随机翻转 |
| 10 | `masked_training` | `bool` | `true` | 仅在遮罩范围内训练 |
| 11 | `blur_out_mask` | `bool` | `false` | 遮罩边缘羽化 |
| 12 | `eyes_mouth_prio` | `bool` | `false` | 眼嘴器官部位优先训练 |
| 13 | `uniform_yaw` | `bool` | `false` | 侧脸均匀采样 |
| 14 | `models_opt_on_gpu` | `bool` | `true` | 模型优化器放在 GPU 显存中 |
| 15 | `random_warp` | `bool` | `true` | 样本随机扭曲 |
| 16 | `clipgrad` | `bool` | `false` | 梯度裁剪 |
| 17 | `pretrain` | `bool` | `false` | 预训练模式 |
| 18 | `opt_states_on_gpu`| `bool` | `true` | 优化器状态放在 GPU 显存中 |
| 19 | `write_preview_history`|`bool`| `false` | 生成历史预览图像文件夹 |
| 20 | `gan_power` | `float`| `0.0` | GAN 判别器强度 (0.0 ~ 5.0) |
| 21 | `gan_patch_size` | `int` | `28` | GAN 补丁块大小 (3 ~ 640) |
| 22 | `gan_dims` | `int` | `16` | GAN 判别器维度 (4 ~ 512) |
| 23 | `true_face_power` | `float`| `0.01` | True Face 真实人脸损耗权重 |
| 24 | `face_style_power` | `float`| `0.0` | 人脸风格损失权重 (0.0 ~ 100.0) |
| 25 | `bg_style_power` | `float`| `0.0` | 背景风格损失权重 (0.0 ~ 100.0) |
| 26 | `random_hsv_power` | `float`| `0.05` | 随机 HSV 色彩抖动强度 (0.0 ~ 0.3) |

---

## 四、 详细修改方案 (Code Modification Guide)

需要对 `deep-face-lab-tf2.x` 代码库的 3 个文件进行改动：

### 1. 文件: `main.py`

#### (1) 添加 `--options-json` 参数定义
在 `p = subparsers.add_parser("train", help="Trainer")` 块中添加参数：

```python
p.add_argument('--options-json', default=None, dest="options_json", help="config training params in json format")
```

#### (2) 传递参数至 `process_train`
在 `process_train(arguments)` 函数的 `kwargs` 字典中添加：

```python
def process_train(arguments):
    osex.set_process_lowest_prio()

    kwargs = {
        'model_class_name'         : arguments.model_name,
        'saved_models_path'        : Path(arguments.model_dir),
        'training_data_src_path'   : Path(arguments.training_data_src_dir),
        'training_data_dst_path'   : Path(arguments.training_data_dst_dir),
        'pretraining_data_path'    : Path(arguments.pretraining_data_dir) if arguments.pretraining_data_dir is not None else None,
        'pretrained_model_path'    : Path(arguments.pretrained_model_dir) if arguments.pretrained_model_dir is not None else None,
        'no_preview'               : arguments.no_preview,
        'force_model_name'         : arguments.force_model_name,
        'force_gpu_idxs'           : [ int(x) for x in arguments.force_gpu_idxs.split(',') ] if arguments.force_gpu_idxs is not None else None,
        'cpu_only'                 : arguments.cpu_only,
        'silent_start'             : arguments.silent_start,
        'execute_programs'         : [ [int(x[0]), x[1] ] for x in arguments.execute_program ],
        'debug'                    : arguments.debug,
        'options_json'             : arguments.options_json, # 👈 新增这一行
    }
    from mainscripts import Trainer
    Trainer.main(**kwargs)
```

---

### 2. 文件: `mainscripts/Trainer.py`

修改 `trainerThread` 和 `main` 函数形参列表，透传 `options_json`：

```python
def trainerThread (s2c, c2s, e,
                    model_class_name = None,
                    saved_models_path = None,
                    training_data_src_path = None,
                    training_data_dst_path = None,
                    pretraining_data_path = None,
                    pretrained_model_path = None,
                    no_preview=False,
                    force_model_name=None,
                    force_gpu_idxs=None,
                    cpu_only=None,
                    silent_start=False,
                    execute_programs = None,
                    debug=False,
                    options_json=None, # 👈 新增形参
                    **kwargs):
    ...
    model = models.import_model(model_class_name)(
                is_training=True,
                saved_models_path=saved_models_path,
                training_data_src_path=training_data_src_path,
                training_data_dst_path=training_data_dst_path,
                pretraining_data_path=pretraining_data_path,
                pretrained_model_path=pretrained_model_path,
                no_preview=no_preview,
                force_model_name=force_model_name,
                force_gpu_idxs=force_gpu_idxs,
                cpu_only=cpu_only,
                silent_start=silent_start,
                options_json=options_json, # 👈 传给 Model 构造函数
                debug=debug)
```

---

### 3. 文件: `models/ModelBase.py`

#### (1) `__init__` 构造函数增强
- 接收 `options_json=None` 参数。
- 若 `options_json` 不为空，**强制设置 `silent_start = True`**。
- 保存 `self.options_json = options_json` 成员变量。

```python
class ModelBase(object):
    def __init__(self, is_training=False,
                 is_exporting=False,
                 saved_models_path=None,
                 training_data_src_path=None,
                 training_data_dst_path=None,
                 pretraining_data_path=None,
                 pretrained_model_path=None,
                 no_preview=False,
                 force_model_name=None,
                 force_gpu_idxs=None,
                 cpu_only=False,
                 debug=False,
                 force_model_class_name=None,
                 silent_start=False,
                 options_json=None, # 👈 新增
                 **kwargs):

        if options_json is not None:
            silent_start = True

        self.silent_start = silent_start
        self.options_json = options_json
        ...
```

#### (2) 添加 `load_train_step_config(self)` 覆写逻辑
在初始化 `self.on_initialize_options()` **之前**，调用 `self.load_train_step_config()`，解析并覆盖 `self.options`：

```python
        # 加载选项后、调用 on_initialize_options() 前插入：
        self.load_train_step_config()
        self.on_initialize_options()
```

`load_train_step_config` 的具体实现：

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

                    # 覆盖到 self.options 中
                    self.options[k] = val
                
                io.log_info(f"✅ [GUI_OPTIONS] 成功从 --options-json 动态解析并注入了 {len(new_options)} 项训练超参数")
            except Exception as e:
                io.log_err(f"❌ [GUI_OPTIONS] 从 --options-json 解析配置失败: {e}")
```

#### (3) 修改 `ask_override` 拦截防停顿倒计时

```python
    def ask_override(self):
        # 如果提供了 options_json (GUI 模式)，跳过 60 秒倒计时与手动参数设置提示
        if self.options_json is not None and len(self.options_json) > 0:
            io.log_info("检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。")
            return False

        return self.is_training and self.iter != 0 and io.input_in_time(
            "两秒内按Enter键可进行手动配置模型参数 Press enter in 2 seconds to override model settings.", 5 if io.is_colab() else 2)
```

---

## 五、 验收与测试验证

完成修改后，使用如下命令测试：

```bash
python main.py train \
  --model SAEHD \
  --training-data-src-dir /path/to/src/aligned \
  --training-data-dst-dir /path/to/dst/aligned \
  --model-dir /path/to/model \
  --silent-start \
  --options-json "{\"batch_size\":16,\"random_warp\":true,\"optimizer\":\"adabelief\",\"precision\":\"fp32\",\"gan_power\":0.1}"
```

**期望的运行输出结果**：
1. 控制台直接显示：`Silent start: choosed model "..."`
2. 随后打印：`✅ [GUI_OPTIONS] 成功从 --options-json 动态解析并注入了 5 项训练超参数`
3. 控制台打印：`检测到 GUI 选项 JSON，自动跳过手动参数设置倒计时。`
4. **不会停顿 60 秒**，也不会等待用户按 Enter，直接载入 `batch_size: 16` 并进入训练迭代！
