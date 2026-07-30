# B3-15 用户/GUI Schema、Summary、独立 Review 与 Handoff 收口

## 1. 基本信息

- Ticket ID：`B3-15`
- 状态：`BLOCKED-BY-B3-14`
- 优先级：P0
- 前置 Ticket：B3-14
- 阻塞 Ticket：Batch 3批次签发、Batch 4冻结 Review
- 目标分支：`codex/batch2-ticket19-loss-window`

## 2. 背景与问题

Batch 3 只有在代码、测试、配置、用户说明、Review和事实状态一致时才能收口。后续 Batch 4–6 已可提前拆成滚动设计草案，但 Batch 4 在 Batch 3完成后仍必须重新审计真实接口，不得直接按旧草案编码。

## 3. Scope

### In Scope

- 完成配置/options-json/用户使用说明。
- 输出逐 Ticket Summary和独立 Review。
- 核对 Master Matrix、GPU/A-B状态和未执行项。
- 更新正式总设计、docs索引、根 handoff。
- 明确 Batch 4 revalidation输入和第一个可执行 Ticket。
- 固化弱模型执行提示模板。

### Out of Scope

- 不实现完整 GUI页面。
- 不改 Batch 4–6代码。
- 不伪造 GPU或视觉结果。
- 不把滚动设计草案标成 READY-FOR-CODE。

### Forbidden Changes

- 禁止用“效果更好”代替证据。
- 禁止遗漏 Commit SHA、测试命令、失败/未执行项。
- 禁止历史 Batch 2 GPU状态改写为 PASS。
- 禁止在 B3 Review未完成时签发 B4编码。
- 禁止让弱模型自行决定未冻结接口。

## 4. 必须更新的正式文档

- `docs/development/batch3-identity-geometry-tasks.md`
- Batch 3 options-json/GUI未来接入说明
- `docs/README.md`
- `docs/implementation/enhanced-dfl-master-implementation-plan.md` 当前状态
- `.handoff/current.md`
- `.scratch/batch3-identity-geometry/handoff/current-design-status.md`

## 5. 用户配置说明

必须说明：

- 所有能力默认关闭。
- 唯一 Gate：`training.enabled && training.loss_hooks && training.identity_geometry`。
- `geometry` section只含参数，无 `geometry.enabled`。
- Anchor如何离线生成、路径如何解析、失配如何回退。
- ratio/contour权重、warmup/ramp语义。
- requested/effective/reason如何看日志。
- Geometry只训练 src stable mask geometry，不直接保证最终 Merge视频脸型。
- Batch 4–6仍负责 Template、Warp、Mask、Temporal。

GUI文档只定义字段、范围、默认值和传递方式；默认值仍由核心配置唯一提供。

## 6. 每 Ticket Summary模板

```text
Ticket ID / 标题 / 状态
Commit SHA(s)
变更文件
实现契约
测试命令与结果
关闭时零影响证据
兼容证据
Review findings与修复
未执行项目
已知风险
后续依赖
```

不得省略未执行和风险。

## 7. 独立 Review门

Review必须检查：

1. 是否仍有直接预测 landmark的伪可微设计。
2. 是否存在重复 Gate或默认值来源。
3. 是否修改网络、checkpoint、optimizer、Merge。
4. 是否 Geometry只进入 src-src mask路径。
5. 是否 aligned landmarks与target transform一致。
6. 是否 disabled不构图/不扩展generator/loss history。
7. 是否错误/Fallback边界符合 B3-05。
8. 是否保存恢复和 Loss Window正确。
9. 是否文档、代码、测试、日志字段一致。
10. 是否把 Batch 4–7功能提前混入。

Finding等级：`P0 BLOCKER / P1 REQUIRED / P2 FOLLOW-UP / NOTE`。P0/P1全部关闭后才可批次签发。

## 8. Batch 4 Revalidation输入

Batch 3完成后，Batch 4 Review必须读取：

- 最终 ShapeAnchorV1 Schema和生成器。
- 最终 ratio names/order。
- Anchor confidence/fingerprint语义。
- Geometry A/B结果和已知局限。
- 模型命名/保存目录实际行为。
- 任何 Batch 3接口偏差。

然后更新 Batch 4 `.srcshape` Schema和issue DAG。滚动草案不得跳过该步骤。

## 9. 实施步骤

1. 汇总所有 Ticket Summary/SHA。
2. 执行完整自动测试并记录事实。
3. 收集 GPU/A-B状态；未执行保持明确标签。
4. 执行独立代码+文档 Review。
5. 修复所有 P0/P1并复审。
6. 更新正式文档和索引。
7. 更新 handoff：Batch 3状态、下一 Frontier、Batch 4 revalidation。
8. 仅在证据满足时标记 Batch 3相应 gate；分别写 Code/Automated/GPU/Visual状态。

## 10. 测试/验收命令

```bash
python -m unittest discover -s tests/smoke -p "test_batch*.py" -q
```

另附 B3-14规定的 GPU/A-B命令和环境记录。文档链接检查、配置示例 roundtrip也必须执行。

## 11. 完成定义

- 15票均有 Summary、Review、SHA。
- P0/P1 findings全部关闭。
- 自动测试和环境测试状态分层准确。
- 正式文档、索引和 handoff同步。
- 用户可按文档启用/关闭/排错。
- Batch 4仍为需 revalidation的设计草案，未越权签发编码。

## 12. Review检查表

- 是否状态夸大？
- 是否遗漏未执行项目？
- 是否配置字段/默认值不一致？
- 是否历史事实被重写？
- 是否 Batch 4草案被误标 READY？
- 是否第一个后续 Ticket和前置条件明确？

## 13. 交付物

- 用户/GUI Schema说明
- 所有 Summary/Review
- 最终 Test/GPU/A-B记录
- docs/index/master plan/handoff更新
- Batch 4 revalidation清单
- 最终 Commit SHA
