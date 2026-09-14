"""
Align a reconstruction volume onto a fixed ground-truth grid before metrics.

Fixed reference: GT (typically 512^3). Moving volume: reconstruction (~513^3).
Adapted from myddw align_to_model.py with fixed/moving roles swapped for ET-dflow.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, Union

import numpy as np
from scipy import ndimage

try:
    import hyperspy.api as hs
except ImportError:  # pragma: no cover
    hs = None  # type: ignore


def center_embed(src: np.ndarray, target_shape: Tuple[int, int, int]) -> np.ndarray:
    """Place src centered into target_shape (crop or zero-pad per axis)."""
    out = np.zeros(target_shape, dtype=np.float32)
    src_slices = []
    dst_slices = []
    for s, t in zip(src.shape, target_shape):
        if s == t:
            src_slices.append(slice(None))
            dst_slices.append(slice(None))
        elif s > t:
            start = (s - t) // 2
            src_slices.append(slice(start, start + t))
            dst_slices.append(slice(None))
        else:
            start = (t - s) // 2
            src_slices.append(slice(None))
            dst_slices.append(slice(start, start + s))
    out[tuple(dst_slices)] = src[tuple(src_slices)]
    return out


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel().astype(np.float64)
    b = b.ravel().astype(np.float64)
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-12:
        return 0.0
    return float(np.dot(a, b) / denom)


def find_best_shift(
    fixed: np.ndarray, moving: np.ndarray, max_shift: int = 8
) -> Tuple[Tuple[int, int, int], float]:
    """Maximize NCC of downsampled volumes over integer shifts of moving."""
    zoom = [min(1.0, 64 / s) for s in fixed.shape]
    f = ndimage.zoom(fixed, zoom, order=1)
    m0 = ndimage.zoom(moving, zoom, order=1)
    best = (0, 0, 0)
    best_ncc = -1.0
    for dz in range(-max_shift, max_shift + 1):
        for dy in range(-max_shift, max_shift + 1):
            for dx in range(-max_shift, max_shift + 1):
                m = np.roll(np.roll(np.roll(m0, dz, 0), dy, 1), dx, 2)
                score = ncc(f, m)
                if score > best_ncc:
                    best_ncc = score
                    best = (
                        int(round(dz / zoom[0])),
                        int(round(dy / zoom[1])),
                        int(round(dx / zoom[2])),
                    )
    return best, best_ncc


def apply_shift(vol: np.ndarray, shift: Tuple[int, int, int]) -> np.ndarray:
    dz, dy, dx = shift
    return np.roll(np.roll(np.roll(vol, dz, 0), dy, 1), dx, 2)


def zscore(vol: np.ndarray) -> np.ndarray:
    v = vol.astype(np.float32)
    return (v - v.mean()) / (v.std() + 1e-6)


def find_best_orientation(
    fixed: np.ndarray, moving: np.ndarray, max_shift: int = 8
) -> Tuple[np.ndarray, Tuple[int, int, int], float, str]:
    """Try rot90/transpose variants; return best-aligned moving volume."""
    best_vol = moving
    best_shift = (0, 0, 0)
    best_ncc = -1.0
    best_tag = "k0"
    for k in range(4):
        cand = np.rot90(moving, k=k, axes=(1, 2)) if k else moving
        for tag, vol in (
            (f"rot90_yx_k{k}", cand),
            (f"transpose01_k{k}", np.transpose(cand, (1, 0, 2))),
            (f"transpose02_k{k}", np.transpose(cand, (2, 1, 0))),
        ):
            if vol.shape != fixed.shape:
                vol = center_embed(vol, tuple(fixed.shape))
            shift, score = find_best_shift(zscore(fixed), zscore(vol), max_shift)
            if score > best_ncc:
                best_ncc = score
                best_shift = shift
                best_vol = apply_shift(vol, shift)
                best_tag = tag
    return best_vol, best_shift, best_ncc, best_tag


def _volume_from_signal(signal: Any) -> np.ndarray:
    return np.asarray(signal.data, dtype=np.float32)


def _signal_from_volume(volume: np.ndarray, title: str = "Aligned reconstruction") -> Any:
    if hs is None:
        raise ImportError("hyperspy is required for signal conversion")
    arr = np.asarray(volume, dtype=np.float32)
    sig = hs.signals.Signal2D(arr)
    sig.metadata.set_item("General.title", title)
    sig.metadata.set_item("Signal.quantity", "Intensity")
    try:
        if sig.axes_manager.navigation_dimension > 0:
            sig.axes_manager.navigation_axes[0].name = "Z"
        if sig.axes_manager.signal_dimension >= 2:
            sig.axes_manager.signal_axes[0].name = "Y"
            sig.axes_manager.signal_axes[1].name = "X"
    except (AttributeError, IndexError, TypeError):
        pass
    return sig


def align_reconstruction_to_ground_truth(
    reconstruction: Union[np.ndarray, Any],
    ground_truth: Union[np.ndarray, Any],
    target_shape: Optional[Tuple[int, int, int]] = None,
    max_shift: int = 8,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Align reconstruction onto the fixed GT grid.

    Args:
        reconstruction: Reconstruction array or HyperSpy signal (~513^3).
        ground_truth: Ground truth array or HyperSpy signal (512^3).
        target_shape: Output grid; defaults to ground_truth.shape.
        max_shift: Integer shift search radius for NCC.

    Returns:
        (aligned_reconstruction, metadata_dict) both on target_shape grid.
    """
    if hasattr(reconstruction, "data"):
        recon = _volume_from_signal(reconstruction)
        recon_shape_before = list(reconstruction.data.shape)
    else:
        recon = np.asarray(reconstruction, dtype=np.float32)
        recon_shape_before = list(recon.shape)

    if hasattr(ground_truth, "data"):
        gt = _volume_from_signal(ground_truth)
        gt_shape = tuple(ground_truth.data.shape)
    else:
        gt = np.asarray(ground_truth, dtype=np.float32)
        gt_shape = tuple(gt.shape)

    if target_shape is None:
        target_shape = gt_shape
    target_shape = tuple(int(x) for x in target_shape)

    fixed = center_embed(gt, target_shape) if gt.shape != target_shape else gt.astype(np.float32)
    recon_embedded = center_embed(recon, target_shape)
    recon_aligned, shift, score, tag = find_best_orientation(fixed, recon_embedded, max_shift)

    meta: Dict[str, Any] = {
        "strategy": "align_reconstruction_to_ground_truth",
        "fixed_reference": "ground_truth",
        "gt_shape": list(gt_shape),
        "reconstruction_shape_before": recon_shape_before,
        "target_shape": list(target_shape),
        "orientation": tag,
        "shift_zyx": list(shift),
        "ncc_approx": score,
    }
    return recon_aligned.astype(np.float32), meta


def align_reconstruction_signal(
    reconstruction: Any,
    ground_truth: Any,
    target_shape: Optional[Tuple[int, int, int]] = None,
    max_shift: int = 8,
) -> Tuple[Any, Dict[str, Any]]:
    """Return aligned reconstruction as HyperSpy Signal2D plus metadata."""
    aligned, meta = align_reconstruction_to_ground_truth(
        reconstruction, ground_truth, target_shape=target_shape, max_shift=max_shift
    )
    return _signal_from_volume(aligned), meta
