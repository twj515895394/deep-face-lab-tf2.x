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
    end_index: Optional[int] = None,
) -> Optional[LossWindowStats]:
    """
    Compute stats on history[start_index:end_index] (half-open).

    end_index=None means len(history) (backward compatible).
    Returns None for empty windows.
    Raises ValueError for end < start, non-finite values, or inconsistent dims.
    """
    if history is None:
        return None

    n = len(history)
    safe_start = int(start_index)
    if safe_start < 0:
        safe_start = 0
    safe_start = min(safe_start, n)

    if end_index is None:
        safe_end = n
    else:
        safe_end = int(end_index)
        if safe_end < 0:
            safe_end = 0
        safe_end = min(safe_end, n)

    if safe_end < safe_start:
        raise ValueError(
            f"Invalid loss window indices: end_index ({safe_end}) < start_index ({safe_start})"
        )

    if safe_start >= safe_end:
        return None

    window_raw = history[safe_start:safe_end]
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


class LossWindowTracker:
    """
    Session-local loss buffer independent of ModelBase.loss_history compression.

    Lifecycle:
      append after each successful train_one_iter
      freeze copy before model.save()
      on save success: log stats then clear (commit)
      on save failure: retain buffer for next successful save
    """

    def __init__(self) -> None:
        self._items: List[Any] = []
        self._iters: List[Optional[int]] = []
        self.degraded: bool = False

    def __len__(self) -> int:
        return len(self._items)

    def clear(self) -> None:
        self._items.clear()
        self._iters.clear()

    def append_loss(self, loss_item: Any, iter_num: Optional[int] = None) -> None:
        if loss_item is None:
            return
        # Store a shallow copy for sequences so later mutation cannot rewrite the window.
        if isinstance(loss_item, (list, tuple)):
            self._items.append(list(loss_item))
        else:
            self._items.append(loss_item)
        try:
            self._iters.append(int(iter_num) if iter_num is not None else None)
        except (TypeError, ValueError):
            self._iters.append(None)

    def append_from_model_history(
        self,
        history: Sequence[Any],
        iter_num: Optional[int] = None,
    ) -> None:
        if history is None or len(history) == 0:
            return
        self.append_loss(history[-1], iter_num=iter_num)

    def freeze(self) -> List[Any]:
        """Return a frozen snapshot of the current window (do not commit)."""
        return list(self._items)

    def freeze_iters(self) -> List[Optional[int]]:
        return list(self._iters)

    def iter_range_for_frozen(
        self,
        frozen: Sequence[Any],
    ) -> Tuple[Optional[int], Optional[int]]:
        """
        Return (start_iter, end_iter) for a freeze snapshot.
        Uses parallel iter markers recorded at append time.
        """
        n = len(frozen)
        if n <= 0:
            return None, None
        # frozen is a prefix snapshot of _items at freeze time.
        iters = self._iters[:n] if len(self._iters) >= n else self._iters
        known = [i for i in iters if i is not None]
        if not known:
            return None, None
        return int(known[0]), int(known[-1])

    def stats_for_frozen(self, frozen: Sequence[Any]) -> Optional[LossWindowStats]:
        return compute_loss_window_stats(frozen, start_index=0, end_index=None)

    def commit(self) -> None:
        """Consume the window after a successful save and clear degraded flag."""
        self._items.clear()
        self._iters.clear()
        self.degraded = False

    def stats(self) -> Optional[LossWindowStats]:
        return self.stats_for_frozen(self._items)


def format_loss_window_log(
    reason: str,
    iter_num: int,
    stats: Optional[LossWindowStats],
    channel_labels: Optional[Sequence[str]] = None,
    start_iter: Optional[int] = None,
    end_iter: Optional[int] = None,
    window_incomplete: bool = False,
    degraded_count: int = 0,
) -> str:
    """
    Structured multi-line save window log.

    Example:
      [Save][scheduled] iter=12000 window=1000 range=11001..12000
        src mean=0.1234 median=0.1200 last=0.1180 min=0.1100 max=0.1500
        dst mean=0.0987 median=0.0970 last=0.0950 min=0.0900 max=0.1200
    """
    flags = []
    if start_iter is not None and end_iter is not None:
        flags.append(f"range={int(start_iter)}..{int(end_iter)}")
    if int(degraded_count or 0) > 0:
        flags.append(f"degraded_count={int(degraded_count)}")
    if window_incomplete:
        flags.append("window_incomplete")
    flag_suffix = (" " + " ".join(flags)) if flags else ""

    if stats is None or stats.count <= 0:
        return f"[Save][{reason}] iter={int(iter_num)} window=0 (empty){flag_suffix}"

    lines = [f"[Save][{reason}] iter={int(iter_num)} window={stats.count}{flag_suffix}"]
    dim = len(stats.mean)
    if channel_labels is None:
        if dim == 2:
            labels = ["src", "dst"]
        elif dim == 1:
            labels = ["loss"]
        else:
            labels = [f"ch{i}" for i in range(dim)]
    else:
        labels = list(channel_labels)
        while len(labels) < dim:
            labels.append(f"ch{len(labels)}")

    for i in range(dim):
        label = labels[i]
        lines.append(
            f"  {label} mean={stats.mean[i]:.4f} median={stats.median[i]:.4f} "
            f"last={stats.last[i]:.4f} min={stats.minimum[i]:.4f} max={stats.maximum[i]:.4f}"
        )
    return "\n".join(lines)
