"""
Align a reconstruction volume onto a fixed ground-truth grid before metrics.

Strategies
----------
- ``fixed``: deterministic axes_order + flip_axes + trim (dataset YAML).
- ``ncc``: search discrete orientations + integer shifts (NCC), then optional refine.
- ``center``: center crop/pad only.

Fixed reference: GT. Moving volume: reconstruction.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import numpy as np
from scipy import ndimage

try:
    import hyperspy.api as hs
except ImportError:  # pragma: no cover
    hs = None  # type: ignore

VolumeLike = Union[np.ndarray, Any]
Shape3 = Tuple[int, int, int]
Shift3 = Tuple[int, int, int]


def center_embed(src: np.ndarray, target_shape: Shape3) -> np.ndarray:
    """Place src centered into target_shape (crop or zero-pad per axis)."""
    return trim_to_shape(src, target_shape, mode="center")


def trim_to_shape(
    src: np.ndarray,
    target_shape: Shape3,
    mode: str = "center",
) -> np.ndarray:
    """Crop or zero-pad ``src`` to ``target_shape``.

    ``mode``:
    - ``center``: crop/pad equally from both ends (integer bias toward start).
    - ``leading``: when oversized, drop the first ``s - t`` voxels (keep trailing).
    - ``trailing``: when oversized, drop the last ``s - t`` voxels (keep leading).
    """
    mode = (mode or "center").strip().lower()
    if mode not in ("center", "leading", "trailing"):
        raise ValueError(f"trim mode must be center|leading|trailing, got {mode!r}")

    out = np.zeros(target_shape, dtype=np.float32)
    src_slices: List[slice] = []
    dst_slices: List[slice] = []
    for s, t in zip(src.shape, target_shape):
        if s == t:
            src_slices.append(slice(None))
            dst_slices.append(slice(None))
        elif s > t:
            if mode == "leading":
                start = s - t
            elif mode == "trailing":
                start = 0
            else:
                start = (s - t) // 2
            src_slices.append(slice(start, start + t))
            dst_slices.append(slice(None))
        else:
            # Undersized: always center-pad (trim mode only affects crop side).
            start = (t - s) // 2
            src_slices.append(slice(None))
            dst_slices.append(slice(start, start + s))
    out[tuple(dst_slices)] = np.asarray(src, dtype=np.float32)[tuple(src_slices)]
    return out


def apply_fixed_geometry(
    volume: np.ndarray,
    target_shape: Shape3,
    axes_order: Sequence[int] = (0, 1, 2),
    flip_axes: Optional[Sequence[int]] = None,
    trim: str = "leading",
) -> np.ndarray:
    """Apply transpose, flips, then trim/pad to ``target_shape``."""
    vol = np.asarray(volume, dtype=np.float32)
    order = tuple(int(x) for x in axes_order)
    if sorted(order) != [0, 1, 2]:
        raise ValueError(f"axes_order must be a permutation of 0,1,2; got {order}")
    if order != (0, 1, 2):
        vol = np.transpose(vol, order)
    for ax in flip_axes or ():
        vol = np.flip(vol, axis=int(ax))
    return trim_to_shape(vol, target_shape, mode=trim)


def shift_volume(
    volume: np.ndarray,
    shift: Shift3,
    cval: float = 0.0,
) -> np.ndarray:
    """Integer shift with zero-fill (no wrap-around). Positive = toward higher index."""
    dz, dy, dx = (int(shift[0]), int(shift[1]), int(shift[2]))
    src = np.asarray(volume, dtype=np.float32)
    if dz == 0 and dy == 0 and dx == 0:
        return src.copy()
    return np.ascontiguousarray(
        ndimage.shift(src, shift=(dz, dy, dx), order=0, mode="constant", cval=cval)
    ).astype(np.float32)


def ncc(a: np.ndarray, b: np.ndarray) -> float:
    a = a.ravel().astype(np.float64)
    b = b.ravel().astype(np.float64)
    a = a - a.mean()
    b = b - b.mean()
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom < 1e-12:
        return 0.0
    return float(np.dot(a, b) / denom)


def zscore(vol: np.ndarray) -> np.ndarray:
    v = vol.astype(np.float32)
    return (v - v.mean()) / (v.std() + 1e-6)


def _clip_shift(shift: Shift3, max_shift: int) -> Shift3:
    m = int(max_shift)
    return (
        int(max(-m, min(m, shift[0]))),
        int(max(-m, min(m, shift[1]))),
        int(max(-m, min(m, shift[2]))),
    )


def find_best_shift(
    fixed: np.ndarray,
    moving: np.ndarray,
    max_shift: int = 8,
    downsample_target: int = 64,
) -> Tuple[Shift3, float]:
    """Maximize NCC over integer shifts.

    ``max_shift`` is the **full-resolution** search radius in voxels.
    Search runs on a downsampled grid (~``downsample_target``^3), then maps
    back and clips to ``[-max_shift, max_shift]``.
    """
    max_shift = int(max_shift)
    if max_shift < 0:
        raise ValueError("max_shift must be >= 0")
    if max_shift == 0:
        return (0, 0, 0), ncc(fixed, moving)

    zoom = [min(1.0, float(downsample_target) / float(s)) for s in fixed.shape]
    f = ndimage.zoom(fixed, zoom, order=1)
    m0 = ndimage.zoom(moving, zoom, order=1)

    # Downsampled radius: at least 1 so we explore neighbors when max_shift>0.
    ds_radii = [
        max(1, int(math.ceil(max_shift * z))) if z > 0 else max_shift for z in zoom
    ]
    # Use isotropic radius = max over axes for a cubic loop (simple, matches config).
    ds_max = max(ds_radii)

    best: Shift3 = (0, 0, 0)
    best_ncc = -1.0
    for dz in range(-ds_max, ds_max + 1):
        for dy in range(-ds_max, ds_max + 1):
            for dx in range(-ds_max, ds_max + 1):
                m = shift_volume(m0, (dz, dy, dx))
                score = ncc(f, m)
                if score > best_ncc:
                    best_ncc = score
                    full = (
                        int(round(dz / zoom[0])),
                        int(round(dy / zoom[1])),
                        int(round(dx / zoom[2])),
                    )
                    best = _clip_shift(full, max_shift)
    return best, float(best_ncc)


def _center_roi(vol: np.ndarray, roi: int = 128) -> np.ndarray:
    """Extract a centered cubic (or rectangular) ROI for refine search."""
    slices = []
    for s in vol.shape:
        if s <= roi:
            slices.append(slice(None))
        else:
            start = (s - roi) // 2
            slices.append(slice(start, start + roi))
    return vol[tuple(slices)]


def refine_shift_roi(
    fixed: np.ndarray,
    moving: np.ndarray,
    refine_max_shift: int = 4,
    roi: int = 128,
) -> Tuple[Shift3, float]:
    """Full-resolution integer NCC refine on a centered ROI."""
    refine_max_shift = int(refine_max_shift)
    if refine_max_shift <= 0:
        return (0, 0, 0), ncc(fixed, moving)

    f = zscore(_center_roi(fixed, roi))
    m0 = zscore(_center_roi(moving, roi))
    best: Shift3 = (0, 0, 0)
    best_ncc = -1.0
    r = refine_max_shift
    for dz in range(-r, r + 1):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                m = shift_volume(m0, (dz, dy, dx))
                score = ncc(f, m)
                if score > best_ncc:
                    best_ncc = score
                    best = (dz, dy, dx)
    return best, float(best_ncc)


def find_best_orientation(
    fixed: np.ndarray,
    moving: np.ndarray,
    max_shift: int = 8,
    refine_max_shift: int = 4,
) -> Tuple[np.ndarray, Shift3, float, float, str, Shift3]:
    """Try rot90/transpose variants; coarse NCC then ROI refine.

    Returns
    -------
    best_vol, final_shift, ncc_coarse, ncc_refine, orientation_tag, coarse_shift
    """
    best_vol = moving
    best_shift: Shift3 = (0, 0, 0)
    best_coarse_shift: Shift3 = (0, 0, 0)
    best_ncc = -1.0
    best_refine = -1.0
    best_tag = "k0"
    target = tuple(int(x) for x in fixed.shape)

    for k in range(4):
        cand = np.rot90(moving, k=k, axes=(1, 2)) if k else moving
        for tag, vol in (
            (f"rot90_yx_k{k}", cand),
            (f"transpose01_k{k}", np.transpose(cand, (1, 0, 2))),
            (f"transpose02_k{k}", np.transpose(cand, (2, 1, 0))),
        ):
            if vol.shape != fixed.shape:
                vol = center_embed(vol, target)
            coarse, score = find_best_shift(zscore(fixed), zscore(vol), max_shift)
            moved = shift_volume(vol, coarse)
            refine, rscore = refine_shift_roi(
                fixed, moved, refine_max_shift=refine_max_shift
            )
            # Rank by coarse score primarily (orientation); refine only adjusts shift.
            if score > best_ncc:
                best_ncc = score
                best_refine = rscore
                best_coarse_shift = coarse
                final = (
                    coarse[0] + refine[0],
                    coarse[1] + refine[1],
                    coarse[2] + refine[2],
                )
                best_shift = final
                best_vol = shift_volume(vol, final)
                best_tag = tag
    return best_vol, best_shift, best_ncc, best_refine, best_tag, best_coarse_shift


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


def _parse_volumes(
    reconstruction: VolumeLike,
    ground_truth: VolumeLike,
    target_shape: Optional[Shape3],
) -> Tuple[np.ndarray, np.ndarray, List[int], Shape3, Shape3]:
    if hasattr(reconstruction, "data"):
        recon = _volume_from_signal(reconstruction)
        recon_shape_before = list(reconstruction.data.shape)
    else:
        recon = np.asarray(reconstruction, dtype=np.float32)
        recon_shape_before = list(recon.shape)

    if hasattr(ground_truth, "data"):
        gt = _volume_from_signal(ground_truth)
        gt_shape = tuple(int(x) for x in ground_truth.data.shape)
    else:
        gt = np.asarray(ground_truth, dtype=np.float32)
        gt_shape = tuple(int(x) for x in gt.shape)

    if target_shape is None:
        target_shape = gt_shape
    target_shape = tuple(int(x) for x in target_shape)
    return recon, gt, recon_shape_before, gt_shape, target_shape


def align_reconstruction_to_ground_truth(
    reconstruction: VolumeLike,
    ground_truth: VolumeLike,
    target_shape: Optional[Shape3] = None,
    max_shift: int = 8,
    strategy: str = "ncc",
    align_fixed: Optional[Dict[str, Any]] = None,
    refine_max_shift: int = 4,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Align reconstruction onto the fixed GT grid.

    Parameters
    ----------
    strategy:
        ``fixed`` | ``ncc`` | ``center``.
    align_fixed:
        For ``fixed``: ``axes_order``, ``flip_axes``, ``trim``.
    max_shift:
        Full-resolution integer shift radius (voxels). Used by ``ncc`` and as
        optional refine after ``fixed``.
    refine_max_shift:
        ROI refine radius after coarse NCC (``ncc`` only).
    """
    recon, gt, recon_shape_before, gt_shape, target_shape = _parse_volumes(
        reconstruction, ground_truth, target_shape
    )
    strategy = (strategy or "ncc").strip().lower()
    fixed_gt = (
        center_embed(gt, target_shape)
        if gt.shape != target_shape
        else gt.astype(np.float32)
    )

    if strategy == "center":
        aligned = center_embed(recon, target_shape)
        meta: Dict[str, Any] = {
            "strategy": "center",
            "fixed_reference": "ground_truth",
            "gt_shape": list(gt_shape),
            "reconstruction_shape_before": recon_shape_before,
            "target_shape": list(target_shape),
            "shift_mode": "none",
        }
        return aligned.astype(np.float32), meta

    if strategy == "fixed":
        cfg = dict(align_fixed or {})
        axes_order = cfg.get("axes_order", [0, 1, 2])
        flip_axes = cfg.get("flip_axes", [])
        trim = str(cfg.get("trim", "leading"))
        aligned = apply_fixed_geometry(
            recon,
            target_shape,
            axes_order=axes_order,
            flip_axes=flip_axes,
            trim=trim,
        )
        shift: Shift3 = (0, 0, 0)
        ncc_after = None
        if int(max_shift) > 0:
            shift, ncc_after = find_best_shift(
                zscore(fixed_gt), zscore(aligned), max_shift=int(max_shift)
            )
            aligned = shift_volume(aligned, shift)
        meta = {
            "strategy": "fixed",
            "fixed_reference": "ground_truth",
            "gt_shape": list(gt_shape),
            "reconstruction_shape_before": recon_shape_before,
            "target_shape": list(target_shape),
            "axes_order": list(axes_order),
            "flip_axes": list(flip_axes or []),
            "trim": trim,
            "shift_zyx": list(shift),
            "shift_mode": "zero_pad",
            "max_shift_fullres": int(max_shift),
        }
        if ncc_after is not None:
            meta["ncc_approx"] = ncc_after
        return aligned.astype(np.float32), meta

    if strategy != "ncc":
        raise ValueError(
            f"Unknown align strategy {strategy!r}; use fixed, ncc, or center"
        )

    # NCC path: center-embed first, then orientation + shift search.
    recon_embedded = center_embed(recon, target_shape)
    (
        recon_aligned,
        shift,
        score,
        rscore,
        tag,
        coarse,
    ) = find_best_orientation(
        fixed_gt,
        recon_embedded,
        max_shift=max_shift,
        refine_max_shift=refine_max_shift,
    )
    meta = {
        "strategy": "ncc",
        "fixed_reference": "ground_truth",
        "gt_shape": list(gt_shape),
        "reconstruction_shape_before": recon_shape_before,
        "target_shape": list(target_shape),
        "orientation": tag,
        "shift_zyx_coarse": list(coarse),
        "shift_zyx": list(shift),
        "ncc_approx": score,
        "ncc_refine": rscore,
        "max_shift_fullres": int(max_shift),
        "refine_max_shift": int(refine_max_shift),
        "shift_mode": "zero_pad",
    }
    return recon_aligned.astype(np.float32), meta


