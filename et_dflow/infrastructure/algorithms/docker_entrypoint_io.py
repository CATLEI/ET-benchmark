"""
Shared helpers for Docker ``run_algorithm.py`` entrypoints.

Keeps HyperSpy load/save behavior consistent with WBP/SIRT containers
(list-of-signals, Signal2D coercion).

**Unified I/O:** pipeline steps should use HyperSpy ``.hspy`` for tilt series and
reconstructions where possible. :func:`save_algorithm_result` normalizes the
output path to end with ``.hspy``.
"""

from __future__ import annotations

import os
import warnings
from pathlib import Path
from typing import Union

import hyperspy.api as hs

from et_dflow.core.models import AlgorithmResult


PathLike = Union[str, Path]

# Formats recommended for cross-algorithm ET-dflow workflows
RECOMMENDED_TILT_SERIES_SUFFIXES = (".hspy",)


def resolve_hspy_output_path(path: PathLike) -> Path:
    """Ensure reconstruction is written with a ``.hspy`` extension."""
    p = Path(path)
    if p.suffix.lower() != ".hspy":
        return p.with_suffix(".hspy")
    return p


def load_tilt_series_hspy(input_path: PathLike) -> hs.signals.Signal2D:
    """
    Load a tilt series (recommended: ``.hspy``; any HyperSpy-readable format works).

    Returns a ``Signal2D`` with shape ``(n_tilts, height, width)`` when possible.
    """
    path = Path(input_path)
    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    if (
        path.suffix.lower() not in RECOMMENDED_TILT_SERIES_SUFFIXES
        and os.environ.get("ET_DFLOW_WARN_NON_HSPY_INPUT", "").lower() in ("1", "true", "yes")
    ):
        warnings.warn(
            f"Input {path.name!r} is not .hspy; ET-dflow recommends .hspy for "
            "uniform algorithm I/O.",
            UserWarning,
            stacklevel=2,
        )

    loaded = hs.load(str(path))
    if isinstance(loaded, list):
        if not loaded:
            raise ValueError("HyperSpy load returned an empty list")
        tilt_series = loaded[0]
    else:
        tilt_series = loaded

    if not isinstance(tilt_series, hs.signals.Signal2D):
        if hasattr(tilt_series, "data") and tilt_series.data.ndim >= 2:
            tilt_series = hs.signals.Signal2D(tilt_series.data.copy())
        else:
            raise TypeError(
                f"Expected Signal2D or array-like 2D/3D data, got {type(tilt_series)}"
            )
    return tilt_series


def save_algorithm_result(result: AlgorithmResult, output_path: PathLike) -> None:
    """
    Write ``result.reconstruction`` as HyperSpy ``.hspy`` (path suffix normalized).

    Sets metadata ``et_dflow.io.output_format`` = ``hyperspy_hspy``.
    """
    out = resolve_hspy_output_path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    try:
        result.reconstruction.metadata.set_item(
            "et_dflow.io.output_format", "hyperspy_hspy"
        )
    except (AttributeError, TypeError):
        pass
    result.reconstruction.save(str(out))
    if Path(output_path).resolve() != out.resolve():
        print(
            f"Note: output path normalized to .hspy → {out}",
        )
    print(f"Saving reconstruction to: {out}")


def print_run_summary(result: AlgorithmResult) -> None:
    """Print timing/size lines (call after algorithm-specific success message)."""
    print(f"  Output shape: {result.reconstruction.data.shape}")
    print(f"  Execution time: {result.execution_time:.2f} seconds")
    mem_mb = result.memory_usage / (1024.0 * 1024.0)
    print(f"  Memory (RSS): {mem_mb:.2f} MB")
