# DeepFaceLab TF2.x 配置与扩展架构设计

## 1. 文档目标

本文定义后续 DeepFaceLab TF2.x 增强能力的工程接入方式，目标是在不破坏原有训练、模型和合成流程的情况下，引入：

- Identity Geometry 优化
- Shape-aware Merge
- 高级训练策略
- 后续 UI/Linux 服务化能力

核心原则：

> 保持兼容，采用扩展，而不是重写。

---

## 2. Feature Flag 设计

所有增强功能默认关闭。

示例：

```yaml
features:
  enable_shape_aware_merge: false
  enable_identity_geometry_loss: false
  enable_shape_template: false
  enable_temporal_stabilization: false
```

旧用户保持原始 DFL 行为。

---

## 3. 配置分层

建议拆分：

```
config/

├── training.yaml
├── merge.yaml
└── runtime.yaml
```

### training.yaml

负责：

- loss 权重
- sampling 策略
- curriculum

### merge.yaml

负责：

- shape mode
- mask mode
- warp 参数
- temporal 参数

---

## 4. Shape-aware Merge 参数

建议：

```yaml
shape_merge:
  mode: off
  source_shape_power: 50
  mask_mode: hybrid
  temporal_smoothing: true
```

模式：

- off：传统 Merge
- source：强制 src geometry
- hybrid：src geometry + dst expression

---

## 5. 扩展模块架构

建议新增：

```
core/

├── shape/
│   ├── source_shape_template.py
│   ├── hybrid_landmark.py
│   └── shape_warp.py
│
├── merge/
│   └── shape_merge.py
│
└── temporal/
    └── stabilizer.py
```

保持原 merger 不被直接替换。

---

## 6. CLI 设计

未来支持：

```bash
--enable-shape-merge
--shape-power 50
--mask-mode hybrid
```

同时保留旧命令兼容。

---

## 7. UI 接入预留

未来 Web/UI 层只调用统一配置接口：

```
Frontend
   |
   v
Config API
   |
   v
DFL Runtime
```

避免 UI 直接修改底层代码。

---

## 8. Linux 服务化方向

未来架构：

```
Web UI
 |
API Server
 |
Job Queue
 |
DFL Worker
 |
GPU Runtime
```

训练、切脸、合成均作为任务执行。

---

## 9. 开发原则

1. 所有新功能必须可关闭。
2. 所有参数必须有默认值。
3. 新模块不能强依赖旧模型。
4. 保持旧 DFM 可加载。
5. 每个优化必须有实验验证。

---

## 10. 后续开发顺序

Phase 1:

完成配置和扩展框架。

Phase 2:

加入训练增强。

Phase 3:

加入 Shape Template。

Phase 4:

加入 Shape-aware Merge。

Phase 5:

UI 和 Linux 服务化。
