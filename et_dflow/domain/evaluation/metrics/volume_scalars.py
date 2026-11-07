"""
Scalar volume metrics computed from reconstruction and ground truth.

Returns None when a metric cannot be computed (shape mismatch, empty mask,
zero variance). Handlers turn None into an empty metrics dict.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from scipy.ndimage import gaussian_filter


_MAX_ELONGATION_POINTS = 2_000_000
_MIN_MASK_VOXELS = 10


def _as_float_arrays(
    recon: np.ndarray,
    gt: np.ndarray,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    recon_data = np.asarray(recon, dtype=np.float64)
    gt_data = np.asarray(gt, dtype=np.float64)
    if recon_data.shape != gt_data.shape:
        return None
    return recon_data, gt_data


def pearson_r2(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """Pearson R² between flattened reconstruction and ground truth."""
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    x = recon_data.ravel()
    y = gt_data.ravel()
    if x.size == 0:
        return None
    x_var = np.var(x)
    y_var = np.var(y)
    if x_var <= 0.0 or y_var <= 0.0:
        return None
    corr = np.corrcoef(x, y)[0, 1]
    if not np.isfinite(corr):
        return None
    return float(corr * corr)


def _axis_ratio(volume: np.ndarray, rng: np.random.Generator) -> Optional[float]:
    """sqrt(λ_max / λ_min) of the covariance of voxels above the 90th percentile."""
    if volume.size == 0:
        return None
    threshold = float(np.percentile(volume, 90.0))
    coords = np.argwhere(volume > threshold)
    if coords.shape[0] < _MIN_MASK_VOXELS:
        return None
    if coords.shape[0] > _MAX_ELONGATION_POINTS:
        idx = rng.choice(coords.shape[0], size=_MAX_ELONGATION_POINTS, replace=False)
        coords = coords[idx]
    centered = coords.astype(np.float64) - coords.mean(axis=0, keepdims=True)
    if centered.shape[0] < 2:
        return None
    cov = np.cov(centered, rowvar=False)
    if cov.ndim == 0:
        return None
    eigenvalues = np.linalg.eigvalsh(cov)
    eigenvalues = np.sort(np.maximum(eigenvalues, 0.0))
    lam_min = float(eigenvalues[0])
    lam_max = float(eigenvalues[-1])
    if lam_min <= 0.0:
        return None
    return float(np.sqrt(lam_max / lam_min))


def elongation_ratio(
    recon: np.ndarray,
    gt: np.ndarray,
    seed: int = 0,
) -> Optional[float]:
    """
    Reconstruction axis ratio divided by ground-truth axis ratio.

    1.0 means the reconstruction has the same anisotropy as the ground truth.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    rng = np.random.default_rng(seed)
    recon_ratio = _axis_ratio(recon_data, rng)
    gt_ratio = _axis_ratio(gt_data, rng)
    if recon_ratio is None or gt_ratio is None or gt_ratio <= 0.0:
        return None
    return float(recon_ratio / gt_ratio)


def edge_rise_pixels(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    10%–90% rise distance along the steepest ground-truth gradient, in pixels.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    if gt_data.ndim < 1:
        return None

    # Smooth slightly so a single noisy voxel does not dominate the gradient pick.
    gt_smooth = gaussian_filter(gt_data, sigma=0.5)
    grads = np.gradient(gt_smooth)
    grad_mag = np.sqrt(sum(g * g for g in grads))
    max_idx = int(np.argmax(grad_mag))
    if float(grad_mag.flat[max_idx]) <= 0.0:
        return None

    peak = np.unravel_index(max_idx, gt_data.shape)
    direction = np.array([float(g.flat[max_idx]) for g in grads], dtype=np.float64)
    norm = float(np.linalg.norm(direction))
    if norm <= 0.0:
        return None
    direction /= norm

    # Sample a line long enough to cross the volume along the dominant axis.
    half_len = int(max(gt_data.shape))
    offsets = np.arange(-half_len, half_len + 1, dtype=np.float64)
    samples = []
    for t in offsets:
        point = np.asarray(peak, dtype=np.float64) + t * direction
        if np.any(point < 0) or np.any(point >= np.asarray(gt_data.shape)):
            continue
        # Nearest-neighbor sample (integer coordinates after rounding).
        idx = tuple(int(round(c)) for c in point)
        if any(i < 0 or i >= s for i, s in zip(idx, recon_data.shape)):
            continue
        samples.append((float(t), float(recon_data[idx])))

    if len(samples) < 4:
        return None

    samples.sort(key=lambda item: item[0])
    positions = np.array([s[0] for s in samples], dtype=np.float64)
    intensities = np.array([s[1] for s in samples], dtype=np.float64)
    lo = float(np.percentile(intensities, 1.0))
    hi = float(np.percentile(intensities, 99.0))
    if hi <= lo:
        return None
    normalized = (intensities - lo) / (hi - lo)

    def _first_crossing(target: float) -> Optional[float]:
        for i in range(1, normalized.size):
            a = normalized[i - 1]
            b = normalized[i]
            if (a < target <= b) or (a > target >= b):
                if b == a:
                    return float(positions[i])
                frac = (target - a) / (b - a)
                return float(positions[i - 1] + frac * (positions[i] - positions[i - 1]))
        return None

    t10 = _first_crossing(0.1)
    t90 = _first_crossing(0.9)
    if t10 is None or t90 is None:
        return None
    rise = abs(t90 - t10)
    if rise <= 0.0:
        return None
    return float(rise)