def align_reconstruction_signal(
    reconstruction: Any,
    ground_truth: Any,
    target_shape: Optional[Shape3] = None,
    max_shift: int = 8,
    strategy: str = "ncc",
    align_fixed: Optional[Dict[str, Any]] = None,
    refine_max_shift: int = 4,
) -> Tuple[Any, Dict[str, Any]]:
    """Return aligned reconstruction as HyperSpy Signal2D plus metadata."""
    aligned, meta = align_reconstruction_to_ground_truth(
        reconstruction,
        ground_truth,
        target_shape=target_shape,
        max_shift=max_shift,
        strategy=strategy,
        align_fixed=align_fixed,
        refine_max_shift=refine_max_shift,
    )
    return _signal_from_volume(aligned), meta


def output_to_gt_enabled(geom: Optional[Dict[str, Any]]) -> bool:
    """Return True if ``output_to_gt`` config requests a transform."""
    if not geom or not isinstance(geom, dict):
        return False
    if geom.get("enabled") is False:
        return False
    return True


def apply_output_to_gt_array(
    volume: np.ndarray,
    geom: Dict[str, Any],
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """Apply ``output_to_gt`` fixed geometry to an in-memory volume."""
    if not output_to_gt_enabled(geom):
        return np.asarray(volume, dtype=np.float32), {
            "strategy": "output_to_gt",
            "applied": False,
            "reason": "disabled_or_missing",
        }
    target_raw = geom.get("target_shape")
    if not target_raw or len(target_raw) != 3:
        raise ValueError("output_to_gt.target_shape must be a length-3 list")
    target_shape = (int(target_raw[0]), int(target_raw[1]), int(target_raw[2]))
    axes_order = geom.get("axes_order", [0, 1, 2])
    flip_axes = geom.get("flip_axes", [])
    trim = str(geom.get("trim", "leading"))
    before = list(np.asarray(volume).shape)
    aligned = apply_fixed_geometry(
        volume,
        target_shape,
        axes_order=axes_order,
        flip_axes=flip_axes,
        trim=trim,
    )
    meta: Dict[str, Any] = {
        "strategy": "output_to_gt",
        "applied": True,
        "axes_order": list(axes_order),
        "flip_axes": list(flip_axes or []),
        "trim": trim,
        "target_shape": list(target_shape),
        "reconstruction_shape_before": before,
        "reconstruction_shape_after": list(aligned.shape),
    }
    return aligned.astype(np.float32), meta


def apply_output_to_gt_file(
    hspy_path: Union[str, Any],
    geom: Dict[str, Any],
    *,
    native_backup_name: str = "reconstruction_native.hspy",
    meta_name: str = "reconstruction_output_to_gt_meta.json",
    force_from_native: bool = True,
) -> Dict[str, Any]:
    """
    On-disk native→GT transform for hybrid master / reeval (no image rebuild).

    - First run: rename ``reconstruction.hspy`` → ``reconstruction_native.hspy``,
      then write GT-frame volume back to ``reconstruction.hspy``.
    - Later runs with ``force_from_native``: always reload from native backup so
      YAML recipe changes can be replayed without re-running algorithms.
    - ``enabled: false``: no-op (returns applied=False).
    """
    import json
    from pathlib import Path

    path = Path(hspy_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    alg_dir = path.parent
    native_path = alg_dir / native_backup_name
    meta_path = alg_dir / meta_name

    if not output_to_gt_enabled(geom):
        meta = {
            "strategy": "output_to_gt",
            "applied": False,
            "reason": "disabled_or_missing",
            "path": str(path),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return meta

    if not native_path.is_file():
        # Current file is assumed native (fresh download or first reeval).
        path.replace(native_path)
    elif force_from_native:
        pass  # keep native; overwrite path from native below
    else:
        meta = {
            "strategy": "output_to_gt",
            "applied": False,
            "reason": "already_transformed_skip",
            "native_path": str(native_path),
            "path": str(path),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
        return meta

    vol = _load_volume_file(native_path)
    aligned, meta = apply_output_to_gt_array(vol, geom)
    meta["native_path"] = str(native_path)
    meta["path"] = str(path)
    meta["strategy"] = "output_to_gt_master"
    _save_volume_file(path, aligned, meta=meta)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)
    return meta


def _load_volume_file(path: Any) -> np.ndarray:
    from pathlib import Path

    p = Path(path)
    if p.suffix.lower() == ".npy":
        return np.asarray(np.load(str(p)), dtype=np.float32)
    if hs is None:
        raise ImportError("hyperspy is required to load .hspy volumes")
    loaded = hs.load(str(p))
    if isinstance(loaded, list):
        loaded = loaded[0]
    return np.asarray(loaded.data, dtype=np.float32)


def _save_volume_file(path: Any, volume: np.ndarray, meta: Optional[Dict[str, Any]] = None) -> None:
    from pathlib import Path

    p = Path(path)
    arr = np.asarray(volume, dtype=np.float32)
    if p.suffix.lower() == ".npy":
        np.save(str(p), arr)
        return
    if hs is None:
        raise ImportError("hyperspy is required to save .hspy volumes")
    out_sig = _signal_from_volume(arr, title="Reconstruction (GT frame)")
    if meta:
        try:
            out_sig.metadata.set_item("et_dflow.geometry.output_to_gt", meta)
        except (AttributeError, TypeError):
            pass
    out_sig.save(str(p))


def resolve_algorithm_output_to_gt(
    config: Dict[str, Any],
    algorithm_name: str,
) -> Optional[Dict[str, Any]]:
    """Look up ``algorithms.<name>.parameters.output_to_gt`` from a full YAML config."""
    algs = config.get("algorithms") or {}
    # Exact key, then sanitized match (dir names may differ slightly).
    entry = algs.get(algorithm_name)
    if entry is None:
        safe = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in algorithm_name
        )
        for k, v in algs.items():
            if "".join(c if c.isalnum() or c in "._-" else "_" for c in k) == safe:
                entry = v
                break
    if not isinstance(entry, dict):
        return None
    params = entry.get("parameters") or {}
    geom = params.get("output_to_gt")
    return dict(geom) if isinstance(geom, dict) else None
