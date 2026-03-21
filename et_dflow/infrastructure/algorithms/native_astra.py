"""
ASTRA Toolbox 3D parallel-beam reconstruction (experimental tilt series).

Sinogram layout matches ASTRA sample s007_3d_reconstruction.py:
(n_angles, det_row_count, det_col_count) — same as tilt series (n_tilts, H, W).

Config (optional):

- astra_algorithm: default SIRT3D_CUDA
- astra_algorithm_fallbacks: extra names to try
- astra_niter: default 150
- astra_vol_shape: [nx, ny, nz]; default max(H, W) cube
- det_spacing_x, det_spacing_y: default 1.0
"""

from __future__ import annotations

import sys
from typing import Any, Dict, List, Optional

import hyperspy.api as hs
import numpy as np

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)


def _cleanup_astra(alg_id, rec_id, proj_id) -> None:
    import astra

    if alg_id is not None:
        try:
            astra.algorithm.delete(alg_id)
        except Exception:
            pass
    for did in (rec_id, proj_id):
        if did is not None:
            try:
                astra.data3d.delete(did)
            except Exception:
                pass


def run_astra_parallel3d(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    import astra

    proj = np.asarray(tilt_series.data, dtype=np.float32)
    if proj.ndim != 3:
        raise ValueError("ASTRA expects (n_tilts, H, W), got %s" % (proj.shape,))

    n_ang, det_rows, det_cols = proj.shape
    angles_deg = extract_tilt_angles_degrees(tilt_series, config)
    if angles_deg.size != n_ang:
        raise ValueError(
            "Tilt angle count %s != n_tilts %s" % (angles_deg.size, n_ang)
        )
    angles = np.ascontiguousarray(
        np.deg2rad(angles_deg.astype(np.float64)), dtype=np.float64
    )

    sx = float(config.get("det_spacing_x", 1.0))
    sy = float(config.get("det_spacing_y", 1.0))
    proj_geom = astra.create_proj_geom(
        "parallel3d", sx, sy, int(det_rows), int(det_cols), angles
    )

    vs = config.get("astra_vol_shape")
    if vs is not None:
        v = [int(x) for x in vs]
        if len(v) != 3:
            raise ValueError("astra_vol_shape must have length 3")
        vol_geom = astra.create_vol_geom(v[0], v[1], v[2])
    else:
        side = int(max(det_rows, det_cols))
        vol_geom = astra.create_vol_geom(side, side, side)

    proj_id = None
    rec_id = None
    alg_id = None
    last_err: Optional[Exception] = None
    try:
        proj_id = astra.data3d.create("-sino", proj_geom, proj)
        rec_id = astra.data3d.create("-vol", vol_geom, 0.0)

        primary = (config.get("astra_algorithm") or "SIRT3D_CUDA").strip()
        fallbacks: List[str] = list(config.get("astra_algorithm_fallbacks") or [])
        to_try: List[str] = [primary] + [n for n in fallbacks if n != primary]
        for name in ("SIRT3D_CUDA", "CGLS3D_CUDA", "SIRT3D", "CGLS3D"):
            if name not in to_try:
                to_try.append(name)

        for algo_name in to_try:
            try:
                cfg = astra.astra_dict(algo_name)
                cfg["ReconstructionDataId"] = rec_id
                cfg["ProjectionDataId"] = proj_id
                alg_id = astra.algorithm.create(cfg)
                niter = int(config.get("astra_niter", 150))
                astra.algorithm.run(alg_id, niter)
                break
            except Exception as e:
                last_err = e
                _cleanup_astra(alg_id, None, None)
                alg_id = None
                print(
                    "WARNING: ASTRA algorithm %r failed: %s" % (algo_name, e),
                    file=sys.stderr,
                )
        else:
            raise RuntimeError(
                "All ASTRA algorithm attempts failed; last error: %r" % (last_err,)
            ) from last_err

        rec = astra.data3d.get(rec_id)
    finally:
        _cleanup_astra(alg_id, rec_id, proj_id)

    rec_sig = numpy_volume_to_signal2d(rec, title="ASTRA reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "astra")

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="astra",
        start_time=start_time,
        extra_metadata={"astra_vol_shape": list(np.asarray(rec).shape)},
    )
