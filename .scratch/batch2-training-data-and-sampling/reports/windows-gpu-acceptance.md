# Windows GPU 验收记录（Ticket 21 / Batch 2 Final Gate）

> 更新日期：2026-07-30  
> 分支：`codex/batch2-ticket19-loss-window`  
> Commit：`e173ea6cd7b02ba26dfa2ac71e11710a5ab7defb`（文档提交时以 git HEAD 为准）  
> 状态：**PENDING-WINDOWS-GPU / ENV-VALIDATION-DEFERRED**  
> **不得**将本文件写成 PASS-WINDOWS-GPU，除非下文实机命令与日志齐全。

---

## 1. 本机探测（2026-07-30）

```text
OS: Windows-10-10.0.19045-SP0
Python: 3.11.7 (pyenv C:\Users\Administrator\.pyenv\pyenv-win\versions\3.11.7\python.exe)
TensorFlow: NOT INSTALLED in acceptance Python (import tensorflow → ModuleNotFoundError)
GPU SAEHD 训练：无法在本环境启动
start method: spawn（Windows 默认）
```

结论：当前验收 Python **无 TF/GPU**，Matrix A/B 的 SAEHD 500 + resume 200 **不能执行**。  
代码侧 smoke 仍可在本机运行。

---

## 2. 已具备的实现侧证据（非 GPU）

```text
命令：
  python -m unittest discover -s tests/smoke -p "test_batch*.py" -q

结果（实现侧 2026-07-30）：
  Ran 331 tests
  OK
  shell EXIT=0

覆盖：
  Analyzer workers/strong/incremental/strict
  Unicode 中文路径
  Sampling fallback 边界
  WeightedIndexHost / spawn 单元
  Trainer save controller（无 GPU）
```

状态标签：

```text
PASS-WINDOWS-SMOKE（unit/smoke）
PENDING-WINDOWS-GPU（SAEHD real train）
```

---

## 3. 固定环境清单（实机时填写）

| 项 | 值 |
|---|---|
| OS | _待填_ |
| Python | _待填_ |
| TensorFlow | _待填_ |
| CUDA / cuDNN | _待填_ |
| GPU 型号 / VRAM | _待填_ |
| CPU / RAM | _待填_ |
| branch | `codex/batch2-ticket19-loss-window` |
| commit | _待填_ |
| precision | **fp32**（强制） |
| optimizer | **adabelief**（强制） |
| 模型 | SAEHD |
| resolution / batch | _待填_ |
| workers | _待填_ |
| faceset format | ordinary / packed |
| sample counts SRC/DST | _待填_ |

---

## 4. 验收矩阵状态

### Matrix A — Legacy Baseline

| 场景 | 自动化 smoke | GPU 实机 |
|---|---|---|
| ordinary + legacy_random | PASS | PENDING-WINDOWS-GPU |
| ordinary + legacy_uniform_yaw | PASS | PENDING-WINDOWS-GPU |
| packed + legacy_random | PASS | PENDING-WINDOWS-GPU |
| packed + legacy_uniform_yaw | PASS | PENDING-WINDOWS-GPU |

### Matrix B — Metadata Sampling（≥500 iter，save/exit/resume≥200）

| 场景 | GPU 实机 |
|---|---|
| ordinary pose_balanced / pose_balanced | PENDING-WINDOWS-GPU |
| ordinary quality_pose_balanced / pose_balanced | PENDING-WINDOWS-GPU |
| ordinary pose_balanced / legacy_random | PENDING-WINDOWS-GPU |
| packed pose_balanced / pose_balanced | PENDING-WINDOWS-GPU |
| packed quality_pose_balanced / quality_pose_balanced | PENDING-WINDOWS-GPU |

### Matrix C — Fallback

| 场景 | 自动化 | GPU 集成 |
|---|---|---|
| missing / invalid / strict / core SampleLoader | PASS（unit） | PENDING-WINDOWS-GPU |

### Matrix D — Analyzer

| 场景 | 自动化 |
|---|---|
| workers 1/2/auto, quick/strong, ordinary/packed, incremental, unicode, strict | PASS |

---

## 5. 实机执行协议（有 TF+GPU 时）

```powershell
# 1) 使用带 CUDA 的项目 venv
# 2) Analyzer
python main.py faceset-analyze --input-dir "D:\换脸项目\data_src\aligned" --workers 2
python main.py faceset-analyze --input-dir "D:\换脸项目\data_dst\aligned" --workers 2

# 3) 训练（示例 options-json 字符串，fp32 + adabelief）
python main.py train SAEHD ... --options-json "{...enhancements...}"

# 4) 记录 500+ iter、manual save、exit、resume 200+
# 5) 将日志片段、iter time、VRAM 填回本文件 §3/§4 并改状态
```

---

## 6. Verdict

```text
Ticket 21 GPU gate：NOT PASS
Batch 2 DONE：禁止
原因：acceptance Python 无 TensorFlow/GPU；SAEHD 矩阵未实跑
允许：继续独立 Review Ticket 18/20 代码；GPU 验收可另机补做
```
