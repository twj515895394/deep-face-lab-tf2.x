# B4-03 Model/SRC Identity、Faceset Fingerprint与Provenance绑定

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；前置B4-01；阻塞B4-05/06/08/11。
- 目标：防止Template被错误模型、错误src faceset或错误identity静默使用。

## In Scope

- 复用Batch2 `build_sample_key/build_sample_id`与最终faceset fingerprint。
- 定义`model_identity`：模型类、逻辑模型名、架构/face_type/resolution等只读兼容信息；不得用机器绝对路径。
- 定义`source_identity`：role=src、可选person_name/namespace。
- 定义provenance来源：offline_faceset、batch3_anchor、training_export、user_provided。
- 定义match结果：trusted_match、model_mismatch、source_mismatch、fingerprint_stale、unknown_legacy。

## 失败语义

- 明确mismatch时Shape能力关闭；传统Merge继续。
- `unknown_legacy`不得自动视为trusted；是否允许实验性使用必须显式配置并在B4-11审计。
- 不因mtime变化单独判identity改变；以冻结fingerprint策略为准。

## 目标代码

`core/enhancements/shape_template/identity.py`，输出immutable `TemplateIdentityCheckResult`，含`valid/trusted/reason/warnings`。

## Forbidden

- 禁止仅按文件名/目录名信任。
- 禁止依赖路径大小写偶然行为。
- 禁止把DST identity绑定进Source Template。
- 禁止记录用户原图绝对路径。

## 测试

`test_batch4_srcshape_identity.py`覆盖ordinary/packed、Windows/Linux路径、Unicode、模型重命名、复制模型目录、faceset新增/删除/替换、person混合、legacy缺字段与稳定reason code。

## 完成定义

身份/fingerprint/provenance规则有矩阵和测试；不修改Batch2身份实现；Summary、Review、SHA完整。
