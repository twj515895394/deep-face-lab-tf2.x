# B5-03 `.srcshape` Loader接入Merger Context与进程边界

- 状态：`DESIGN-DRAFT-REVALIDATE-AFTER-B4`；P0；前置B5-01；阻塞B5-05/07/11。
- 目标：在Merger启动阶段一次性发现/加载/校验Template，并把compact immutable context安全传给worker；不做Hybrid/Warp。

## 接入位置

B5-01后冻结宿主入口。原则：主进程在创建`InteractiveMergerSubprocessor`前解析Template；`client_dict`只传compact arrays/identity/confidence/version，不传loader、文件句柄、完整JSON或路径扫描逻辑。每frame不得重复读盘。

## Runtime对象

`ShapeTemplateContext`至少含canonical_landmarks float32[68,2]、ratio map、confidence、model/source/fingerprint checks、template hash、effective/reason。arrays只读、spawn可pickle、大小受限。

## 状态

power=0或Gate关：不发现/加载。缺失/可选invalid：effective=false、传统Merge继续。显式invalid/strict/I/O按B4最终矩阵失败。多worker收到相同hash/context。

## Forbidden

不在`MergeMaskedFace`每帧加载；不传绝对用户路径到worker日志；不修改predictor outputs；不因Template存在自动启用；不热重载。

## 测试

`test_batch5_template_merger_context.py`覆盖Gate关零调用、startup一次、spawn pickle、multiworker hash、invalid fallback、显式fatal、immutable、Unicode、context size和worker异常传播。

## 完成定义

Merger Context生命周期、进程边界和fallback有测试；不改变像素输出；Summary、Review、SHA完整。
