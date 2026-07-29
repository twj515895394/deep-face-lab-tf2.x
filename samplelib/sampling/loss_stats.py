import math
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence, Tuple
import numpy as np


@dataclass(frozen=True)
class LossWindowStats:
    count: int
    mean: Tuple[float, ...]
    median: Tuple[float, ...]
    last: Tuple[float, ...]
    minimum: Tuple[float, ...]
    maximum: Tuple[float, ...]

    def mean_list(self) -> List[float]:
        return list(self.mean)


def _normalize_loss_item(item: Any) -> Tuple[float, ...]:
    if isinstance(item, (int, float, np.number)):
        val = float(item)
        if not math.isfinite(val):
            raise ValueError(f"Non-finite loss value encountered: {val}")
        return (val,)
    
    if hasattr(item, "__iter__") and not isinstance(item, (str, bytes)):
        res = []
        for x in item:
            val = float(x)
            if not math.isfinite(val):
                raise ValueError(f"Non-finite loss value encountered: {val}")
            res.append(val)
        if len(res) == 0:
            raise ValueError("Empty loss item tuple encountered")
        return tuple(res)

    val = float(item)
    if not math.isfinite(val):
        raise ValueError(f"Non-finite loss value encountered: {val}")
    return (val,)


def compute_loss_window_stats(
    history: Sequence[Any],
    start_index: int = 0,
) -> Optional[LossWindowStats]:
    if history is None:
        return None

    safe_start = max(0, int(start_index))
    if safe_start >= len(history):
        return None

    window_raw = history[safe_start:]
    if len(window_raw) == 0:
        return None

    normalized_items: List[Tuple[float, ...]] = []
    expected_dim: Optional[int] = None

    for item in window_raw:
        norm_item = _normalize_loss_item(item)
        if expected_dim is None:
            expected_dim = len(norm_item)
        elif len(norm_item) != expected_dim:
            raise ValueError(
                f"Inconsistent loss dimensions in window: expected {expected_dim}, got {len(norm_item)}"
            )
        normalized_items.append(norm_item)

    count = len(normalized_items)
    if count == 0 or expected_dim is None:
        return None

    arr = np.array(normalized_items, dtype=np.float64)

    means = tuple(float(x) for x in np.mean(arr, axis=0))
    medians = tuple(float(x) for x in np.median(arr, axis=0))
    lasts = tuple(float(x) for x in arr[-1])
    mins = tuple(float(x) for x in np.min(arr, axis=0))
    maxs = tuple(float(x) for x in np.max(arr, axis=0))

    return LossWindowStats(
        count=count,
        mean=means,
        median=medians,
        last=lasts,
        minimum=mins,
        maximum=maxs,
    )
