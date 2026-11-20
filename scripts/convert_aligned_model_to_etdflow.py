#!/usr/bin/env python3
"""
Convert Aligned model TIFF stacks to ET-dflow benchmark inputs.

Usage:
    python scripts/convert_aligned_model_to_etdflow.py --variant sm80
    python scripts/convert_aligned_model_to_etdflow.py --variant sm70_step2 \\
      --src data/datasets/simulated/raw_data
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List, Sequence, Tuple

import numpy as np
import yaml

import hyperspy.api as hs

from et_dflow.infrastructure.data.preprocessing.steps.alignment.tilt_axis_rotate import (
    prepare_projections_for_wbp,
)


def _imread_stack(path: Path) -> np.ndarray:
    """Load a multi-page TIFF without requiring tifffile at runtime."""
    try:
        import tifffile

        return np.asarray(tifffile.imread(str(path)))
    except ImportError:
        pass
    try:
        import imageio.v3 as iio

        return np.asarray(iio.imread(str(path)))
    except Exception:
        pass
    from PIL import Image

    im = Image.open(path)
    frames = []
    n = getattr(im, "n_frames", 1)
    for i in range(n):
        im.seek(i)
        frames.append(np.asarray(im))
    return np.stack(frames, axis=0)

# (candidate filenames, tilt_min, tilt_max, step_deg)
# First existing candidate under --src wins.
VARIANTS = {
    "sm50": (["Proj_tilt_-50-+50_512x513.tif"], -50.0, 50.0, 1.0),
    "sm60": (
        [
            "Proj_tilt_-60-+60_512x513.tif",
            "Proj_tilt_-60-+60_512x513(1).tif",
        ],
        -60.0,
        60.0,
        1.0,
    ),
    "sm70": (["Proj_tilt_-70-+70_512x513.tif"], -70.0, 70.0, 1.0),
    "sm80": (["Proj_tilt_-80-+80_512x513.tif"], -80.0, 80.0, 1.0),
    "sm90": (["Proj_tilt_-90-+90_512x513.tiff"], -90.0, 90.0, 1.0),
    "sm40": (["Proj_tilt_-40-+40_512x513.tif"], -40.0, 40.0, 1.0),
    "sm70_step2": (
        ["Proj_tilt_-70-+70_step2_512x513.tif"],
        -70.0,
        70.0,
        2.0,
    ),
    "sm70_step4": (
        ["Proj_tilt_-70-+70_step4_512x513.tif"],
        -70.0,
        70.0,
        4.0,
    ),
}

DEFAULT_SRC = Path("data/datasets/simulated/raw_data")
GT_FILENAME = "model.tif"


def _tilt_angles(tilt_min: float, tilt_max: float, n: int) -> np.ndarray:
    return np.linspace(tilt_min, tilt_max, n, dtype=np.float64)


def _expected_n_frames(tilt_min: float, tilt_max: float, step_deg: float) -> int:
    span = tilt_max - tilt_min
    n = int(round(span / step_deg)) + 1
    return n


def _resolve_proj_file(src: Path, candidates: Sequence[str]) -> Path:
    tried: List[Path] = []
    for name in candidates:
        path = src / name
        tried.append(path)
        if path.is_file():
            return path
    raise FileNotFoundError(
        "Projection stack not found. Tried:\n  "
        + "\n  ".join(str(p) for p in tried)
    )


def _write_tilt_series_hspy(proj: np.ndarray, angles: np.ndarray, out_path: Path) -> None:
    data = np.asarray(proj, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D projection stack, got shape {data.shape}")
    signal = hs.signals.Signal2D(data)
    signal.metadata.set_item("General.title", "Aligned model tilt series")
    signal.metadata.set_item("Signal.quantity", "Intensity")
    signal.metadata.set_item("Acquisition_instrument.TEM.tilt_series", angles.tolist())
    try:
        if signal.axes_manager.navigation_dimension > 0:
            signal.axes_manager.navigation_axes[0].name = "Tilt"
            signal.axes_manager.navigation_axes[0].units = "degrees"
    except (AttributeError, IndexError, TypeError):
        pass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    signal.save(str(out_path), overwrite=True)


def _write_volume_hspy(volume: np.ndarray, out_path: Path, title: str) -> None:
    data = np.asarray(volume, dtype=np.float32)
    if data.ndim != 3:
        raise ValueError(f"Expected 3D volume, got shape {data.shape}")
    signal = hs.signals.Signal2D(data)
    signal.metadata.set_item("General.title", title)
    signal.metadata.set_item("Signal.quantity", "Intensity")
    try:
        if signal.axes_manager.navigation_dimension > 0:
            signal.axes_manager.navigation_axes[0].name = "Z"
        if signal.axes_manager.signal_dimension >= 2:
            signal.axes_manager.signal_axes[0].name = "Y"
            signal.axes_manager.signal_axes[1].name = "X"
    except (AttributeError, IndexError, TypeError):
        pass
    out_path.parent.mkdir(parents=True, exist_ok=True)
    signal.save(str(out_path), overwrite=True)


def convert_variant(
    src: Path,
    out: Path,
    variant: str,
) -> Path:
    if variant not in VARIANTS:
        raise ValueError(f"Unknown variant {variant!r}; choose from {list(VARIANTS)}")

    candidates, tilt_min, tilt_max, step_deg = VARIANTS[variant]
    proj_path = _resolve_proj_file(src, candidates)
    gt_path = src / GT_FILENAME
    if not gt_path.is_file():
        raise FileNotFoundError(f"Ground truth not found: {gt_path}")

    print(f"[convert] reading projections: {proj_path.name}", flush=True)
    proj_raw = _imread_stack(proj_path)
    print(f"[convert] reading ground truth: {gt_path.name}", flush=True)
    gt = _imread_stack(gt_path)
    n_tilts = int(proj_raw.shape[0])
    expected = _expected_n_frames(tilt_min, tilt_max, step_deg)
    if n_tilts != expected:
        raise ValueError(
            f"Frame count mismatch for {variant}: got {n_tilts}, "
            f"expected {expected} for [{tilt_min}, {tilt_max}] step {step_deg}°"
        )
    angles = _tilt_angles(tilt_min, tilt_max, n_tilts)
    # Guard: linspace step must match nominal step for integer grids.
    if n_tilts >= 2:
        measured = float(np.median(np.diff(angles)))
        if abs(measured - step_deg) > 1e-6:
            raise ValueError(
                f"Angle step mismatch for {variant}: linspace median {measured} "
                f"vs nominal {step_deg}"
            )

    print(
        "[convert] tilt-axis prep (myddw-compatible: rotate_mode=auto, snap_to_90=True)",
        flush=True,
    )
    proj, angles, axis_meta = prepare_projections_for_wbp(
        proj_raw,
        angles,
        rotate_mode="auto",
        snap_to_90=True,
        tolerance_deg=5.0,
    )
    print(
        f"[convert] axis QC: offset_before={axis_meta.get('estimated_offset_deg_before'):.2f}° "
        f"correction={axis_meta.get('correction_applied_deg'):.2f}° "
        f"action={axis_meta.get('action')} "
        f"shape {axis_meta.get('original_shape_nhw')} -> {axis_meta.get('wbp_shape_nhw')}",
        flush=True,
    )

    if out.exists():
        # Allow overwrite of contents but keep a clear log.
        print(f"[convert] output exists, overwriting files under {out}", flush=True)

    raw_dir = out / "raw"
    gt_dir = out / "ground_truth"
    tilt_hspy = raw_dir / "tilt_series.hspy"
    angles_txt = raw_dir / "tilt_angles.txt"
    volume_hspy = gt_dir / "volume.hspy"

    print(f"[convert] writing {tilt_hspy}", flush=True)
    _write_tilt_series_hspy(proj, angles, tilt_hspy)
    angles_txt.write_text("\n".join(f"{a:.6f}" for a in angles) + "\n", encoding="utf-8")
    print(f"[convert] writing {volume_hspy}", flush=True)
    _write_volume_hspy(gt, volume_hspy, title="Aligned model ground truth")

    metadata = {
        "name": f"aligned_model_{variant}",
        "type": "simulated",
        "version": "1",
        "has_ground_truth": True,
        "source_root": str(src.resolve()),
        "variant": variant,
        "tilt_range": [tilt_min, tilt_max],
        # Historical field = tilt limit |α|. Protocol wedge = 180 - 2|α|.
        "missing_wedge_angle": abs(tilt_min),
        "missing_wedge_deg": float(180.0 - (tilt_max - tilt_min)),
        "angular_step_deg": float(step_deg),
        "num_projections": n_tilts,
        "projection_shape_raw": list(proj_raw.shape),
        "projection_shape": list(proj.shape),
        "ground_truth_shape": list(gt.shape),
        "projection_file": proj_path.name,
        "ground_truth_file": GT_FILENAME,
        "tilt_axis_prep": axis_meta,
        "paths": {
            "tilt_series": "raw/tilt_series.hspy",
            "tilt_angles": "raw/tilt_angles.txt",
            "ground_truth": "ground_truth/volume.hspy",
        },
    }
    (out / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )

    print(f"[ok] variant={variant}", flush=True)
    print(
        f"     projections raw: {proj_path.name} shape={proj_raw.shape} "
        f"dtype={proj_raw.dtype}",
        flush=True,
    )
    print(f"     projections prep: shape={proj.shape}", flush=True)
    print(f"     ground truth: {gt_path.name} shape={gt.shape} dtype={gt.dtype}", flush=True)
    print(
        f"     angles: {n_tilts} frames, [{tilt_min}, {tilt_max}] step={step_deg}°",
        flush=True,
    )
    print(f"     output: {out.resolve()}", flush=True)
    return out


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Aligned model TIFFs to ET-dflow dataset layout."
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=DEFAULT_SRC,
        help="Source directory containing model.tif and Proj_tilt_* files",
    )
    parser.add_argument(
        "--variant",
        choices=sorted(VARIANTS),
        default="sm70",
        help="Missing-wedge / sparse variant (default: sm70)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output dataset root (default: data/datasets/simulated/aligned_model_<variant>_v1)",
    )
    return parser.parse_args()


def main() -> None:
    if sys.platform == "win32":
        import io

        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

    args = parse_args()
    out = args.out or Path(f"./data/datasets/simulated/aligned_model_{args.variant}_v1")
    convert_variant(args.src.resolve(), out.resolve(), args.variant)


if __name__ == "__main__":
    main()
