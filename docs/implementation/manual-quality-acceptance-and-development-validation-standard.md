# Manual Quality Acceptance and Development Validation Standard

## 1. Purpose

本文档定义 DeepFaceLab TF2.x 增强开发阶段的验证标准。

定位：

- 代码正确性由开发流程和自动化检查保证。
- 最终换脸质量由人工基于固定素材进行评估。

不设计自动化模型评分系统作为第一阶段目标。

## 2. Validation Layers

### Layer A: Development Validation

由开发人员、Agent 或 CI 完成。

目标：确认功能稳定、接口正确。

检查内容：

- 项目可以正常启动。
- 配置文件可以正常加载。
- Feature Flag 开关正常。
- 原始 DFL 流程不受影响。
- 新模块关闭时行为与原版本一致。
- 新模块开启时不存在异常。
- 模型可以正常训练。
- Checkpoint 可以保存和恢复。
- Merge 流程可以正常执行。

## 3. Manual Quality Evaluation

最终视觉效果由人工判断。

重点观察：

### Identity

- src 五官保持程度。
- src 脸型迁移程度。
- 下颌、脸宽、颧骨等骨相是否改善。

### Expression

- dst 表情是否正常保留。
- 嘴型、眼睛动作是否自然。

### Geometry

- 是否存在脸部拉伸。
- 是否出现边缘错位。
- 是否出现形变跳动。

### Video Stability

- 连续帧是否稳定。
- Mask 是否闪烁。
- Shape Warp 是否抖动。

## 4. A/B Comparison Standard

所有优化需要与 baseline 对比：

Baseline:

- 原始 TF2.x 流程。

Experimental:

- 新增强模块。

保持：

- 相同素材。
- 相同训练条件。
- 相同 Merge 参数。

## 5. Suggested Test Cases

### Case 1: 正脸高清

验证身份和脸型迁移。

### Case 2: 大角度侧脸

验证几何稳定性。

### Case 3: 强表情

验证 expression 保留。

### Case 4: 遮挡场景

验证 mask 和 occlusion 处理。

### Case 5: 视频连续运动

验证 temporal stability。

## 6. Agent Responsibility Boundary

AI Agent 负责：

- 修改代码。
- 运行测试。
- 检查错误。
- 输出日志。
- 保证工程可运行。

AI Agent 不负责：

- 判断最终是否达到电影级视觉效果。
- 替代人工审美评价。
- 自动决定最佳参数。

## 7. Future Extension

未来如果项目进入大规模服务化阶段，可以增加：

- 自动化回归测试。
- 视觉质量指标。
- Identity Similarity 评估。
- Temporal Consistency 指标。

但第一阶段保持人工验收为主。