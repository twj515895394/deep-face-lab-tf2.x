import hashlib
import os
import re
from pathlib import Path, PureWindowsPath
from typing import Optional



def normalize_sample_path(path_str: str) -> str:
    """
    Normalize sample relative path for identity building.
    - Converts Windows backslashes '\\' to forward slashes '/'.
    - Removes leading './'.
    - Rejects absolute paths and paths containing '..'.
    - Preserves exact character casing for canonical representation.
    """
    if not path_str:
        raise ValueError("Sample path cannot be empty.")

    # Standardize backslashes
    clean_path = path_str.replace("\\", "/")

    # Check for Windows drive letters (e.g., C:/...) or absolute root
    if re.match(r"^[a-zA-Z]:", clean_path) or clean_path.startswith("/"):
        raise ValueError(f"Absolute paths are rejected for sample identity: {path_str}")

    # Split parts and validate no parent directory traversal '..'
    parts = [p for p in clean_path.split("/") if p and p != "."]
    if ".." in parts:
        raise ValueError(f"Directory traversal '..' is rejected in sample identity: {path_str}")

    if not parts:
        raise ValueError(f"Invalid sample path after normalization: {path_str}")

    return "/".join(parts)


def build_sample_key(filename: str, person_name: str = None, is_packed: bool = False, faceset_root: Optional[Path] = None) -> str:
    """
    Build canonical sample key for ordinary files, person facesets, or packed facesets.
    Examples:
    - Ordinary: "/path/to/faceset/00001.jpg", faceset_root="/path/to/faceset" -> "00001.jpg"
    - Subdirectory/Person: person_name="person_10", filename="00001.jpg" -> "person_10/00001.jpg"
    - Relative path: "personA/00001.jpg" -> "personA/00001.jpg"
    """
    if isinstance(filename, Path):
        filename = str(filename)

    # Standardize backslashes
    raw_path = filename.replace("\\", "/")

    # If filename is an absolute path and faceset_root is provided or detectable
    if faceset_root is not None:
        root_str = str(faceset_root).replace("\\", "/")
        if raw_path.startswith(root_str):
            raw_path = os.path.relpath(raw_path, root_str).replace("\\", "/")

    # Fallback for absolute path without faceset_root
    if (re.match(r"^[a-zA-Z]:", raw_path) or raw_path.startswith("/")) and person_name is None:
        # Extract relative path or basename if absolute
        raw_path = os.path.basename(raw_path)

    # Extract basename or relative parts
    if person_name and not raw_path.startswith(f"{person_name}/"):
        base_name = os.path.basename(raw_path)
        combined = f"{person_name}/{base_name}"
    else:
        combined = raw_path

    return normalize_sample_path(combined)


def build_sample_id(sample_key: str, namespace: str = "dfl-faceset-v1") -> str:
    """
    Generate stable 32-character SHA256 hex ID from sample_key and namespace.
    Same sample_key always produces the exact same sample_id regardless of host machine/OS.
    """
    canonical_key = normalize_sample_path(sample_key)
    payload = f"{namespace}\n{canonical_key}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:32]
