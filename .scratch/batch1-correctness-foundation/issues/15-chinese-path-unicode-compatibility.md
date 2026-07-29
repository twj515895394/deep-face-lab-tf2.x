# 15 — 训练全链路中文路径与 Unicode 编码兼容

Status: completed
Type: AFK
Blocked by: None — 可以立即开始

**构建内容:** 解决 `deep-face-lab-tf2.x` 后端在 Windows/Cross-platform 环境下包含中文或 Non-ASCII 字符路径（`src-dir`, `dst-dir`, `model-dir` 等）时触发的崩溃、乱码或读写失败问题，确保全链路 Unicode 兼容。

- [x] 在 `main.py` 最顶部设置 Windows UTF-8 控制台标准输出/错误流编码防护。
- [x] 规范 `main.py` 中的 `fixPathAction` 确保路径统一解析为 Unicode `str` 绝对路径。
- [x] 替换 `core/interact/interact.py` 中 Headless 模式遗留的原生 `cv2.imwrite` 为 `cv2ex.cv2_imwrite`，消除 OpenCV C++ 中文路径限制。
- [x] 为 `models/ModelBase.py` 及相关模块中的文本与摘要文件读写（如 `summary.txt`、`options_json` 等）补齐显式 `encoding='utf-8'`。
- [x] 编写自动化 smoke 测试，验证带中文路径的模型初始化、数据加载与训练流程。

## 代码修改详细规格

### 1. 文件: `main.py`
* **标准流编码防护**: 在入口处注入 UTF-8 流重写，防止控制台打印中文路径时抛出 `UnicodeEncodeError`:
  ```python
  import sys
  import io
  if sys.platform == 'win32':
      if hasattr(sys.stdout, 'buffer'):
          sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
      if hasattr(sys.stderr, 'buffer'):
          sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
  ```
* **路径规范化**: 确认 `fixPathAction` 保持 unicode string 返回：
  ```python
  class fixPathAction(argparse.Action):
      def __call__(self, parser, namespace, values, option_string=None):
          setattr(namespace, self.dest, os.path.abspath(os.path.expanduser(values)))
  ```

### 2. 文件: `core/interact/interact.py`
* **OpenCV 中文路径写图修复**: 在 `on_show_image` 的 `_HEADLESS_MODE` 分支中，使用 `cv2ex.cv2_imwrite` 替换直接调用 `cv2.imwrite`:
  ```python
  from core.cv2ex import cv2_imwrite
  ...
  def on_show_image (self, wnd_name, img):
      if _HEADLESS_MODE:
          safe_name = wnd_name.replace('/', '_').replace('\\', '_').replace(':', '_')
          save_path = os.path.join(_headless_preview_dir, f"{safe_name}.png")
          cv2_imwrite(save_path, img)
      else:
          cv2.imshow (wnd_name, img)
  ```

### 3. 文件: `models/ModelBase.py`
* **文本文件读写补齐 `encoding='utf-8'`**:
  - `save()` 方法写入 `summary.txt`:
    ```python
    Path(self.get_summary_path()).write_text(self.get_summary_text(), encoding='utf-8')
    ```
  - `load_train_step_config()` 解析 `options_json`: 确保标准 json utf-8 解码。

### 4. 自动化测试文件: `tests/smoke/test_chinese_path_compatibility.py` [NEW]
* 创建专门的 Smoke 测试，构造临时中文路径目录（如 `tests/tmp_中文数据/data_src`），验证 `pathex`, `cv2ex`, `ModelBase` 路径加载和 IO 正常无报错。

## 验证与测试要点

1. **中文路径读取与加载校验**：
   在包含中文的路径下运行 `python main.py train --training-data-src-dir "D:/测试_data_src" --training-data-dst-dir "D:/测试_data_dst" --model-dir "D:/测试_model"`，验证模型能正常读取样本与数据。
2. **Headless Preview 保存校验**：
   在 `--no-preview` 模式下训练，确认 `_preview` 目录下预览图片正常生成且不触发 OpenCV 编码报错。
3. **单元测试通过**：
   运行 pytest `tests/smoke/test_chinese_path_compatibility.py` 确保 100% 通过。

## 完成总结报告

- [x] 本 issue 完成后需在 `.scratch/batch1-correctness-foundation/reports/15-chinese-path-unicode-compatibility-summary.md` 生成 summary 报告。
- [x] 在本 issue 的 `## Comments` 中追加 summary 报告路径。

## Comments

- 2026-07-29 09:31: Issue 已初始化创建。
- 2026-07-29 09:35: 已完成代码修改与测试验证，生成总结报告：[15-chinese-path-unicode-compatibility-summary.md](file:///t:/deep-face-lab-tf2.x/.scratch/batch1-correctness-foundation/reports/15-chinese-path-unicode-compatibility-summary.md)。

