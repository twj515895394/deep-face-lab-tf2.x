import json
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from samplelib.metadata.schema import FacesetMetadataV1, MetadataValidationResult


class MetadataStoreError(Exception):
    """Base exception for metadata store operations."""

    def __init__(self, message: str, path: Optional[Path] = None, cause: Optional[Exception] = None):
        super().__init__(message)
        self.path = path
        self.cause = cause


@dataclass
class AtomicWriteResult:
    target_path: Path
    backup_path: Optional[Path]
    bytes_written: int
    replaced: bool


def write_metadata_atomic(
    path: Path,
    metadata: FacesetMetadataV1,
    keep_backup: bool = True,
) -> AtomicWriteResult:
    """
    Write FacesetMetadataV1 to target JSON file atomically and safely.

    Process:
    1. Serialize metadata & validate finite JSON (allow_nan=False)
    2. Write to temporary file in same directory (.tmp)
    3. Flush & fsync to disk
    4. Re-read temp file & validate with FacesetMetadataV1.load_json
    5. Optionally create single .bak backup of existing target
    6. os.replace(temp, target)
    7. Clean up temporary resources
    """
    target_path = Path(path).resolve()
    parent_dir = target_path.parent
    try:
        parent_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        raise MetadataStoreError(f"Failed to create directory {parent_dir}: {e}", path=parent_dir, cause=e)

    temp_path = parent_dir / f".{target_path.name}.tmp"
    backup_path: Optional[Path] = None
    replaced = target_path.exists()
    bytes_written = 0

    try:
        # Step 1 & 2: Serialize & Write to temp file
        data_dict = metadata.to_dict()
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data_dict, f, ensure_ascii=False, indent=2, allow_nan=False)
            f.flush()
            os.fsync(f.fileno())

        bytes_written = temp_path.stat().st_size

        # Step 4: Re-read & Validate temp file
        loaded_meta, val_result = FacesetMetadataV1.load_json(temp_path)
        if not val_result.is_supported or not val_result.is_valid:
            issues_str = "; ".join([f"[{i.code}] {i.message}" for i in val_result.issues])
            raise MetadataStoreError(
                f"Validation failed on written temp file {temp_path}: {issues_str}",
                path=temp_path,
            )

        # Step 5: Optional backup of existing target file
        if replaced and keep_backup:
            backup_path = target_path.with_suffix(target_path.suffix + ".bak")
            try:
                shutil.copy2(target_path, backup_path)
            except Exception as e:
                raise MetadataStoreError(
                    f"Failed to create backup file at {backup_path}: {e}",
                    path=backup_path,
                    cause=e,
                )

        # Step 6: Atomic replace
        try:
            os.replace(temp_path, target_path)
        except OSError as e:
            err_msg = (
                f"Failed to replace {target_path} with {temp_path}: {e}. "
                f"If on Windows, ensure no other process is holding a lock on {target_path}."
            )
            raise MetadataStoreError(err_msg, path=target_path, cause=e)

        return AtomicWriteResult(
            target_path=target_path,
            backup_path=backup_path,
            bytes_written=bytes_written,
            replaced=replaced,
        )

    except Exception as e:
        # Clean up temp file on failure
        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass
        if not isinstance(e, MetadataStoreError):
            raise MetadataStoreError(f"Atomic metadata write failed: {e}", path=target_path, cause=e)
        raise e


def load_metadata(path: Path, strict: bool = False) -> Tuple[FacesetMetadataV1, MetadataValidationResult]:
    """
    Safely load metadata file with validation.
    """
    target_path = Path(path).resolve()
    return FacesetMetadataV1.load_json(target_path)
