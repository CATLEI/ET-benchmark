"""Tests for Axis-W crop and Axis-S sparse tilt preparation."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import hyperspy.api as hs
import numpy as np
import yaml

_SCRIPT = (
    Path(__file__).resolve().parents[2] / "scripts" / "prepare_tilt_conditions.py"
)
_spec = importlib.util.spec_from_file_location("prepare_tilt_conditions", _SCRIPT)
_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
sys.modules["prepare_tilt_conditions"] = _mod
_spec.loader.exec_module(_mod)
crop_dataset = _mod.crop_dataset
sparse_dataset = _mod.sparse_dataset


def _fake_dataset(root: Path, tmin: float, tmax: float, step: float) -> Path:
    angles = np.arange(tmin, tmax + 0.5 * step, step, dtype=np.float64)
    if abs(angles[-1] - tmax) > 1e-6:
        angles = np.append(angles, tmax)
    n = len(angles)
    proj = np.arange(n * 4 * 5, dtype=np.float32).reshape(n, 4, 5)
    raw = root / "raw"
    raw.mkdir(parents=True)
    sig = hs.signals.Signal2D(proj)
    sig.metadata.set_item(
        "Acquisition_instrument.TEM.tilt_series", angles.tolist()
    )
    sig.save(str(raw / "tilt_series.hspy"), overwrite=True)
    (raw / "tilt_angles.txt").write_text(
        "\n".join(f"{a:.6f}" for a in angles) + "\n", encoding="utf-8"
    )
    gt_dir = root / "ground_truth"
    gt_dir.mkdir(parents=True)
    hs.signals.Signal2D(np.ones((4, 4, 5), dtype=np.float32)).save(
        str(gt_dir / "volume.hspy"), overwrite=True
    )
    return root


def test_crop_keeps_step_and_wedge(tmp_path: Path):
    src = _fake_dataset(tmp_path / "sm80", -80.0, 80.0, 1.0)
    out = crop_dataset(src, tmp_path / "sm40", tilt_max=40.0)
    meta = yaml.safe_load((out / "metadata.yaml").read_text(encoding="utf-8"))
    assert meta["tilt_range"] == [-40.0, 40.0]
    assert abs(meta["missing_wedge_deg"] - 100.0) < 1e-9
    assert abs(meta["angular_step_deg_median"] - 1.0) < 1e-6
    assert meta["num_projections"] == 81  # -40..40 inclusive


def test_sparse_2deg_keeps_ends(tmp_path: Path):
    src = _fake_dataset(tmp_path / "sm70", -70.0, 70.0, 1.0)
    out = sparse_dataset(src, tmp_path / "sm70_2", step_deg=2.0)
    angles = np.loadtxt(str(out / "raw" / "tilt_angles.txt"))
    assert angles[0] == -70.0
    assert angles[-1] == 70.0
    assert len(angles) == 71
    meta = yaml.safe_load((out / "metadata.yaml").read_text(encoding="utf-8"))
    assert meta["angular_step_deg"] == 2.0
    assert (out / "skipped_angles" / "tilt_angles.txt").is_file()


def test_experimental_holdout(tmp_path: Path):
    src = _fake_dataset(tmp_path / "exp", -70.0, 70.0, 1.0)
    # Drop GT to mimic experimental
    import shutil

    shutil.rmtree(src / "ground_truth")
    out = crop_dataset(
        src, tmp_path / "exp50", tilt_max=50.0, hold_out_high_tilts=True
    )
    meta = yaml.safe_load((out / "metadata.yaml").read_text(encoding="utf-8"))
    assert meta["has_ground_truth"] is False
    assert meta["held_out_high_tilts"]["n_frames"] == 40  # |θ|>50
