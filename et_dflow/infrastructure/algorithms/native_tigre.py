"""
TIGRE (pytigre) reconstruction bridge for ET tilt series.

Expects GPU-enabled image (e.g. ``registry.dp.tech/davinci/tigre:...``).
Angles are taken from config/metadata via :func:`extract_tilt_angles_degrees` (degrees),
converted to radians for TIGRE.

Config (optional, JSON/YAML ``parameters``):

- ``tigre_algorithm``: ``"fdk"`` (default), ``"ossart"``, or ``"sirt"``
- ``tigre_niter``, ``tigre_blocksize``: iterations / block for OS-SART
- ``nVoxel``: length-3 list ``[nz, ny, nx]``; default cube from max(detector H, W)
- ``tigre_gpu_id``: int GPU index (default ``0``)
"""

from __future__ import annotations

import sys
from typing import Any, Dict

import hyperspy.api as hs
import numpy as np

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)


def run_tigre_reconstruction(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    import tigre
    import tigre.algorithms as algs

    proj = np.asarray(tilt_series.data, dtype=np.float32)
    if proj.ndim != 3:
        raise ValueError(f"TIGRE adapter expects shape (n_tilts, H, W), got {proj.shape}")

    n_ang, det_h, det_w = proj.shape
    angles_deg = extract_tilt_angles_degrees(tilt_series, config)
    if angles_deg.size != n_ang:
        raise ValueError(
            f"Tilt angle count {angles_deg.size} != n_tilts {n_ang}"
        )
    angles = np.deg2rad(angles_deg.astype(np.float32))

    nv = config.get("nVoxel")
    if nv is not None:
        n_voxel = np.array(nv, dtype=np.int32).reshape(3)
    else:
        side = int(max(det_h, det_w))
        n_voxel = np.array([side, side, side], dtype=np.int32)

    geo = tigre.geometry(
        mode="parallel",
        nVoxel=n_voxel,
        default=True,
    )
    geo.nDetector = np.array([det_w, det_h], dtype=np.int32)
    geo.dDetector = np.array([1.0, 1.0], dtype=np.float32)
    geo.sDetector = geo.nDetector.astype(np.float32) * geo.dDetector

    gpu_id = int(config.get("tigre_gpu_id", 0))
    try:
        from tigre.utilities import gpu as tigre_gpu

        names = tigre_gpu.getGpuNames()
        if len(names) == 0:
            print(
                "WARNING: TIGRE reports no GPU; reconstruction may fail.",
                file=sys.stderr,
            )
            gpuids = 0
        else:
            gpuids = tigre_gpu.getGpuIds(names[min(gpu_id, len(names) - 1)])
    except Exception as exc:  # pragma: no cover
        print(f"WARNING: TIGRE GPU init fallback: {exc}", file=sys.stderr)
        gpuids = gpu_id

    method = (config.get("tigre_algorithm") or "fdk").lower().strip()
    if method == "fdk":
        fdk_fn = getattr(algs, "fdk", None) or getattr(algs, "FDK", None)
        if fdk_fn is None:
            raise RuntimeError("TIGRE build has no fdk/FDK algorithm")
        vol = fdk_fn(proj, geo, angles, gpuids=gpuids)
    elif method in ("ossart", "os-sart"):
        niter = int(config.get("tigre_niter", 20))
        block = int(config.get("tigre_blocksize", 20))
        vol = algs.ossart(
            proj, geo, angles, niter, blocksize=block, gpuids=gpuids
        )
    elif method == "sirt":
        niter = int(config.get("tigre_niter", 20))
        vol = algs.sirt(proj, geo, angles, niter, gpuids=gpuids)
    else:
        raise ValueError(
            f"Unknown tigre_algorithm {method!r}; use fdk, ossart, or sirt"
        )

    rec_sig = numpy_volume_to_signal2d(vol, title="TIGRE reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "tigre")
    rec_sig.metadata.set_item("et_dflow.tigre_algorithm", method)

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="tigre",
        start_time=start_time,
        extra_metadata={
            "tigre_algorithm": method,
            "nVoxel": n_voxel.tolist(),
        },
    )
