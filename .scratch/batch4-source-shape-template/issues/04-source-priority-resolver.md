# B4-04 Template来源优先级、显式Override与冲突Resolver

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-01；阻塞B4-10。
- 目标：在不读取/生成Template内容的情况下，冻结候选来源和冲突决策；执行Agent不得自行挑“最新”。

## 候选来源草案

```text
1. 用户显式template_path
2. 已绑定当前模型的training-derived Template
3. 用户显式offline output
4. 当前src faceset默认offline Template
5. none
```

最终优先级在B4-01后冻结。显式路径存在但invalid时不得继续寻找其他候选；必须返回该显式失败。

## API

`resolve_template_source(candidates, policy) -> TemplateSourceDecision`，输出`requested/source/path/conflict/reason/alternatives`，不加载JSON。

## 冲突规则

- 多个同优先级候选必须`conflict=true`并要求用户选择，禁止按mtime/文件大小排序。
- model-bound与faceset-bound来源identity不一致不得自动比较confidence。
- 自动发现只允许固定目录和固定命名模式，不递归扫描。
- 相对路径相对明确root解析，不使用cwd。

## Forbidden

- 不实现writer/loader。
- 不弹交互窗口；本票只返回结构化决策。
- 不通过confidence覆盖显式用户选择。
- 不从网络、环境变量或用户主目录隐式发现。

## 测试

`test_batch4_template_source_resolver.py`覆盖每种单一来源、显式invalid、多候选冲突、路径Unicode、相对root、同文件去重、symlink/大小写平台行为和稳定reason。

## 完成定义

所有来源、优先级、冲突与fallback均由纯函数和测试决定；Summary、Review、SHA完整。
