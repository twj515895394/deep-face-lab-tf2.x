"""Optimizer save/reload/next-step roundtrip audit helpers.

本模块为 Ticket 05 建立可比较基线：
1. 记录 AdaBelief / RMSprop / Lion 的 slot dtype；
2. 比较连续训练与保存恢复后下一步更新误差；
3. 在 macOS 缺 TensorFlow 时提供与源码公式对齐的 NumPy 轻量替代。

不在此修改 Lion 公式语义；当前 Lion 轨迹按仓库现有实现（只用 beta_1 更新 c）审计。
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np


def _load_precision_contract():
    """按文件加载，避免 core.leras 包初始化拉起 nn/colorama/tensorflow。"""
    import importlib.util
    import sys
    from pathlib import Path

    module_name = "batch1_precision_contract_runtime"
    if module_name in sys.modules:
        return sys.modules[module_name]
    path = Path(__file__).with_name("precision_contract.py")
    spec = importlib.util.spec_from_file_location(module_name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_pc = _load_precision_contract()
audit_precision_dtypes = _pc.audit_precision_dtypes
collect_optimizer_slot_dtype_snapshot = _pc.collect_optimizer_slot_dtype_snapshot
resolve_precision_contract = _pc.resolve_precision_contract

SUPPORTED_OPTIMIZERS = ("adabelief", "rmsprop", "lion")
DEFAULT_DTYPE = "float32"


def _as_float_array(value: Any, dtype: str = DEFAULT_DTYPE) -> np.ndarray:
    return np.asarray(value, dtype=np.dtype(dtype))


def _dtype_name(value: Any) -> str:
    if value is None:
        return DEFAULT_DTYPE
    if isinstance(value, str):
        return value
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    dtype = getattr(value, "dtype", None)
    if dtype is not None and dtype is not value:
        return _dtype_name(dtype)
    return str(np.dtype(value))


def _max_abs_error(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch for error: {a.shape} vs {b.shape}")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def _resolution_for_dtype(dtype_name: str) -> float:
    try:
        return float(np.finfo(np.dtype(dtype_name)).resolution)
    except (TypeError, ValueError):
        return 1.1920929e-07


class _NumpySlotBag:
    """Fake optimizer bag so precision_contract can observe slot dtypes."""

    def __init__(self, slots: Mapping[str, Any], iterations_dtype: str = "int64"):
        self.iterations = type("Iters", (), {"dtype": iterations_dtype})()
        for key, value in slots.items():
            setattr(self, key, value)

    def get_weights(self) -> List[Any]:
        values: List[Any] = [self.iterations]
        for name in ("ms_dict", "vs_dict", "c_dict", "accumulators_dict", "ms", "vs", "c", "accumulators"):
            bag = getattr(self, name, None)
            if isinstance(bag, Mapping):
                values.extend(bag.values())
            elif isinstance(bag, (list, tuple)):
                values.extend(bag)
        return values


def _lr_at_step(base_lr: float, step_after_update: int, lr_cos: int, dtype_name: str) -> float:
    lr = float(base_lr)
    if lr_cos:
        angle = float(step_after_update) * (2.0 * 3.1415926535 / float(lr_cos))
        lr *= (float(np.cos(np.asarray(angle, dtype=np.float64))) + 1.0) / 2.0
    return float(np.asarray(lr, dtype=np.dtype(dtype_name)))


def numpy_optimizer_step(
    name: str,
    weight: np.ndarray,
    grad: np.ndarray,
    state: MutableMapping[str, Any],
    *,
    lr: float,
    beta_1: float = 0.9,
    beta_2: float = 0.999,
    rho: float = 0.9,
    lr_cos: int = 0,
    dtype_name: str = DEFAULT_DTYPE,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Apply one optimizer step using formulas aligned to current source code."""
    opt = str(name).strip().lower()
    w = _as_float_array(weight, dtype_name)
    g = _as_float_array(grad, dtype_name)
    iters = int(state.get("iterations", 0)) + 1
    next_state: Dict[str, Any] = {"iterations": iters}

    if opt == "adabelief":
        ms = _as_float_array(state.get("ms", np.zeros_like(w)), dtype_name)
        vs = _as_float_array(state.get("vs", np.zeros_like(w)), dtype_name)
        m_t = beta_1 * ms + (1.0 - beta_1) * g
        v_t = beta_2 * vs + (1.0 - beta_2) * np.square(g - m_t)
        step_lr = _lr_at_step(lr, iters, lr_cos, dtype_name)
        resolution = _resolution_for_dtype(dtype_name)
        v_diff = -step_lr * m_t / (np.sqrt(v_t) + resolution)
        new_w = w + v_diff
        next_state.update({"ms": m_t.astype(w.dtype, copy=False), "vs": v_t.astype(w.dtype, copy=False)})
        return new_w.astype(w.dtype, copy=False), next_state

    if opt == "rmsprop":
        acc = _as_float_array(state.get("acc", np.zeros_like(w)), dtype_name)
        new_a = rho * acc + (1.0 - rho) * np.square(g)
        step_lr = _lr_at_step(lr, iters, lr_cos, dtype_name)
        resolution = _resolution_for_dtype(dtype_name)
        v_diff = -step_lr * g / (np.sqrt(new_a) + resolution)
        new_w = w + v_diff
        next_state["acc"] = new_a.astype(w.dtype, copy=False)
        return new_w.astype(w.dtype, copy=False), next_state

    if opt == "lion":
        # 保持与当前 Lion.py 一致：c 用 beta_1 更新，beta_2 未参与。
        # Ticket 06 才会修复公式；这里只建立可观测基线。
        c = _as_float_array(state.get("c", np.zeros_like(w)), dtype_name)
        c_t = beta_1 * c + (1.0 - beta_1) * g
        m_t = np.sign(c_t)
        step_lr = _lr_at_step(lr, iters, lr_cos, dtype_name)
        update = -step_lr * m_t
        new_w = w + update
        next_state["c"] = c_t.astype(w.dtype, copy=False)
        return new_w.astype(w.dtype, copy=False), next_state

    raise ValueError(f"unsupported optimizer: {name}")


