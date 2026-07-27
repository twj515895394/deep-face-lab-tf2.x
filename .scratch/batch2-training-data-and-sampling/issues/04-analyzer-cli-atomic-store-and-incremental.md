# 04 — 交付 Analyzer CLI、原子存储、增量更新与正式报告

Status: open
Type: AFK
Blocked by: `03-lightweight-faceset-analyzer-core.md`

**构建内容：** 将 Analyzer 核心包装为用户可直接长期使用的命令，生成正式 Metadata sidecar 和报告；支持安全覆盖、增量更新、普通/Packed Faceset、清晰退出码和失败后保留旧文件。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 02、03 summary，确认 Schema、Analyzer config/result 和 issue code
3. `main.py` 当前 subcommand 注册模式
4. `mainscripts/Util.py` 及现有 faceset metadata 备份工具，避免命名和语义冲突
5. `samplelib/PackedFaceset.py` 的路径判断
6. 项目现有日志、progress bar 和退出码习惯

## 当前源码事实必须先确认

- `main.py` 如何将 argparse 参数传给 mainscript；
- `io.log_info/log_err/progress_bar_generator` 的使用方式；
- Windows 下主入口如何设置 multiprocessing spawn；
- 现有 util `--save-faceset-metadata` 实际用途，确保新命令不复用其名称；
- Ticket 03 Analyzer 是否已经支持 workers；若没有，本 Ticket 不得在 CLI 中伪装支持多 worker。

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

### 建议退出码

```text
0  分析完成；非 strict 下允许存在单图 invalid
2  CLI 参数错误
3  输入目录/数据不可用
4  Schema/旧 Metadata 不可读取且策略拒绝覆盖
5  Analyzer 顶层失败
6  写入/原子替换失败
```

使用项目已有 main 异常处理时可以映射到等价非零值，但必须写入 summary。

## 建议施工顺序

### Step 1：先做 Store 纯函数

建议接口：

```python
@dataclass
class AtomicWriteResult:
    target_path: Path
    backup_path: Optional[Path]
    bytes_written: int
    replaced: bool


def write_metadata_atomic(path: Path, metadata: FacesetMetadataV1, keep_backup: bool = True) -> AtomicWriteResult:
    ...
```

顺序固定：

```text
serialize allow_nan=False
→ 写同目录 temp
→ flush/fsync
→ 重新读取 temp
→ Schema validate
→ 可选生成/替换一次 backup
→ os.replace(temp, target)
→ 清理残留 temp
```

先完成故障注入测试，再接 CLI。

### Step 2：实现增量 planner

不要在 CLI 函数里直接堆 if。建议：

```python
plan = build_incremental_plan(old_metadata, current_signatures, analyzer_version, config)
plan.reuse_ids
plan.recompute_ids
plan.added_ids
plan.removed_ids
plan.reasons
```

规则：

- key/ID 相同且 signature/兼容版本相同：复用 raw metrics；
- signature 改变：重算；
- 新增：分析；
- 删除：从新 manifest 移除；
- Analyzer/quality policy 不兼容：全量或明确部分重算；
- 复用 raw metrics 后必须重新计算全局 percentile 与最终 quality。

### Step 3：实现 Report builder

控制台摘要和 JSON 报告由同一 summary 数据生成，避免两套统计不一致。大列表必须限制展示数量，完整异常可写机器报告。

### Step 4：实现 mainscript

`mainscripts/FacesetAnalyzer.py` 只负责编排：

```text
校验路径/参数
→ 加载旧 Metadata（可选）
→ 生成增量 plan
→ 调 Analyzer
→ final metadata/report
→ atomic write
→ 输出摘要/退出状态
```

### Step 5：最后注册 main.py subcommand

只新增独立命令，不改变现有 `util`、`train`、`merge` 参数。

## 详细任务

