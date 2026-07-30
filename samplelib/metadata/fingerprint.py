import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

DEFAULT_QUICK_CHUNK_SIZE = 65536
SIGNATURE_MODE_QUICK = "quick"
SIGNATURE_MODE_STRONG = "strong"
QUICK_HASH_ALGORITHM = "sha256_first_last_chunk_size"
STRONG_HASH_ALGORITHM = "sha256_full"


@dataclass(frozen=True)
class SampleSignature:
    sample_key: str
    byte_size: int
    mtime_ns: Optional[int] = None
    packed_offset: Optional[int] = None
    quick_hash: Optional[str] = None
    content_sha256: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "sample_key": self.sample_key,
            "byte_size": self.byte_size,
            "mtime_ns": self.mtime_ns,
            "packed_offset": self.packed_offset,
            "quick_hash": self.quick_hash,
            "content_sha256": self.content_sha256,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SampleSignature":
        return cls(
            sample_key=data["sample_key"],
            byte_size=int(data["byte_size"]),
            mtime_ns=int(data["mtime_ns"]) if data.get("mtime_ns") is not None else None,
            packed_offset=int(data["packed_offset"]) if data.get("packed_offset") is not None else None,
            quick_hash=data.get("quick_hash"),
            content_sha256=data.get("content_sha256"),
        )


def compute_quick_hash(raw_bytes: bytes, chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE) -> str:
    """
    Bounded content fingerprint:
    SHA256(first_chunk || last_chunk || ascii_decimal_size)
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    n = len(raw_bytes)
    first = raw_bytes[:chunk_size]
    last = raw_bytes[-chunk_size:] if n > chunk_size else raw_bytes
    return compute_quick_hash_chunks(first, last, n, chunk_size=chunk_size)


def compute_quick_hash_chunks(
    first_chunk: bytes,
    last_chunk: bytes,
    total_size: int,
    chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE,
) -> str:
    """Quick hash from already-bounded first/last chunks (no full-file requirement)."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")
    if total_size < 0:
        raise ValueError("total_size must be >= 0")
    if total_size > chunk_size:
        first = first_chunk[:chunk_size]
        last = last_chunk[-chunk_size:] if len(last_chunk) > chunk_size else last_chunk
    else:
        # Entire payload fits in one chunk; first/last must both be that payload.
        body = first_chunk[:total_size]
        first = body
        last = body
    hasher = hashlib.sha256()
    hasher.update(first)
    hasher.update(last)
    hasher.update(str(int(total_size)).encode("ascii"))
    return hasher.hexdigest()


