"""Slice-wise classic DART on parallel-beam electron tomography.

Each detector row is an independent 2D problem. Fixed pixels are held at the
segmented gray value by zeroing them before every full sweep of the residual
problem and adding them back afterwards. ``ReconstructionMaskId`` is not used:
the CPU and CUDA headers disagree on which mask value is updated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import hyperspy.api as hs
import numpy as np

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)

_ALLOWED_ALGEBRAIC = ("SIRT_CUDA", "SART_CUDA")


def sirt_run_count(method: str, sweeps: int, n_angles: int) -> int:
    """ASTRA ``algorithm.run`` count for ``sweeps`` passes over all angles.

    ``SIRT_CUDA`` treats one ``run`` step as a full pass. ``SART_CUDA`` treats
    one ``run`` step as a single projection angle, so a full pass is
    ``n_angles`` steps (``IterativeTomography.m``).
    """
    name = str(method).upper()
    n_sweeps = int(sweeps)
    n_ang = int(n_angles)
    if n_sweeps < 1 or n_ang < 1:
        raise ValueError("sweeps and n_angles must be positive")
    if name == "SIRT_CUDA":
        return n_sweeps
    if name == "SART_CUDA":
        return n_sweeps * n_ang
    raise ValueError(
        "dart_algebraic must be SIRT_CUDA or SART_CUDA, got %r" % (method,)
    )


def validate_gray_levels(config: Dict[str, Any]) -> np.ndarray:
    """Return ascending finite gray levels. Missing or illegal values fail."""
    if "dart_gray_levels" not in config or config.get("dart_gray_levels") is None:
        raise ValueError("dart_gray_levels is required for DART")
    levels = np.asarray(config["dart_gray_levels"], dtype=np.float64).reshape(-1)
    if levels.size < 2 or not np.all(np.isfinite(levels)):
        raise ValueError(
            "dart_gray_levels must contain at least two finite values, got %r"
            % (config.get("dart_gray_levels"),)
        )
    if np.unique(levels).size != levels.size:
        raise ValueError("dart_gray_levels contains duplicates: %r" % (levels.tolist(),))
    return np.sort(levels)


def segment_nearest(image: np.ndarray, levels: np.ndarray) -> np.ndarray:
    """Map every pixel to the nearest gray level (midpoint thresholds)."""
    rho = np.asarray(levels, dtype=np.float64).reshape(-1)
    diff = np.abs(np.asarray(image, dtype=np.float64)[..., None] - rho)
    return rho[np.argmin(diff, axis=-1)]


def boundary_mask(labels: np.ndarray, connectivity: int = 8) -> np.ndarray:
    """True where a neighbor has a different label. Connectivity is 4 or 8."""
    if connectivity not in (4, 8):
        raise ValueError("dart_connectivity must be 4 or 8, got %r" % (connectivity,))
    lab = np.asarray(labels)
    edges = np.zeros(lab.shape, dtype=bool)
    shifts: List[Tuple[int, int]] = [(-1, 0), (1, 0), (0, -1), (0, 1)]
    if connectivity == 8:
        shifts.extend([(-1, -1), (-1, 1), (1, -1), (1, 1)])
    for di, dj in shifts:
        if di == 0 and dj == 0:
            continue
        src_r = slice(max(di, 0), lab.shape[0] + min(di, 0))
        src_c = slice(max(dj, 0), lab.shape[1] + min(dj, 0))
        dst_r = slice(max(-di, 0), lab.shape[0] + min(-di, 0))
        dst_c = slice(max(-dj, 0), lab.shape[1] + min(-dj, 0))
        differ = lab[dst_r, dst_c] != lab[src_r, src_c]
        edges[dst_r, dst_c] |= differ
    return edges


def free_pixel_mask(
    labels: np.ndarray,
    random_fraction: float,
    seed: int,
    connectivity: int = 8,
) -> np.ndarray:
    """Boundary pixels are free. Other pixels are freed with ``random_fraction``."""
    fraction = float(random_fraction)
    if not 0.0 <= fraction <= 1.0:
        raise ValueError("dart_random must be in [0, 1], got %r" % (random_fraction,))
    boundary = boundary_mask(labels, connectivity)
    rng = np.random.default_rng(int(seed))
    extra = rng.random(labels.shape) < fraction
    return boundary | extra


def slice_sinograms(proj: np.ndarray) -> np.ndarray:
    """``(n_angles, n_rows, n_cols)`` -> ``(n_rows, n_angles, n_cols)``."""
    data = np.asarray(proj)
    if data.ndim != 3:
        raise ValueError("tilt series must be (n_angles, n_rows, n_cols), got %s" % (data.shape,))
    return np.transpose(data, (1, 0, 2))


def stack_slices(slices: Sequence[np.ndarray]) -> np.ndarray:
    """Stack per-row images ``(n_cols, n_cols)`` into ``(n_rows, n_cols, n_cols)``."""
    return np.stack([np.asarray(s) for s in slices], axis=0)


class ParallelSliceSolver:
    """CUDA parallel-beam projector and SIRT/SART for one square slice size."""

    def __init__(self, angles_rad: np.ndarray, n_cols: int, method: str):
        import astra

        self.astra = astra
        self.method = str(method).upper()
        if self.method not in _ALLOWED_ALGEBRAIC:
            raise ValueError(
                "dart_algebraic must be SIRT_CUDA or SART_CUDA, got %r" % (method,)
            )
        self.n_angles = int(np.asarray(angles_rad).shape[0])
        self.n_cols = int(n_cols)
        angles = np.ascontiguousarray(angles_rad, dtype=np.float64)
        self.proj_geom = astra.create_proj_geom("parallel", 1.0, self.n_cols, angles)
        self.vol_geom = astra.create_vol_geom(self.n_cols, self.n_cols)
        self.sino_id = astra.data2d.create("-sino", self.proj_geom, 0)
        self.rec_id = astra.data2d.create("-vol", self.vol_geom, 0)
        cfg = astra.astra_dict(self.method)
        cfg["ProjectionDataId"] = self.sino_id
        cfg["ReconstructionDataId"] = self.rec_id
        self.alg_id = astra.algorithm.create(cfg)
        self._fp_id: Optional[int] = None
        self._bp_id: Optional[int] = None

    def close(self) -> None:
        astra = self.astra
        for alg in (self.alg_id, self._fp_id, self._bp_id):
            if alg is None:
                continue
            try:
                astra.algorithm.delete(alg)
            except Exception:
                pass
        for did in (self.sino_id, self.rec_id):
            try:
                astra.data2d.delete(did)
            except Exception:
                pass

    def _store_vol(self, image: np.ndarray) -> None:
        self.astra.data2d.store(
            self.rec_id, np.ascontiguousarray(image, dtype=np.float32)
        )

    def _store_sino(self, sino: np.ndarray) -> None:
        self.astra.data2d.store(
            self.sino_id, np.ascontiguousarray(sino, dtype=np.float32)
        )

    def project(self, image: np.ndarray) -> np.ndarray:
        astra = self.astra
        self._store_vol(image)
        if self._fp_id is None:
            cfg = astra.astra_dict("FP_CUDA")
            cfg["VolumeDataId"] = self.rec_id
            cfg["ProjectionDataId"] = self.sino_id
            self._fp_id = astra.algorithm.create(cfg)
        astra.algorithm.run(self._fp_id)
        sino = np.array(astra.data2d.get(self.sino_id), dtype=np.float64, copy=True)
        expected = (self.n_angles, self.n_cols)
        if sino.shape != expected:
            raise RuntimeError(
                "FP_CUDA sinogram shape %s != %s" % (sino.shape, expected)
            )
        return sino

    def backproject(self, sino: np.ndarray) -> np.ndarray:
        astra = self.astra
        self._store_sino(sino)
        self._store_vol(np.zeros((self.n_cols, self.n_cols), dtype=np.float32))
        if self._bp_id is None:
            cfg = astra.astra_dict("BP_CUDA")
            cfg["ProjectionDataId"] = self.sino_id
            cfg["ReconstructionDataId"] = self.rec_id
            self._bp_id = astra.algorithm.create(cfg)
        astra.algorithm.run(self._bp_id)
        rec = np.array(astra.data2d.get(self.rec_id), dtype=np.float64, copy=True)
        expected = (self.n_cols, self.n_cols)
        if rec.shape != expected:
            raise RuntimeError("BP_CUDA volume shape %s != %s" % (rec.shape, expected))
        return rec

    def reconstruct(self, sino: np.ndarray, volume: np.ndarray, sweeps: int) -> np.ndarray:
        astra = self.astra
        self._store_sino(sino)
        self._store_vol(volume)
        niter = sirt_run_count(self.method, sweeps, self.n_angles)
        astra.algorithm.run(self.alg_id, niter)
        rec = np.array(astra.data2d.get(self.rec_id), dtype=np.float64, copy=True)
        expected = (self.n_cols, self.n_cols)
        if rec.shape != expected:
            raise RuntimeError(
                "%s volume shape %s != %s" % (self.method, rec.shape, expected)
            )
        return rec


def _dart_options(config: Dict[str, Any]) -> Dict[str, Any]:
    method = str(config.get("dart_algebraic") or "SIRT_CUDA").upper()
    if method not in _ALLOWED_ALGEBRAIC:
        raise ValueError(
            "dart_algebraic must be SIRT_CUDA or SART_CUDA, got %r" % (method,)
        )
    connectivity = int(config.get("dart_connectivity", 8))
    if connectivity not in (4, 8):
        raise ValueError("dart_connectivity must be 4 or 8, got %r" % (connectivity,))
    return {
        "method": method,
        "init_iters": int(config.get("dart_init_iters", 50)),
        "outer_iters": int(config.get("dart_outer_iters", 20)),
        "inner_iters": int(config.get("dart_inner_iters", 5)),
        "random": float(config.get("dart_random", 0.1)),
        "seed": int(config.get("dart_seed", 0)),
        "connectivity": connectivity,
        "sigma": float(config.get("dart_smooth_sigma", 1.0)),
    }


def run_dart_slice(
    sino: np.ndarray,
    solver: ParallelSliceSolver,
    levels: np.ndarray,
    options: Dict[str, Any],
    *,
    row_seed: int,
) -> np.ndarray:
    """One detector row. ``sino`` is ``(n_angles, n_cols)``."""
    from scipy.ndimage import gaussian_filter

    n_cols = solver.n_cols
    vol = solver.reconstruct(
        sino, np.zeros((n_cols, n_cols), dtype=np.float64), options["init_iters"]
    )
    for outer in range(int(options["outer_iters"])):
        segmented = segment_nearest(vol, levels)
        free = free_pixel_mask(
            segmented,
            options["random"],
            int(row_seed) + outer,
            options["connectivity"],
        )
        fixed = ~free
        fixed_image = np.where(fixed, segmented, 0.0)
        residual = sino - solver.project(fixed_image)
        updated = np.where(free, vol, 0.0)
        for _ in range(int(options["inner_iters"])):
            updated[fixed] = 0.0
            updated = solver.reconstruct(residual, updated, sweeps=1)
            updated[fixed] = 0.0
        vol = updated + fixed_image
        drift = np.max(np.abs(vol[fixed] - segmented[fixed])) if np.any(fixed) else 0.0
        if float(drift) > 1e-4:
            raise RuntimeError(
                "DART fixed pixels drifted by %s after adding the fixed image back"
                % (drift,)
            )
        if options["sigma"] > 0.0 and outer + 1 < int(options["outer_iters"]):
            vol = gaussian_filter(vol, sigma=float(options["sigma"]))
    return vol


def run_dart(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    from et_dflow.infrastructure.algorithms.native_astra import _require_nvidia_gpu

    levels = validate_gray_levels(config)
    options = _dart_options(config)
    proj = np.asarray(tilt_series.data, dtype=np.float32)
    rows = slice_sinograms(proj)
    n_rows, n_angles, n_cols = rows.shape
    angles_deg = extract_tilt_angles_degrees(tilt_series, config)
    if int(angles_deg.size) != n_angles:
        raise ValueError(
            "Tilt angle count %s != n_tilts %s" % (angles_deg.size, n_angles)
        )
    angles = np.deg2rad(angles_deg.astype(np.float64))
    gpu_line = _require_nvidia_gpu()
    print("DART GPU: %s" % gpu_line)
    print(
        "DART rows=%s cols=%s angles=%s method=%s gray_levels=%s"
        % (n_rows, n_cols, n_angles, options["method"], levels.tolist())
    )

    solver = ParallelSliceSolver(angles, n_cols, options["method"])
    slices: List[np.ndarray] = []
    try:
        for row in range(n_rows):
            rec = run_dart_slice(
                np.asarray(rows[row], dtype=np.float64),
                solver,
                levels,
                options,
                row_seed=int(options["seed"]) + row * 10007,
            )
            slices.append(rec)
            if row % 32 == 0 or row + 1 == n_rows:
                print("DART row %s/%s" % (row + 1, n_rows))
    finally:
        solver.close()

    volume = stack_slices(slices).astype(np.float32, copy=False)
    rec_sig = numpy_volume_to_signal2d(volume, title="DART reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "dart")
    rec_sig.metadata.set_item("et_dflow.dart_gray_levels", levels.tolist())
    rec_sig.metadata.set_item("et_dflow.dart_algebraic", options["method"])
    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="dart",
        start_time=start_time,
        extra_metadata={
            "dart_gray_levels": levels.tolist(),
            "dart_algebraic": options["method"],
            "dart_random": options["random"],
            "dart_seed": options["seed"],
            "dart_outer_iters": options["outer_iters"],
            "dart_inner_iters": options["inner_iters"],
            "dart_connectivity": options["connectivity"],
        },
    )
