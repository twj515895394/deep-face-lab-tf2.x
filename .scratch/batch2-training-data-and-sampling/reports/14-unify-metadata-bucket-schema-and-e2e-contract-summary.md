# Ticket 14 — 统一 Metadata Bucket Schema 与 Analyzer→Loader→Policy 端到端契约 实施总结报告

> 状态：RESOLVED / PASS  
> 修改 Commit：c302087 .. HEAD  
> 运行环境：Windows 11 (Python 3.11.7)

---

## 1. 概述与核心变更

本 Ticket 彻底修复了原本 `FacesetAnalyzer` 输出的姿态桶名称与 `FacesetMetadataLoader` 识别名称不一致导致的 P0 阻断缺陷。在本次修复前，Analyzer 输出 `extreme_left`, `minor_left` 等名称，而 Loader 只尝试匹配 `front`, `slight_left` 等旧名称，导致 `yaw_bucket_ids` 全为 `-1`、`pose_valid` 全为 `False`，姿态平衡采样（`pose_balanced`）静默失效。

### 主要改动内容：
1. **新增单一契约定义源 [samplelib/metadata/contracts.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/contracts.py)**:
   - 定义 7 个 Canonical Yaw Bucket: `("extreme_left", "major_left", "minor_left", "center", "minor_right", "major_right", "extreme_right")` (IDs 0..6)。
   - 定义 3 个 Canonical Pitch Bucket: `("up", "level", "down")` (IDs 0..2)。
   - 定义 Legacy Aliases: `front -> center`, `slight_left -> minor_left`, `left -> major_left`, `right -> major_right`, `center -> level` (pitch)。对于无方向信息的旧 `extreme` 映射为 `unknown` (`-1`) 且标为 `pose_valid=False`。
   - 提供公共解析函数 `get_yaw_bucket_id`, `get_pitch_bucket_id`, `normalize_yaw_bucket_name`, `normalize_pitch_bucket_name`。
   - 提供统一的 Sample Record 有效性判定 helper 函数 (`get_record_image_valid`, `get_record_pose_valid`, `get_record_quality_valid`, `get_record_yaw_bucket`, `get_record_pitch_bucket`)。

2. **重构各元数据模块以使用统一契约**:
   - **[pose.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/pose.py)**: `assign_yaw_bucket` 和 `assign_pitch_bucket` 严格返回 Canonical 桶名。
   - **[analyzer.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/analyzer.py)**: 在 summary 中预先初始化包含全量 7 个 Canonical 桶和 unknown 的完整统计字典。
   - **[loader.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/loader.py)**: 使用 `contracts.py` 的映射，`pose_valid[i]` 仅在 `p_info.get("valid", False)` 且 `yaw_bucket_ids[i] != UNKNOWN_BUCKET_ID` 时为 `True`。
   - **[schema.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/schema.py)** & **[report.py](file:///t:/deep-face-lab-tf2.x/samplelib/metadata/report.py)**: 同步引入 `contracts.py` 校验与解析。

3. **新增端到端（E2E）完整流程 Smoke 测试**:
   - **[test_batch2_metadata_sampling_e2e.py](file:///t:/deep-face-lab-tf2.x/tests/smoke/test_batch2_metadata_sampling_e2e.py)**: 涵盖 Ordinary / Packed 人脸数据集从 `Analyzer` -> `JSON Sidecar` -> `Loader` -> `PoseBalancedPolicy` -> `WeightedIndexHost` 完整流程及 Legacy Alias 兼容读取。

---

## 2. 规约与 Bucket ID 对照表

### Canonical Yaw Buckets
| ID | Canonical Name | 识别的前端角度范围 (Rad) | 旧 Legacy Alias 映射 |
|----|----------------|--------------------------|----------------------|
| 0 | `extreme_left` | yaw < -0.8 | - |
| 1 | `major_left` | -0.8 <= yaw < -0.4 | `left` |
| 2 | `minor_left` | -0.4 <= yaw < -0.15 | `slight_left` |
| 3 | `center` | -0.15 <= yaw <= 0.15 | `front`, `pitch_center_yaw_center` |
| 4 | `minor_right` | 0.15 < yaw <= 0.4 | `slight_right` |
| 5 | `major_right` | 0.4 < yaw <= 0.8 | `right` |
| 6 | `extreme_right` | yaw > 0.8 | - |
| -1 | `unknown` | 非有限角度 / 无法识别 | `extreme` (缺少方向信息) |

### Canonical Pitch Buckets
| ID | Canonical Name | 识别的前端角度范围 (Rad) | 旧 Legacy Alias 映射 |
|----|----------------|--------------------------|----------------------|
| 0 | `up` | pitch < -0.15 | - |
| 1 | `level` | -0.15 <= pitch <= 0.15 | `center` |
| 2 | `down` | pitch > 0.15 | - |
| -1 | `unknown` | 非有限角度 / 无法识别 | - |

---

## 3. 测试验证结果

执行全量 Smoke 单元测试：
```bash
python -m unittest discover -s tests/smoke -p "test_*.py"
```

**结果**:
- **测试用例总数**: 185
- **测试通过率**: 100% (185/185 PASS)
- **关键断言验证**:
  1. `test_loader_perfect_match`: 验证真实 `Analyzer` 输出能被 `Loader` 100% 识别，`pose_valid` 均为 `True`，`yaw_bucket_ids` 包含正确 ID（非 `-1`）。
  2. `test_e2e_ordinary_faceset_pipeline`: 验证端到端普通文件夹分析、加载、计算权重与 IndexHost 随机抽取。
  3. `test_e2e_packed_faceset_pipeline`: 验证打包 `faceset.pak` 端到端全流程。
  4. `test_e2e_legacy_alias_sidecar_reading`: 验证 legacy alias（如 `front`, `slight_left`）正常转换且无方向信息的 `extreme` 妥善降级为 unknown。

---

## 4. 结论与下一 Ticket 可依赖接口

Ticket 14 已完满解决，重新签发 **RESOLVED** 状态。

### 解锁的下一 Ticket:
- **Ticket 15** (options-json 与 SRC/DST 侧配置解析)
- **Ticket 16** (WeightedIndexHost Windows spawn 修复)
- **Ticket 17** (Analyzer Workers、强指纹与 Stale 检测)
- **Ticket 18** (Incremental Summary 修复)