- [ ] 新增 `mainscripts/FacesetAnalyzer.py`。
- [ ] `main.py` 新增独立 subcommand，不复用 `util --save-faceset-metadata` 名称。
- [ ] 默认输出 `<input-dir>/faceset_metadata.v1.json`。
- [ ] 默认报告 `<input-dir>/faceset_metadata_report.v1.json`。
- [ ] `--incremental` 和 `--force` 互斥或有明确优先级。
- [ ] workers 默认 `min(cpu_count, 8)`，允许 1 作为调试模式。
- [ ] 参数错误、输入无数据、写入失败返回非零退出码。
- [ ] 非 strict 的单图失败仍可成功退出，但报告 invalid count。

### Store

- [ ] 新增 `samplelib/metadata/store.py`。
- [ ] 目标文件父目录验证和创建规则明确。
- [ ] 序列化时禁止 NaN / Inf。
- [ ] 写入 `.tmp`，flush，允许时 fsync。
- [ ] 临时文件重新读取并 Schema 校验。
- [ ] 使用 `os.replace` 原子替换。
- [ ] 替换失败时保留旧目标，清理 temp。
- [ ] 可选保留一次 `.bak`，但必须有明确规则，不能无限累积。
- [ ] Windows 文件占用错误输出目标路径和解决建议。

### Incremental

- [ ] 加载旧 Metadata，检查 schema/analyzer 版本。
- [ ] 以 sample_id/key/signature 决定复用或重算。
- [ ] 统计 reused/recomputed/added/removed。
- [ ] key 相同 signature 改变必须重算。
- [ ] 删除样本从新文件移除。
- [ ] collision 不猜测，相关样本重算并记录。
- [ ] 复用 raw metrics 后重新计算全局 normalized quality 和 summary。
- [ ] Analyzer 版本或 quality policy 变化时按兼容规则全量或部分重算。

### Report

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
- `samplelib/metadata/incremental.py`
- `samplelib/metadata/report.py`
- `main.py`
- `tests/smoke/test_batch2_analyzer_cli.py`
- `tests/smoke/test_batch2_metadata_store.py`
- `tests/smoke/test_batch2_incremental.py`

## 最小测试命令

```bash
python -m compileall mainscripts/FacesetAnalyzer.py samplelib/metadata main.py
python -m unittest \
  tests.smoke.test_batch2_metadata_store \
  tests.smoke.test_batch2_incremental \
  tests.smoke.test_batch2_analyzer_cli
```

CLI 必须至少手工执行一次 synthetic ordinary 和 packed fixture，并在 summary 记录完整命令。

## 禁止捷径与常见错误

- 不允许直接覆盖目标 JSON 后再验证。
- 不允许 temp 文件写到其他磁盘/分区后假设 `os.replace` 原子。
- 不允许 incremental 复用旧的最终 quality_score 而不重算全局 percentile。
- 不允许 `--force` 和 `--incremental` 同时无定义地生效。
- 不允许 workers 参数存在但始终被忽略。
- 不允许 Windows spawn 在模块 import 时创建进程池。
- 不允许复用旧 util metadata 备份命令名称。
- 不允许 Analyzer 自动修改或删除原图。

## 验收标准

- [ ] 用户可从命令行完成首次和增量分析。
- [ ] 输出文件可由 Schema v1 重新读取。
- [ ] 任意写入失败不破坏上一次有效 Metadata。
- [ ] 报告足以人工定位坏图和姿态分布。
- [ ] 普通与 Packed 无需不同命令。
- [ ] Analyzer 不修改原图、不解包 faceset.pak。
- [ ] Ticket 05 能直接调用稳定的 store/schema 输出，不依赖 CLI 内部实现。

## 回退

删除可选 CLI 和新模块不会影响 train、merge 或旧 util 命令。

## 不在本 ticket

- 不让训练加载 Metadata。
- 不生成采样权重。
- 不新增 SAEHD 交互选项。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/04-analyzer-cli-atomic-store-and-incremental-summary.md`，记录命令、退出码、文件格式、原子写证据、增量测试和 Windows 注意事项。
- [ ] 给出 Ticket 05 可依赖的默认路径、Schema 版本和读取方式。
- [ ] 分别标记 single-worker PASS 与 Windows multi-worker PENDING/PASS。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建，等待 Ticket 03 完成。
- 2026-07-27：补充原子写顺序、增量 planner、退出码、测试命令和常见失败。