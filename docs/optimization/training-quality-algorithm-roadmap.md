# DFL TF2.x Training Quality Algorithm Roadmap

## 1. 文档定位

本文档用于规划 DeepFaceLab TF2.x 后续训练质量优化方向。

优化顺序遵循：

```
训练正确性
    ↓
训练性能
    ↓
训练质量
    ↓
高级算法实验
```

所有质量优化必须基于 benchmark 和可复现实验，不以单一 Loss 数值作为唯一判断。

---

# 2. 当前质量瓶颈分析

当前 SAEHD 质量主要受以下因素影响：

- faceset 数据质量
- 姿态覆盖不足
- 遮挡样本不足
- identity 保持能力
- 高频细节恢复能力
- mask 边界质量
- 时序稳定性

因此优化方向分为：

```
数据层
 ↓
采样层
 ↓
Loss层
 ↓
网络结构层
 ↓
时序增强层
```

---

# 3. 第一优先级：数据与采样优化

## 3.1 Faceset 智能分析

增加 faceset analyzer：

- 清晰度评分
- 模糊检测
- 重复帧检测
- 姿态分类
- 表情分类
- 遮挡评分
- 光照分类
- 人脸质量评分

目标：

减少低价值样本，提高有效训练比例。

---

## 3.2 难样本采样

设计 LossWeightedSampler：

根据历史训练结果动态调整采样概率。

关注：

- 大角度脸
- 遮挡脸
- 低光照脸
- 表情极端样本

风险：

过度采样可能导致分布偏移，因此需要采样比例上限。

---

# 4. Loss 优化路线

## 4.1 Identity Loss

目标：

增强源身份保持能力。

候选：

- ArcFace embedding loss
- Face recognition feature loss

验证：

- identity similarity
- 五官保持

---

## 4.2 Perceptual Loss

候选：

- LPIPS
- VGG feature loss
- DINO feature loss

作用：

提高视觉感知一致性。

风险：

可能降低像素级重建精度。

---

## 4.3 Frequency Loss

候选：

- FFT Loss
- Laplacian Pyramid Loss
- Focal Frequency Loss

目标：

改善：

- 毛发
- 皮肤纹理
- 高频细节

---

## 4.4 Geometry Loss

增加：

- Landmark Loss
- 3D face alignment loss
- Eye/Mouth region loss

目标：

减少：

- 眼睛漂移
- 嘴型错误
- 五官变形

---

# 5. 网络结构增强方向

## 5.1 Attention 模块

候选：

- CBAM
- SE Block
- ECA

作用：

增强关键区域关注。

重点区域：

- 眼睛
- 鼻子
- 嘴部

风险：

增加计算量，需要消融实验。

---

## 5.2 Decoder 改造

方向：

- 多尺度 decoder
- 高频细节分支
- mask/rgb decoder 解耦

目标：

提高融合自然度。

---

# 6. GAN 优化方向

当前 GAN 训练风险较高。

建议：

先保持关闭，单独实验：

- discriminator 稳定性
- gradient penalty
- feature matching

评价：

不能只看锐度，需要关注身份一致性。

---

# 7. 时序一致性方向

视频换脸核心问题：

单帧优秀 != 视频优秀。

后续方向：

- landmark temporal smoothing
- mask temporal smoothing
- optical flow consistency
- latent temporal constraint

目标：

减少：

- 闪烁
- 面部抖动
- 颜色跳变

---

# 8. 实验优先级

## P0

必须先完成：

- Faceset Analyzer
- 难样本采样
- Identity Loss 实验
- Landmark Loss 实验

## P1

- LPIPS
- Frequency Loss
- CBAM
- 多尺度 Decoder

## P2

- GAN 改造
- Temporal Model
- 大模型 Encoder

---

# 9. 验证标准

所有算法实验必须记录：

- 训练配置
- 数据集
- step 数
- Loss 曲线
- Preview 对比
- identity similarity
- 视频测试结果
- 性能变化

禁止仅根据训练 Loss 判断效果。

---

# 10. 后续开发顺序

```
Benchmark 完成
        ↓
Faceset 智能分析
        ↓
采样优化
        ↓
Loss实验
        ↓
网络结构实验
        ↓
时序优化
```

