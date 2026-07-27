# 12 — 完成兼容矩阵、用户文档、状态收口与下一批次 handoff

Status: open
Type: AFK
Blocked by: `11-batch2-test-matrix-and-windows-acceptance.md`

**构建内容：** 基于实际实现与 Windows FP32 验收结果，完成 Batch 2 的兼容矩阵、Analyzer/训练使用教程、限制说明、状态索引、handoff 和后续 Batch 3 入口；确保文档只描述已验证事实，不把延期能力写成已实现。

## Agent 开工前必读

1. `.scratch/batch2-training-data-and-sampling/AGENT_IMPLEMENTATION_GUIDE.md`
2. Ticket 01-11 所有 summary
3. `reports/windows-gpu-acceptance.md`
4. 当前实际代码中的 CLI `--help`、SamplingConfig 默认值和日志文本
5. `docs/README.md`
6. `docs/implementation/enhanced-dfl-master-implementation-plan.md`
7. `.handoff/current.md` 和最近 handoff
8. Batch 1 最终文档/交接的状态写法

本 Ticket 不负责凭设计补齐代码。任何未验证功能必须写成 pending、blocked 或 deferred。

## 当前事实核对清单

写文档前逐项从代码/报告确认：

- Analyzer 命令名称和全部参数；
- 默认 Metadata/Report 路径；
- Schema version 和 analyzer version；
- 四种 sampling mode 的实际名称；
- `training.metadata_sampling` master flag；
- 默认 pose/quality/uniform/min/max 参数；
- requested/effective/fallback 日志实际格式；
- ordinary/person/packed 实际支持状态；
- Windows W1-W9 哪些 PASS/FAIL/PENDING；
- 性能数据；
- save/exit/resume 结果；
- 已知限制和未解决问题。

若代码默认值与设计文档不同，以最终审核通过的代码和 Ticket 11 记录为事实，并同步修正文档冲突。

## 目标

- 用户能够独立生成 Metadata、选择模式、查看报告、排查 fallback。
- 开发者能知道稳定接口、默认行为和后续可依赖边界。
- Batch 2 状态与真实验证一致。
- 动态 Loss sampler、脸型训练、Lion、低精度继续明确延期。
- 下一 Agent 可以只读 current handoff、spec 和用户文档继续工作。

## 建议施工顺序

### Step 1：先生成实现事实表

在 summary 草稿中建立：

| 项目 | 设计值 | 代码值 | Windows 验证 | 最终文档值 |
|---|---|---|---|---|
| CLI | | | | |
| metadata path | | | | |
| sampling modes | | | | |
| defaults | | | | |
| fallback | | | | |

先消除冲突，再写用户教程。

### Step 2：完成兼容矩阵

每行至少包含：

```text
场景
输入/配置
requested mode
effective mode
预期行为
实际验证平台
状态
证据链接
```

不要只写“兼容/不兼容”。

### Step 3：编写用户文档

推荐结构：

```text
1. 功能解决什么问题
2. 前置要求
3. 分析 ordinary faceset
4. 分析 Packed Faceset
5. 增量更新
6. 报告字段解读
7. 四种采样模式
8. SAEHD 启用方法
9. requested/effective/fallback 日志
10. 保存恢复
11. 故障排查
12. 已知限制与延期功能
```

命令必须从目标平台复制验证，不要凭记忆手写。

### Step 4：更新开发文档和总路线

只更新状态和稳定接口，不重写历史设计。总实施计划 Batch 2 状态必须依据 Ticket 11：

- Windows 全部通过：done；
- 仅轻量验证：done-macos-lightweight-pending-windows；
- 存在阻断：blocked / in-progress。

### Step 5：生成 handoff

handoff 必须列出：

- 最终 commit/branch；
- 新增/修改文件；
- 稳定公共 API；
- 测试命令与状态；
- Windows 环境和 W1-W9 结果；
- 性能数据；
- 已知限制；
- 下一步只进入 Batch 3 前置设计；
- 明确不要顺手开发动态 sampler。

### Step 6：交叉链接检查

检查所有链接存在：

```text
current handoff
→ final handoff
→ spec
→ detailed design
→ issues/reports
→ usage doc
→ master plan
```

## 兼容矩阵

至少覆盖：

- [ ] 旧模型，无 enhancements。
- [ ] 新模型，全部增强关闭。
- [ ] uniform_yaw False / True。
- [ ] Metadata Sampling master flag False。
- [ ] legacy_random / legacy_uniform_yaw。
- [ ] pose_balanced / quality_pose_balanced。
- [ ] Metadata missing / invalid / unsupported。
- [ ] partial match above/below threshold。
- [ ] src/dst 单侧 fallback。
- [ ] ordinary / Packed / person faceset。
- [ ] debug / single worker / multi worker。
- [ ] eyes_mouth False / True。
- [ ] FP32 + AdaBelief save/resume。
- [ ] Merge / DFM 不受影响。

## 用户文档

建议新增或更新：

