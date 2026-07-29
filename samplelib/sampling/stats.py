from dataclasses import dataclass, field
from typing import Any, Dict, Optional

import numpy as np


@dataclass
class SamplingStats:
    """
    Compact sampling statistics container for tracking draw frequency,
    cycle builds, duplicate retries, and bucket distributions.
    """

    total_draws: int = 0
    bucket_draw_counts: Optional[np.ndarray] = None
    quality_quantile_draw_counts: Optional[np.ndarray] = None
    metadata_valid_draws: int = 0
    fallback_record_draws: int = 0
    duplicate_retries: int = 0
    accepted_duplicates: int = 0
    cycle_build_count: int = 0
    cycle_build_seconds: float = 0.0

    def snapshot(self) -> "SamplingStats":
        """Return a deep copy snapshot of the current stats state."""
        return SamplingStats(
            total_draws=self.total_draws,
            bucket_draw_counts=self.bucket_draw_counts.copy() if self.bucket_draw_counts is not None else None,
            quality_quantile_draw_counts=(
                self.quality_quantile_draw_counts.copy()
                if self.quality_quantile_draw_counts is not None
                else None
            ),
            metadata_valid_draws=self.metadata_valid_draws,
            fallback_record_draws=self.fallback_record_draws,
            duplicate_retries=self.duplicate_retries,
            accepted_duplicates=self.accepted_duplicates,
            cycle_build_count=self.cycle_build_count,
            cycle_build_seconds=self.cycle_build_seconds,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert stats into a JSON-serializable dictionary."""
        return {
            "total_draws": self.total_draws,
            "bucket_draw_counts": (
                self.bucket_draw_counts.tolist() if self.bucket_draw_counts is not None else None
            ),
            "quality_quantile_draw_counts": (
                self.quality_quantile_draw_counts.tolist()
                if self.quality_quantile_draw_counts is not None
                else None
            ),
            "metadata_valid_draws": self.metadata_valid_draws,
            "fallback_record_draws": self.fallback_record_draws,
            "duplicate_retries": self.duplicate_retries,
            "accepted_duplicates": self.accepted_duplicates,
            "cycle_build_count": self.cycle_build_count,
            "cycle_build_seconds": round(self.cycle_build_seconds, 6),
        }
