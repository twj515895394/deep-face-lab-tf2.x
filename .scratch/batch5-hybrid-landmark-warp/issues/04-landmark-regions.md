# B5-04 Landmark分区、Stable Identity与Dynamic Expression契约

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-01；阻塞B5-05/06/08。
- 目标：冻结Hybrid composition中哪些点/分量来自src稳定几何、哪些来自dst动态表达，避免整套src landmarks覆盖dst表情。

## 分区

- Stable高权重：jaw 0..16、chin中心、cheek外轮廓、face width相关控制点。
- Mixed：nose bridge/base、eye centers等稳定比例与pose相关点，使用明确blend。
- Dynamic：brows17..26、eyes36..47、mouth48..67，主要保留dst offset/开合。
- Anchor reference：内部固定点索引和对称pair；最终表在B5-01后冻结。

## 数据结构

`LandmarkRegionSpec`包含point indices、src_identity_weight、dst_expression_weight、pose_transform规则、confidence multiplier。权重范围[0,1]且每点composition规则唯一，不允许运行时任意字典覆盖。

## 规则

- stable不是静态屏幕坐标，仍随dst pose transform。
- dynamic不是完全忽略src，稳定中心/比例可作为弱参考，但不得压制开合。
- `source_shape_power=0`所有src identity权重归零。
- 68点以外/错误schema拒绝。

## Forbidden

不实现Hybrid算法；不引入语义分割/3DMM；不让用户逐点配置；不使用左右眼命名歧义；不把mouth/jaw混为一组。

## 测试

`test_batch5_landmark_regions.py`覆盖完整覆盖无重叠歧义、左右对称、动态点、zero power、权重范围、固定serialization和错误schema。

## 完成定义

每个点的职责和blend语义可审计，供B5-05/06/08唯一复用；Summary、Review、SHA完整。
