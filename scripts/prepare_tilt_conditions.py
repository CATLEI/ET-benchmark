#!/usr/bin/env python3
"""Prepare Axis-W / Axis-S tilt subsets without changing core reconstruction code.

Operations (no interpolation, no added noise):

1. Crop tilt range ``|θ| ≤ alpha`` from a parent stack (Axis W / experimental).
2. Subsample angular step 2° / 4° keeping endpoints (Axis S).
3. Write held-out frames for experimental reprojection tests.

Examples::

    # sm40 from sm80 at 1°
    python scripts/prepare_tilt_conditions.py crop \\
      --src data/datasets/simulated/aligned_model_sm80_v1 \\
      --tilt-max 40 \\
      --out data/datasets/simulated/aligned_model_sm40_v1

    # sparse 2° / 4° from sm70
    python scripts/prepare_tilt_conditions.py sparse \\
      --src data/datasets/simulated/aligned_model_sm70_v1 \\
      --steps 2,4 \\
      --out-root data/datasets/simulated

    # experimental crop with held-out high tilts
    python scripts/prepare_tilt_conditions.py crop \\
      --src data/datasets/experimental/my_exp_v1 \\
      --tilt-max 50 \\
      --hold-out-high-tilts \\
      --out data/datasets/experimental/my_exp_pm50_v1
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import yaml

try:
    import hyperspy.api as hs
except ImportError as exc:  # pragma: no cover
    raise SystemExit(f"hyperspy required: {exc}") from exc


def _load_tilt_series(dataset: Path) -> Tuple[np.ndarray, np.ndarray, Path]:
    raw = dataset / "raw"
    hspy = raw / "tilt_series.hspy"
    angles_txt = raw / "tilt_angles.txt"
    if not hspy.is_file():
        raise FileNotFoundError(f"Missing {hspy}")
    sig = hs.load(str(hspy))
    data = np.asarray(sig.data)
    if angles_txt.is_file():
        angles = np.loadtxt(str(angles_txt), dtype=np.float64)
        if angles.ndim != 1:
            angles = angles.ravel()
    else:
        meta_angles = None
        try:
            meta_angles = sig.metadata.Acquisition_instrument.TEM.tilt_series
        except AttributeError:
            meta_angles = None
        if meta_angles is None:
            raise FileNotFoundError(
                f"No tilt_angles.txt and no metadata tilt_series in {hspy}"
            )
        angles = np.asarray(meta_angles, dtype=np.float64).ravel()
    if len(angles) != data.shape[0]:
        raise ValueError(
            f"Angle count {len(angles)} != projections {data.shape[0]}"
        )
    return data, angles, hspy


def _write_tilt_series(
    out_dataset: Path,
    proj: np.ndarray,
    angles: np.ndarray,
    title: str,
) -> None:
    raw = out_dataset / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    sig = hs.signals.Signal2D(np.asarray(proj, dtype=np.float32))
    sig.metadata.set_item("General.title", title)
    sig.metadata.set_item(
        "Acquisition_instrument.TEM.tilt_series", angles.astype(float).tolist()
    )
    sig.save(str(raw / "tilt_series.hspy"), overwrite=True)
    (raw / "tilt_angles.txt").write_text(
        "\n".join(f"{a:.6f}" for a in angles) + "\n", encoding="utf-8"
    )


def _copy_gt_if_present(src: Path, dst: Path) -> bool:
    gt_src = src / "ground_truth" / "volume.hspy"
    if not gt_src.is_file():
        return False
    gt_dst = dst / "ground_truth"
    gt_dst.mkdir(parents=True, exist_ok=True)
    shutil.copy2(gt_src, gt_dst / "volume.hspy")
    return True


def _write_metadata(
    out: Path,
    payload: Dict[str, Any],
) -> None:
    (out / "metadata.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def crop_dataset(
    src: Path,
    out: Path,
    tilt_max: float,
    hold_out_high_tilts: bool = False,
) -> Path:
    """Keep frames with |θ| ≤ tilt_max; optionally save held-out high tilts."""
    proj, angles, _ = _load_tilt_series(src)
    keep = np.abs(angles) <= float(tilt_max) + 1e-9
    if not np.any(keep):
        raise ValueError(f"No frames with |θ| ≤ {tilt_max}")
    kept_proj = proj[keep]
    kept_ang = angles[keep]
    # Verify step consistency on kept set
    if len(kept_ang) >= 2:
        diffs = np.diff(np.sort(kept_ang))
        step = float(np.median(diffs))
    else:
        step = float("nan")

    out = out.resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    out.mkdir(parents=True)
    _write_tilt_series(
        out,
        kept_proj,
        kept_ang,
        title=f"tilt crop ±{tilt_max}° from {src.name}",
    )
    has_gt = _copy_gt_if_present(src, out)

    held = None
    if hold_out_high_tilts:
        drop = ~keep
        if np.any(drop):
            held_dir = out / "held_out_high_tilts"
            held_dir.mkdir(parents=True)
            np.save(str(held_dir / "projections.npy"), proj[drop])
            np.savetxt(str(held_dir / "tilt_angles.txt"), angles[drop], fmt="%.6f")
            held = {
                "n_frames": int(drop.sum()),
                "tilt_min": float(angles[drop].min()),
                "tilt_max": float(angles[drop].max()),
                "paths": {
                    "projections": "held_out_high_tilts/projections.npy",
                    "tilt_angles": "held_out_high_tilts/tilt_angles.txt",
                },
            }

    meta = {
        "name": out.name,
        "type": "simulated" if has_gt else "experimental_subset",
        "has_ground_truth": has_gt,
        "parent_dataset": str(src.resolve()),
        "operation": "crop_tilt_range",
        "tilt_range": [float(-tilt_max), float(tilt_max)],
        # Protocol definition: wedge = 180 - 2α for single-axis ±α
        "missing_wedge_deg": float(180.0 - 2.0 * tilt_max),
        "tilt_limit_deg": float(tilt_max),
        "angular_step_deg_median": step,
        "num_projections": int(kept_ang.size),
        "held_out_high_tilts": held,
        "paths": {
            "tilt_series": "raw/tilt_series.hspy",
            "tilt_angles": "raw/tilt_angles.txt",
            "ground_truth": "ground_truth/volume.hspy" if has_gt else None,
        },
    }
    _write_metadata(out, meta)
    print(
        f"[ok] crop ±{tilt_max}° -> {out} "
        f"n={kept_ang.size} step≈{step:.4g}° wedge={meta['missing_wedge_deg']}°",
        flush=True,
    )
    return out


def sparse_dataset(
    src: Path,
    out: Path,
    step_deg: float,
) -> Path:
    """Keep every step_deg degrees, forcing endpoints ±max(|θ|)."""
    proj, angles, _ = _load_tilt_series(src)
    order = np.argsort(angles)
    ang = angles[order]
    pr = proj[order]
    t_min = float(ang[0])
    t_max = float(ang[-1])
    # Target grid including ends
    target = np.arange(t_min, t_max + 0.5 * step_deg, step_deg, dtype=np.float64)
    if abs(target[-1] - t_max) > 1e-6:
        target = np.append(target, t_max)
    # Match each target to nearest available angle (exact for integer grids)
    keep_idx: List[int] = []
    used = set()
    for t in target:
        j = int(np.argmin(np.abs(ang - t)))
        if abs(ang[j] - t) > 1e-3:
            raise ValueError(
                f"No frame within 0.001° of target {t}; "
                f"nearest {ang[j]}. Refusing to interpolate."
            )
        if j not in used:
            keep_idx.append(j)
            used.add(j)
    keep_idx = sorted(keep_idx)
    kept_ang = ang[keep_idx]
    kept_proj = pr[keep_idx]

    out = out.resolve()
    if out.exists():
        raise FileExistsError(f"Refusing to overwrite {out}")
    out.mkdir(parents=True)
    _write_tilt_series(
        out,
        kept_proj,
        kept_ang,
        title=f"sparse {step_deg}° from {src.name}",
    )
    has_gt = _copy_gt_if_present(src, out)
    # Skipped angles for reprojection diagnostics
    skip = np.ones(len(ang), dtype=bool)
    skip[keep_idx] = False
    if np.any(skip):
        skip_dir = out / "skipped_angles"
        skip_dir.mkdir(parents=True)
        np.save(str(skip_dir / "projections.npy"), pr[skip])
        np.savetxt(str(skip_dir / "tilt_angles.txt"), ang[skip], fmt="%.6f")

    meta = {
        "name": out.name,
        "type": "simulated" if has_gt else "experimental_subset",
        "has_ground_truth": has_gt,
        "parent_dataset": str(src.resolve()),
        "operation": "sparse_angular_step",
        "tilt_range": [t_min, t_max],
        "missing_wedge_deg": float(180.0 - (t_max - t_min)),
        "angular_step_deg": float(step_deg),
        "num_projections": int(kept_ang.size),
        "note": "per-frame dose fixed; frame count reduced (no added noise)",
        "paths": {
            "tilt_series": "raw/tilt_series.hspy",
            "tilt_angles": "raw/tilt_angles.txt",
            "ground_truth": "ground_truth/volume.hspy" if has_gt else None,
            "skipped_angles": "skipped_angles/" if np.any(skip) else None,
        },
    }
    _write_metadata(out, meta)
    print(
        f"[ok] sparse {step_deg}° -> {out} n={kept_ang.size} "
        f"range=[{t_min}, {t_max}]",
        flush=True,
    )
    return out


def _cmd_crop(args: argparse.Namespace) -> int:
    crop_dataset(
        args.src.resolve(),
        args.out.resolve(),
        tilt_max=float(args.tilt_max),
        hold_out_high_tilts=bool(args.hold_out_high_tilts),
    )
    return 0


def _cmd_sparse(args: argparse.Namespace) -> int:
    steps = [float(x) for x in str(args.steps).split(",") if x.strip()]
    out_root = args.out_root.resolve()
    src = args.src.resolve()
    for step in steps:
        if abs(step - 1.0) < 1e-9:
            print("[skip] step 1° is the parent; not rewriting", flush=True)
            continue
        name = f"{src.name}_step{int(step) if step == int(step) else step}deg"
        if args.out_root_name_prefix:
            name = f"{args.out_root_name_prefix}_pm70_step{int(step)}deg"
        sparse_dataset(src, out_root / name, step_deg=step)
    return 0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_crop = sub.add_parser("crop", help="Axis W / experimental tilt-range crop")
    p_crop.add_argument("--src", type=Path, required=True)
    p_crop.add_argument("--out", type=Path, required=True)
    p_crop.add_argument("--tilt-max", type=float, required=True, help="Keep |θ|≤this")
    p_crop.add_argument(
        "--hold-out-high-tilts",
        action="store_true",
        help="Save dropped high-tilt frames for reprojection tests",
    )
    p_crop.set_defaults(func=_cmd_crop)

    p_sparse = sub.add_parser("sparse", help="Axis S angular sparsification")
    p_sparse.add_argument("--src", type=Path, required=True)
    p_sparse.add_argument("--out-root", type=Path, required=True)
    p_sparse.add_argument("--steps", type=str, default="2,4")
    p_sparse.add_argument(
        "--out-root-name-prefix",
        type=str,
        default="",
        help="Optional prefix instead of parent folder name",
    )
    p_sparse.set_defaults(func=_cmd_sparse)

    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
