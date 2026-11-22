#!/usr/bin/env python3
"""Convert RESIRE Zenodo datasets into ET-dflow layout.

Source: https://zenodo.org/records/7819857 (RESIRE_publication.zip)

Examples:
  # After unzipping under data/datasets/raw_downloads/resire/
  python scripts/convert_resire_to_etdflow.py --all

  python scripts/convert_resire_to_etdflow.py --dataset vesicle
  python scripts/convert_resire_to_etdflow.py --dataset coral --axis-prep
"""

from __future__ import annotations

import argparse
import zipfile
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import numpy as np
import yaml

import hyperspy.api as hs

from et_dflow.infrastructure.data.preprocessing.steps.alignment.tilt_axis_rotate import (
    prepare_projections_for_wbp,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW = ROOT / "data" / "datasets" / "raw_downloads" / "resire"
ZIP_NAME = "RESIRE_publication.zip"
DATA_SUBDIR = Path("RESIRE_publication") / "data"

# dataset_id -> conversion spec
DATASETS: Dict[str, Dict[str, Any]] = {
    "vesicle": {
        "dataset_id": "resire_vesicle_v1",
        "name": "RESIRE Vesicle (simulated)",
        "type": "simulated",
        "out": ROOT / "data" / "datasets" / "simulated" / "resire_vesicle_v1",
        "proj_mat": DATA_SUBDIR / "vesicle" / "vesicle3_projections.mat",
        "angles_mat": DATA_SUBDIR / "vesicle" / "vesicle3_angles.mat",
        "gt_mrc": DATA_SUBDIR / "vesicle" / "vesicle.mrc",
        "material": "vesicle_phantom",
        "sample_type": "biological_vesicle",
        "description": (
            "RESIRE SciRep 2023 simulated vesicle (64^3), "
            "41 projections ±70° / 3.5°, with ground-truth volume."
        ),
        "citation": "Pham et al., Sci Rep 13, 5624 (2023); Zenodo 10.5281/zenodo.7819857",
    },
    "coral": {
        "dataset_id": "resire_aragonite_coral_v1",
        "name": "RESIRE Aragonite Coral",
        "type": "experimental",
        "out": ROOT
        / "data"
        / "datasets"
        / "experimental"
        / "public"
        / "resire_aragonite_coral_v1",
        "proj_mat": DATA_SUBDIR / "coral" / "dragonhead_projections_processed.mat",
        "angles_mat": DATA_SUBDIR / "coral" / "dragonhead_angles.mat",
        "gt_mrc": None,
        "material": "aragonite",
        "sample_type": "biomineral",
        "description": (
            "RESIRE SciRep 2023 aragonite coral ADF-STEM tilt series "
            "(69 projections, −60°…+76°, pre-aligned)."
        ),
        "citation": "Pham et al., Sci Rep 13, 5624 (2023); Zenodo 10.5281/zenodo.7819857",
    },
    "thinfilm": {
        "dataset_id": "resire_ta_thinfilm_v1",
        "name": "RESIRE Amorphous Ta Thin Film",
        "type": "experimental",
        "out": ROOT
        / "data"
        / "datasets"
        / "experimental"
        / "public"
        / "resire_ta_thinfilm_v1",
        "proj_mat": DATA_SUBDIR / "thinfilm" / "proj_crop3.mat",
        "angles_mat": DATA_SUBDIR / "thinfilm" / "final_ang.mat",
        "gt_mrc": None,
        "material": "Ta",
        "sample_type": "amorphous_thin_film",
        "description": (
            "RESIRE SciRep 2023 amorphous Ta thin-film ADF-STEM tilt series "
            "(Zenodo deposit: 51 projections in proj_crop3.mat + final_ang.mat, "
            "pre-aligned/cropped; paper text cites a 46-projection subset)."
        ),
        "citation": "Pham et al., Sci Rep 13, 5624 (2023); Zenodo 10.5281/zenodo.7819857",
    },
}


def _load_mat(path: Path) -> Dict[str, np.ndarray]:
    """Load MATLAB .mat (v5 via scipy, v7.3 via h5py)."""
    try:
        from scipy.io import loadmat

        raw = loadmat(str(path), squeeze_me=False, struct_as_record=False)
        return {
            k: np.asarray(v)
            for k, v in raw.items()
            if not k.startswith("__")
        }
    except NotImplementedError:
        pass
    except ValueError as exc:
        if "HDF" not in str(exc) and "MATLAB 7.3" not in str(exc):
            raise

    import h5py

    out: Dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as f:
        for key in f.keys():
            out[key] = np.asarray(f[key])
    return out


def _pick_array(
    arrays: Dict[str, np.ndarray],
    prefer_ndim: Optional[int] = None,
    min_ndim: int = 1,
) -> Tuple[str, np.ndarray]:
    """Pick the most likely data array from a .mat dict."""
    items = [(k, v) for k, v in arrays.items() if np.asarray(v).ndim >= min_ndim]
    if not items:
        raise ValueError(f"No usable arrays in mat keys={list(arrays)}")
    if prefer_ndim is not None:
        preferred = [(k, v) for k, v in items if np.asarray(v).ndim == prefer_ndim]
        if preferred:
            items = preferred
    # Prefer larger arrays (actual data over metadata scalars).
    items.sort(key=lambda kv: np.asarray(kv[1]).size, reverse=True)
    key, val = items[0]
    return key, np.asarray(val)


def _ensure_nhw(proj: np.ndarray) -> np.ndarray:
    """Normalize projection stack to (N, H, W)."""
    arr = np.asarray(proj, dtype=np.float32)
    if arr.ndim != 3:
        raise ValueError(f"Expected 3D projections, got shape {arr.shape}")

    # Heuristics: tilt count is usually the smallest or medium axis for ET stacks.
    # Common layouts: (H,W,N), (N,H,W), (H,N,W).
    shape = arr.shape
    # If first dim is square-ish with second and third is smaller -> likely HWN
    if shape[0] == shape[1] and shape[2] < shape[0]:
        arr = np.moveaxis(arr, -1, 0)
    elif shape[1] == shape[2] and shape[0] <= max(shape[1], shape[2]):
        # already NHW or close
        pass
    elif shape[0] == shape[2] and shape[1] < shape[0]:
        # H N W
        arr = np.moveaxis(arr, 1, 0)
    else:
        # Fallback: put the smallest axis first as N
        n_axis = int(np.argmin(shape))
        if n_axis != 0:
            arr = np.moveaxis(arr, n_axis, 0)
    return np.ascontiguousarray(arr, dtype=np.float32)


def _extract_tilt_angles(angles_raw: np.ndarray, n_proj: int) -> np.ndarray:
    """Extract 1D tilt angles (degrees) from RESIRE angle arrays."""
    a = np.asarray(angles_raw, dtype=np.float64)
    a = np.squeeze(a)
    if a.ndim == 0:
        raise ValueError("Angle array is scalar")
    if a.ndim == 1:
        if a.size == n_proj:
            return a.astype(np.float64)
        raise ValueError(f"1D angles size {a.size} != n_proj {n_proj}")
    if a.ndim == 2:
        # RESIRE often stores (N,3) or (3,N) Euler angles; theta is usually col/row 1.
        if a.shape[0] == n_proj:
            if a.shape[1] == 1:
                return a[:, 0]
            if a.shape[1] >= 2:
                # Prefer middle column if 3 Euler angles (phi, theta, psi)
                return a[:, 1] if a.shape[1] == 3 else a[:, 0]
        if a.shape[1] == n_proj:
            if a.shape[0] == 1:
                return a[0]
            if a.shape[0] >= 2:
                return a[1] if a.shape[0] == 3 else a[0]
    raise ValueError(
        f"Cannot interpret angles shape {angles_raw.shape} for n_proj={n_proj}"
    )


def _read_mrc(path: Path) -> np.ndarray:
    try:
        import mrcfile

        with mrcfile.open(str(path), permissive=True) as mrc:
            return np.asarray(mrc.data, dtype=np.float32)
    except ImportError:
        pass
    # Minimal MRC reader (mode 2 float32)
    with open(path, "rb") as f:
        header = f.read(1024)
        nx, ny, nz = np.frombuffer(header[0:12], dtype="<i4")
        mode = int(np.frombuffer(header[12:16], dtype="<i4")[0])
        dtype_map = {0: np.int8, 1: np.int16, 2: np.float32, 6: np.uint16}
        if mode not in dtype_map:
            raise ValueError(f"Unsupported MRC mode {mode} for {path}")
        data = np.frombuffer(f.read(), dtype=dtype_map[mode])
        data = data[: int(nx) * int(ny) * int(nz)].reshape(
            (int(nz), int(ny), int(nx))
        )
        return np.asarray(data, dtype=np.float32)


def _write_tilt_series_hspy(proj: np.ndarray, angles: np.ndarray, out_path: Path) -> None:
    data = np.asarray(proj, dtype=np.float32)
    signal = hs.signals.Signal2D(data)
    signal.metadata.set_item("General.title", "RESIRE tilt series")
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
        raise ValueError(f"Expected 3D volume, got {data.shape}")
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


def ensure_extracted(raw_root: Path) -> Path:
    """Ensure RESIRE_publication/data exists under raw_root; unzip if needed."""
    data_root = raw_root / DATA_SUBDIR
    if data_root.is_dir():
        return data_root
    zip_path = raw_root / ZIP_NAME
    if not zip_path.is_file():
        raise FileNotFoundError(
            f"Missing {zip_path}. Download from "
            "https://zenodo.org/records/7819857/files/RESIRE_publication.zip?download=1"
        )
    print(f"[extract] unzipping {zip_path} -> {raw_root}", flush=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        zf.extractall(raw_root)
    if not data_root.is_dir():
        # Some archives may nest differently; search.
        matches = list(raw_root.rglob("vesicle3_projections.mat"))
        if not matches:
            raise FileNotFoundError(f"Could not find data after extract under {raw_root}")
        return matches[0].parents[1]  # .../data
    return data_root


def convert_one(
    key: str,
    raw_root: Path,
    apply_axis_prep: bool,
) -> Path:
    spec = DATASETS[key]
    ensure_extracted(raw_root)
    proj_path = (raw_root / spec["proj_mat"]).resolve()
    angles_path = (raw_root / spec["angles_mat"]).resolve()
    if not proj_path.is_file():
        hits = list(raw_root.rglob(Path(spec["proj_mat"]).name))
        if not hits:
            raise FileNotFoundError(proj_path)
        proj_path = hits[0]
        angles_path = proj_path.parent / Path(spec["angles_mat"]).name

    print(f"[convert:{key}] projections={proj_path}", flush=True)
    print(f"[convert:{key}] angles={angles_path}", flush=True)

    proj_key, proj_raw = _pick_array(_load_mat(proj_path), prefer_ndim=3, min_ndim=3)
    ang_key, ang_raw = _pick_array(_load_mat(angles_path), min_ndim=1)
    print(
        f"[convert:{key}] mat keys proj={proj_key}{tuple(proj_raw.shape)} "
        f"ang={ang_key}{tuple(np.asarray(ang_raw).shape)}",
        flush=True,
    )

    proj = _ensure_nhw(proj_raw)
    angles = _extract_tilt_angles(ang_raw, n_proj=proj.shape[0])
    # Keep ascending tilt order for pipeline consistency.
    order = np.argsort(angles)
    if not np.all(order == np.arange(len(angles))):
        angles = angles[order]
        proj = proj[order]
        print(f"[convert:{key}] sorted projections by ascending tilt", flush=True)
    tilt_min = float(np.min(angles))
    tilt_max = float(np.max(angles))
    step = float(np.median(np.diff(angles))) if proj.shape[0] >= 2 else 0.0

    axis_meta = None
    if apply_axis_prep:
        print(
            f"[convert:{key}] tilt-axis prep (rotate_mode=auto, snap_to_90=True)",
            flush=True,
        )
        proj, angles, axis_meta = prepare_projections_for_wbp(
            proj,
            angles,
            rotate_mode="auto",
            snap_to_90=True,
            tolerance_deg=5.0,
        )
        print(
            f"[convert:{key}] axis QC: action={axis_meta.get('action')} "
            f"correction={axis_meta.get('correction_applied_deg'):.2f}° "
            f"shape {axis_meta.get('original_shape_nhw')} -> {axis_meta.get('wbp_shape_nhw')}",
            flush=True,
        )

    out: Path = spec["out"]
    raw_dir = out / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    tilt_hspy = raw_dir / "tilt_series.hspy"
    angles_txt = raw_dir / "tilt_angles.txt"
    _write_tilt_series_hspy(proj, angles, tilt_hspy)
    angles_txt.write_text(
        "\n".join(f"{a:.6f}" for a in angles) + "\n", encoding="utf-8"
    )

    has_gt = False
    gt_shape = None
    if spec["gt_mrc"] is not None:
        gt_path = (raw_root / spec["gt_mrc"]).resolve()
        if not gt_path.is_file():
            hits = list(raw_root.rglob(Path(spec["gt_mrc"]).name))
            if not hits:
                raise FileNotFoundError(gt_path)
            gt_path = hits[0]
        print(f"[convert:{key}] GT={gt_path}", flush=True)
        gt = _read_mrc(gt_path)
        gt_dir = out / "ground_truth"
        _write_volume_hspy(gt, gt_dir / "volume.hspy", title="RESIRE vesicle ground truth")
        has_gt = True
        gt_shape = list(gt.shape)

    size_mb = tilt_hspy.stat().st_size / (1024 * 1024)
    today = date.today().isoformat()
    metadata: Dict[str, Any] = {
        "dataset_id": spec["dataset_id"],
        "name": spec["name"],
        "version": "1.0",
        "type": spec["type"],
        "has_ground_truth": has_gt,
        "created_date": today,
        "last_updated": today,
        "source": "RESIRE Zenodo 10.5281/zenodo.7819857",
        "citation": spec["citation"],
        "source_files": {
            "projections": str(proj_path),
            "angles": str(angles_path),
            "ground_truth": str(spec["gt_mrc"]) if has_gt else None,
        },
        "tilt_range": [tilt_min, tilt_max],
        "missing_wedge_angle": float(max(abs(tilt_min), abs(tilt_max))),
        "missing_wedge_deg": float(180.0 - (tilt_max - tilt_min)),
        "angular_step_deg": step,
        "num_projections": int(proj.shape[0]),
        "projection_shape_raw": list(np.asarray(proj_raw).shape),
        "projection_shape": list(proj.shape),
        "data_files": {
            "tilt_series": {
                "path": "raw/tilt_series.hspy",
                "format": "hyperspy",
                "size_mb": round(size_mb, 3),
                "shape": list(proj.shape),
                "dtype": "float32",
            },
            "ground_truth": {
                "available": has_gt,
                **(
                    {
                        "path": "ground_truth/volume.hspy",
                        "format": "hyperspy",
                        "shape": gt_shape,
                    }
                    if has_gt
                    else {}
                ),
            },
            "tilt_angles": {
                "path": "raw/tilt_angles.txt",
                "format": "txt",
            },
        },
        "experimental_parameters": {
            "tilt_range": [tilt_min, tilt_max],
            "tilt_step": step,
            "num_projections": int(proj.shape[0]),
            "tilt_axis": "single",
            "aligned_source": True,
        },
        "sample": {
            "type": spec["sample_type"],
            "material": spec["material"],
            "description": spec["description"],
        },
        "paths": {
            "tilt_series": "raw/tilt_series.hspy",
            "tilt_angles": "raw/tilt_angles.txt",
            "ground_truth": "ground_truth/volume.hspy" if has_gt else None,
        },
        "created": {
            "date": today,
            "source": "RESIRE Zenodo",
        },
    }
    if axis_meta is not None:
        metadata["tilt_axis_prep"] = axis_meta

    (out / "metadata.yaml").write_text(
        yaml.safe_dump(metadata, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    (out / "README.md").write_text(
        "\n".join(
            [
                f"# {spec['name']}",
                "",
                f"- **dataset_id**: `{spec['dataset_id']}`",
                f"- **type**: {spec['type']}",
                f"- **has_ground_truth**: {str(has_gt).lower()}",
                f"- **source**: RESIRE Zenodo ([10.5281/zenodo.7819857](https://doi.org/10.5281/zenodo.7819857))",
                f"- **citation**: {spec['citation']}",
                f"- **tilt range**: [{tilt_min:.3f}, {tilt_max:.3f}] deg "
                f"({proj.shape[0]} frames, median step ≈ {step:.4f}°)",
                f"- **shape**: `{list(proj.shape)}` (N, H, W)",
                "",
                spec["description"],
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(
        f"[ok:{key}] {out} shape={proj.shape} angles=[{angles[0]:.3f},{angles[-1]:.3f}] "
        f"GT={'yes' if has_gt else 'no'}",
        flush=True,
    )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW,
        help="Directory containing RESIRE_publication.zip or extracted tree",
    )
    p.add_argument(
        "--dataset",
        choices=list(DATASETS) + ["all"],
        default="all",
        help="Which RESIRE subset to convert",
    )
    p.add_argument(
        "--all",
        action="store_true",
        help="Convert all three datasets (alias for --dataset all)",
    )
    p.add_argument(
        "--axis-prep",
        action="store_true",
        help="Apply tilt-axis rotate/snap (off by default; RESIRE deposits are pre-aligned).",
    )
    p.add_argument(
        "--no-axis-prep",
        action="store_true",
        help=argparse.SUPPRESS,  # backwards-compatible alias
    )
    args = p.parse_args()
    raw_root = args.raw_root.resolve()
    keys = list(DATASETS) if (args.all or args.dataset == "all") else [args.dataset]
    apply_axis_prep = bool(args.axis_prep) and not bool(args.no_axis_prep)
    for key in keys:
        convert_one(key, raw_root=raw_root, apply_axis_prep=apply_axis_prep)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
