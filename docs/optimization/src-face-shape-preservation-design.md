# src Face Shape Preservation Design

## 背景

DFL 长期存在一个典型问题：

训练后结果身份接近 source，但脸型仍明显保留 destination。

表现：

- 五官像 source
- 脸宽像 destination
- 下颌像 destination
- 轮廓像 destination

原因：脸型同时属于身份和几何属性，传统训练没有明确监督。

---

# 1. 优化目标

在不修改模型结构情况下，让训练过程学习：

```
source identity geometry
        >
 destination face geometry
```

同时保持：

- dst 表情
- dst 姿态
- dst 光照
- dst 视频运动

---

# 2. Face Shape 定义

脸型包含：

- 脸宽
- 下颌线
- 颧骨比例
- 额头比例
- 眼距
- 鼻脸比例
- 下巴长度

这些不是普通纹理信息。

---

# 3. Face Shape Loss

增加几何监督：

```
source landmark
        |
shape vector

swap landmark
        |
shape vector

compare
```

重点约束：

- jaw
- cheek
- face contour
- eye distance
- nose width

---

# 4. Shape 与 Expression 分离

不能直接约束全部 landmark。

应该拆分：

## Identity Geometry

来源：source

包括：

- 脸宽
- 下颌
- 颧骨
- 眼距

## Expression Geometry

来源：destination

包括：

- 嘴张开
- 眉毛变化
- 眼睛开合

目标：

```
source shape
+
destination expression
```

---

# 5. Source Identity Anchor

为 source faceset 建立 identity anchor。

选择：

- 正脸
- 高清
- 无表情
- 清晰光照

作为身份中心。

训练时：

swap shape 应靠近 anchor。

---

# 6. Region Shape Mask

使用 face parsing 提取：

- jaw
- cheek
- skin
- boundary

重点加强：

- 下巴
- 脸颊
- 外轮廓

---

# 7. src/dst 非对称策略

Source：

强化身份和几何稳定。

Destination：

强化运动属性。

避免 destination 几何信息过度主导。

---

# 8. Curriculum

阶段1：

强化 source identity + shape。

阶段2：

加入 dst pose/expression。

阶段3：

增强 texture 与 boundary。

---

# 9. 不建议当前修改

暂不引入：

- 新 backbone
- diffusion
- transformer
- 大规模重构

原因：

当前主要问题是监督目标不足，而不是模型容量不足。

---

# 10. 后续实验

建议建立消融实验：

A:
原始训练

B:
Identity Loss

C:
Shape Loss

D:
Identity + Shape

E:
Identity + Shape + Region

比较：

- 身份相似度
- 脸型迁移程度
- 表情保持
- 视频稳定性

---

# 结论

Face Shape Preservation 是 DFL 从普通换脸走向高保真身份迁移的重要方向。

在当前工程约束下，应优先通过训练监督增强，而不是立即修改模型结构。
