# Windows GPU 真实训练验收记录模板

> 适用于 Ticket 01 - 12 在真实 Windows GPU 环境下执行 FP32 + AdaBelief 验收。

## 环境硬件信息

- **OS / Windows Version**: 
- **GPU Device Name**: 
- **CUDA / cuDNN Version**: 
- **TensorFlow Version**: 
- **Python Version**: 

## 验证项目与判定标准

| 序号 | 验证项 | 预期行为 / 门槛 | 实际结果 | 状态 (PASS/FAIL) |
|---|---|---|---|---|
| 1 | FP32 + AdaBelief 启动 | 正常初始化不崩溃 | | |
| 2 | Ordinary Faceset 训练 | 稳定迭代 1000+ iter | | |
| 3 | Packed Faceset 训练 | `faceset.pak` 正常读取训练 | | |
| 4 | 多进程 Generator (workers > 1) | 无死锁、崩溃或内存泄露 | | |
| 5 | Save / Exit / Resume 周期 | 恢复权重与训练 step 完整 | | |
| 6 | 性能与迭代耗时 | 记录单 iter ms 均值与 VRAM 占用 | | |

## 详细日志与采样数据

```text
[Insert console log snippet / performance metrics here]
```

## 结论

- **验收结论**: 
- **记录时间**: 
