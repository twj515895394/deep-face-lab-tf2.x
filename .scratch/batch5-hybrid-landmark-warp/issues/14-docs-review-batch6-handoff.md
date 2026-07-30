# B5-14 用户/GUI Schema、独立Review、Batch 6输出契约与Handoff

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-13；阻塞Batch5签发和Batch6 Revalidation。
- 目标：收口代码、配置、视觉/性能证据，发布Batch6可依赖的Hybrid/Warp/Quality唯一接口。

## 必须完成

- 14票Summary、Review、P0/P1修复、SHA。
- 更新正式B5文档、docs索引、master plan、根handoff。
- 用户说明Template要求、power、fallback、不同姿态/表情风险、Interactive快捷键、排错。
- GUI未来字段表只映射核心默认值。
- 发布Batch6 consumer contract：Hybrid landmarks、warped predicted face/mask、coverage map、warp quality metrics/reason、face/frame identity、坐标空间和lifecycle。
- 自动/Windows/performance/visual状态分层。

## Batch6 Revalidation输入

最终triangle topology、Hybrid region weights、WarpResult/QualityResult、Merge插入顺序、RGB/mask mapping、多脸/worker/session行为、视觉artifact和性能瓶颈。Batch6必须据此更新Mask与Temporal票。

## Forbidden

不在B5实现Shape-aware Soft Mask/EMA/One Euro；不把视觉PROMISING写成生产PASS；不遗漏power0和fallback证据；不直接签发B6编码。

## 完成定义

P0/P1关闭、文档/代码/测试一致、真实状态准确、Batch6 consumer API唯一且有fixture；交付用户文档、GUI字段、Review、Handoff、最终SHA。