def serialize_optimizer_state(name: str, weight: np.ndarray, state: Mapping[str, Any]) -> Dict[str, Any]:
    """Serialize weight + optimizer slots in a pickle-friendly dict."""
    opt = str(name).strip().lower()
    payload: Dict[str, Any] = {
        "optimizer": opt,
        "schema_version": 1,
        "weight": np.asarray(weight).copy(),
        "iterations": int(state.get("iterations", 0)),
        "weight_dtype": _dtype_name(weight),
        "slot_dtypes": {},
    }
    if opt == "adabelief":
        payload["ms"] = np.asarray(state["ms"]).copy()
        payload["vs"] = np.asarray(state["vs"]).copy()
        payload["slot_dtypes"] = {
            "ms": _dtype_name(payload["ms"]),
            "vs": _dtype_name(payload["vs"]),
            "iterations": "int64",
        }
    elif opt == "rmsprop":
        payload["acc"] = np.asarray(state["acc"]).copy()
        payload["slot_dtypes"] = {
            "acc": _dtype_name(payload["acc"]),
            "iterations": "int64",
        }
    elif opt == "lion":
        payload["c"] = np.asarray(state["c"]).copy()
        payload["slot_dtypes"] = {
            "c": _dtype_name(payload["c"]),
            "iterations": "int64",
        }
    else:
        raise ValueError(f"unsupported optimizer: {name}")
    return payload


def deserialize_optimizer_state(payload: Mapping[str, Any]) -> Tuple[np.ndarray, Dict[str, Any]]:
    opt = str(payload.get("optimizer", "")).strip().lower()
    weight = np.asarray(payload["weight"]).copy()
    state: Dict[str, Any] = {"iterations": int(payload.get("iterations", 0))}
    if opt == "adabelief":
        state["ms"] = np.asarray(payload["ms"]).copy()
        state["vs"] = np.asarray(payload["vs"]).copy()
    elif opt == "rmsprop":
        state["acc"] = np.asarray(payload["acc"]).copy()
    elif opt == "lion":
        state["c"] = np.asarray(payload["c"]).copy()
    else:
        raise ValueError(f"unsupported optimizer payload: {opt}")
    return weight, state


