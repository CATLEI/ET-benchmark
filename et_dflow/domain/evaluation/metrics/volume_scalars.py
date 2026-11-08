"""
Scalar volume metrics computed from reconstruction and ground truth.

Returns None when a metric cannot be computed (shape mismatch, empty mask,
zero variance). Handlers turn None into an empty metrics dict.
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
from scipy.ndimage import (
    binary_erosion,
    distance_transform_edt,
    gaussian_filter,
    label,
)


_MAX_ELONGATION_POINTS = 2_000_000
_MAX_HAUSDORFF_SURFACE = 250_000
_MAX_PSD_SAMPLES = 2_000_000
_MIN_MASK_VOXELS = 10
_PSD_BINS = 32


def _as_float_arrays(
    recon: np.ndarray,
    gt: np.ndarray,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    recon_data = np.asarray(recon, dtype=np.float64)
    gt_data = np.asarray(gt, dtype=np.float64)
    if recon_data.shape != gt_data.shape:
        return None
    return recon_data, gt_data


def solid_threshold_from_gt(gt: np.ndarray) -> float:
    """Mid-range threshold for solid vs void on GT-derived intensity."""
    gt_data = np.asarray(gt, dtype=np.float64)
    lo = float(gt_data.min())
    hi = float(gt_data.max())
    if hi <= lo:
        return lo
    return 0.5 * (lo + hi)


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


def _solid_mask(volume: np.ndarray, threshold: Optional[float] = None) -> np.ndarray:
    """Boolean solid mask. Prefer mid-range when the intensity is near-binary."""
    vol = np.asarray(volume, dtype=np.float64)
    if threshold is None:
        lo = float(vol.min())
        hi = float(vol.max())
        if hi <= lo:
            return np.zeros(vol.shape, dtype=bool)
        # Near-binary volumes (common in simulated porous GT) make percentile
        # masks empty when the 90th percentile equals the solid plateau.
        unique = np.unique(vol)
        if unique.size <= 8:
            threshold = 0.5 * (lo + hi)
        else:
            threshold = float(np.percentile(vol, 90.0))
            if not np.any(vol > threshold):
                threshold = 0.5 * (lo + hi)
    return vol >= float(threshold)


def _axis_ratio(volume: np.ndarray, rng: np.random.Generator) -> Optional[float]:
    """sqrt(λ_max / λ_min) of the covariance of solid-phase voxels."""
    if volume.size == 0:
        return None
    coords = np.argwhere(_solid_mask(volume))
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
    Hyper-Tomo leaderboard column ``Elongation`` (closer to 1 is better for
    missing-wedge stretch).
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


def dice_coefficient(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """Dice overlap of solid phases. Threshold taken from GT mid-range."""
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    pred = _solid_mask(recon_data, thr)
    target = _solid_mask(gt_data, thr)
    intersection = float(np.count_nonzero(pred & target))
    denom = float(np.count_nonzero(pred) + np.count_nonzero(target))
    if denom <= 0.0:
        return 1.0
    return float(2.0 * intersection / denom)


def hausdorff95_px(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    95th-percentile directed Hausdorff distance of solid surfaces (voxels).

    Uses Euclidean distance transform on the GT solid complement, sampled on
    the reconstruction surface. Smaller is better.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    pred = _solid_mask(recon_data, thr)
    target = _solid_mask(gt_data, thr)
    if not np.any(pred) or not np.any(target):
        return None
    pred_surface = pred & ~binary_erosion(pred, iterations=1, border_value=0)
    if not np.any(pred_surface):
        pred_surface = pred
    # Distance to nearest GT solid voxel from every non-solid GT voxel, then
    # read distances on the reconstruction surface.
    dt = distance_transform_edt(~target)
    dists = dt[pred_surface]
    if dists.size == 0:
        return None
    if dists.size > _MAX_HAUSDORFF_SURFACE:
        rng = np.random.default_rng(0)
        dists = rng.choice(dists, size=_MAX_HAUSDORFF_SURFACE, replace=False)
    value = float(np.percentile(dists, 95.0))
    if not np.isfinite(value):
        return None
    return value


def porosity_abs_error(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """Absolute void-fraction error using the GT mid-range solid threshold."""
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    gt_porosity = 1.0 - float(np.mean(_solid_mask(gt_data, thr)))
    recon_porosity = 1.0 - float(np.mean(_solid_mask(recon_data, thr)))
    return float(abs(recon_porosity - gt_porosity))


def _void_clearance_radii(
    void_mask: np.ndarray,
    rng: np.random.Generator,
) -> np.ndarray:
    """Euclidean clearance radius (voxels) at every void voxel."""
    if not np.any(void_mask):
        return np.zeros(0, dtype=np.float64)
    radii = distance_transform_edt(void_mask)[void_mask].astype(np.float64, copy=False)
    if radii.size > _MAX_PSD_SAMPLES:
        radii = rng.choice(radii, size=_MAX_PSD_SAMPLES, replace=False)
    return radii


def psd_wasserstein_px(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    1D Wasserstein-1 distance between void clearance-radius histograms (pixels).

    Radii come from the Euclidean distance transform of the void phase. Shared
    bins are taken from the joint max radius. Smaller is better.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    rng = np.random.default_rng(0)
    r_gt = _void_clearance_radii(~_solid_mask(gt_data, thr), rng)
    r_recon = _void_clearance_radii(~_solid_mask(recon_data, thr), rng)
    if r_gt.size == 0 and r_recon.size == 0:
        return 0.0
    if r_gt.size == 0 or r_recon.size == 0:
        return None
    r_max = float(max(r_gt.max(), r_recon.max(), 1.0))
    bins = np.linspace(0.0, r_max, _PSD_BINS + 1)
    h_gt, _ = np.histogram(r_gt, bins=bins)
    h_recon, _ = np.histogram(r_recon, bins=bins)
    if h_gt.sum() <= 0 or h_recon.sum() <= 0:
        return None
    p_gt = h_gt.astype(np.float64) / float(h_gt.sum())
    p_recon = h_recon.astype(np.float64) / float(h_recon.sum())
    dx = float(bins[1] - bins[0])
    w1 = float(np.sum(np.abs(np.cumsum(p_gt) - np.cumsum(p_recon))) * dx)
    if not np.isfinite(w1):
        return None
    return w1


def _specific_surface_area(solid: np.ndarray) -> Optional[float]:
    """Surface voxels per volume voxel (6-connected solid boundary)."""
    if solid.size == 0:
        return None
    if not np.any(solid):
        return 0.0
    surface = solid & ~binary_erosion(solid, iterations=1, border_value=0)
    return float(np.count_nonzero(surface) / solid.size)


def ssa_rel_error(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    Relative error of specific surface area (solid boundary voxels / volume).

    ``|SSA_recon - SSA_gt| / max(SSA_gt, eps)``. Smaller is better.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    ssa_gt = _specific_surface_area(_solid_mask(gt_data, thr))
    ssa_recon = _specific_surface_area(_solid_mask(recon_data, thr))
    if ssa_gt is None or ssa_recon is None:
        return None
    denom = max(abs(ssa_gt), 1e-12)
    return float(abs(ssa_recon - ssa_gt) / denom)


def _largest_void_cc_fraction(void_mask: np.ndarray) -> float:
    """Fraction of void voxels that lie in the largest void component."""
    void_count = int(np.count_nonzero(void_mask))
    if void_count == 0:
        return 0.0
    labeled, n_features = label(void_mask)
    if n_features <= 0:
        return 0.0
    counts = np.bincount(labeled.ravel())
    if counts.size <= 1:
        return 0.0
    return float(counts[1:].max() / void_count)


def void_cc_fraction_abs_error(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    Absolute error of the largest-void connected-component fraction.

    Captures connectivity / fragmentation of the pore network. Smaller is better.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    frac_gt = _largest_void_cc_fraction(~_solid_mask(gt_data, thr))
    frac_recon = _largest_void_cc_fraction(~_solid_mask(recon_data, thr))
    return float(abs(frac_recon - frac_gt))


def _percolates(mask: np.ndarray, axis: int) -> bool:
    """True if a connected component touches both faces along ``axis``."""
    if mask.ndim != 3 or not np.any(mask):
        return False
    labeled, n_features = label(mask)
    if n_features <= 0:
        return False
    front = np.unique(np.take(labeled, 0, axis=axis))
    back = np.unique(np.take(labeled, -1, axis=axis))
    front = front[front > 0]
    back = back[back > 0]
    if front.size == 0 or back.size == 0:
        return False
    return bool(np.intersect1d(front, back).size > 0)


def percolation_mismatch(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    """
    Fraction of axes (0,1,2) where void percolation disagrees with GT.

    0 means the same open/closed pore behaviour on all three axes.
    """
    arrays = _as_float_arrays(recon, gt)
    if arrays is None:
        return None
    recon_data, gt_data = arrays
    thr = solid_threshold_from_gt(gt_data)
    void_gt = ~_solid_mask(gt_data, thr)
    void_recon = ~_solid_mask(recon_data, thr)
    mismatches = 0
    for axis in range(3):
        if _percolates(void_gt, axis) != _percolates(void_recon, axis):
            mismatches += 1
    return float(mismatches / 3.0)


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
