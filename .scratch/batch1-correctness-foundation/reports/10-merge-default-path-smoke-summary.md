# Ticket 10：Merge 默认路径 smoke 总结

> 状态：macOS 轻量验证通过；Windows GPU 真实模型 Merge 质量仍待补证。
> 生成时间：2026-07-26 18:19:47 Asia/Shanghai

## 结论

已建立 Merge 默认路径 smoke。测试通过 dummy predictor、最小 landmarks fixture 和依赖 stub 加载真实 `MergerConfigMasked` / `MergeMaskedFace`，验证 Enhancement Config 缺失或全部关闭时不改变传统 MergeMasked 默认路径。

## 新增 / 修改接口

- 新增 `tests/smoke/test_batch1_merge_default_path.py`。
- 未修改 `merger/MergeMasked.py`、`merger/MergerConfig.py` 或 Merge 算法逻辑。

## 测试覆盖

- Enhancement Config 缺失时 merge 增强全部关闭。
- `merge.enabled=False` 时子 flag 不生效。
- `MergerConfigMasked` 默认配置不要求 enhancement sidecar。
- dummy predictor 返回传统三输出协议：predicted face、src mask、dst mask。
- `MergeMaskedFace` 默认 overlay 路径输出 shape / dtype / finite / range 合法。
- `mode='original'` 返回原图路径可执行。
- 缺失配置与显式关闭配置下输出一致。

## 技术验证结果

```text
python3 -m unittest tests.smoke.test_batch1_merge_default_path -v
7 tests OK

python3 -m unittest discover -s tests/smoke -p 'test_batch1_*.py' -v
49 tests OK

python3 -m py_compile core/leras/optimizer_roundtrip.py core/leras/precision_contract.py tests/smoke/test_batch1_optimizer_roundtrip.py tests/smoke/test_batch1_merge_default_path.py
passed

python3 -m tools.smoke.batch1_mac_smoke --print-json
status: pass, syntax scan: 174 files, 0 errors
```

## 风险与注意事项

- 本 smoke 是 macOS 结构级验证，OpenCV warp/resize/color transfer 由最小 stub 支撑，不能替代真实 Merge 质量验收。
- 本轮只验证传统路径不变；未实现 Shape-aware Merge，也未接入未来增强分支。
- 真实 `MergeMasked(...)` 磁盘读图入口仍受 macOS 缺 `cv2` 限制，Windows GPU / OpenCV 环境需补充真实模型和真实图片验证。

## 人工验证建议

- Windows GPU 环境中使用可加载模型跑 1-3 帧默认 Merge，记录输出图片、mask shape、dtype、finite 和视觉人工验收。
- 后续实现 Shape-aware Merge 前，保留本 smoke 作为“增强关闭时传统路径不变”的回归门。
