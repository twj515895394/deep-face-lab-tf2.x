# B4-01 Batch 3产物复核、Geometry Bridge基线、坐标契约与Fixtures

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B3`；P0；阻塞B4-02/03/04。
- 目标：Batch 3真实完成后重新读取最终代码、Schema、A/B和保存目录，冻结B4施工基线。本票不实现`.srcshape`。

## 必读与代码锚点

- Batch 3最终Summary/Reviews/ShapeAnchorV1、ratio顺序、SDF定义。
- `models/ModelBase.py::get_model_name/get_model_root_path/get_strpath_storage_for_file`
- `models/Model_SAEHD/Model.py::get_MergerConfig/predictor_func`
- `merger/MergeMasked.py`、`MergerConfig.py`、`InteractiveMergerSubprocessor.py`
- Batch 2 identity/fingerprint/atomic-write helpers。

## In Scope

- 记录前置Commit和实际文件/函数/数据shape。
- 冻结canonical坐标、landmark schema、ratio names/order、float32/finite规则。
- 冻结模型名与saved_models_path的真实命名行为。
- 建立ordinary/packed/Unicode、多identity、旧模型fixtures。
- 对本草案所有假设输出`CONFIRMED/CHANGED/REMOVED/NEW`差异表。

## Forbidden

- 不得基于当前草案跳过真实审计。
- 不得修改Batch 3历史事实或将GPU未执行写成PASS。
- 不得开始writer/loader/Merge代码。
- 不得让后续弱模型自行解决差异。

## 测试/证据

新建`tests/smoke/test_batch4_contracts.py`，验证坐标/ratio/schema fixtures、模型命名、路径Unicode和Batch3样例roundtrip。运行完整`test_batch*.py`基线并记录测试数、OS、Python、SHA；GPU项保持事实状态。

## 完成定义

差异表、冻结契约、fixtures、DAG修订和独立Review完成；所有受影响Ticket同步后，才可签发B4-02/03/04。
