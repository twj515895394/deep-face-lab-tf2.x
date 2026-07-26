"""Precision contract and dtype audit helpers.

本模块只描述和审计当前实现的 dtype 事实，不在 Batch 1 中重写低精度训练语义。
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Mapping, Optional


STATUS_VALIDATED = "validated"
STATUS_EXPERIMENTAL = "experimental"
STATUS_BLOCKED = "blocked"

SUPPORTED_PRECISIONS = ("fp32", "fp16", "bf16")
PRECISION_ALIASES = {
    "fp32": "fp32",
    "float32": "fp32",
    "fp16": "fp16",
    "float16": "fp16",
    "half": "fp16",
    "mixed_float16": "fp16",
    "bf16": "bf16",
    "bfloat16": "bf16",
    "mixed_bfloat16": "bf16",
}

CURRENT_DTYPE_CONTRACT = {
    "fp32": {
        "status": STATUS_VALIDATED,
        "compute_dtype": "float32",
        "master_weight_dtype": "float32",
        "gradient_dtype": "float32",
        "optimizer_slot_dtypes": ["float32"],
        "placeholder_dtype": "float32",
        "save_file_dtype": "float32",
        "load_variable_dtype": "float32",
        "loss_scale_mode": "none",
        "loss_scale_value": 1.0,
        "risk_notes": "FP32 is the Batch 1 validated baseline.",
    },
    "fp16": {
        "status": STATUS_EXPERIMENTAL,
        "compute_dtype": "float16",
        "master_weight_dtype": "float16",
        "gradient_dtype": "float16",
        "optimizer_slot_dtypes": ["float16"],
        "placeholder_dtype": "float16",
        "save_file_dtype": "float32",
        "load_variable_dtype": "float16",
        "loss_scale_mode": "missing_dynamic_loss_scale",
        "loss_scale_value": 1.0,
        "risk_notes": "FP16 lacks complete finite gate, loss scaling, roundtrip, and Windows GPU evidence.",
    },
    "bf16": {
        "status": STATUS_EXPERIMENTAL,
        "compute_dtype": "bfloat16",
        "master_weight_dtype": "bfloat16",
        "gradient_dtype": "bfloat16",
        "optimizer_slot_dtypes": ["bfloat16"],
        "placeholder_dtype": "bfloat16",
        "save_file_dtype": "float32",
        "load_variable_dtype": "bfloat16",
        "loss_scale_mode": "legacy_static",
        "loss_scale_value": 32768.0,
        "risk_notes": "BF16 remains experimental until dtype, finite, roundtrip, and Windows GPU evidence is complete.",
    },
}


def normalize_precision_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip().lower()
    if not text:
        return None
    return PRECISION_ALIASES.get(text)


def _dtype_name(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    dtype = getattr(value, "dtype", None)
    if dtype is not None and dtype is not value:
        return _dtype_name(dtype)
    text = str(value)
    if text.startswith("<") and "'" in text:
        start = text.find("'")
        end = text.rfind("'")
        if end > start:
            return text[start + 1:end]
    return text


def _unique_dtype_names(values: Iterable[Any]) -> List[str]:
    result = []
    seen = set()
    for value in values:
        name = _dtype_name(value)
        if name and name not in seen:
            result.append(name)
            seen.add(name)
    return result


def _runtime_capabilities(runtime_capabilities: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    caps = {
        "tensorflow_available": None,
        "float16_dtype_available": True,
        "bfloat16_dtype_available": None,
        "cuda_gpu_available": None,
    }
    if runtime_capabilities is not None:
        caps.update(dict(runtime_capabilities))
        return caps

    try:
        import tensorflow as tf  # type: ignore
    except Exception as exc:
        caps.update(
            {
                "tensorflow_available": False,
                "float16_dtype_available": False,
                "bfloat16_dtype_available": False,
                "cuda_gpu_available": False,
                "probe_error": f"{type(exc).__name__}: {exc}",
            }
        )
        return caps

    caps["tensorflow_available"] = True
    caps["float16_dtype_available"] = hasattr(tf, "float16")
    caps["bfloat16_dtype_available"] = hasattr(tf, "bfloat16")
    try:
        caps["cuda_gpu_available"] = bool(tf.config.list_physical_devices("GPU"))
    except Exception:
        caps["cuda_gpu_available"] = None
    return caps


def resolve_precision_contract(
    requested_precision: Any = "fp32",
    device_config: Any = None,
    *,
    runtime_capabilities: Optional[Mapping[str, Any]] = None,
    allow_blocked_fallback: bool = True,
) -> Dict[str, Any]:
    del device_config
    caps = _runtime_capabilities(runtime_capabilities)
    normalized = normalize_precision_name(requested_precision)
    fallback_reason = None

    if normalized is None:
        effective = "fp32"
        requested = str(requested_precision)
        fallback_reason = "invalid_requested_precision"
    else:
        requested = normalized
        effective = normalized

    if effective == "fp16" and caps.get("float16_dtype_available") is False:
        fallback_reason = "float16_dtype_unavailable"
    elif effective == "bf16" and caps.get("bfloat16_dtype_available") is False:
        fallback_reason = "bfloat16_dtype_unavailable"
    elif effective in ("fp16", "bf16") and caps.get("tensorflow_available") is False:
        fallback_reason = "tensorflow_unavailable"

    blocked_request = fallback_reason and normalized in ("fp16", "bf16")
    if blocked_request and allow_blocked_fallback:
        effective = "fp32"

    base = dict(CURRENT_DTYPE_CONTRACT[effective])
    contract = {
        "requested_precision": requested,
        "requested_precision_normalized": normalized,
        "effective_precision": effective,
        "fallback_reason": fallback_reason,
        "runtime_capabilities": caps,
        "use_fp16": effective == "fp16",
        "use_bf16": effective == "bf16",
        "target_master_weight_contract": {
            "master_weight_dtype": "float32",
            "gradient_accumulation_dtype": "float32",
            "optimizer_slot_dtype": "float32",
            "status": "target_not_implemented_in_batch1",
        },
    }
    contract.update(base)
    if blocked_request:
        contract["status"] = STATUS_BLOCKED
    return contract


def collect_weight_dtype_snapshot(weights: Iterable[Any]) -> List[str]:
    return _unique_dtype_names(weights)


def collect_optimizer_slot_dtype_snapshot(optimizer: Any) -> Dict[str, List[str]]:
    slots = {}
    for name in ("ms", "vs", "c", "m", "v", "accumulators", "weights"):
        values = getattr(optimizer, name, None)
        if values is None:
            continue
        if not isinstance(values, (list, tuple)):
            values = [values]
        slots[name] = _unique_dtype_names(values)
    get_weights = getattr(optimizer, "get_weights", None)
    if callable(get_weights):
        try:
            slots["get_weights"] = _unique_dtype_names(get_weights())
        except Exception:
            pass
    return slots


def audit_precision_dtypes(
    contract: Mapping[str, Any],
    *,
    weights: Optional[Iterable[Any]] = None,
    gradients: Optional[Iterable[Any]] = None,
    optimizer: Any = None,
    placeholders: Optional[Iterable[Any]] = None,
    save_file_dtype: Any = None,
    load_variable_dtype: Any = None,
    max_abs_reload_error: Any = None,
) -> Dict[str, Any]:
    report = dict(contract)
    observed = {
        "placeholder_dtypes": collect_weight_dtype_snapshot(placeholders or []),
        "master_weight_dtypes": collect_weight_dtype_snapshot(weights or []),
        "gradient_dtypes": collect_weight_dtype_snapshot(gradients or []),
        "optimizer_slots": collect_optimizer_slot_dtype_snapshot(optimizer) if optimizer is not None else {},
        "save_file_dtype": _dtype_name(save_file_dtype),
        "load_variable_dtype": _dtype_name(load_variable_dtype),
        "max_abs_reload_error": max_abs_reload_error,
    }
    observed["optimizer_slot_dtypes_observed"] = _unique_dtype_names(
        dtype for values in observed["optimizer_slots"].values() for dtype in values
    )

    mismatches = []
    expected_pairs = (
        ("master_weight_dtype", observed["master_weight_dtypes"]),
        ("gradient_dtype", observed["gradient_dtypes"]),
        ("placeholder_dtype", observed["placeholder_dtypes"]),
    )
    for field, values in expected_pairs:
        if values and report.get(field) not in values:
            mismatches.append(f"{field}: expected {report.get(field)}, observed {values}")

    if observed["save_file_dtype"] and observed["save_file_dtype"] != report.get("save_file_dtype"):
        mismatches.append(
            f"save_file_dtype: expected {report.get('save_file_dtype')}, observed {observed['save_file_dtype']}"
        )
    if observed["load_variable_dtype"] and observed["load_variable_dtype"] != report.get("load_variable_dtype"):
        mismatches.append(
            f"load_variable_dtype: expected {report.get('load_variable_dtype')}, observed {observed['load_variable_dtype']}"
        )

    report["observed"] = observed
    report["mismatches"] = mismatches
    report["evidence"] = {
        "macos_structural_audit": True,
        "optimizer_roundtrip_verified": max_abs_reload_error is not None,
        "windows_gpu_evidence": "missing",
    }
    report["capability_boundaries"] = {
        "compute": report.get("compute_dtype"),
        "master_weight": report.get("master_weight_dtype"),
        "gradient": report.get("gradient_dtype"),
        "optimizer_slot": report.get("optimizer_slot_dtypes"),
        "save_file": report.get("save_file_dtype"),
        "load_variable": report.get("load_variable_dtype"),
    }
    if mismatches and report.get("status") == STATUS_VALIDATED:
        report["status"] = STATUS_EXPERIMENTAL
    report["summary"] = summarize_precision_contract(report)
    return report


def summarize_precision_contract(contract: Mapping[str, Any]) -> str:
    return (
        "PrecisionContract("
        f"requested={contract.get('requested_precision')}, "
        f"effective={contract.get('effective_precision')}, "
        f"status={contract.get('status')}, "
        f"compute={contract.get('compute_dtype')}, "
        f"weight={contract.get('master_weight_dtype')}, "
        f"gradient={contract.get('gradient_dtype')}, "
        f"slot={contract.get('optimizer_slot_dtypes')}, "
        f"fallback={contract.get('fallback_reason')})"
    )


def build_default_saehd_contract(
    requested_precision: Any = "fp32",
    *,
    runtime_capabilities: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    return audit_precision_dtypes(
        resolve_precision_contract(requested_precision, runtime_capabilities=runtime_capabilities)
    )
