# Ticket 11：Batch 1 兼容矩阵与 handoff 汇总

> 状态：macOS 轻量复核通过；Windows GPU 真实训练、保存恢复与 Merge 质量仍待补证。  
> 生成时间：2026-07-26 20:34:48 Asia/Shanghai

## 结论

Batch 1 的 P0 正确性修复、兼容配置骨架、optimizer / precision 可观测性、训练保存恢复 smoke 与 Merge 默认路径 smoke 已完成 macOS 轻量实现与复核。当前可进入 Batch 2 的设计和轻量开发准备，但不能把 Batch 1 宣称为 Windows GPU / TensorFlow / SAEHD 真实训练验收完成。

本轮没有新增运行时接口、参数或算法能力；只更新 Batch 1 状态矩阵、兼容矩阵、验证记录、风险清单、最新 handoff 和文档索引。

## Batch 1 完成状态矩阵

| Ticket | 状态 | macOS 轻量验证 | Windows GPU 验证 |
|---|---|---|---|
| 01 baseline / macOS smoke harness | done-macos-lightweight | pass | 待验证 |
| 02 Eyes / Mouth Priority 真实 mask | done-macos-lightweight | pass | 待验证 |
| 03 训练异常语义 | done-macos-lightweight | pass | 待验证 |
| 04 Precision Contract 与 dtype 审计 | done-macos-lightweight | pass | 待验证 |
| 05 optimizer roundtrip 审计 | done-macos-lightweight | pass | 待验证 |
| 06 Lion v2 与 legacy state 保护 | done-macos-lightweight | pass | 待验证 |
| 07 finite gradient gate / Loss Scaling | done-macos-lightweight | pass | 待验证 |
| 08 Enhancement Feature Flag 骨架 | done-macos-lightweight | pass | 待验证 |
| 09 训练保存恢复 smoke | done-macos-lightweight | pass | 待验证 |
| 10 Merge 默认路径 smoke | done-macos-lightweight | pass | 待验证 |
| 11 兼容矩阵与 handoff 汇总 | done-macos-lightweight | pass | 不适用，记录待验边界 |

## 兼容矩阵

| 场景 | Batch 1 当前结论 | 证据 | 剩余风险 |
|---|---|---|---|
| 旧模型无 `enhancements` | 默认全部增强关闭，不改变旧训练 / Merge 意图 | `tests/smoke/test_batch1_config_defaults.py`、`tests/smoke/test_batch1_training_save_resume_smoke.py` | Windows GPU 旧 SAEHD `data.dat` 真实加载待验证 |
| 新模型全部增强关闭 | 传统路径保持默认行为 | `tests/smoke/test_batch1_config_defaults.py`、`tests/smoke/test_batch1_merge_default_path.py` | 真实模型目录与 OpenCV Merge 待验证 |
| `eyes_mouth_prio=False` | 继续接受 src/dst 各三输出样本 | `tests/smoke/test_batch1_eyes_mouth_masks.py` | Windows 真实 DataGenerator 启动待验证 |
| `eyes_mouth_prio=True` | 要求第 4 个真实 EM mask，缺失 / shape mismatch / non-finite 立即失败 | `tests/smoke/test_batch1_eyes_mouth_masks.py` | Windows 真实训练 loss 路径待验证 |
| AdaBelief / RMSprop state | NumPy roundtrip 与 save/resume smoke 通过 | `tests/smoke/test_batch1_optimizer_roundtrip.py`、`tests/smoke/test_batch1_training_save_resume_smoke.py` | 真实 TensorFlow session slot 恢复待验证 |
| Lion v2 state | 新 v2 state 可保存恢复；legacy state 不静默污染新公式 | `tests/smoke/test_batch1_optimizer_roundtrip.py` | 旧模型真实恢复后短训稳定性待验证 |
| FP32 precision | Batch 1 validated baseline | `tests/smoke/test_batch1_precision_contract.py` | Windows CUDA / cuDNN 真实训练待验证 |
| FP16 / BF16 precision | 保持 experimental / blocked，不宣称 validated | `tests/smoke/test_batch1_precision_contract.py`、`tests/smoke/test_batch1_finite_gradient_gate.py` | GPU dtype、loss scale、保存恢复稳定性待验证 |
| finite gradient gate | non-finite step 跳过 optimizer update | `tests/smoke/test_batch1_finite_gradient_gate.py` | 真实 TensorFlow 图执行与日志可观测性待验证 |
| Merge 无 enhancement config | dummy predictor 下传统默认路径可执行 | `tests/smoke/test_batch1_merge_default_path.py` | 真实图片、真实模型、OpenCV 质量待验证 |
| CLI | Batch 1 未新增必须 CLI 参数 | 文档与代码复核 | 后续 Batch 2 新 flag 必须默认关闭 |

