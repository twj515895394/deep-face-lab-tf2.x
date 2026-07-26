"""Batch 1 training save/resume smoke helpers.

本模块只覆盖 macOS 可执行的最小保存恢复语义：主权重、optimizer state、
销毁/重建后的下一步轨迹，以及旧配置缺失时的安全默认。真实 SAEHD / GPU
session 保存恢复仍由 Windows 验证清单补证。
"""

from __future__ import annotations

import importlib.util
import pickle
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Dict, Mapping, MutableMapping, Optional, Sequence, Tuple

import numpy as np


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CHECKPOINT_FILENAME = "training_state.pkl"
WINDOWS_GPU_SAVE_RESUME_VALIDATION = (
    "Create a minimal SAEHD workspace with 8-16 aligned src/dst faces.",
    "Initialize SAEHD fp32 at resolution 64 or 96 with batch size 2.",
    "Run 2-5 training iterations and confirm finite losses.",
    "Save all model files and verify they are non-empty.",
    "Terminate the process or reset the TensorFlow session.",
    "Reload the same model directory without new enhancement config fields.",
    "Confirm model iteration continues from the saved value.",
    "Confirm optimizer iterations and slots are restored.",
    "Run 2-5 additional iterations and record loss/weight/slot deltas.",
    "Keep FP16/BF16 marked experimental until GPU evidence is attached.",
)


def _load_module(module_name: str, path: Path):
    if module_name in sys.modules:
        return sys.modules[module_name]
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"cannot load module {module_name} from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _optimizer_roundtrip_module():
    return _load_module(
        "batch1_optimizer_roundtrip_for_training_save_resume",
        Path(__file__).with_name("optimizer_roundtrip.py"),
    )


def _precision_contract_module():
    return _load_module(
        "batch1_precision_contract_for_training_save_resume",
        Path(__file__).with_name("precision_contract.py"),
    )


def _enhancement_config_module():
    return _load_module(
        "batch1_enhancement_config_for_training_save_resume",
        REPO_ROOT / "core" / "enhancements" / "config.py",
    )


def _max_abs_error(left: Any, right: Any) -> float:
    a = np.asarray(left, dtype=np.float64)
    b = np.asarray(right, dtype=np.float64)
    if a.shape != b.shape:
        raise ValueError(f"shape mismatch for error: {a.shape} vs {b.shape}")
    return float(np.max(np.abs(a - b))) if a.size else 0.0