def _slot_bag_from_state(name: str, state: Mapping[str, Any], dtype_name: str) -> _NumpySlotBag:
    opt = str(name).strip().lower()
    holder = type("DTypeHolder", (), {"dtype": dtype_name})
    if opt == "adabelief":
        slots = {
            "ms_dict": {"w": holder()},
            "vs_dict": {"w": holder()},
            "ms": [holder()],
            "vs": [holder()],
        }
    elif opt == "rmsprop":
        slots = {
            "accumulators_dict": {"w": holder()},
            "accumulators": [holder()],
        }
    elif opt == "lion":
        slots = {
            "c_dict": {"w": holder()},
            "c": [holder()],
        }
    else:
        raise ValueError(f"unsupported optimizer: {name}")
    return _NumpySlotBag(slots)


def run_numpy_optimizer_roundtrip(
    name: str,
    *,
    weight: Optional[Sequence[float]] = None,
    grads: Optional[Sequence[Sequence[float]]] = None,
    lr: float = 1e-3,
    beta_1: float = 0.9,
    beta_2: float = 0.999,
    rho: float = 0.9,
    lr_cos: int = 0,
    warmup_steps: int = 2,
    dtype_name: str = DEFAULT_DTYPE,
    requested_precision: str = "fp32",
) -> Dict[str, Any]:
    """Compare continuous train vs save/reload then one more update.

    流程：
    1. 固定小向量权重与梯度序列；
    2. 连续训练 warmup_steps + 1；
    3. 在 warmup_steps 处序列化并反序列化；
    4. 恢复后再走 1 步，比较 weight/slot/update 误差。
    """
    opt = str(name).strip().lower()
    if opt not in SUPPORTED_OPTIMIZERS:
        raise ValueError(f"unsupported optimizer: {name}")

    if weight is None:
        weight_arr = _as_float_array([0.25, -0.50, 0.75, 0.125], dtype_name)
    else:
        weight_arr = _as_float_array(weight, dtype_name)

    if grads is None:
        grad_list = [
            _as_float_array([0.10, -0.20, 0.05, 0.00], dtype_name),
            _as_float_array([-0.05, 0.15, -0.25, 0.10], dtype_name),
            _as_float_array([0.20, 0.05, -0.10, -0.15], dtype_name),
        ]
    else:
        grad_list = [_as_float_array(g, dtype_name) for g in grads]

    if len(grad_list) < warmup_steps + 1:
        raise ValueError("grads must cover warmup_steps + 1 updates")

    common_kwargs = {
        "lr": lr,
        "beta_1": beta_1,
        "beta_2": beta_2,
        "rho": rho,
        "lr_cos": lr_cos,
        "dtype_name": dtype_name,
    }

    cont_w = weight_arr.copy()
    cont_state: Dict[str, Any] = {"iterations": 0}
    if opt == "adabelief":
        cont_state.update({"ms": np.zeros_like(cont_w), "vs": np.zeros_like(cont_w)})
    elif opt == "rmsprop":
        cont_state["acc"] = np.zeros_like(cont_w)
    else:
        cont_state["c"] = np.zeros_like(cont_w)

    for step_idx in range(warmup_steps + 1):
        cont_w, cont_state = numpy_optimizer_step(opt, cont_w, grad_list[step_idx], cont_state, **common_kwargs)

    rt_w = weight_arr.copy()
    rt_state: Dict[str, Any] = {"iterations": 0}
    if opt == "adabelief":
        rt_state.update({"ms": np.zeros_like(rt_w), "vs": np.zeros_like(rt_w)})
    elif opt == "rmsprop":
        rt_state["acc"] = np.zeros_like(rt_w)
    else:
        rt_state["c"] = np.zeros_like(rt_w)

    for step_idx in range(warmup_steps):
        rt_w, rt_state = numpy_optimizer_step(opt, rt_w, grad_list[step_idx], rt_state, **common_kwargs)

    payload = serialize_optimizer_state(opt, rt_w, rt_state)
    loaded_w, loaded_state = deserialize_optimizer_state(payload)

    reload_weight_error = _max_abs_error(rt_w, loaded_w)
    reload_slot_errors = {"iterations": float(abs(int(rt_state["iterations"]) - int(loaded_state["iterations"])))}
    for key in rt_state:
        if key == "iterations":
            continue
        reload_slot_errors[key] = _max_abs_error(rt_state[key], loaded_state[key])
    max_abs_reload_error = max([reload_weight_error, *reload_slot_errors.values()]) if reload_slot_errors else reload_weight_error

    resume_w, resume_state = numpy_optimizer_step(
        opt,
        loaded_w,
        grad_list[warmup_steps],
        loaded_state,
        **common_kwargs,
    )

    update_errors = {
        "weight": _max_abs_error(cont_w, resume_w),
        "iterations": float(abs(int(cont_state["iterations"]) - int(resume_state["iterations"]))),
    }
    for key in cont_state:
        if key == "iterations":
            continue
        update_errors[key] = _max_abs_error(cont_state[key], resume_state[key])
    max_abs_update_error = max(update_errors.values()) if update_errors else 0.0

    slot_bag = _slot_bag_from_state(opt, resume_state, dtype_name)
    slot_snapshot = collect_optimizer_slot_dtype_snapshot(slot_bag)
    contract = resolve_precision_contract(
        requested_precision,
        runtime_capabilities={
            "tensorflow_available": False,
            "float16_dtype_available": False,
            "bfloat16_dtype_available": False,
            "cuda_gpu_available": False,
        },
    )
    audit = audit_precision_dtypes(
        contract,
        weights=[type("W", (), {"dtype": dtype_name})()],
        gradients=[type("G", (), {"dtype": dtype_name})()],
        optimizer=slot_bag,
        save_file_dtype=dtype_name if dtype_name == "float32" else "float32",
        load_variable_dtype=dtype_name,
        max_abs_reload_error=max_abs_reload_error,
    )

    expected_slots = {
        "adabelief": ["ms_dict", "vs_dict"],
        "rmsprop": ["accumulators_dict"],
        "lion": ["c_dict"],
    }[opt]

    return {
        "optimizer": opt,
        "mode": "numpy_lightweight",
        "tensorflow_available": False,
        "dtype": dtype_name,
        "warmup_steps": warmup_steps,
        "optimizer_slot_dtypes": {
            key: slot_snapshot.get(key, [])
            for key in expected_slots + ["iterations", "get_weights"]
            if key in slot_snapshot or key in expected_slots
        },
        "slot_snapshot": slot_snapshot,
        "serialized_slot_dtypes": payload.get("slot_dtypes", {}),
        "max_abs_reload_error": max_abs_reload_error,
        "max_abs_update_error": max_abs_update_error,
        "reload_errors": {
            "weight": reload_weight_error,
            **reload_slot_errors,
        },
        "update_errors": update_errors,
        "continuous_final_weight": cont_w.copy(),
        "resumed_final_weight": resume_w.copy(),
        "continuous_final_state": {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in cont_state.items()},
        "resumed_final_state": {k: (v.copy() if isinstance(v, np.ndarray) else v) for k, v in resume_state.items()},
        "precision_audit": audit,
        "lion_formula_note": (
            "current_source_uses_beta1_only_for_c; beta2_not_applied_in_ticket_05"
            if opt == "lion"
            else None
        ),
        "windows_gpu_validation_required": [
            "Real TensorFlow session save/load through nn.Saveable",
            "GPU optimizer slot roundtrip on AdaBelief/RMSprop/Lion",
            "SAEHD model-level save/resume after Ticket 06/07",
        ],
    }


def run_all_numpy_optimizer_roundtrips(
    *,
    dtype_name: str = DEFAULT_DTYPE,
    warmup_steps: int = 2,
) -> Dict[str, Any]:
    reports = {
        name: run_numpy_optimizer_roundtrip(
            name,
            dtype_name=dtype_name,
            warmup_steps=warmup_steps,
        )
        for name in SUPPORTED_OPTIMIZERS
    }
    return {
        "mode": "numpy_lightweight",
        "optimizers": list(SUPPORTED_OPTIMIZERS),
        "reports": reports,
        "max_abs_reload_error": max(item["max_abs_reload_error"] for item in reports.values()),
        "max_abs_update_error": max(item["max_abs_update_error"] for item in reports.values()),
    }