## 技术验证结果

本轮主 Agent 已在 macOS 本机复跑：

```bash
python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py' -v
```

结果：

```text
Ran 73 tests in 0.510s
OK
```

```bash
python3 -m tools.smoke.batch1_mac_smoke --print-json
```

关键结果：

```text
status: pass
Python: 3.12.8
platform: Darwin arm64
syntax_scan: 177 files, 0 errors
numpy: 2.4.4 available
cv2: missing
tensorflow: missing
core.leras.nn: missing colorama
models / merger.MergeMasked: missing cv2
training_save_resume: pass
optimizers: adabelief, rmsprop, lion
max_abs_reload_error: 0.0
max_abs_update_error: 0.0
```

```bash
python3 -m py_compile core/leras/training_save_resume_smoke.py tools/smoke/batch1_mac_smoke.py core/leras/precision_contract.py core/leras/optimizer_roundtrip.py core/enhancements/config.py tests/smoke/test_batch1_config_defaults.py tests/smoke/test_batch1_eyes_mouth_masks.py tests/smoke/test_batch1_finite_gradient_gate.py tests/smoke/test_batch1_mac_smoke.py tests/smoke/test_batch1_merge_default_path.py tests/smoke/test_batch1_optimizer_roundtrip.py tests/smoke/test_batch1_precision_contract.py tests/smoke/test_batch1_training_save_resume_smoke.py
```

结果：通过，无输出。

## Windows GPU 人工验证建议

- Windows 启动脚本、Python 环境、CUDA / cuDNN / TensorFlow GPU discovery。
- SAEHD FP32 最小模型初始化，resolution 64 或 96，batch size 2，短训 2-5 step 并确认 finite losses。
- `eyes_mouth_prio=False` 三输出路径与 `eyes_mouth_prio=True` 四输出路径真实 DataGenerator 启动。
- 人工注入或构造 non-finite 梯度，验证 finite gate 跳过 update 且权重不污染。
- 旧 Lion state 恢复：主权重可加载，legacy optimizer state 被重置或明确 warning，后续短训可继续。
- 训练 N step 后保存，退出进程或重置 TensorFlow session，重载后继续 N step，确认 model iteration / optimizer state / loss 没有异常跳变。
- 默认 Merge 使用真实模型与真实图片跑 1-3 帧，记录输出 shape、dtype、finite、视觉质量和 OpenCV 路径稳定性。
- FP16 / BF16 保持 experimental，直到真实 GPU dtype、loss scale、保存恢复证据补齐。

## Batch 2 判断

Batch 1 不阻断进入 Batch 2 的设计和轻量开发准备，因为默认关闭、旧配置兼容、P0 正确性 smoke 和文档边界已经建立。  
但 Windows GPU 真实训练、保存恢复和 Merge 质量仍是后续合并或发布增强能力前的硬性验收门。

## 模型路由复核

本轮按 `codex-model-routing-team` 执行 1 个 Gemini inspect Worker：

```text
task_id: B1-T11-GEMINI-REVIEW-20260726-2031
model: cli-proxy/gemini-3.6-flash-high
thinking: high
thread_id: 019f9e6a-564f-75b3-8fd3-a55337e9aa39
status: completed
adopted: partially
```

采纳内容：Worker 的总体风险分类、兼容矩阵结构、Windows GPU 待验证维度。  
未采纳内容：Worker 文本中的 AST 扫描数量使用 174；主 Agent 本轮实测为 177，最终文档采用 177。

RoutePlan 与 ledger：

```text
.scratch/batch1-correctness-foundation/reports/route-plan-ticket11-20260726.json
.scratch/batch1-correctness-foundation/reports/model-routing-ledger-ticket11-20260726.json
```

## 风险与注意事项

- 不要把 macOS lightweight smoke 写成真实 GPU 训练或真实 Merge 质量已验证。
- 不要把 FP16 / BF16 写成 validated。
- Ticket 07 的 skipped update / zero loss 表示防护触发，不应被误读为训练质量提升。
- Batch 2 不得重新打开 Batch 1 已冻结的默认关闭、旧配置兼容、三输出默认路径和 legacy state 保护原则。
