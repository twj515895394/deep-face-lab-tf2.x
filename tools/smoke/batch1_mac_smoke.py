"""Batch 1 lightweight smoke harness for macOS development.

The checks in this module intentionally avoid real GPU training. They record
what can be trusted on a CPU-only macOS workstation and list the Windows GPU
validation that must still happen before closing Batch 1.
"""

import argparse
import ast
import importlib
import importlib.util
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[2]

REQUIRED_REPO_FILES = (
    "main.py",
    "requirements.txt",
    ".handoff/current.md",
    "docs/development/batch1-correctness-and-extension-foundation-tasks.md",
    ".scratch/batch1-correctness-foundation/issues/01-baseline-and-mac-smoke-harness.md",
)

REPO_MODULES = ("core", "models", "merger", "samplelib")
OPTIONAL_DEPENDENCIES = ("numpy", "cv2", "tensorflow")
LIGHTWEIGHT_IMPORT_ATTEMPTS = ("core.leras.nn", "models", "merger.MergeMasked")
SKIP_SYNTAX_DIRS = {".git", "__pycache__", "workspace", ".venv", "venv"}

WINDOWS_GPU_VALIDATION_ITEMS = (
    "Windows launch scripts and environment activation",
    "CUDA / cuDNN / TensorFlow GPU discovery",
    "SAEHD FP32 initialization with a real or fixture model directory",
    "One minimal SAEHD training step on GPU",
    "Model save, session restart, reload, and next-step resume",
    "Default Merge path with a real model or approved Windows fixture",
)


def _run_git(args: List[str], repo_root: Path) -> Optional[str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _import_status(module_name: str) -> Dict[str, Any]:
    try:
        module = importlib.import_module(module_name)
    except Exception as exc:
        return {
            "available": False,
            "error_type": type(exc).__name__,
            "message": str(exc),
        }
    return {
        "available": True,
        "version": getattr(module, "__version__", None),
    }


def _iter_python_files(repo_root: Path) -> Iterable[Path]:
    for path in sorted(repo_root.rglob("*.py")):
        if any(part in SKIP_SYNTAX_DIRS for part in path.relative_to(repo_root).parts):
            continue
        yield path


def run_syntax_scan(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    errors = []
    count = 0
    for path in _iter_python_files(repo_root):
        count += 1
        rel_path = str(path.relative_to(repo_root))
        try:
            ast.parse(path.read_text(encoding="utf-8"), filename=rel_path)
        except Exception as exc:
            errors.append({
                "file": rel_path,
                "error_type": type(exc).__name__,
                "message": str(exc),
            })
    return {
        "files_scanned": count,
        "errors": errors,
    }


def collect_environment(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "repo_root": str(repo_root),
        "git": {
            "commit": _run_git(["rev-parse", "HEAD"], repo_root),
            "branch": _run_git(["branch", "--show-current"], repo_root),
        },
        "python": {
            "version": platform.python_version(),
            "executable": sys.executable,
            "implementation": platform.python_implementation(),
        },
        "platform": {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "macos_lightweight_only": platform.system() == "Darwin",
        },
        "dependencies": {
            name: _import_status(name)
            for name in OPTIONAL_DEPENDENCIES
        },
        "lightweight_import_attempts": {
            name: _import_status(name)
            for name in LIGHTWEIGHT_IMPORT_ATTEMPTS
        },
        "windows_gpu_validation_required": list(WINDOWS_GPU_VALIDATION_ITEMS),
    }


def run_lightweight_checks(repo_root: Path = REPO_ROOT) -> Dict[str, Any]:
    repo_root = repo_root.resolve()
    git_commit = _run_git(["rev-parse", "HEAD"], repo_root)
    git_branch = _run_git(["branch", "--show-current"], repo_root)
    required_files = {
        path: (repo_root / path).exists()
        for path in REQUIRED_REPO_FILES
    }
    repo_modules = {
        name: {"available": _module_available(name)}
        for name in REPO_MODULES
    }
    syntax_scan = run_syntax_scan(repo_root)
    checks = {
        "git_metadata_available": git_commit is not None and git_branch is not None,
        "python_version_supported": sys.version_info >= (3, 6),
        "required_files": required_files,
        "repo_modules": repo_modules,
        "syntax_scan": syntax_scan,
        "gpu_training_skipped_by_design": True,
    }
    required_ok = (
        checks["git_metadata_available"]
        and
        checks["python_version_supported"]
        and all(required_files.values())
        and all(item["available"] for item in repo_modules.values())
        and not syntax_scan["errors"]
    )
    return {
        "status": "pass" if required_ok else "fail",
        "checks": checks,
        "notes": [
            "This smoke harness does not validate GPU training on macOS.",
            "Windows GPU validation remains required before closing Batch 1.",
        ],
    }


def write_smoke_outputs(
    output_dir: Path,
    environment: Dict[str, Any],
    summary: Dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "smoke-summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def default_output_dir(repo_root: Path = REPO_ROOT) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return repo_root / "workspace" / "validation" / "batch1" / timestamp


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run Batch 1 macOS lightweight smoke checks."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for environment.json and smoke-summary.json.",
    )
    parser.add_argument(
        "--print-json",
        action="store_true",
        help="Print the summary JSON to stdout after writing files.",
    )
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    repo_root = REPO_ROOT
    output_dir = args.output_dir or default_output_dir(repo_root)

    environment = collect_environment(repo_root)
    summary = run_lightweight_checks(repo_root)
    write_smoke_outputs(output_dir, environment, summary)

    if args.print_json:
        print(json.dumps({"environment": environment, "summary": summary}, indent=2))

    return 0 if summary["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
