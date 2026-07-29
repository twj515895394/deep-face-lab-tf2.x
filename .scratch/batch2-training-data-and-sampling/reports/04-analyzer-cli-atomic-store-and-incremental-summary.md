# Batch 2 Ticket 04 — Faceset Analyzer CLI, Atomic Store & Incremental Update 研发总结

> 完成时间：2026-07-29  
> 状态：PASS (macOS / CPU 验证通过)

## 1. 概述与核心变更

本 Ticket 完成了将 `FacesetAnalyzer` 封装为独立可直接运行的 CLI 命令（`python main.py faceset-analyze`），以及底层安全的事务写与增量 Plan 机制：

1. **`samplelib/metadata/store.py`**:
   - `write_metadata_atomic(path, metadata, keep_backup=True)`: 实现了标准事务写过程 (json 序列化 -> `.tmp` -> `fsync` -> 重新 `load_json` 校验 schema -> 可选创建 `.bak` -> `os.replace` 原子覆盖)。若遇到文件锁定或校验失败，保留原目标文件，清理 `.tmp` 并抛出可辨识异常 `MetadataStoreError`。
   - `load_metadata(path)`: 封装安全性读取与验证。
2. **`samplelib/metadata/incremental.py`**:
   - `build_incremental_plan(...)`: 根据旧元数据与当前样本 signatures（MD5/sha256/mtime）比较，区分出 reused/recomputed/added/removed。在 analyzer 版本改变或强制 `--force` 时回退为全量分析。
   - `reconcile_and_finalize_samples(...)`: 整合复用样本与新分析样本，强制重新运行 Pass 2 Percentile 归一化计算，并重新聚合 Faceset 整体 Summary，确保采样评分不偏置。
3. **`samplelib/metadata/report.py`**:
   - `generate_analyzer_report(...)`, `print_console_summary(...)`, `save_report_json(...)`: 生成高亮控制台 Summary 与机器可读的 JSON Report，带有结构化的姿态分布、异常细节与弃权声明（Disclaimer）。
4. **`mainscripts/FacesetAnalyzer.py` & `main.py`**:
   - `mainscripts/FacesetAnalyzer.py`: 负责 CLI 顶层调度、路径校验、格式检测 (ordinary/packed)、增量分流与退出码控制（0: 成功, 2: 参数错, 3: 目录不可用, 5: 严格模式错误, 6: 写入失败）。
   - `main.py`: 注册 `faceset-analyze` 子命令。

---

## 2. 自动化与命令行验证

### 2.1 单元测试套件
```bash
python -m compileall mainscripts/FacesetAnalyzer.py samplelib/metadata main.py
python -m unittest discover -s tests/smoke -p "test_*.py"
```
- 测试结果：**114/114 PASS**。

### 2.2 真实 CLI 命令验证
```bash
# 首次全量分析
python main.py faceset-analyze --input-dir .scratch/test_faceset_cli
# 增量分析
python main.py faceset-analyze --input-dir .scratch/test_faceset_cli --incremental
```
- 输出验证：
  - 首次分析：`Incremental plan: Reused=0, Recomputed=0, Added=10, Removed=0`
  - 增量分析：`Incremental plan: Reused=10, Recomputed=0, Added=0, Removed=0`
  - 生产 `.bak` 备份文件，原子写逻辑完美替代原目标文件。

---

## 3. `--options-json` 训练配置同步状态

```text
--options-json 文档同步：NA
文档版本：v1.0
修改章节：无（本 Ticket 属于 Faceset 预处理工具 CLI，不属于 SAEHD 训练配置参数）
```

---

## 4. Ticket 05 可依赖的规范与接口

- **默认 Metadata 路径**：`<aligned_dir>/faceset_metadata.v1.json`
- **默认 Report 路径**：`<aligned_dir>/faceset_metadata_report.v1.json`
- **Schema 版本**：`v1` (`FacesetMetadataV1`)
- **读取方式**：`samplelib.metadata.store.load_metadata(path)` 或 `FacesetMetadataV1.load_json(path)`

---

## 5. Windows / GPU 待办

- **Windows Single/Multi-worker 验证**：`PENDING-WINDOWS`
