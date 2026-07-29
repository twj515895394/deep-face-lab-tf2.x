import hashlib
import json
from dataclasses import asdict, dataclass
from typing import List, Optional


@dataclass(frozen=True)
class SampleSignature:
    sample_key: str
    byte_size: int
    mtime_ns: Optional[int] = None
    packed_offset: Optional[int] = None
    quick_hash: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sample_key": self.sample_key,
            "byte_size": self.byte_size,
            "mtime_ns": self.mtime_ns,
            "packed_offset": self.packed_offset,
            "quick_hash": self.quick_hash,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SampleSignature":
        return cls(
            sample_key=data["sample_key"],
            byte_size=int(data["byte_size"]),
            mtime_ns=int(data["mtime_ns"]) if data.get("mtime_ns") is not None else None,
            packed_offset=int(data["packed_offset"]) if data.get("packed_offset") is not None else None,
            quick_hash=data.get("quick_hash"),
        )


def build_sample_signature(
    sample_key: str,
    byte_size: int,
    mtime_ns: Optional[int] = None,
    packed_offset: Optional[int] = None,
    quick_hash: Optional[str] = None,
) -> SampleSignature:
    """
    Construct a SampleSignature for ordinary or packed sample records.
    """
    return SampleSignature(
        sample_key=sample_key,
        byte_size=byte_size,
        mtime_ns=mtime_ns,
        packed_offset=packed_offset,
        quick_hash=quick_hash,
    )


def build_dataset_fingerprint(signatures: List[SampleSignature]) -> str:
    """
    Generate deterministic, cross-process dataset fingerprint.
    - Signatures are strictly sorted ascending by sample_key.
    - Each record is canonicalized to UTF-8 and fed into SHA256.
    """
    hasher = hashlib.sha256()

    # Sort strictly by sample_key (Unicode code point order)
    sorted_signatures = sorted(signatures, key=lambda sig: sig.sample_key)

    for sig in sorted_signatures:
        record_str = (
            f"{sig.sample_key}\n"
            f"{sig.byte_size}\n"
            f"{sig.mtime_ns if sig.mtime_ns is not None else ''}\n"
            f"{sig.packed_offset if sig.packed_offset is not None else ''}\n"
            f"{sig.quick_hash if sig.quick_hash is not None else ''}\n---"
        )
        hasher.update(record_str.encode("utf-8"))

    return hasher.hexdigest()
