# 04 — 交付 Analyzer CLI、原子存储、增量更新与正式报告

Status: open
Type: AFK
Blocked by: `03-lightweight-faceset-analyzer-core.md`

**构建内容：** 将 Analyzer 核心包装为用户可直接长期使用的命令，生成正式 Metadata sidecar 和报告；支持安全覆盖、增量更新、普通/Packed Faceset、清晰退出码和失败后保留旧文件。

## 目标

- 用户有明确、独立、不会与现有 metadata 备份工具混淆的入口。
- Metadata 写入具备事务性，失败不会破坏旧文件。
- faceset 新增、删除、修改后可以增量更新。
- 控制台和机器报告都能说明分析了什么、失败了什么。
- Analyzer 本身成为 Batch 2 的一个完整可用产品，而非训练内部隐藏步骤。

## CLI 设计

建议新增：

```bash
python main.py faceset-analyze \
  --input-dir <aligned> \
  [--output-file <path>] \
  [--report-file <path>] \
  [--incremental] \
  [--force] \
  [--workers N] \
  [--strong-fingerprint] \
  [--strict]
```

- [ ] 新增 `mainscripts/FacesetAnalyzer.py`。
- [ ] `main.py` 新增独立 subcommand，不复用 `util --save-faceset-metadata` 名称。
- [ ] 默认输出 `<input-dir>/faceset_metadata.v1.json`。
- [ ] 默认报告 `<input-dir>/faceset_metadata_report.v1.json`。
- [ ] `--incremental` 和 `--force` 互斥或有明确优先级。
- [ ] workers 默认 `min(cpu_count, 8)`，允许 1 作为调试模式。
- [ ] 参数错误、输入无数据、写入失败返回非零退出码。
- [ ] 非 strict 的单图失败仍可成功退出，但报告 invalid count。

## Store 设计

- [ ] 新增 `samplelib/metadata/store.py`。
- [ ] 目标文件父目录验证和创建规则明确。
- [ ] 序列化时禁止 NaN / Inf。
- [ ] 写入 `.tmp`，flush，允许时 fsync。
- [ ] 临时文件重新读取并 Schema 校验。
- [ ] 使用 `os.replace` 原子替换。
- [ ] 替换失败时保留旧目标，清理 temp。
- [ ] 可选保留一次 `.bak`，但必须有明确规则，不能无限累积。
- [ ] Windows 文件占用错误输出目标路径和解决建议。

## Incremental 设计

- [ ] 加载旧 Metadata，检查 schema/analyzer 版本。
- [ ] 以 sample_id/key/signature 决定复用或重算。
- [ ] 统计 reused/recomputed/added/removed。
- [ ] key 相同 signature 改变必须重算。
- [ ] 删除样本从新文件移除。
- [ ] collision 不猜测，相关样本重算并记录。
- [ ] 复用 raw metrics 后重新计算全局 normalized quality 和 summary。
- [ ] Analyzer 版本或 quality policy 变化时按兼容规则全量或部分重算。

## Report 设计

- [ ] 新增 `samplelib/metadata/report.py`。
- [ ] 输出 faceset format、count、fingerprint、elapsed、throughput。
- [ ] 输出 pose/quality 分布和 issue counts。
- [ ] 输出有限条失败/低质量 sample key，不把超大列表刷屏。
- [ ] 机器报告包含完整或可配置数量的异常列表。
- [ ] 明确声明 quality score 只是采样辅助，不是最终换脸质量评分。

## 测试场景

- [ ] 首次全量分析。
- [ ] 第二次 incremental 全部复用。
- [ ] 新增一张：added=1。
- [ ] 修改一张：recomputed=1。
- [ ] 删除一张：removed=1。
- [ ] Metadata 被截断：旧文件保留或明确覆盖策略。
- [ ] temp 写入失败：旧文件不变。
- [ ] unsupported schema：不错误复用。
- [ ] ordinary / packed。
- [ ] workers=1 / workers>1。
- [ ] Windows spawn 入口不递归启动。

## 建议文件

- `mainscripts/FacesetAnalyzer.py`
- `samplelib/metadata/store.py`
- `samplelib/metadata/report.py`
- `main.py`
- `tests/smoke/test_batch2_analyzer_cli.py`
- `tests/smoke/test_batch2_metadata_store.py`

## 验收标准

- [ ] 用户可从命令行完成首次和增量分析。
- [ ] 输出文件可由 Schema v1 重新读取。
- [ ] 任意写入失败不破坏上一次有效 Metadata。
- [ ] 报告足以人工定位坏图和姿态分布。
- [ ] 普通与 Packed 无需不同命令。
- [ ] Analyzer 不修改原图、不解包 faceset.pak。

## 回退

删除可选 CLI 和新模块不会影响 train、merge 或旧 util 命令。

## 不在本 ticket

- 不让训练加载 Metadata。
- 不生成采样权重。
- 不新增 SAEHD 交互选项。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/04-analyzer-cli-atomic-store-and-incremental-summary.md`，记录命令、退出码、文件格式、原子写证据、增量测试和 Windows 注意事项。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 03 完成。