def normalize_legacy_training_options(options: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    """Return the legacy-safe option facts used by the smoke report."""
    raw_options = dict(options or {})
    cfg = _enhancement_config_module().normalize_enhancement_config(
        raw_options.get("enhancements")
    )
    return {
        "has_enhancements_field": "enhancements" in raw_options,
        "training_enabled": cfg.training_enabled,
        "merge_enabled": cfg.merge_enabled,
        "fallback_on_optional_error": cfg.fallback_on_optional_error,
        "strict_validation": cfg.strict_validation,
        "normalized_enhancements": cfg.to_dict(),
    }


def _initial_state(optimizer: str, weight: np.ndarray) -> Dict[str, Any]:
    opt = optimizer.strip().lower()
    state: Dict[str, Any] = {"iterations": 0}
    if opt == "adabelief":
        state.update({"ms": np.zeros_like(weight), "vs": np.zeros_like(weight)})
    elif opt == "rmsprop":
        state["acc"] = np.zeros_like(weight)
    elif opt == "lion":
        rt = _optimizer_roundtrip_module()
        state["c"] = np.zeros_like(weight)
        state["lion_state_schema_version"] = rt.LION_STATE_SCHEMA_VERSION
    else:
        raise ValueError(f"unsupported optimizer: {optimizer}")
    return state


def _train_steps(
    optimizer: str,
    weight: np.ndarray,
    state: MutableMapping[str, Any],
    grads: Sequence[np.ndarray],
    *,
    lr: float,
    dtype_name: str,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    rt = _optimizer_roundtrip_module()
    current_weight = np.asarray(weight, dtype=np.dtype(dtype_name)).copy()
    current_state: Dict[str, Any] = dict(state)
    for grad in grads:
        current_weight, current_state = rt.numpy_optimizer_step(
            optimizer,
            current_weight,
            grad,
            current_state,
            lr=lr,
            dtype_name=dtype_name,
        )
    return current_weight, current_state


def save_training_checkpoint(
    checkpoint_path: Path,
    *,
    optimizer: str,
    weight: np.ndarray,
    state: Mapping[str, Any],
    model_iter: int,
    options: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    rt = _optimizer_roundtrip_module()
    payload = {
        "schema_version": 1,
        "model_iter": int(model_iter),
        "options": dict(options or {}),
        "optimizer_payload": rt.serialize_optimizer_state(optimizer, weight, state),
    }
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_bytes(pickle.dumps(payload, protocol=4))
    stat = checkpoint_path.stat()
    return {
        "path": str(checkpoint_path),
        "exists": checkpoint_path.exists(),
        "non_empty": stat.st_size > 0,
        "size_bytes": stat.st_size,
    }


def load_training_checkpoint(checkpoint_path: Path) -> Dict[str, Any]:
    payload = pickle.loads(checkpoint_path.read_bytes())
    rt = _optimizer_roundtrip_module()
    weight, state = rt.deserialize_optimizer_state(payload["optimizer_payload"])
    return {
        "schema_version": int(payload.get("schema_version", 0)),
        "model_iter": int(payload.get("model_iter", 0)),
        "options": dict(payload.get("options", {})),
        "weight": weight,
        "optimizer_state": state,
    }


def run_training_save_resume_smoke(
    *,
    optimizer: str = "adabelief",
    dtype_name: str = "float32",
    requested_precision: str = "fp32",
    storage_dir: Optional[Path] = None,
    legacy_options: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Run a deterministic train/save/destroy/reload/resume smoke.

    返回结果用于测试和 macOS smoke 汇总；它不代表真实 TensorFlow session 已验证。
    """
    opt = optimizer.strip().lower()
    dtype = np.dtype(dtype_name)
    initial_weight = np.asarray([0.25, -0.50, 0.75, 0.125], dtype=dtype)
    grads = [
        np.asarray([0.10, -0.20, 0.05, 0.00], dtype=dtype),
        np.asarray([-0.05, 0.15, -0.25, 0.10], dtype=dtype),
        np.asarray([0.20, 0.05, -0.10, -0.15], dtype=dtype),
    ]
    lr = 1e-3

    options = dict(legacy_options or {"resolution": 64, "face_type": "f"})
    legacy_config = normalize_legacy_training_options(options)
    pc = _precision_contract_module()
    precision_contract = pc.resolve_precision_contract(
        requested_precision,
        runtime_capabilities={
            "tensorflow_available": False,
            "float16_dtype_available": False,
            "bfloat16_dtype_available": False,
            "cuda_gpu_available": False,
        },
    )
    low_precision_contracts = {
        name: pc.resolve_precision_contract(
            name,
            runtime_capabilities={
                "tensorflow_available": False,
                "float16_dtype_available": False,
                "bfloat16_dtype_available": False,
                "cuda_gpu_available": False,
            },
        )
        for name in ("fp16", "bf16")
    }

    def _run(checkpoint_root: Path) -> Dict[str, Any]:
        checkpoint_path = checkpoint_root / DEFAULT_CHECKPOINT_FILENAME
        cont_weight, cont_state = _train_steps(
            opt,
            initial_weight,
            _initial_state(opt, initial_weight),
            grads,
            lr=lr,
            dtype_name=dtype_name,
        )
        saved_weight, saved_state = _train_steps(
            opt,
            initial_weight,
            _initial_state(opt, initial_weight),
            grads[:2],
            lr=lr,
            dtype_name=dtype_name,
        )
        checkpoint = save_training_checkpoint(
            checkpoint_path,
            optimizer=opt,
            weight=saved_weight,
            state=saved_state,
            model_iter=int(saved_state["iterations"]),
            options=options,
        )

        # 显式丢弃旧对象引用，模拟进程退出或 session 销毁后的恢复入口。
        destroyed_weight = None
        destroyed_state = None
        del destroyed_weight, destroyed_state

        loaded = load_training_checkpoint(checkpoint_path)
        loaded_legacy_config = normalize_legacy_training_options(loaded["options"])
        resumed_weight, resumed_state = _train_steps(
            opt,
            loaded["weight"],
            loaded["optimizer_state"],
            grads[2:],
            lr=lr,
            dtype_name=dtype_name,
        )

        slot_keys = sorted(
            key
            for key in resumed_state
            if key not in ("iterations", "lion_state_schema_version", "legacy_state_reset")
        )
        reload_slot_errors = {
            key: _max_abs_error(saved_state[key], loaded["optimizer_state"][key])
            for key in slot_keys
            if key in saved_state and key in loaded["optimizer_state"]
        }
        update_errors = {
            "weight": _max_abs_error(cont_weight, resumed_weight),
            "iterations": float(abs(int(cont_state["iterations"]) - int(resumed_state["iterations"]))),
        }
        for key in slot_keys:
            if key in cont_state and key in resumed_state:
                update_errors[key] = _max_abs_error(cont_state[key], resumed_state[key])

        return {
            "optimizer": opt,
            "mode": "numpy_training_save_resume",
            "dtype": dtype_name,
            "requested_precision": requested_precision,
            "checkpoint": checkpoint,
            "legacy_options": legacy_config,
            "loaded_legacy_options": loaded_legacy_config,
            "precision_contract": precision_contract,
            "low_precision_status": {
                name: contract["status"]
                for name, contract in low_precision_contracts.items()
            },
            "model_iter_before_save": int(saved_state["iterations"]),
            "model_iter_after_load": int(loaded["model_iter"]),
            "model_iter_after_resume": int(resumed_state["iterations"]),
            "optimizer_iterations_before_save": int(saved_state["iterations"]),
            "optimizer_iterations_after_load": int(loaded["optimizer_state"]["iterations"]),
            "optimizer_iterations_after_resume": int(resumed_state["iterations"]),
            "weight_changed_before_save": _max_abs_error(initial_weight, saved_weight) > 0.0,
            "weight_changed_after_resume": _max_abs_error(saved_weight, resumed_weight) > 0.0,
            "max_abs_reload_error": max(
                [_max_abs_error(saved_weight, loaded["weight"]), *reload_slot_errors.values()]
                or [0.0]
            ),
            "max_abs_update_error": max(update_errors.values()) if update_errors else 0.0,
            "reload_errors": {
                "weight": _max_abs_error(saved_weight, loaded["weight"]),
                **reload_slot_errors,
            },
            "update_errors": update_errors,
            "optimizer_slot_keys": slot_keys,
            "representative_checks": list(WINDOWS_GPU_SAVE_RESUME_VALIDATION),
            "macos_lightweight_only": True,
            "windows_gpu_validation_required": list(WINDOWS_GPU_SAVE_RESUME_VALIDATION),
        }

    if storage_dir is None:
        with TemporaryDirectory() as tmpdir:
            return _run(Path(tmpdir))
    return _run(Path(storage_dir))


def run_all_training_save_resume_smokes() -> Dict[str, Any]:
    reports = {
        optimizer: run_training_save_resume_smoke(optimizer=optimizer)
        for optimizer in ("adabelief", "rmsprop", "lion")
    }
    return {
        "mode": "numpy_training_save_resume",
        "optimizers": list(reports),
        "reports": reports,
        "max_abs_reload_error": max(item["max_abs_reload_error"] for item in reports.values()),
        "max_abs_update_error": max(item["max_abs_update_error"] for item in reports.values()),
        "macos_lightweight_only": True,
        "windows_gpu_validation_required": list(WINDOWS_GPU_SAVE_RESUME_VALIDATION),
    }
