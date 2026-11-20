"""
Protocol bypass metrics (Track A/B/C scientific scores).

These functions are intentionally NOT wired into ``chain.py``. Existing
workflow metric names and formulas stay unchanged. Call from
``scripts/reeval_protocol_metrics.py`` or other offline tools.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence, Tuple

import numpy as np

_MIN_VOXELS = 16


def _as_float_pair(
    recon: Any,
    gt: Any,
) -> Optional[Tuple[np.ndarray, np.ndarray]]:
    recon_data = np.asarray(getattr(recon, "data", recon), dtype=np.float64)
    gt_data = np.asarray(getattr(gt, "data", gt), dtype=np.float64)
    if recon_data.shape != gt_data.shape or recon_data.size < _MIN_VOXELS:
        return None
    return recon_data, gt_data


def affine_intensity_align(
    recon: np.ndarray,
    gt: np.ndarray,
) -> Tuple[np.ndarray, float, float]:
    """OLS fit ``a * recon + b ≈ gt``. Returns aligned volume, a, b."""
    x = np.asarray(recon, dtype=np.float64).ravel()
    y = np.asarray(gt, dtype=np.float64).ravel()
    x_var = float(np.var(x))
    if x_var <= 0.0 or not np.isfinite(x_var):
        return np.asarray(recon, dtype=np.float64), 1.0, 0.0
    # Solve [x, 1] @ [a, b] = y
    a = float(np.cov(x, y, bias=True)[0, 1] / x_var)
    b = float(np.mean(y) - a * np.mean(x))
    if not np.isfinite(a):
        a, b = 1.0, 0.0
    aligned = a * np.asarray(recon, dtype=np.float64) + b
    return aligned, a, b


def pearson_cc(recon: np.ndarray, gt: np.ndarray) -> Optional[float]:
    arrays = _as_float_pair(recon, gt)
    if arrays is None:
        return None
    x, y = arrays[0].ravel(), arrays[1].ravel()
    if float(np.var(x)) <= 0.0 or float(np.var(y)) <= 0.0:
        return None
    corr = float(np.corrcoef(x, y)[0, 1])
    return corr if np.isfinite(corr) else None


def ssim_global(
    recon: np.ndarray,
    gt: np.ndarray,
) -> Optional[float]:
    """
    Global SSIM on flattened volumes (same simplified formula as chain.py).

    Prefer this over skimage so protocol bypass works without scikit-image.
    """
    arrays = _as_float_pair(recon, gt)
    if arrays is None:
        return None
    recon_flat = arrays[0].ravel()
    gt_flat = arrays[1].ravel()
    c1 = 0.01 ** 2
    c2 = 0.03 ** 2
    mu1 = float(np.mean(recon_flat))
    mu2 = float(np.mean(gt_flat))
    sigma1_sq = float(np.var(recon_flat))
    sigma2_sq = float(np.var(gt_flat))
    sigma12 = float(np.mean((recon_flat - mu1) * (gt_flat - mu2)))
    numerator = (2.0 * mu1 * mu2 + c1) * (2.0 * sigma12 + c2)
    denominator = (mu1 ** 2 + mu2 ** 2 + c1) * (sigma1_sq + sigma2_sq + c2)
    if denominator <= 0.0:
        return None
    val = numerator / denominator
    return float(val) if np.isfinite(val) else None


# Back-compat alias used by early drafts / tests.
ssim_3d_mean = ssim_global


def affine_aligned_ssim_cc(
    recon: Any,
    gt: Any,
) -> Dict[str, Any]:
    arrays = _as_float_pair(recon, gt)
    if arrays is None:
        return {}
    recon_data, gt_data = arrays
    aligned, scale, offset = affine_intensity_align(recon_data, gt_data)
    out: Dict[str, Any] = {
        "protocol_affine_scale": float(scale),
        "protocol_affine_offset": float(offset),
    }
    cc = pearson_cc(aligned, gt_data)
    if cc is not None:
        out["protocol_affine_cc"] = cc
    ssim_v = ssim_global(aligned, gt_data)
    if ssim_v is not None:
        out["protocol_affine_ssim"] = ssim_v
    return out


def missing_wedge_mask(
    shape: Sequence[int],
    tilt_min_deg: float,
    tilt_max_deg: float,
    tilt_axis: str = "y",
) -> np.ndarray:
    """
    Boolean mask True inside the missing-wedge Fourier region.

    Assumes single-axis tilt about ``tilt_axis`` (default y). The measured
    wedge in the xz Fourier plane spans angles within [tilt_min, tilt_max]
    from the optical axis convention used by the aligned-model stacks
    (±α around 0 with beam along z).
    """
    nz, ny, nx = (int(s) for s in shape)
    kz = np.fft.fftfreq(nz)
    ky = np.fft.fftfreq(ny)
    kx = np.fft.fftfreq(nx)
    Kz, Ky, Kx = np.meshgrid(kz, ky, kx, indexing="ij")

    # Angle from z-axis in the plane perpendicular to tilt axis.
    if tilt_axis.lower() == "y":
        rho = np.sqrt(Kx ** 2 + Kz ** 2)
        # Angle of radial vector in xz: 0 = +z (beam), ±90 = ±x.
        ang = np.degrees(np.arctan2(Kx, Kz))
    elif tilt_axis.lower() == "x":
        rho = np.sqrt(Ky ** 2 + Kz ** 2)
        ang = np.degrees(np.arctan2(Ky, Kz))
    else:
        raise ValueError("tilt_axis must be 'x' or 'y'")

    # Measured region: |ang| within tilt range (with wrap handling for ±).
    # For tilt in [α_min, α_max], Fourier slices cover that angular sector.
    measured = (ang >= tilt_min_deg) & (ang <= tilt_max_deg)
    # Also cover the opposite half-plane (central slice theorem symmetry).
    measured |= (ang >= tilt_min_deg + 180.0) & (ang <= tilt_max_deg + 180.0)
    measured |= (ang >= tilt_min_deg - 180.0) & (ang <= tilt_max_deg - 180.0)

    missing = ~measured
    missing &= rho > 0  # exclude DC
    return missing


def _complex_cc(a: np.ndarray, b: np.ndarray) -> Optional[float]:
    if a.size < _MIN_VOXELS:
        return None
    num = np.vdot(a, b)
    den = np.linalg.norm(a) * np.linalg.norm(b)
    if den <= 0.0:
        return None
    val = float(np.real(num / den))
    return val if np.isfinite(val) else None


def wedge_in_out_cc(
    recon: Any,
    gt: Any,
    tilt_min_deg: float,
    tilt_max_deg: float,
    tilt_axis: str = "y",
) -> Dict[str, Any]:
    """
    Correlation in Fourier space inside / outside the missing wedge.

    Both volumes are FFT'd; CC is computed on complex coefficients in each
    region (DeepDeWedge-style separation of fill vs fidelity).
    """
    arrays = _as_float_pair(recon, gt)
    if arrays is None:
        return {}
    recon_data, gt_data = arrays
    aligned, _, _ = affine_intensity_align(recon_data, gt_data)

    fr = np.fft.fftn(aligned)
    fg = np.fft.fftn(gt_data)
    missing = missing_wedge_mask(
        aligned.shape, tilt_min_deg, tilt_max_deg, tilt_axis=tilt_axis
    )
    measured = ~missing
    # Keep DC out of both (already False in missing; force for measured).
    measured = measured.copy()
    measured[(0,) * aligned.ndim] = False

    out: Dict[str, Any] = {
        "protocol_tilt_min_deg": float(tilt_min_deg),
        "protocol_tilt_max_deg": float(tilt_max_deg),
        "protocol_missing_wedge_deg": float(180.0 - (tilt_max_deg - tilt_min_deg)),
    }
    cc_in = _complex_cc(fr[missing], fg[missing])
    cc_out = _complex_cc(fr[measured], fg[measured])
    if cc_in is not None:
        out["protocol_wedge_in_cc"] = cc_in
    if cc_out is not None:
        out["protocol_wedge_out_cc"] = cc_out
    return out


def fsc_curve_protocol(
    recon: Any,
    gt: Any,
    n_shells: int = 64,
    thresholds: Sequence[float] = (0.5, 0.143),
    pixel_size_nm: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Full FSC curve (not wired into chain). Resolutions at given thresholds
    in pixels; optional nm if ``pixel_size_nm`` is set.
    """
    arrays = _as_float_pair(recon, gt)
    if arrays is None:
        return {}
    recon_data, gt_data = arrays
    aligned, _, _ = affine_intensity_align(recon_data, gt_data)

    shape = aligned.shape
    max_dim = float(max(shape))
    fr = np.fft.fftshift(np.fft.fftn(aligned))
    fg = np.fft.fftshift(np.fft.fftn(gt_data))

    coords = np.meshgrid(
        *[np.arange(s) - s // 2 for s in shape],
        indexing="ij",
    )
    r_pixels = np.sqrt(sum(c.astype(np.float64) ** 2 for c in coords))
    freq = r_pixels / max_dim

    shell_edges = np.linspace(0.0, 0.5, int(n_shells) + 1)
    fsc_values = []
    shell_freqs = []
    for i in range(int(n_shells)):
        mask = (freq >= shell_edges[i]) & (freq < shell_edges[i + 1])
        if not np.any(mask):
            continue
        f1 = fr[mask]
        f2 = fg[mask]
        d1 = np.sqrt(np.sum(np.abs(f1) ** 2))
        d2 = np.sqrt(np.sum(np.abs(f2) ** 2))
        if d1 <= 0.0 or d2 <= 0.0:
            continue
        fsc = float(np.real(np.sum(f1 * np.conj(f2))) / (d1 * d2))
        fsc_values.append(fsc)
        shell_freqs.append(0.5 * (shell_edges[i] + shell_edges[i + 1]))

    out: Dict[str, Any] = {
        "protocol_fsc_curve": {
            "spatial_frequency_cycles_per_px": shell_freqs,
            "fsc": fsc_values,
            "n_shells": int(n_shells),
        }
    }
    if pixel_size_nm is not None and pixel_size_nm > 0:
        out["protocol_pixel_size_nm"] = float(pixel_size_nm)

    for thr in thresholds:
        key = ("protocol_fsc_res_0p5_px" if abs(thr - 0.5) < 1e-9
               else "protocol_fsc_res_0p143_px" if abs(thr - 0.143) < 1e-9
               else "protocol_fsc_res_%.3f_px" % thr)
        res_freq = shell_freqs[-1] if shell_freqs else None
        for fsc, center in zip(fsc_values, shell_freqs):
            if fsc < thr:
                res_freq = center
                break
        if res_freq is not None and res_freq > 0:
            out[key] = float(1.0 / res_freq)
            if pixel_size_nm is not None and pixel_size_nm > 0:
                out[key.replace("_px", "_nm")] = float(pixel_size_nm / res_freq)
    return out


def compute_protocol_metrics(
    recon: Any,
    gt: Any,
    tilt_min_deg: float = -70.0,
    tilt_max_deg: float = 70.0,
    pixel_size_nm: Optional[float] = None,
    tilt_axis: str = "y",
) -> Dict[str, Any]:
    """Aggregate bypass metrics for one reconstruction / GT pair."""
    metrics: Dict[str, Any] = {}
    metrics.update(affine_aligned_ssim_cc(recon, gt))
    metrics.update(
        wedge_in_out_cc(
            recon, gt, tilt_min_deg, tilt_max_deg, tilt_axis=tilt_axis
        )
    )
    metrics.update(
        fsc_curve_protocol(recon, gt, pixel_size_nm=pixel_size_nm)
    )
    return metrics