def compute_content_sha256(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


def read_sample_raw_bytes(sample: Any, samples_path: Optional[Union[str, Path]] = None) -> bytes:
    """
    Read raw sample bytes for ordinary or packed Sample objects.
    Uses Sample.read_raw_file when available; does not re-parse pak format.
    """
    off_size = getattr(sample, "_filename_offset_size", None)
    if off_size is not None:
        # Packed: Sample.read_raw_file ignores filename and uses offset/size.
        return sample.read_raw_file()

    path = getattr(sample, "filename", None)
    if path is None:
        raise FileNotFoundError("Sample has no filename for raw byte read")
    p = Path(path)
    if not p.is_file() and samples_path is not None:
        candidate = Path(samples_path) / path
        if candidate.is_file():
            p = candidate
    if not p.is_file():
        raise FileNotFoundError(f"Ordinary sample file not found: {path}")
    with open(p, "rb") as f:
        return f.read()


def _resolve_ordinary_path(sample: Any, samples_path: Optional[Union[str, Path]] = None) -> Path:
    path = getattr(sample, "filename", None)
    if path is None:
        raise FileNotFoundError("Sample has no filename for raw byte read")
    p = Path(path)
    if not p.is_file() and samples_path is not None:
        candidate = Path(samples_path) / path
        if candidate.is_file():
            p = candidate
    if not p.is_file():
        raise FileNotFoundError(f"Ordinary sample file not found: {path}")
    return p


def read_sample_bounded_chunks(
    sample: Any,
    samples_path: Optional[Union[str, Path]] = None,
    chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE,
) -> tuple:
    """
    Bounded I/O for quick signatures: seek/read first+last chunk only.

    Returns (first_chunk, last_chunk, total_size).
    Ordinary files use Path seek; packed samples use known offset/size.
    """
    if chunk_size <= 0:
        raise ValueError("chunk_size must be > 0")

    off_size = getattr(sample, "_filename_offset_size", None)
    if off_size is not None:
        packed_path, packed_offset, packed_size = off_size
        declared_size = int(packed_size)
        offset = int(packed_offset)
        with open(packed_path, "rb") as f:
            f.seek(0, 2)
            file_end = int(f.tell())
            # Match Sample.read_raw_file short-read behavior at EOF so quick_hash
            # embeds the same size as compute_quick_hash(full_bytes).
            available = max(0, min(declared_size, file_end - offset))
            total_size = int(available)
            f.seek(offset)
            first = f.read(min(chunk_size, total_size)) if total_size > 0 else b""
            if total_size > chunk_size:
                f.seek(offset + total_size - chunk_size)
                last = f.read(chunk_size)
            else:
                last = first
        return first, last, total_size

    p = _resolve_ordinary_path(sample, samples_path=samples_path)
    with open(p, "rb") as f:
        f.seek(0, 2)
        total_size = int(f.tell())
        f.seek(0)
        first = f.read(min(chunk_size, total_size)) if total_size > 0 else b""
        if total_size > chunk_size:
            f.seek(total_size - chunk_size)
            last = f.read(chunk_size)
        else:
            last = first
    return first, last, total_size


def build_sample_signature(
    sample_key: str,
    byte_size: int,
    mtime_ns: Optional[int] = None,
    packed_offset: Optional[int] = None,
    quick_hash: Optional[str] = None,
    content_sha256: Optional[str] = None,
) -> SampleSignature:
    """Construct a SampleSignature for ordinary or packed sample records."""
    return SampleSignature(
        sample_key=sample_key,
        byte_size=byte_size,
        mtime_ns=mtime_ns,
        packed_offset=packed_offset,
        quick_hash=quick_hash,
        content_sha256=content_sha256,
    )


def build_signature_from_sample(
    sample: Any,
    sample_key: str,
    samples_path: Optional[Union[str, Path]] = None,
    mode: str = SIGNATURE_MODE_QUICK,
    chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE,
    raw_bytes: Optional[bytes] = None,
) -> SampleSignature:
    """
    Build a SampleSignature for a live Sample.

    mode=quick: sample_key + size + mtime/offset + quick_hash (when bytes available)
    mode=strong: also full content_sha256 over raw bytes
    """
    mode = (mode or SIGNATURE_MODE_QUICK).lower()
    if mode not in (SIGNATURE_MODE_QUICK, SIGNATURE_MODE_STRONG):
        raise ValueError(f"Unsupported signature mode: {mode}")

    off_size = getattr(sample, "_filename_offset_size", None)
    mtime_ns: Optional[int] = None
    packed_offset: Optional[int] = None
    byte_size = 0

    if off_size is not None:
        _, packed_offset, byte_size = off_size
        packed_offset = int(packed_offset)
        byte_size = int(byte_size)
    else:
        path = Path(getattr(sample, "filename", ""))
        if not path.is_file() and samples_path is not None:
            cand = Path(samples_path) / getattr(sample, "filename", "")
            if cand.is_file():
                path = cand
        if path.is_file():
            st = path.stat()
            byte_size = int(st.st_size)
            mtime_ns = int(st.st_mtime_ns)
        else:
            byte_size = 0
            mtime_ns = None

    quick_hash = None
    content_sha256 = None
    data = raw_bytes

    if mode == SIGNATURE_MODE_STRONG:
        # Strong: one full read only (caller may pass raw_bytes to avoid re-read).
        if data is None:
            try:
                data = read_sample_raw_bytes(sample, samples_path=samples_path)
            except Exception:
                data = None
        if data is not None:
            if byte_size <= 0:
                byte_size = len(data)
            quick_hash = compute_quick_hash(data, chunk_size=chunk_size)
            content_sha256 = compute_content_sha256(data)
    else:
        # Quick: bounded first/last I/O; never require a full-file read.
        if data is not None:
            if byte_size <= 0:
                byte_size = len(data)
            quick_hash = compute_quick_hash(data, chunk_size=chunk_size)
        else:
            try:
                first, last, total = read_sample_bounded_chunks(
                    sample, samples_path=samples_path, chunk_size=chunk_size
                )
                if byte_size <= 0:
                    byte_size = int(total)
                quick_hash = compute_quick_hash_chunks(
                    first, last, int(total), chunk_size=chunk_size
                )
            except Exception:
                quick_hash = None

    return SampleSignature(
        sample_key=sample_key,
        byte_size=byte_size,
        mtime_ns=mtime_ns,
        packed_offset=packed_offset,
        quick_hash=quick_hash,
        content_sha256=content_sha256,
    )


def signature_mode_from_analysis_config(analysis_config: Optional[dict]) -> str:
    if not isinstance(analysis_config, dict):
        return SIGNATURE_MODE_QUICK
    sig_cfg = analysis_config.get("signature")
    if not isinstance(sig_cfg, dict):
        return SIGNATURE_MODE_QUICK
    mode = str(sig_cfg.get("mode") or SIGNATURE_MODE_QUICK).lower()
    if mode not in (SIGNATURE_MODE_QUICK, SIGNATURE_MODE_STRONG):
        return SIGNATURE_MODE_QUICK
    return mode


def signature_config_dict(
    mode: str,
    chunk_size: int = DEFAULT_QUICK_CHUNK_SIZE,
) -> Dict[str, Any]:
    mode = (mode or SIGNATURE_MODE_QUICK).lower()
    if mode == SIGNATURE_MODE_STRONG:
        algorithm = STRONG_HASH_ALGORITHM
    else:
        algorithm = QUICK_HASH_ALGORITHM
    return {
        "mode": mode,
        "algorithm": algorithm,
        "chunk_size": int(chunk_size),
    }


def signatures_match(
    saved_sig: Optional[dict],
    current_sig: SampleSignature,
    mode: Optional[str] = None,
) -> bool:
    """
    Compare a persisted signature dict with a current SampleSignature.

    Strong mode requires content_sha256 equality.
    Quick mode uses quick_hash when both sides have it; otherwise falls back to
    legacy fields (size/mtime/offset).
    Strong saved vs quick current never matches.
    """
    if not isinstance(saved_sig, dict):
        return False
    if saved_sig.get("sample_key") != current_sig.sample_key:
        return False
    try:
        if int(saved_sig.get("byte_size", -1)) != int(current_sig.byte_size):
            return False
    except (TypeError, ValueError):
        return False

    saved_strong = saved_sig.get("content_sha256")
    effective_mode = (mode or SIGNATURE_MODE_QUICK).lower()

    if effective_mode == SIGNATURE_MODE_STRONG:
        if not saved_strong or not current_sig.content_sha256:
            return False
        return saved_strong == current_sig.content_sha256

    # Quick path: strong-only records must not silently match quick current.
    if saved_strong and not current_sig.content_sha256:
        return False
    if saved_strong and current_sig.content_sha256:
        return saved_strong == current_sig.content_sha256

    saved_quick = saved_sig.get("quick_hash")
    if saved_quick and current_sig.quick_hash:
        return saved_quick == current_sig.quick_hash

    # Legacy field compare (pre-quick_hash metadata).
    saved_mtime = saved_sig.get("mtime_ns")
    if saved_mtime is not None and current_sig.mtime_ns is not None:
        try:
            if int(saved_mtime) != int(current_sig.mtime_ns):
                return False
        except (TypeError, ValueError):
            return False
    elif saved_mtime is not None or current_sig.mtime_ns is not None:
        # One side missing mtime: still allow if packed offsets match.
        pass

    saved_off = saved_sig.get("packed_offset")
    if saved_off is not None or current_sig.packed_offset is not None:
        try:
            if (
                (saved_off is None) != (current_sig.packed_offset is None)
                or (
                    saved_off is not None
                    and int(saved_off) != int(current_sig.packed_offset)
                )
            ):
                return False
        except (TypeError, ValueError):
            return False

    return True


def build_dataset_fingerprint(signatures: List[SampleSignature]) -> str:
    """
    Generate deterministic, cross-process dataset fingerprint.
    - Signatures are strictly sorted ascending by sample_key.
    - Each record is canonicalized to UTF-8 and fed into SHA256.
    - content_sha256 is included only when present (strong mode) to avoid
      changing pure-quick fingerprints when the field is absent.
    """
    hasher = hashlib.sha256()
    sorted_signatures = sorted(signatures, key=lambda sig: sig.sample_key)

    for sig in sorted_signatures:
        record_str = (
            f"{sig.sample_key}\n"
            f"{sig.byte_size}\n"
            f"{sig.mtime_ns if sig.mtime_ns is not None else ''}\n"
            f"{sig.packed_offset if sig.packed_offset is not None else ''}\n"
            f"{sig.quick_hash if sig.quick_hash is not None else ''}\n"
        )
        if sig.content_sha256:
            record_str += f"{sig.content_sha256}\n"
        record_str += "---"
        hasher.update(record_str.encode("utf-8"))

    return hasher.hexdigest()
