"""
GENFIRE-Python bridge: writes temporary ``.mat`` stacks and calls ``genfire.main.main``.

Requires the ``genfire`` package (e.g. image ``registry.dp.tech/davinci/genfire-python:...``).
GENFIRE expects **square** projections of shape ``(N, N, n_tilts)``; we center-pad
non-square detectors and force **even** ``N``.

Odd ``N`` (or odd size after GENFIRE's oversampling pad) breaks upstream
``fillInFourierGrid``: its FFT meshgrid uses ``arange(-n2, n2)`` (length N-1 when
N is odd) then reshapes to ``N*N`` — e.g. 1024² vs 1025² on sm70.

**Headless:** set ``displayFigure.DisplayFigureON = False`` on parameters.

Config (optional):

- ``genfire_num_iterations`` (default ``50``)
- ``genfire_oversampling_ratio`` (default ``3``)
- ``genfire_interpolation_cutoff`` (default ``0.5``)
- ``genfire_resolution_state``: 1 / 2 / 3 (default ``2``, no resolution extension)
- ``genfire_calculate_rfree`` (default ``False`` for speed in batch)
- ``genfire_gridding_method``: ``"FFT"`` or ``"DFT"`` (default ``"FFT"``)
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any, Dict

import hyperspy.api as hs
import numpy as np
import scipy.io

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)


def _pad_square_projections(stack_nthw: np.ndarray) -> np.ndarray:
    """``stack_nthw``: (n_tilts, H, W) → (N, N, n_tilts) float32 with even N."""
    n, h, w = stack_nthw.shape
    side = int(max(h, w))
    if side % 2:
        side += 1
    out = np.zeros((side, side, n), dtype=np.float32)
    oy = (side - h) // 2
    ox = (side - w) // 2
    for i in range(n):
        out[oy : oy + h, ox : ox + w, i] = stack_nthw[i].astype(np.float32, copy=False)
    return out


def _coerce_oversampling_ratio(raw: Any) -> Any:
    """GENFIRE does ``paddedDim = dims[0] * oversamplingRatio`` then ``ncBig = paddedDim // 2``.

    If ``oversamplingRatio`` is a ``float``, ``paddedDim`` stays float, ``ncBig`` stays
    float (``512.0 // 2 == 256.0``), and the final crop raises::

        TypeError: slice indices must be integers ...

    Whole-number ratios must be passed as ``int``. Non-integer ratios use a mul
    helper that always returns ``int`` paddedDim even when ``dims[0]`` is NumPy.
    """
    ratio = float(raw)
    if abs(ratio - round(ratio)) < 1e-12:
        return int(round(ratio))

    class _IntPadOversampling:
        __slots__ = ("_value",)

        def __init__(self, value: float) -> None:
            self._value = float(value)

        def __float__(self) -> float:
            return self._value

        def __repr__(self) -> str:
            return f"IntPadOversampling({self._value})"

        def _mul(self, other: Any) -> int:
            return int(round(float(other) * self._value))

        def __mul__(self, other: Any) -> int:
            return self._mul(other)

        def __rmul__(self, other: Any) -> int:
            return self._mul(other)

    return _IntPadOversampling(ratio)


def run_genfire_reconstruction(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    import genfire.fileio as gf_io
    import genfire.main as gf_main
    from genfire.reconstruct import ReconstructionParameters

    stack = np.asarray(tilt_series.data, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError(f"GENFIRE adapter expects (n_tilts, H, W), got {stack.shape}")

    angles_deg = extract_tilt_angles_degrees(tilt_series, config)
    if angles_deg.size != stack.shape[0]:
        raise ValueError(
            f"Tilt angle count {angles_deg.size} != n_tilts {stack.shape[0]}"
        )

    projections = _pad_square_projections(stack)
    # GENFIRE multiplies Euler angles by PI/180 — pass degrees, not radians.
    tilt = angles_deg.astype(np.float64)
    euler = np.stack([np.zeros_like(tilt), tilt, np.zeros_like(tilt)], axis=1)

    with tempfile.TemporaryDirectory(prefix="et_dflow_genfire_") as tmp:
        tmp_path = Path(tmp)
        proj_mat = tmp_path / "projections.mat"
        ang_mat = tmp_path / "angles.mat"
        out_mrc = tmp_path / "genfire_out.mrc"

        scipy.io.savemat(str(proj_mat), {"projections": projections})
        scipy.io.savemat(str(ang_mat), {"angles": euler})

        rp = ReconstructionParameters()
        rp.projections = str(proj_mat.resolve())
        rp.eulerAngles = str(ang_mat.resolve())
        rp.support = ""
        rp.useDefaultSupport = True
        rp.resultsFilename = str(out_mrc.resolve())
        rp.numIterations = int(config.get("genfire_num_iterations", 50))
        rp.oversamplingRatio = _coerce_oversampling_ratio(
            config.get("genfire_oversampling_ratio", 3)
        )
        rp.interpolationCutoffDistance = float(
            config.get("genfire_interpolation_cutoff", 0.5)
        )
        rp.resolutionExtensionSuppressionState = int(
            config.get("genfire_resolution_state", 2)
        )
        rp.calculateRfree = bool(config.get("genfire_calculate_rfree", False))
        rp.displayFigure.DisplayFigureON = False
        rp.griddingMethod = str(config.get("genfire_gridding_method", "FFT"))
        rp.verbose = bool(config.get("genfire_verbose", False))

        gf_main.main(rp)

        if not out_mrc.is_file():
            raise FileNotFoundError(f"GENFIRE did not write {out_mrc}")

        vol = gf_io.readVolume(str(out_mrc))

    rec_sig = numpy_volume_to_signal2d(vol, title="GENFIRE reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "genfire")

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="genfire",
        start_time=start_time,
        extra_metadata={"genfire_iterations": rp.numIterations},
    )
