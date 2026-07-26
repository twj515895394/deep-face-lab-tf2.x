# Ticket 05：optimizer roundtrip 审计基础总结

> 状态：macOS 轻量验证通过；Windows GPU 真实 TensorFlow session / SAEHD 保存恢复仍待补证。
> 生成时间：2026-07-26 18:19:47 Asia/Shanghai

## 结论

已建立 AdaBelief、RMSprop、Lion 的 optimizer roundtrip 轻量审计基础。当前实现使用与源码公式对齐的 NumPy 小向量路径，记录 slot dtype、保存恢复误差和恢复后下一步更新误差，不修改 Lion 公式。

## 新增 / 修改接口

- 新增 `core/leras/optimizer_roundtrip.py`。
  - `numpy_optimizer_step(...)`
  - `serialize_optimizer_state(...)`
  - `deserialize_optimizer_state(...)`
  - `run_numpy_optimizer_roundtrip(...)`
  - `run_all_numpy_optimizer_roundtrips(...)`
- 扩展 `core/leras/precision_contract.py::collect_optimizer_slot_dtype_snapshot()`：
  - 新增对真实 leras optimizer 属性 `ms_dict`、`vs_dict`、`c_dict`、`accumulators_dict`、`iterations` 的 dtype 采集。

## 测试覆盖

- 新增 `tests/smoke/test_batch1_optimizer_roundtrip.py`。
- 覆盖 AdaBelief / RMSprop / Lion：
  - 固定小向量连续更新；
  - warmup 后序列化 / 反序列化；
  - 恢复后下一步更新与连续训练比较；
  - slot dtype snapshot；
  - max absolute reload/update error；
  - Lion 当前 beta2 不影响轨迹的 legacy 事实记录。

## 技术验证结果

```text
python3 -m unittest tests.smoke.test_batch1_optimizer_roundtrip -v
6 tests OK

python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py' -v
49 tests OK

python3 -m py_compile core/leras/optimizer_roundtrip.py core/leras/precision_contract.py tests/smoke/test_batch1_optimizer_roundtrip.py tests/smoke/test_batch1_merge_default_path.py
passed

python3 -m tools.smoke.batch1_mac_smoke --print-json
status: pass, syntax scan: 174 files, 0 errors
```

## 风险与注意事项

- 本 ticket 不修 Lion 公式；当前 Lion 仍是 legacy 轨迹，Ticket 06 需要基于该审计 harness 修复并比较。
- 本轮未走真实 TensorFlow `nn.Saveable` / session / GPU optimizer state，不能替代 Windows GPU 保存恢复验证。
- FP16 / BF16 仍保持 experimental，不声明低精度 roundtrip 已验证。

## 人工验证建议

- Windows GPU 环境中，在 Ticket 06 / 07 后用真实 SAEHD 模型目录补充 optimizer state 保存恢复验证。
- 对 Lion v2 修复前后输出 old/new trajectory diff，确认 legacy state 不被静默解释为新公式 state。
