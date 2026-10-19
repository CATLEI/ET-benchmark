"""
ASTRA Toolbox 3D parallel-beam reconstruction (experimental tilt series).

Tilt series in this project is ``(n_angles, det_rows, det_cols)``.
ASTRA parallel3d projection data is ``(det_rows, n_angles, det_cols)``
(see https://astra-toolbox.com/docs/data3d.html). The adapter transposes
before ``data3d.create``.

Volume geometry is ``create_vol_geom(n_rows, n_cols, n_slices)`` with
rows along Y, columns along X, slices along Z (detector rows).
``data3d.get`` returns ``(n_slices, n_rows, n_cols)``.

Config (optional):

- astra_algorithm: default ``FBP_CUDA`` (Ram-Lak filter, then ``BP3D_CUDA``).
  ASTRA has no 3D parallel ``FBP3D_CUDA``. ``FBP_CUDA`` in the toolbox is 2D only.
- filter_type: ``ram-lak`` (aliases ``ramp``), ``shepp-logan``, ``cosine``,
  ``hamming``, ``hann``, ``none``
- astra_algorithm_fallbacks: extra names for the iterative path only
- astra_niter: iterative algorithms only; default 150
- gpu_index: ``BP3D_CUDA`` option.GPUindex, default 0
- astra_vol_shape: [nx, ny, nz]; default nx=ny=det_cols, nz=det_rows
- det_spacing_x, det_spacing_y: default 1.0 (column spacing, row spacing)
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


_FBP_NAMES = {"FBP_CUDA", "FBP3D_CUDA"}
_DIRECT_BP_NAMES = _FBP_NAMES | {"BP3D_CUDA"}


def tilt_series_to_astra_sino(proj: np.ndarray) -> np.ndarray:
    """``(n_angles, det_rows, det_cols)`` → ASTRA ``(det_rows, n_angles, det_cols)``."""
    if proj.ndim != 3:
        raise ValueError("ASTRA expects (n_tilts, H, W), got %s" % (proj.shape,))
    return np.ascontiguousarray(np.transpose(proj, (1, 0, 2)), dtype=np.float32)


def apply_parallel_fbp_filter(sino: np.ndarray, filter_name: str = "ram-lak") -> np.ndarray:
    """Ramp-filter ``(det_rows, n_angles, det_cols)`` along detector columns.

    The frequency response follows the common discrete Ram-Lak convention
    (``2 * |fftfreq|``, peak 1). The result is scaled by ``pi / (2 * n_angles)``,
    the same factor used by scikit-image ``iradon``. ``BP3D_CUDA`` then does
    the unfiltered backprojection.
    """
    if sino.ndim != 3:
        raise ValueError("sinogram must be (det_rows, n_angles, det_cols), got %s" % (sino.shape,))
    name = filter_name.lower().replace("_", "-")
    if name == "ramp":
        name = "ram-lak"
    n_angles = int(sino.shape[1])
    n = int(sino.shape[-1])
    n_pad = int(2 ** np.ceil(np.log2(max(64, 2 * n))))
    omega = np.fft.rfftfreq(n_pad).astype(np.float64) * 2.0
    if name == "none":
        filt = np.ones_like(omega)
    elif name == "ram-lak":
        filt = omega
    elif name == "shepp-logan":
        with np.errstate(divide="ignore", invalid="ignore"):
            window = np.ones_like(omega)
            nonzero = omega > 0
            window[nonzero] = np.sin(omega[nonzero] * np.pi / 2.0) / (
                omega[nonzero] * np.pi / 2.0
            )
        filt = omega * window
    elif name == "cosine":
        filt = omega * np.cos(omega * np.pi / 2.0)
    elif name == "hamming":
        filt = omega * (0.54 + 0.46 * np.cos(omega * np.pi))
    elif name == "hann":
        filt = omega * (0.5 + 0.5 * np.cos(omega * np.pi))
    else:
        raise ValueError(
            "filter_type must be ram-lak, ramp, shepp-logan, cosine, "
            "hamming, hann, or none; got %r" % (filter_name,)
        )
    padded = np.pad(sino.astype(np.float32, copy=False), ((0, 0), (0, 0), (0, n_pad - n)))
    spectrum = np.fft.rfft(padded, axis=-1)
    filtered = np.fft.irfft(spectrum * filt, n=n_pad, axis=-1)[..., :n]
    scale = np.pi / (2.0 * max(n_angles, 1))
    return np.ascontiguousarray(filtered * scale, dtype=np.float32)


def _require_nvidia_gpu() -> str:
    """Return the first ``nvidia-smi -L`` line, or raise if no GPU is visible."""
    import subprocess

    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError(
            "CUDA reconstruction requires nvidia-smi and a visible GPU; "
            "nvidia-smi is not installed in this container"
        ) from exc
    listing = (result.stdout or "").strip()
    if result.returncode != 0 or "GPU" not in listing:
        detail = listing or (result.stderr or "").strip()
        raise RuntimeError(
            "CUDA reconstruction requires a visible NVIDIA GPU. nvidia-smi: %s" % detail
        )
    return listing.splitlines()[0]


def _run_bp3d_cuda(astra: Any, proj_id: int, rec_id: int, gpu_index: int) -> int:
    cfg = astra.astra_dict("BP3D_CUDA")
    cfg["ProjectionDataId"] = proj_id
    cfg["ReconstructionDataId"] = rec_id
    cfg["option"] = {"GPUindex": int(gpu_index)}
    alg_id = astra.algorithm.create(cfg)
    # One backprojection. A second argument would repeat it on some builds.
    astra.algorithm.run(alg_id)
    return alg_id


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
    sino = tilt_series_to_astra_sino(proj)
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
        nx, ny, nz = v
        vol_geom = astra.create_vol_geom(ny, nx, nz)
    else:
        # One slice per detector row (tilt axis). In-plane size follows detector columns,
        # same default as WBP Nrecon = width.
        vol_geom = astra.create_vol_geom(int(det_cols), int(det_cols), int(det_rows))

    requested = (config.get("astra_algorithm") or "FBP_CUDA").strip()
    filter_name: Optional[str] = None
    used_backend = requested
    proj_id = None
    rec_id = None
    alg_id = None
    last_err: Optional[Exception] = None
    try:
        if requested.upper() in _DIRECT_BP_NAMES:
            gpu_line = _require_nvidia_gpu()
            print("ASTRA GPU: %s" % gpu_line)
            if requested.upper() in _FBP_NAMES:
                filter_name = str(config.get("filter_type") or "ram-lak")
                sino = apply_parallel_fbp_filter(sino, filter_name)
                print(
                    "ASTRA FBP_CUDA: filter=%s then BP3D_CUDA (one backprojection)"
                    % filter_name
                )
            else:
                print("ASTRA BP3D_CUDA: unfiltered backprojection")
            proj_id = astra.data3d.create("-sino", proj_geom, sino)
            rec_id = astra.data3d.create("-vol", vol_geom, 0.0)
            alg_id = _run_bp3d_cuda(
                astra, proj_id, rec_id, int(config.get("gpu_index", 0))
            )
            used_backend = "BP3D_CUDA"
        else:
            proj_id = astra.data3d.create("-sino", proj_geom, sino)
            rec_id = astra.data3d.create("-vol", vol_geom, 0.0)
            # An explicit list, including [], tries only those names. Omitting the
            # key keeps the previous CUDA-then-CPU chain.
            if "astra_algorithm_fallbacks" in config:
                fallbacks = list(config.get("astra_algorithm_fallbacks") or [])
                to_try = [requested] + [n for n in fallbacks if n != requested]
            else:
                to_try = [requested]
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
                    used_backend = algo_name
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
    rec_sig.metadata.set_item("et_dflow.astra_algorithm", requested)
    rec_sig.metadata.set_item("et_dflow.astra_backend", used_backend)
    if filter_name:
        rec_sig.metadata.set_item("et_dflow.fbp_filter", filter_name)

    extra = {
        "astra_vol_shape": list(np.asarray(rec).shape),
        "astra_algorithm": requested,
        "astra_backend": used_backend,
    }
    if filter_name:
        extra["fbp_filter"] = filter_name
    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="astra",
        start_time=start_time,
        extra_metadata=extra,
    )