- [ ] `docs/usage/faceset-metadata-and-sampling.md`。
- [ ] Analyzer CLI 参数和可复制示例。
- [ ] Metadata 文件位置、备份和增量更新。
- [ ] 四种 sampling mode 的区别。
- [ ] 默认参数和保守调节建议。
- [ ] 日志 requested/effective/fallback 解读。
- [ ] ordinary / Packed 使用方式。
- [ ] 如何检查报告中的低质量和姿态样本。
- [ ] 明确程序不自动删除图片。
- [ ] Metadata 损坏或删除后的恢复方式。
- [ ] 明确 quality score 不是最终换脸质量评分。
- [ ] 明确 sampler draw state 不保存，但模型/optimizer save-resume 不受影响。

## 用户文档必须包含的故障排查表

| 日志/现象 | 含义 | 用户动作 |
|---|---|---|
| metadata missing | sidecar 不存在 | 运行 Analyzer 或使用 legacy |
| invalid_file | JSON 损坏 | 恢复 backup/重新分析 |
| unsupported_schema | 版本过高 | 使用兼容版本或 legacy |
| partial_match | faceset 有变化 | 增量分析并检查匹配率 |
| effective legacy_* | 智能模式回退 | 查看 fallback reason |
| worker/TF error | 核心错误 | 不应被当成 Metadata fallback |

实际 reason 名称按代码替换。

## 开发文档

- [ ] 更新 `docs/README.md`。
- [ ] 更新总实施计划 Batch 2 状态。
- [ ] 记录 Schema v1、Sampling Policy 和 WeightedIndexHost 稳定接口。
- [ ] 记录 Windows 验收环境和结果链接。
- [ ] 记录性能基线。
- [ ] 记录已知限制和后续 schema 扩展规则。
- [ ] 更新正式 Batch 2 详细设计的“当前实现状态”，不覆盖历史目标说明。

## Handoff

- [ ] 新建带时间戳 handoff。
- [ ] 更新 `.handoff/current.md` 指向最新交接。
- [ ] 列出实际 commit、文件、函数、测试命令和结果。
- [ ] 标记 macOS/CPU 与 Windows GPU 各自完成范围。
- [ ] 列出未完成风险。
- [ ] 下一步明确进入 Batch 3 Loss Hook 前置设计，而不是顺手开发动态 sampler。
- [ ] 历史 handoff 不删除。

## 状态规则

只有 Ticket 11 Windows 验收通过后，spec 才能从：

```text
ready-for-implementation
```

更新为：

```text
done
```

若只有 CPU/macOS 轻量验证：

```text
done-macos-lightweight-pending-windows
```

若存在阻断：

```text
in-progress-blocked
```

不得写成完整完成。

## 明确延期

文档必须明确：

- [ ] Dynamic Loss-aware Sampling：deferred / future experimental。
- [ ] Identity Geometry / 脸型 Loss：Batch 4。
- [ ] Source Shape Template：Batch 5。
- [ ] Shape-aware Merge：Batch 6。
- [ ] Lion 后续开发：paused。
- [ ] FP16/BF16 正式验收：paused / experimental。

## 最小验证命令

```bash
python main.py faceset-analyze --help
python main.py train --help
python -m unittest discover -s tests/smoke -p "test_batch2_*.py"
```

文档中的每条命令必须在目标环境执行或明确标记未执行。还应运行仓库 Markdown 链接检查工具；若没有工具，至少人工检查本 Ticket 新增链接。

## 禁止捷径与常见错误

- 不允许把设计默认值复制到用户文档而不核对代码。
- 不允许把 Ticket 11 FAIL/PENDING 写成 PASS。
- 不允许将“训练可以启动”写成“保存恢复已通过”。
- 不允许把普通 faceset 验证推断为 Packed 已支持。
- 不允许把 quality score 描述为自动删除或最终质量评分。
- 不允许写动态 Loss sampler、脸型训练或低精度已实现。
- 不允许更新 current handoff 却不创建新的时间戳 handoff。
- 不允许删除历史 handoff 或 `.scratch` reports。
- 不允许在文档 Ticket 补做大段运行时代码并绕过前置验收。

## 验收标准

- [ ] 用户按照文档可以完成 Analyzer + 训练闭环。
- [ ] 文档中的命令在目标平台验证或明确标记状态。
- [ ] 所有默认值与代码一致。
- [ ] 所有完成状态有测试/报告依据。
- [ ] 延期功能未被误写为 Batch 2 已完成。
- [ ] `.scratch` issues、reports、正式设计和 handoff 互相链接。
- [ ] 下一 Agent 能从 `.handoff/current.md` 和 spec 继续。
- [ ] 兼容矩阵每行有证据来源。

## 回退

文档提交不改变运行时；历史 handoff 不删除。若发现文档事实错误，应修正文档并保留更正记录，而不是篡改测试报告。

## 完成总结报告

- [ ] 生成 `.scratch/batch2-training-data-and-sampling/reports/12-compatibility-docs-and-handoff-summary.md`。
- [ ] 汇总最终产品能力、Windows 验证、性能、限制和下一步。
- [ ] 附实现事实表、兼容矩阵路径和最终 handoff 路径。
- [ ] 明确 spec 最终状态变更依据。

## Comments

- 2026-07-27：由 Batch 2 详细设计创建；本 ticket 负责批次收口，不负责补做未完成代码。
- 2026-07-27：补充弱模型事实表、文档施工顺序、证据化兼容矩阵、故障排查和状态禁区。