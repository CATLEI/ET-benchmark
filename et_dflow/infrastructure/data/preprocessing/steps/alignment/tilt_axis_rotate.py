"""
Tilt-axis QC and in-plane rotation prep for WBP (ported from myddw).

myddw convention: stack as (H, W, N), tilt axis along H (axis 0).
ET-dflow WBP expects (N, H, W), then transposes to (H, W, N) for reconstruction.

Source of truth: myddw/ddw/utils/tilt_axis_qc.py + pipeline/batch_odd_even_wbp.load_aligned_stack
Defaults matching SM70 prepare-wbp: rotate_mode=auto, snap_to_90=True, tolerance_deg=5.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional, Tuple

import numpy as np
from scipy import ndimage


def nhw_to_hwn(stack: np.ndarray) -> np.ndarray:
    """(N, H, W) -> (H, W, N)."""
    arr = np.asarray(stack)
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D stack, got {arr.shape}")
    return np.transpose(arr, (1, 2, 0))


def hwn_to_nhw(stack: np.ndarray) -> np.ndarray:
    """(H, W, N) -> (N, H, W)."""
    arr = np.asarray(stack)
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D stack, got {arr.shape}")
    return np.transpose(arr, (2, 0, 1))


def ensure_hwn(volume: np.ndarray) -> np.ndarray:
    """
    Infer (N,H,W) vs (H,W,N) the same way as myddw load_aligned_stack.
    Projection count is the smallest axis.
    """
    volume = np.asarray(volume)
    if volume.ndim != 3:
        raise ValueError(f"Expected 3D TIFF stack, got shape {volume.shape}")
    if volume.shape[0] <= volume.shape[1] and volume.shape[0] <= volume.shape[2]:
        return np.transpose(volume, (1, 2, 0))  # (N,H,W) -> (H,W,N)
    if volume.shape[2] <= volume.shape[0] and volume.shape[2] <= volume.shape[1]:
        return volume  # already (H,W,N)
    raise ValueError(
        f"Cannot infer TIFF layout from shape {volume.shape}; "
        "expected (N,H,W) or (H,W,N)."
    )


def _calculate_line_intensity(intensity_var: np.ndarray, angle_deg: float, n: int) -> np.ndarray:
    nx, ny = intensity_var.shape
    cenx = np.floor(nx / 2)
    ceny = np.floor(ny / 2)
    ang = angle_deg * np.pi / 180.0
    w = np.zeros(n)
    v = np.zeros(n)
    for i in range(n):
        x = i * np.cos(ang)
        y = i * np.sin(ang)
        sx = abs(np.floor(x) - x)
        sy = abs(np.floor(y) - y)
        px = int(np.floor(x) + cenx)
        py = int(np.floor(y) + ceny)
        if 0 <= px < nx and 0 <= py < ny:
            w[i] += (1 - sx) * (1 - sy)
            v[i] += (1 - sx) * (1 - sy) * intensity_var[px, py]
        px = int(np.ceil(x) + cenx)
        py = int(np.floor(y) + ceny)
        if 0 <= px < nx and 0 <= py < ny:
            w[i] += sx * (1 - sy)
            v[i] += sx * (1 - sy) * intensity_var[px, py]
        px = int(np.floor(x) + cenx)
        py = int(np.ceil(y) + ceny)
        if 0 <= px < nx and 0 <= py < ny:
            w[i] += (1 - sx) * sy
            v[i] += (1 - sx) * sy * intensity_var[px, py]
        px = int(np.ceil(x) + cenx)
        py = int(np.ceil(y) + ceny)
        if 0 <= px < nx and 0 <= py < ny:
            w[i] += sx * sy
            v[i] += sx * sy * intensity_var[px, py]
    mask = w != 0
    v[mask] = v[mask] / w[mask]
    return v


def _intensity_variance_map(data: np.ndarray) -> np.ndarray:
    """Build variance map over projections; data shape (H, W, N)."""
    tilt_series = np.asarray(data, dtype=np.float64)
    _, _, n_proj = tilt_series.shape
    intensity = np.zeros(tilt_series.shape, dtype=np.float64)
    norm = 1.0
    for i in range(n_proj):
        tilt_image = tilt_series[:, :, i]
        tilt_image_f = np.abs(np.fft.fft2(tilt_image))
        if i == 0:
            norm = float(tilt_image_f[0, 0]) or 1.0
        intensity[:, :, i] = np.fft.fftshift(tilt_image_f / norm)
    intensity = np.power(intensity, 0.2)
    return np.var(intensity, axis=2)


def estimate_tilt_axis_offset(data_hwn: np.ndarray) -> float:
    """
    Estimate tilt-axis offset in degrees relative to axis 0 (H).
    0° means axis is vertical in the H–W plane (target for WBP).
    """
    intensity_var = _intensity_variance_map(data_hwn)
    coarse_step = 2.0
    fine_step = 0.1
    coarse_angles = np.arange(-90, 90, coarse_step)
    nx, ny = intensity_var.shape
    n = int(np.round(min(nx, ny) // 3))
    n = max(n, 8)

    coarse_sums = np.array(
        [
            float(np.sum(_calculate_line_intensity(intensity_var, float(a), n)))
            for a in coarse_angles
        ]
    )
    rot_ang = float(coarse_angles[int(np.argmin(coarse_sums))])

    fine_angles = np.arange(rot_ang - coarse_step, rot_ang + coarse_step + fine_step, fine_step)
    fine_sums = np.array(
        [
            float(np.sum(_calculate_line_intensity(intensity_var, float(a), n)))
            for a in fine_angles
        ]
    )
    return float(fine_angles[int(np.argmin(fine_sums))])


def axis_is_consistent(offset_deg: float, tolerance_deg: float) -> bool:
    return abs(float(offset_deg)) <= float(tolerance_deg)


def decide_correction(
    offset_deg: float,
    tolerance_deg: float,
    rotate_mode: str = "auto",
    manual_degrees: int = 0,
    manual_direction: str = "cw",
) -> float:
    """Return correction angle (degrees) in the H–W plane; 0 = no rotation."""
    mode = (rotate_mode or "auto").strip().lower()
    if mode in ("off", "none"):
        return 0.0
    if mode == "manual":
        deg = abs(int(manual_degrees))
        if deg == 0:
            return 0.0
        sign = -1.0 if manual_direction.lower() == "cw" else 1.0
        return sign * float(deg)
    if axis_is_consistent(offset_deg, tolerance_deg):
        return 0.0
    return -float(offset_deg)


def apply_correction(
    data_hwn: np.ndarray,
    correction_deg: float,
    *,
    snap_to_90: bool = False,
) -> np.ndarray:
    """Rotate stack in axes (0, 1). Positive correction_deg = CCW (scipy / np.rot90)."""
    if abs(correction_deg) < 1e-6:
        return np.asarray(data_hwn, dtype=np.float32)
    vol = np.asarray(data_hwn, dtype=np.float32)
    if snap_to_90:
        quarters = int(round(abs(correction_deg) / 90.0)) % 4
        if quarters == 0:
            return vol
        k = quarters if correction_deg > 0 else -quarters
        return np.rot90(vol, k=k, axes=(0, 1)).astype(np.float32, copy=False)
    out = ndimage.rotate(
        vol,
        float(correction_deg),
        axes=(0, 1),
        reshape=False,
        order=1,
        mode="constant",
        cval=0.0,
    )
    return np.asarray(out, dtype=np.float32)


@dataclass
class TiltAxisPrepResult:
    estimated_offset_deg_before: float
    estimated_offset_deg_after: Optional[float]
    correction_applied_deg: float
    rotate_mode: str
    snap_to_90: bool
    tolerance_deg: float
    action: str
    original_shape_nhw: Tuple[int, int, int]
    wbp_shape_nhw: Tuple[int, int, int]
    original_shape_hwn: Tuple[int, int, int]
    wbp_shape_hwn: Tuple[int, int, int]

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["original_shape_nhw"] = list(self.original_shape_nhw)
        d["wbp_shape_nhw"] = list(self.wbp_shape_nhw)
        d["original_shape_hwn"] = list(self.original_shape_hwn)
        d["wbp_shape_hwn"] = list(self.wbp_shape_hwn)
        return d


def prepare_projections_for_wbp(
    projections: np.ndarray,
    angles: Optional[np.ndarray] = None,
    *,
    rotate_mode: str = "auto",
    snap_to_90: bool = True,
    tolerance_deg: float = 5.0,
    manual_degrees: int = 0,
    manual_direction: str = "cw",
) -> Tuple[np.ndarray, Optional[np.ndarray], Dict[str, Any]]:
    """
    Apply myddw-compatible tilt-axis prep; return ET-dflow (N, H, W) stack.

    Args:
        projections: (N,H,W) or (H,W,N)
        angles: optional tilt angles (unchanged; spatial rotation only)
        rotate_mode: auto | off | manual
        snap_to_90: snap correction to nearest 90° and use np.rot90
        tolerance_deg: skip rotation if |offset| <= tolerance (auto)

    Returns:
        (prepared_nhw, angles, meta_dict)
    """
    raw = np.asarray(projections, dtype=np.float32)
    data_hwn = ensure_hwn(raw)
    # Remember whether input was NHW so we report original_shape in NHW when possible
    if raw.shape[0] <= raw.shape[1] and raw.shape[0] <= raw.shape[2]:
        original_nhw = tuple(int(x) for x in raw.shape)
    else:
        original_nhw = tuple(int(x) for x in hwn_to_nhw(data_hwn).shape)

    offset_before = estimate_tilt_axis_offset(data_hwn)
    correction = decide_correction(
        offset_before,
        tolerance_deg,
        rotate_mode=rotate_mode,
        manual_degrees=manual_degrees,
        manual_direction=manual_direction,
    )

    mode = (rotate_mode or "auto").strip().lower()
    data_after = data_hwn
    offset_after: Optional[float] = None
    action = "none"

    if mode in ("off", "none"):
        action = "qc_only"
        offset_after = offset_before
    elif abs(correction) > 1e-6:
        data_after = apply_correction(data_hwn, correction, snap_to_90=snap_to_90)
        offset_after = estimate_tilt_axis_offset(data_after)
        action = (
            "rotated"
            if axis_is_consistent(offset_after, tolerance_deg)
            else "failed_verification"
        )
    else:
        offset_after = offset_before
        action = "none"

    prepared_nhw = hwn_to_nhw(data_after).astype(np.float32, copy=False)
    result = TiltAxisPrepResult(
        estimated_offset_deg_before=float(offset_before),
        estimated_offset_deg_after=None if offset_after is None else float(offset_after),
        correction_applied_deg=float(correction),
        rotate_mode=mode,
        snap_to_90=bool(snap_to_90),
        tolerance_deg=float(tolerance_deg),
        action=action,
        original_shape_nhw=original_nhw,  # type: ignore[arg-type]
        wbp_shape_nhw=tuple(int(x) for x in prepared_nhw.shape),  # type: ignore[arg-type]
        original_shape_hwn=tuple(int(x) for x in data_hwn.shape),  # type: ignore[arg-type]
        wbp_shape_hwn=tuple(int(x) for x in data_after.shape),  # type: ignore[arg-type]
    )
    meta = result.to_dict()
    meta["rotate_applied"] = action == "rotated"
    meta["note"] = (
        "myddw-compatible tilt-axis prep; angles unchanged; "
        "target tilt axis along H for WBP (Nslice)"
    )
    ang = None if angles is None else np.asarray(angles, dtype=np.float64)
    return prepared_nhw, ang, meta
