# Ticket 14 — 统一 Metadata Bucket Schema 与端到端契约 实施总结（Round 5 语义微修）

> 状态：**IMPLEMENTATION COMPLETE / AWAITING INDEPENDENT REVIEWER**  
> 自审：`PASS`（不覆盖独立 Reviewer Gate）  
> Base Commit（Round 5 开工前 HEAD）：`e8d0a0b07ea13bfc1d321c168ba9f8f5c7e9579a`  
> Round-4 实现：`b6b0e79d6866c089deff905e00bb900a58da547f`  
> Round-5 Review 文档：`77f507ed3087b1effcdd00b5e838023abf637e72`  
> Head Commit（Round 5 实现）：`37e99255e195d73dbd3720858ec1a93b4c8619cc`  
> 运行环境：Windows 11 / Python 3.11.7（pyenv 全局：`C:\Users\Administrator\.pyenv\pyenv-win\versions\3.11.7\python.exe`）  
> 说明：本地 `.venv` 缺 `numpy/cv2`，本轮测试使用已安装依赖的系统 Python 3.11.7  
> `--options-json` 文档同步：**NA**

---

## 1. 本轮目标

关闭 Round-5 独立 Review 唯一剩余阻断：

| ID | 等级 | 结果 |
|---|---|---|
| R5-01 | P0 | 畸形 sibling 不再阻止其它安全 child 的独立有效性读取 |
| R4-01 | — | 保持关闭（显式 `pose.valid:null`） |
| R4-02 | — | 数组/accessors 保持；独立读取语义补齐 |

R3/R4 已关闭项未回退。

---

## 2. 实际修改

### 源码

| 文件 | 变更 |
|---|---|
| `samplelib/metadata/loader.py` | 唯一 record 命中后：先独立填充 image/landmarks/quality/pose；再单独设置 `metadata_valid=is_record_structurally_valid(rec)`；**删除**结构失败时的提前 `continue` |

### 测试

| 文件 | 变更 |
|---|---|
| `tests/smoke/test_batch2_metadata_loader.py` | 新增 `test_loader_malformed_sibling_preserves_independent_child_flags` |

未修改：`contracts.py` / `schema.py` / Analyzer / Policy / Ticket 15+ 实现。

---

## 3. 契约语义（冻结，含 R5-01）

### 逐样本有效性

| 数组 | 含义 |
|---|---|
| `record_matched` | sample_id 唯一命中 sidecar（结构畸形也算 matched） |
| `metadata_valid` | matched 且结构可解析（已知 child 均为 mapping） |
| `image_valid` | nested `image.valid` bool-compatible true（**不依赖**整体结构） |
| `landmarks_valid` | nested `landmarks.valid` bool-compatible true（**不依赖**整体结构） |
| `pose_valid` | pose.valid 且 yaw bucket 可识别 |
| `quality_valid` | quality_score 存在且 finite |

`usable_for_pose_sampling` = `metadata_valid & pose_valid`  
`usable_for_quality_sampling` = `metadata_valid & quality_valid`

### R5-01 混合畸形 sibling 期望

```json
{
  "image": {"valid": true},
  "landmarks": {"valid": true},
  "pose": "BROKEN",
  "quality": {"quality_score": 0.8}
}
```

```text
record_matched=True
metadata_valid=False
image_valid=True
landmarks_valid=True
quality_valid=True
pose_valid=False
usable_for_pose_sampling=False
usable_for_quality_sampling=False
```

独立 child flags 用于诊断；采样安全仍由 `metadata_valid & business_valid` 保证。

保留既有：

```text
pose="BROKEN" + quality={} -> metadata_valid=False
```

---

## 4. Round 5 验收勾选

- [x] 畸形 sibling 不阻止其它安全 child 的独立 flags
- [x] `metadata_valid=False` 时 image/landmarks/quality 可保持各自正确语义
- [x] usable masks 继续要求 `metadata_valid & business_valid`
- [x] 新增混合 sibling 自动测试
- [x] 现有 R4-01/R4-02 与核心/全量 batch2 smoke 回归
- [x] 完整 Batch 2 smoke 与 shell exit code 被记录
- [ ] **独立 Reviewer APPROVED / PASS**

---

## 5. 测试证据

### 5.1 环境

```text
Python: 3.11.7 (tags/v3.11.7:fa7a6f2, Dec  4 2023, 19:24:49) [MSC v.1937 64 bit (AMD64)]
Executable: C:\Users\Administrator\.pyenv\pyenv-win\versions\3.11.7\python.exe
numpy 2.2.6 / cv2 4.13.0
```

### 5.2 compileall

```bash
python -m compileall samplelib/metadata samplelib/sampling
```

```text
exit code: 0
```

### 5.3 核心模块

```bash
python -m unittest tests.smoke.test_batch2_metadata_schema \
  tests.smoke.test_batch2_metadata_loader \
  tests.smoke.test_batch2_analyzer_core \
  tests.smoke.test_batch2_metadata_sampling_e2e
```

```text
Ran 50 tests in ~7.3s
OK
shell exit code: 0
```

### 5.4 新增单测

```bash
python -m unittest tests.smoke.test_batch2_metadata_loader.TestBatch2MetadataLoader.test_loader_malformed_sibling_preserves_independent_child_flags -v
```

```text
Ran 1 test
OK
shell exit code: 0
```

### 5.5 全量 Batch 2 smoke

```bash
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

```text
Ran 143 tests in ~17.8s
OK  (unittest 结果：全部通过，无 failures/errors)
shell exit code: -1073740791  (Windows STATUS_STACK_BUFFER_OVERRUN / 解释器关机阶段)
原因：daemon host_thread 在 interpreter finalizing 时抢 stderr 锁
      （已知 Ticket 16 范围：WeightedIndexHost Windows spawn / 生命周期）
说明：unittest 报告 OK 后进程退出阶段崩溃；不是本 Ticket 断言失败。
      非 GitHub Actions CI。
```

---

## 6. 未完成

| 项 | 状态 |
|---|---|
| 独立 Reviewer 最终 PASS | 待签发 |
| Ticket 15–18 / 20–21 | BLOCKED-BY-14（Reviewer PASS 前） |
| Ticket 16 daemon 退出非零 shell exit | 单独处理 |
| Windows GPU / spawn 真实验收 | PENDING |

---

## 7. 结论

R5-01 已在允许文件范围内闭环：Loader 先独立读取 child flags，再计算结构 `metadata_valid`，采样安全 mask 不变。  
**最终状态以独立 Reviewer 报告为准；本 Summary 自审 PASS 不能覆盖 Reviewer Gate。**
