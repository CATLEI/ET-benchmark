"""TVR-DART: soft segmentation, automatic gray values, Huber regularization.

The soft step matches the CWI definition: the normalized background gray value
stays 0, and each transition is

``delta * expit(2 * (K / delta) * (latent - midpoint))``.

The penalty is the Huber norm with epsilon 1e-4, not isotropic TV. Gray values
and per-transition ``K`` are estimated on the three detector rows with the
largest initial SIRT mass, alternating short latent updates and parameter
updates. The full volume is then reconstructed row by row with in-plane Huber.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Tuple

import hyperspy.api as hs
import numpy as np
from scipy.special import expit

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.native_dart import (
    ParallelSliceSolver,
    slice_sinograms,
    stack_slices,
)


def validate_n_gray(config: Dict[str, Any]) -> int:
    """Require an integer phase count of at least 2, including background."""
    if "tvr_n_gray" not in config or config.get("tvr_n_gray") is None:
        raise ValueError("tvr_n_gray is required for TVR-DART")
    raw = config["tvr_n_gray"]
    if isinstance(raw, bool) or isinstance(raw, float) and not float(raw).is_integer():
        raise ValueError("tvr_n_gray must be an integer >= 2, got %r" % (raw,))
    try:
        n_gray = int(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError("tvr_n_gray must be an integer >= 2, got %r" % (raw,)) from exc
    if n_gray < 2:
        raise ValueError("tvr_n_gray must be an integer >= 2, got %r" % (raw,))
    return n_gray


def soft_segment(
    latent: np.ndarray, gray_values: Sequence[float], sharpness: Sequence[float]
) -> np.ndarray:
    """CWI soft segmentation. ``gray_values[0]`` is the background level."""
    rho = np.asarray(gray_values, dtype=np.float64).reshape(-1)
    gain = np.asarray(sharpness, dtype=np.float64).reshape(-1)
    if gain.size != rho.size - 1:
        raise ValueError(
            "sharpness length %s != n_gray - 1 (%s)" % (gain.size, rho.size - 1)
        )
    out = np.full(np.shape(latent), rho[0], dtype=np.float64)
    x = np.asarray(latent, dtype=np.float64)
    for i in range(rho.size - 1):
        delta = float(rho[i + 1] - rho[i])
        if abs(delta) < 1e-12:
            continue
        midpoint = 0.5 * (float(rho[i]) + float(rho[i + 1]))
        kg = float(gain[i]) / delta
        out = out + delta * expit(2.0 * kg * (x - midpoint))
    return out


def soft_segment_dx(
    latent: np.ndarray, gray_values: Sequence[float], sharpness: Sequence[float]
) -> np.ndarray:
    """Derivative of :func:`soft_segment` with respect to ``latent``."""
    rho = np.asarray(gray_values, dtype=np.float64).reshape(-1)
    gain = np.asarray(sharpness, dtype=np.float64).reshape(-1)
    deriv = np.zeros(np.shape(latent), dtype=np.float64)
    x = np.asarray(latent, dtype=np.float64)
    for i in range(rho.size - 1):
        delta = float(rho[i + 1] - rho[i])
        if abs(delta) < 1e-12:
            continue
        midpoint = 0.5 * (float(rho[i]) + float(rho[i + 1]))
        kg = float(gain[i]) / delta
        gate = expit(2.0 * kg * (x - midpoint))
        deriv = deriv + delta * gate * (1.0 - gate) * (2.0 * kg)
    return deriv


def _forward_differences(image: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    dx = np.zeros(image.shape, dtype=np.float64)
    dy = np.zeros(image.shape, dtype=np.float64)
    dx[:, :-1] = image[:, 1:] - image[:, :-1]
    dy[:-1, :] = image[1:, :] - image[:-1, :]
    return dx, dy


def huber_value(image: np.ndarray, epsilon: float) -> float:
    """Isotropic Huber penalty. ``g <= epsilon`` is quadratic, otherwise linear."""
    dx, dy = _forward_differences(np.asarray(image, dtype=np.float64))
    magnitude = np.sqrt(dx * dx + dy * dy)
    eps = float(epsilon)
    small = magnitude <= eps
    penalty = np.empty(magnitude.shape, dtype=np.float64)
    penalty[small] = magnitude[small] ** 2 / (2.0 * eps)
    penalty[~small] = magnitude[~small] - eps / 2.0
    return float(np.sum(penalty))


def huber_grad(image: np.ndarray, epsilon: float) -> np.ndarray:
    """Gradient of :func:`huber_value` with respect to the image."""
    data = np.asarray(image, dtype=np.float64)
    dx, dy = _forward_differences(data)
    magnitude = np.sqrt(dx * dx + dy * dy)
    eps = float(epsilon)
    small = magnitude <= eps
    weight_x = np.empty_like(dx)
    weight_y = np.empty_like(dy)
    weight_x[small] = dx[small] / eps
    weight_y[small] = dy[small] / eps
    big = ~small
    weight_x[big] = dx[big] / magnitude[big]
    weight_y[big] = dy[big] / magnitude[big]
    grad = np.zeros_like(data)
    grad[:, :-1] -= weight_x[:, :-1]
    grad[:, 1:] += weight_x[:, :-1]
    grad[:-1, :] -= weight_y[:-1, :]
    grad[1:, :] += weight_y[:-1, :]
    return grad


def estimate_row_range(
    volume: np.ndarray, override: Optional[Sequence[int]] = None
) -> Tuple[int, int]:
    """Inclusive detector-row range used to estimate gray values.

    The default is the row with the largest summed initial reconstruction and
    one row on either side. ``override`` is ``[start, end]``.
    """
    n_rows = int(volume.shape[0])
    if override is not None:
        if len(override) != 2:
            raise ValueError("tvr_estimate_rows must be [start, end]")
        start = max(0, min(n_rows - 1, int(override[0])))
        end = max(0, min(n_rows - 1, int(override[1])))
        if end < start:
            start, end = end, start
        return start, end
    energy = np.sum(np.asarray(volume, dtype=np.float64), axis=(1, 2))
    center = int(np.argmax(energy))
    return max(0, center - 1), min(n_rows - 1, center + 1)


def _pack_params(gray_values: np.ndarray, sharpness: np.ndarray) -> np.ndarray:
    return np.concatenate([np.asarray(gray_values, dtype=np.float64)[1:], sharpness])


def _unpack_params(packed: np.ndarray, n_gray: int) -> Tuple[np.ndarray, np.ndarray]:
    n_free = int(n_gray) - 1
    rho = np.concatenate([[0.0], np.asarray(packed[:n_free], dtype=np.float64)])
    gain = np.asarray(packed[n_free:], dtype=np.float64)
    return rho, gain


def _slice_objective(
    latent: np.ndarray,
    sino: np.ndarray,
    solver: ParallelSliceSolver,
    gray_values: np.ndarray,
    sharpness: np.ndarray,
    lamb: float,
    epsilon: float,
) -> Tuple[float, np.ndarray]:
    segmented = soft_segment(latent, gray_values, sharpness)
    projected = solver.project(segmented)
    residual = projected - sino
    fit = float(np.sum(residual * residual))
    penalty = huber_value(segmented, epsilon)
    grad_seg = 2.0 * solver.backproject(residual) + lamb * huber_grad(segmented, epsilon)
    grad = grad_seg * soft_segment_dx(latent, gray_values, sharpness)
    return fit + lamb * penalty, grad


def _fit_latent(
    latent: np.ndarray,
    sino: np.ndarray,
    solver: ParallelSliceSolver,
    gray_values: np.ndarray,
    sharpness: np.ndarray,
    lamb: float,
    epsilon: float,
    maxiter: int,
) -> np.ndarray:
    from scipy.optimize import minimize

    shape = latent.shape

    def objective(flat: np.ndarray) -> Tuple[float, np.ndarray]:
        value, grad = _slice_objective(
            flat.reshape(shape), sino, solver, gray_values, sharpness, lamb, epsilon
        )
        return value, grad.ravel()

    result = minimize(
        objective,
        np.asarray(latent, dtype=np.float64).ravel(),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": int(maxiter), "disp": False},
    )
    return result.x.reshape(shape)


def _fit_slab_latent(
    latents: np.ndarray,
    sinos: np.ndarray,
    solver: ParallelSliceSolver,
    gray_values: np.ndarray,
    sharpness: np.ndarray,
    lamb: float,
    epsilon: float,
    maxiter: int,
) -> np.ndarray:
    from scipy.optimize import minimize

    n_slab = latents.shape[0]
    shape = latents.shape[1:]

    def objective(flat: np.ndarray) -> Tuple[float, np.ndarray]:
        images = flat.reshape((n_slab,) + shape)
        total = 0.0
        grads = np.zeros_like(images)
        for index in range(n_slab):
            value, grad = _slice_objective(
                images[index],
                sinos[index],
                solver,
                gray_values,
                sharpness,
                lamb,
                epsilon,
            )
            total += value
            grads[index] = grad
        return total, grads.ravel()

    result = minimize(
        objective,
        np.asarray(latents, dtype=np.float64).ravel(),
        method="L-BFGS-B",
        jac=True,
        options={"maxiter": int(maxiter), "disp": False},
    )
    return result.x.reshape(latents.shape)


def _fit_params(
    packed0: np.ndarray,
    latents: np.ndarray,
    sinos: np.ndarray,
    solver: ParallelSliceSolver,
    n_gray: int,
    lamb: float,
    epsilon: float,
    maxiter: int,
) -> np.ndarray:
    from scipy.optimize import minimize

    def objective(packed: np.ndarray) -> float:
        gray_values, sharpness = _unpack_params(packed, n_gray)
        total = 0.0
        for index in range(latents.shape[0]):
            segmented = soft_segment(latents[index], gray_values, sharpness)
            projected = solver.project(segmented)
            residual = projected - sinos[index]
            total += float(np.sum(residual * residual))
            total += lamb * huber_value(segmented, epsilon)
        return total

    result = minimize(
        objective,
        np.asarray(packed0, dtype=np.float64),
        method="L-BFGS-B",
        options={"maxiter": int(maxiter), "disp": False},
    )
    return result.x


def run_tvr_dart(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    from et_dflow.infrastructure.algorithms.native_astra import _require_nvidia_gpu

    n_gray = validate_n_gray(config)
    lamb = float(config.get("tvr_lambda", 10.0))
    epsilon = float(config.get("tvr_huber_epsilon", 1e-4))
    init_iters = int(config.get("tvr_init_sirt_iters", 50))
    estimate_iters = int(config.get("tvr_estimate_iters", 20))
    niter = int(config.get("tvr_niter", 50))
    sharpness0 = float(config.get("tvr_sharpness", 4.0))

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
    print("TVR-DART GPU: %s" % gpu_line)

    solver = ParallelSliceSolver(angles, n_cols, "SIRT_CUDA")
    try:
        initial = np.zeros((n_rows, n_cols, n_cols), dtype=np.float64)
        blank = np.zeros((n_cols, n_cols), dtype=np.float64)
        for row in range(n_rows):
            initial[row] = solver.reconstruct(
                np.asarray(rows[row], dtype=np.float64), blank, init_iters
            )
        scale = float(np.max(initial))
        if scale <= 0.0:
            raise RuntimeError("TVR-DART initial SIRT maximum is %s" % (scale,))
        initial /= scale
        sinos = np.asarray(rows, dtype=np.float64) / scale

        row_start, row_end = estimate_row_range(initial, config.get("tvr_estimate_rows"))
        print(
            "TVR-DART estimate rows %s:%s n_gray=%s scale=%s"
            % (row_start, row_end, n_gray, scale)
        )
        gray_values = np.linspace(0.0, 1.0, n_gray)
        sharpness = np.full(n_gray - 1, sharpness0, dtype=np.float64)
        slab_latent = initial[row_start : row_end + 1].copy()
        slab_sino = sinos[row_start : row_end + 1]
        for _ in range(estimate_iters):
            previous = gray_values.copy()
            slab_latent = _fit_slab_latent(
                slab_latent,
                slab_sino,
                solver,
                gray_values,
                sharpness,
                lamb,
                epsilon,
                maxiter=2,
            )
            packed = _fit_params(
                _pack_params(gray_values, sharpness),
                slab_latent,
                slab_sino,
                solver,
                n_gray,
                lamb,
                epsilon,
                maxiter=5,
            )
            gray_values, sharpness = _unpack_params(packed, n_gray)
            denom = max(float(np.sum(np.abs(previous))), 1e-12)
            change = float(np.sum(np.abs(gray_values - previous))) / denom
            print("TVR-DART gray %s rel_change=%s" % (gray_values.tolist(), change))
            if change < 1e-3:
                break

        slices: List[np.ndarray] = []
        for row in range(n_rows):
            latent = _fit_latent(
                initial[row],
                sinos[row],
                solver,
                gray_values,
                sharpness,
                lamb,
                epsilon,
                maxiter=niter,
            )
            slices.append(soft_segment(latent, gray_values, sharpness) * scale)
            if row % 32 == 0 or row + 1 == n_rows:
                print("TVR-DART row %s/%s" % (row + 1, n_rows))
    finally:
        solver.close()

    volume = stack_slices(slices).astype(np.float32, copy=False)
    gray_physical = (gray_values * scale).tolist()
    rec_sig = numpy_volume_to_signal2d(volume, title="TVR-DART reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "tvr_dart")
    rec_sig.metadata.set_item("et_dflow.tvr_gray_values", gray_physical)
    rec_sig.metadata.set_item("et_dflow.tvr_sharpness", sharpness.tolist())
    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="tvr_dart",
        start_time=start_time,
        extra_metadata={
            "tvr_n_gray": n_gray,
            "tvr_gray_values": gray_physical,
            "tvr_sharpness": sharpness.tolist(),
            "tvr_lambda": lamb,
            "tvr_huber_epsilon": epsilon,
            "tvr_estimate_rows": [row_start, row_end],
        },
    )
