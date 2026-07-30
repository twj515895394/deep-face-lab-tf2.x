# Batch 3 Master Test Matrix

> 当前状态：DESIGN ONLY / NOT EXECUTED

| Gate | 场景 | 预期 |
|---|---|---|
| Config | 无 Batch3 字段 | 全部 requested/effective=false，旧行为不变 |
| Config | 非法/unknown/新 schema | 安全关闭并给出 warning，不隐式启用 |
| Contract | wrong shape/dtype/mask | 专用校验失败；核心错误传播 |
| Hook | registry empty / weights zero | 总 loss 与基线等价 |
| Anchor | valid ordinary/packed identity | 加载成功且 identity/fingerprint 匹配 |
| Anchor | missing/stale/corrupt | fallback 模式关闭 geometry；strict 抛错 |
| Feature | translation/scale variants | 归一化特征按契约不变 |
| Feature | expression-only eye/mouth change | identity geometry target 不变化 |
| Ratio Loss | zero/known delta/masked | 数值与 NumPy reference 一致 |
| Landmark Loss | zero/known delta/masked | 数值与 NumPy reference 一致 |
| Numeric | NaN/Inf/empty valid set | 不静默进入 optimizer；状态/错误明确 |
| Curriculum | warmup/ramp/stable boundaries | stage/progress/weights 确定且可恢复 |
| SAEHD Off | all flags off | graph/loss/gradient/save/sampling/Merge 基线等价 |
| SAEHD On | ratio/landmark/combined | 单项日志可见、梯度有限、step 正常 |
| Compatibility | old options/checkpoint | 可加载，新增能力默认关闭 |
| Control | save/exit/resume/loss window | 迭代与阶段恢复一致，无控制流回归 |
| Regression | existing `test_batch*.py` | 全部通过 |
| Environment | Windows TF/CUDA short smoke | 单项与组合至少短跑；状态单独记录 |
| Visual A/B | long GPU + fixed preview set | 脸型稳定性、表情保留和伪影人工记录 |

## 建议命令

```bash
python -m unittest discover -s tests/smoke -p "test_batch3*.py" -q
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

GPU 项没有真实日志、配置、checkpoint、样本说明和预览证据时，一律保持 `NOT EXECUTED`。