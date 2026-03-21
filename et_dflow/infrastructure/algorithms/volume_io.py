"""Load 3D volumes from disk paths (.npy / .mrc / .rec) for CLI-based adapters."""

from __future__ import annotations

import glob
import os
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np


def load_volume_array_from_path(path: Path) -> np.ndarray:
    """Load a 3D array from ``.npy`` or MRC-like formats via ``mrcfile``."""
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    suf = path.suffix.lower()
    if suf == ".npy":
        return np.asarray(np.load(str(path)), dtype=np.float32)
    if suf in (".mrc", ".rec"):
        import mrcfile

        with mrcfile.open(str(path), mode="r", permissive=True) as mrc:
            return np.asarray(mrc.data, dtype=np.float32)
    raise ValueError(f"Unsupported volume extension: {path.suffix}")


def pick_newest_glob(directory: str, pattern: str) -> Optional[Path]:
    paths = sorted(
        Path(p)
        for p in glob.glob(os.path.join(directory, pattern))
        if os.path.isfile(p)
    )
    if not paths:
        return None
    return max(paths, key=lambda p: p.stat().st_mtime)


def resolve_cli_output_volume(
    config: Dict[str, Any],
    *,
    path_key: str,
    dir_key: str,
    glob_key: str,
    default_glob: str = "*.mrc",
) -> Path:
    """Resolve explicit path or newest file under ``dir`` matching ``glob``."""
    p = config.get(path_key)
    if p:
        cand = Path(str(p)).expanduser()
        if cand.is_file():
            return cand

    out_dir = config.get(dir_key)
    pattern = config.get(glob_key, default_glob)
    if out_dir and os.path.isdir(str(out_dir)):
        picked = pick_newest_glob(str(out_dir), str(pattern))
        if picked is not None:
            return picked

    raise FileNotFoundError(
        f"Could not resolve output volume: set {path_key} or {dir_key}+{glob_key}"
    )
