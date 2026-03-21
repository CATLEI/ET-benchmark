"""
Shared helpers for Docker algorithm adapters (native solvers + placeholders).

Keeps tilt-angle extraction aligned with WBP/SIRT and builds :class:`AlgorithmResult`
without going through :class:`et_dflow.domain.algorithms.base.Algorithm`.
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

import hyperspy.api as hs
import numpy as np

from et_dflow.core.models import AlgorithmResult


def extract_tilt_angles_degrees(
    data: hs.signals.Signal2D, config: Dict[str, Any]
) -> np.ndarray:
    """
    Resolve tilt angles in **degrees** (same rules as WBP / SIRT).

    Order: ``config['tilt_angles']`` → HyperSpy TEM metadata →
    ``np.linspace(tilt_range[0], tilt_range[1], n_tilts)``.
    """
    if "tilt_angles" in config:
        angles = config["tilt_angles"]
        if isinstance(angles, (list, np.ndarray)):
            return np.asarray(angles, dtype=np.float64)

    try:
        if hasattr(data.metadata, "Acquisition_instrument"):
            tem = getattr(data.metadata.Acquisition_instrument, "TEM", None)
            if tem and hasattr(tem, "tilt_series"):
                tilt_angles = tem.tilt_series
                if tilt_angles is not None:
                    return np.asarray(tilt_angles, dtype=np.float64)
    except (AttributeError, TypeError):
        pass

    n_tilts = int(data.data.shape[0])
    tilt_range = config.get("tilt_range", [-60.0, 60.0])
    return np.linspace(float(tilt_range[0]), float(tilt_range[1]), n_tilts)


def make_adapter_algorithm_result(
    reconstruction: hs.signals.BaseSignal,
    *,
    algorithm_name: str,
    start_time: float,
    extra_metadata: Optional[Dict[str, Any]] = None,
) -> AlgorithmResult:
    """Build :class:`AlgorithmResult` with RSS memory (bytes), like :class:`Algorithm`."""
    import psutil

    process = psutil.Process(os.getpid())
    meta = {"algorithm": algorithm_name, **(extra_metadata or {})}
    return AlgorithmResult(
        reconstruction=reconstruction,
        execution_time=time.time() - start_time,
        memory_usage=float(process.memory_info().rss),
        metadata=meta,
        algorithm_name=algorithm_name,
    )


def numpy_volume_to_signal2d(volume: np.ndarray, *, title: str) -> hs.signals.Signal2D:
    """Wrap a 3D array as ``Signal2D`` (nav Z, signal Y, X), same style as WBP."""
    arr = np.asarray(volume, dtype=np.float32)
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D volume, got shape {arr.shape}")
    sig = hs.signals.Signal2D(arr)
    sig.metadata.set_item("General.title", title)
    sig.metadata.set_item("Signal.quantity", "Intensity")
    try:
        if sig.axes_manager.navigation_dimension > 0:
            nav_axis = sig.axes_manager.navigation_axes[0]
            nav_axis.name = "Z"
            nav_axis.units = "px"
        if sig.axes_manager.signal_dimension >= 2:
            sy, sx = sig.axes_manager.signal_axes[0], sig.axes_manager.signal_axes[1]
            sy.name, sy.units = "Y", "px"
            sx.name, sx.units = "X", "px"
    except (AttributeError, IndexError, TypeError):
        pass
    return sig
