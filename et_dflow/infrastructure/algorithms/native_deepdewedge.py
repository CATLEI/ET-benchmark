"""
DeepDeWedge bridge: even/odd ramp FBP, then ``ddw`` prepare / fit / refine.

Paper (Wiedemann & Heckel, Nat Commun 2024) Step 1 splits the tilt series by
acquisition order, reconstructs each half with ramp FBP, then feeds the pair
into DeepDeWedge. Official ``ddw`` does not perform that FBP; this module does
it in-process (NumPy + :func:`apply_parallel_fbp_filter`), then runs:

1. ``ddw prepare-data``
2. ``ddw fit-model``
3. pick lowest validation-loss checkpoint
4. ``ddw refine-tomogram``

Optional refine-only mode: set ``ddw_refine_config_yaml`` and
``ddw_pipeline: false`` to skip FBP/training and only run refine.
"""

from __future__ import annotations

import csv
import math
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import hyperspy.api as hs
import numpy as np
import yaml

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.native_astra import apply_parallel_fbp_filter
from et_dflow.infrastructure.algorithms.volume_io import (
    load_volume_array_from_path,
    resolve_cli_output_volume,
)


def _require_ddw() -> str:
    ddw_bin = shutil.which("ddw")
    if not ddw_bin:
        raise RuntimeError("Executable 'ddw' not found on PATH")
    return ddw_bin


def _write_mrc(path: Path, volume: np.ndarray) -> None:
    import mrcfile

    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.ascontiguousarray(volume, dtype=np.float32)
    with mrcfile.new(str(path), overwrite=True) as mrc:
        mrc.set_data(arr)


def _mw_angle_degrees(angles_deg: np.ndarray, config: Dict[str, Any]) -> int:
    if config.get("ddw_mw_angle") is not None:
        return int(round(float(config["ddw_mw_angle"])))
    if angles_deg.size >= 2:
        span = float(np.max(angles_deg) - np.min(angles_deg))
    else:
        tilt_range = config.get("tilt_range") or [-60.0, 60.0]
        span = float(tilt_range[1]) - float(tilt_range[0])
    mw = int(round(180.0 - span))
    if mw <= 0 or mw >= 180:
        raise ValueError(
            "Computed mw_angle=%s from tilt span=%s is invalid; set ddw_mw_angle"
            % (mw, span)
        )
    return mw


def _subtomo_size_for_volume(shape: Tuple[int, ...], config: Dict[str, Any]) -> int:
    if config.get("ddw_subtomo_size") is not None:
        size = int(config["ddw_subtomo_size"])
    else:
        size = 96
    vmin = int(min(shape))
    if vmin < 64:
        raise ValueError(
            "Tomogram min dim %s < 64; DeepDeWedge subtomo_size cannot be set" % vmin
        )
    size = min(size, vmin)
    size = (size // 8) * 8
    if size < 64:
        raise ValueError(
            "Aligned subtomo_size %s < 64 for volume shape %s" % (size, shape)
        )
    return size


def _ddw_enlarged_subtomo_size(subtomo_size: int) -> int:
    """Match DeepDeWedge ``ceil_to_even_integer(sqrt(2) * subtomo_size)``."""
    return int(math.ceil((math.sqrt(2) * float(subtomo_size)) / 2.0) * 2)


def _extract_larger_subtomos_for_volume(
    shape: Tuple[int, ...],
    subtomo_size: int,
    config: Dict[str, Any],
) -> bool:
    """
    DDW defaults ``extract_larger_subtomos_for_rotating=True``, which expands the
    unfold window to ~sqrt(2)*size (64 → 92). On volumes smaller than that
    expanded size (e.g. RESIRE vesicle 64³) prepare-data crashes. Disable
    automatically unless the user overrides.
    """
    if config.get("ddw_extract_larger_subtomos_for_rotating") is not None:
        return bool(config["ddw_extract_larger_subtomos_for_rotating"])
    vmin = int(min(shape))
    return _ddw_enlarged_subtomo_size(subtomo_size) <= vmin


def _subtomo_grid_count(
    shape: Tuple[int, ...], subtomo_size: int, stride: int
) -> int:
    dims = [int(d) for d in shape]
    if any(d < subtomo_size for d in dims):
        return 0
    n = 1
    for d in dims:
        n *= (d - subtomo_size) // stride + 1
    return int(n)


def _parallel_backproject_slice(
    filtered_sino: np.ndarray, angles_rad: np.ndarray, n_out: int
) -> np.ndarray:
    """Unfiltered parallel BP for one slice; ``filtered_sino`` is ``(n_angles, n_det)``."""
    n_angles, n_det = filtered_sino.shape
    if n_angles != angles_rad.size:
        raise ValueError("sinogram angles mismatch")
    yy, xx = np.mgrid[0:n_out, 0:n_out]
    yy = yy.astype(np.float64) - (n_out - 1) * 0.5
    xx = xx.astype(np.float64) - (n_out - 1) * 0.5
    cx = (n_det - 1) * 0.5
    recon = np.zeros((n_out, n_out), dtype=np.float64)
    for a_idx, theta in enumerate(angles_rad):
        t = xx * np.cos(theta) + yy * np.sin(theta) + cx
        t0 = np.floor(t).astype(np.int32)
        t1 = t0 + 1
        w1 = t - t0
        w0 = 1.0 - w1
        proj = filtered_sino[a_idx]
        vals = np.zeros_like(t, dtype=np.float64)
        valid0 = (t0 >= 0) & (t0 < n_det)
        valid1 = (t1 >= 0) & (t1 < n_det)
        vals[valid0] += w0[valid0] * proj[t0[valid0]]
        vals[valid1] += w1[valid1] * proj[t1[valid1]]
        recon += vals
    return recon.astype(np.float32)


def ramp_fbp_volume(
    projections: np.ndarray, angles_deg: np.ndarray
) -> np.ndarray:
    """
    Ramp (Ram-Lak) FBP for ``projections`` shaped ``(n_angles, H, W)``.

    Returns volume ``(H, W, W)``: filter via :func:`apply_parallel_fbp_filter`,
    then NumPy parallel-beam backprojection (CPU).
    """
    stack = np.asarray(projections, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("projections must be (n_angles, H, W), got %s" % (stack.shape,))
    angles = np.asarray(angles_deg, dtype=np.float64)
    if angles.size != stack.shape[0]:
        raise ValueError(
            "angle count %s != n_angles %s" % (angles.size, stack.shape[0])
        )
    # (H, n_angles, W) for the shared Ram-Lak filter
    sino = np.transpose(stack, (1, 0, 2))
    filtered = apply_parallel_fbp_filter(sino, "ram-lak")
    h, n_angles, w = filtered.shape
    angles_rad = np.deg2rad(angles)
    vol = np.empty((h, w, w), dtype=np.float32)
    for i in range(h):
        vol[i] = _parallel_backproject_slice(filtered[i], angles_rad, w)
        if i == 0 or (i + 1) % 64 == 0 or i + 1 == h:
            print("DDW_RUN step=fbp slice=%s/%s" % (i + 1, h), flush=True)
    return vol


def _even_odd_split(
    stack: np.ndarray, angles: np.ndarray
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Split by acquisition order (paper even/odd), not by tilt sign."""
    n = stack.shape[0]
    if n < 4:
        raise ValueError("Need at least 4 projections for even/odd FBP, got %s" % n)
    even_idx = np.arange(0, n, 2)
    odd_idx = np.arange(1, n, 2)
    return (
        stack[even_idx],
        angles[even_idx],
        stack[odd_idx],
        angles[odd_idx],
    )


def _build_ddw_config_dict(
    *,
    project_dir: Path,
    tomo0: Path,
    tomo1: Path,
    mask_path: Path,
    mw_angle: int,
    subtomo_size: int,
    num_epochs: int,
    standardize: bool,
    volume_shape: Tuple[int, ...],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    extract_larger = _extract_larger_subtomos_for_volume(
        volume_shape, subtomo_size, config
    )
    # Exact-fit volumes (e.g. 64³ with size 64) only yield one cube; use full-size stride.
    default_stride = (
        subtomo_size
        if int(min(volume_shape)) == subtomo_size
        else max(8, round(subtomo_size * 2 / 3))
    )
    stride = int(config.get("ddw_subtomo_stride") or default_stride)
    overlap = int(config.get("ddw_subtomo_overlap") or max(1, subtomo_size // 3))
    n_subtomos = _subtomo_grid_count(volume_shape, subtomo_size, stride)
    if config.get("ddw_val_fraction") is not None:
        val_fraction = float(config["ddw_val_fraction"])
    elif n_subtomos <= 1:
        # ceil(1 * 0.2) == 1 would put the only cube in val and leave fit empty.
        val_fraction = 0.0
    else:
        val_fraction = 0.2
    default_fit_bs = 1 if n_subtomos <= 5 else 5
    fit_bs = int(config.get("ddw_fit_batch_size") or default_fit_bs)
    refine_bs = int(config.get("ddw_refine_batch_size") or min(10, max(1, fit_bs)))
    num_workers = int(config.get("ddw_num_workers") or 4)
    # With val_fraction=0 (e.g. vesicle 64³ → one cube), DDW skips val_loss
    # checkpoints. Our previous save_every=1e9 + fitting_loss=0 wrote nothing.
    has_val = val_fraction > 0.0 and n_subtomos > 1
    if config.get("ddw_save_n_val_loss") is not None:
        save_n_val = int(config["ddw_save_n_val_loss"])
    else:
        save_n_val = 1 if has_val else 0
    if config.get("ddw_save_n_fitting_loss") is not None:
        save_n_fit = int(config["ddw_save_n_fitting_loss"])
    else:
        save_n_fit = 0 if has_val else 1
    if config.get("ddw_save_every_n_epochs") is not None:
        save_every = int(config["ddw_save_every_n_epochs"])
    elif has_val:
        # Prefer val_loss top-k; avoid flooding epoch/ with every-epoch dumps.
        save_every = max(num_epochs + 1, 10**9)
    else:
        # Guarantee at least one epoch checkpoint when only fitting_loss is used.
        save_every = max(1, num_epochs)
    pad_before = bool(config.get("ddw_pad_before_subtomo_extraction", False))
    return {
        "shared": {
            "project_dir": str(project_dir),
            "tomo0_files": [str(tomo0)],
            "tomo1_files": [str(tomo1)],
            "subtomo_size": subtomo_size,
            "mw_angle": mw_angle,
            "num_workers": num_workers,
            "gpu": 0,
            "seed": int(config.get("ddw_seed") or 42),
            "standardize_full_tomos": bool(standardize),
        },
        "prepare_data": {
            "mask_files": [str(mask_path)],
            "min_nonzero_mask_fraction_in_subtomo": float(
                config.get("ddw_min_nonzero_mask_fraction", 0.0)
            ),
            "subtomo_extraction_strides": [stride, stride, stride],
            "val_fraction": val_fraction,
            "extract_larger_subtomos_for_rotating": extract_larger,
            "pad_before_subtomo_extraction": pad_before,
        },
        "fit_model": {
            "unet_params_dict": {
                "chans": int(config.get("ddw_unet_chans") or 64),
                "num_downsample_layers": 3,
                "drop_prob": 0.0,
            },
            "adam_params_dict": {"lr": float(config.get("ddw_lr") or 0.0004)},
            "num_epochs": num_epochs,
            "batch_size": fit_bs,
            "update_subtomo_missing_wedges_every_n_epochs": int(
                config.get("ddw_update_mw_every") or 10
            ),
            "check_val_every_n_epochs": int(config.get("ddw_check_val_every") or 1),
            "save_n_models_with_lowest_val_loss": save_n_val,
            "save_n_models_with_lowest_fitting_loss": save_n_fit,
            "save_model_every_n_epochs": save_every,
            "logger": "csv",
        },
        "refine_tomogram": {
            "model_checkpoint_file": "",
            "subtomo_overlap": overlap,
            "batch_size": refine_bs,
        },
    }


def _run_ddw(ddw_bin: str, subcommand: str, yaml_path: Path, env: Dict[str, str]) -> None:
    print("DDW_RUN step=%s config=%s" % (subcommand, yaml_path), flush=True)
    subprocess.run(
        [ddw_bin, subcommand, "--config", str(yaml_path)],
        check=True,
        env=env,
    )


def _parse_loss_from_ckpt_name(path: Path) -> Optional[float]:
    """Parse ``val_loss`` / ``fitting_loss`` from Lightning checkpoint filenames."""
    m = re.search(
        r"(?:val[_-]?loss|fitting[_-]?loss)[=_]?([0-9]*\.?[0-9]+(?:e-?[0-9]+)?)",
        path.name,
        re.I,
    )
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


def _pick_best_val_checkpoint(project_dir: Path) -> Tuple[Path, Optional[float]]:
    logdir = project_dir / "logs"
    preferred_dirs = (
        logdir / "checkpoints" / "val_loss",
        logdir / "checkpoints" / "fitting_loss",
        logdir / "checkpoints" / "epoch",
    )
    candidates: List[Path] = []
    for d in preferred_dirs:
        if d.is_dir():
            found = sorted(d.glob("*.ckpt"))
            if found:
                candidates = found
                break
    if not candidates:
        candidates = sorted(logdir.rglob("*.ckpt")) if logdir.is_dir() else []
    if not candidates:
        raise FileNotFoundError(
            "No DeepDeWedge checkpoints under %s after fit-model" % logdir
        )

    scored: List[Tuple[float, Path]] = []
    for ckpt in candidates:
        loss = _parse_loss_from_ckpt_name(ckpt)
        if loss is not None:
            scored.append((loss, ckpt))

    if not scored:
        # CSV logger metrics
        for metrics in logdir.rglob("metrics.csv"):
            try:
                with metrics.open(newline="") as fh:
                    reader = csv.DictReader(fh)
                    best_epoch = None
                    best_loss = None
                    for row in reader:
                        for key in (
                            "val_loss",
                            "validation_loss",
                            "val_loss_epoch",
                            "fitting_loss",
                        ):
                            if key in row and row[key] not in (None, ""):
                                try:
                                    loss = float(row[key])
                                except ValueError:
                                    continue
                                if best_loss is None or loss < best_loss:
                                    best_loss = loss
                                    best_epoch = row.get("epoch")
                    if best_epoch is not None and best_loss is not None:
                        for ckpt in candidates:
                            if ("epoch=%s" % best_epoch) in ckpt.name or (
                                "epoch_%s" % best_epoch
                            ) in ckpt.name:
                                print(
                                    "DDW_RUN step=pick-model ckpt=%s loss=%s "
                                    "(from %s)"
                                    % (ckpt, best_loss, metrics),
                                    flush=True,
                                )
                                return ckpt, best_loss
            except OSError:
                continue
        chosen = max(candidates, key=lambda p: p.stat().st_mtime)
        print(
            "DDW_RUN step=pick-model ckpt=%s loss=unknown (fallback newest)"
            % chosen,
            flush=True,
        )
        return chosen, None

    scored.sort(key=lambda x: x[0])
    best_loss, best_ckpt = scored[0]
    print(
        "DDW_RUN step=pick-model ckpt=%s loss=%s" % (best_ckpt, best_loss),
        flush=True,
    )
    return best_ckpt, best_loss


def run_deepdewedge_refine(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """Refine-only path when an existing DeepDeWedge YAML is provided."""
    del tilt_series

    yaml_path = config.get("ddw_refine_config_yaml")
    if not yaml_path:
        raise ValueError(
            "native DeepDeWedge refine-only requires parameters.ddw_refine_config_yaml"
        )
    yaml_path = str(Path(yaml_path).expanduser())
    if not os.path.isfile(yaml_path):
        raise FileNotFoundError("ddw_refine_config_yaml not found: %s" % yaml_path)

    ddw_bin = _require_ddw()
    extra_args: List[str] = config.get("ddw_refine_extra_args") or []
    if not isinstance(extra_args, list):
        raise TypeError("ddw_refine_extra_args must be a list of CLI strings")

    cmd: List[str] = [ddw_bin, "refine-tomogram", "--config", yaml_path, *extra_args]
    env = {**os.environ, **(config.get("ddw_env") or {})}
    print("DDW_RUN step=refine-tomogram config=%s" % yaml_path, flush=True)
    subprocess.run(cmd, check=True, env=env)

    chosen = resolve_cli_output_volume(
        config,
        path_key="ddw_output_volume_path",
        dir_key="ddw_output_dir",
        glob_key="ddw_output_glob",
        default_glob="*.mrc",
    )
    vol = load_volume_array_from_path(chosen)
    rec_sig = numpy_volume_to_signal2d(vol, title="DeepDeWedge refinement")
    rec_sig.metadata.set_item("et_dflow.native_solver", "deepdewedge")
    rec_sig.metadata.set_item("et_dflow.ddw_output", str(chosen))
    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="deepdewedge",
        start_time=start_time,
        extra_metadata={"ddw_config": yaml_path, "ddw_output": str(chosen)},
    )


def run_deepdewedge_reconstruction(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """
    Full paper-style pipeline inside the DeepDeWedge container.

    Set ``ddw_pipeline: false`` with ``ddw_refine_config_yaml`` to only refine.
    """
    if config.get("ddw_pipeline", True) is False:
        return run_deepdewedge_refine(tilt_series, config, start_time=start_time)

    ddw_bin = _require_ddw()
    stack = np.asarray(tilt_series.data, dtype=np.float32)
    if stack.ndim != 3:
        raise ValueError("DeepDeWedge expects (n_tilts, H, W), got %s" % (stack.shape,))
    angles = extract_tilt_angles_degrees(tilt_series, config)
    mw_angle = _mw_angle_degrees(angles, config)
    print(
        "DDW_RUN step=split n_tilts=%s mw_angle=%s" % (stack.shape[0], mw_angle),
        flush=True,
    )
    t0, a0, t1, a1 = _even_odd_split(stack, angles)

    print("DDW_RUN step=fbp half=even n=%s" % t0.shape[0], flush=True)
    vol0 = ramp_fbp_volume(t0, a0)
    print("DDW_RUN step=fbp half=odd n=%s" % t1.shape[0], flush=True)
    vol1 = ramp_fbp_volume(t1, a1)
    if vol0.shape != vol1.shape:
        raise RuntimeError(
            "even/odd FBP shapes differ: %s vs %s" % (vol0.shape, vol1.shape)
        )

    subtomo_size = _subtomo_size_for_volume(vol0.shape, config)
    extract_larger = _extract_larger_subtomos_for_volume(
        vol0.shape, subtomo_size, config
    )
    mean_abs = 0.5 * (float(np.mean(np.abs(vol0))) + float(np.mean(np.abs(vol1))))
    std_mean = 0.5 * (float(np.std(vol0)) + float(np.std(vol1)))
    standardize = bool(config.get("ddw_standardize_full_tomos"))
    if config.get("ddw_standardize_full_tomos") is None:
        standardize = mean_abs < 1e-3 or std_mean < 1e-3
    num_epochs = int(config.get("ddw_num_epochs") or 5)

    work_root = Path(config.get("ddw_work_dir") or tempfile.mkdtemp(prefix="et_ddw_"))
    work_root.mkdir(parents=True, exist_ok=True)
    project_dir = work_root / "project"
    project_dir.mkdir(parents=True, exist_ok=True)
    tomo0 = work_root / "tomo0.mrc"
    tomo1 = work_root / "tomo1.mrc"
    mask_path = work_root / "mask.mrc"
    _write_mrc(tomo0, vol0)
    _write_mrc(tomo1, vol1)
    _write_mrc(mask_path, np.ones(vol0.shape, dtype=np.float32))

    cfg = _build_ddw_config_dict(
        project_dir=project_dir,
        tomo0=tomo0,
        tomo1=tomo1,
        mask_path=mask_path,
        mw_angle=mw_angle,
        subtomo_size=subtomo_size,
        num_epochs=num_epochs,
        standardize=standardize,
        volume_shape=tuple(int(x) for x in vol0.shape),
        config=config,
    )
    yaml_path = work_root / "ddw_config.yaml"
    with yaml_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(cfg, fh, sort_keys=False)
    print(
        "DDW_RUN step=write-config path=%s subtomo_size=%s enlarge=%s "
        "enlarged_need=%s vol=%s standardize=%s epochs=%s"
        % (
            yaml_path,
            subtomo_size,
            extract_larger,
            _ddw_enlarged_subtomo_size(subtomo_size),
            tuple(int(x) for x in vol0.shape),
            standardize,
            num_epochs,
        ),
        flush=True,
    )

    env = {**os.environ, **(config.get("ddw_env") or {})}
    # Run from work_root so relative paths inside ddw stay stable if any remain.
    old_cwd = os.getcwd()
    try:
        os.chdir(str(work_root))
        _run_ddw(ddw_bin, "prepare-data", yaml_path, env)
        _run_ddw(ddw_bin, "fit-model", yaml_path, env)
        ckpt, val_loss = _pick_best_val_checkpoint(project_dir)
        cfg["refine_tomogram"]["model_checkpoint_file"] = str(ckpt.resolve())
        with yaml_path.open("w", encoding="utf-8") as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False)
        _run_ddw(ddw_bin, "refine-tomogram", yaml_path, env)
    finally:
        os.chdir(old_cwd)

    refined_dir = project_dir / "refined_tomograms"
    if config.get("ddw_output_volume_path") or config.get("ddw_output_dir"):
        chosen = resolve_cli_output_volume(
            config,
            path_key="ddw_output_volume_path",
            dir_key="ddw_output_dir",
            glob_key="ddw_output_glob",
            default_glob="*.mrc",
        )
    else:
        chosen = resolve_cli_output_volume(
            {
                "ddw_output_dir": str(refined_dir),
                "ddw_output_glob": "*_refined.mrc",
            },
            path_key="ddw_output_volume_path",
            dir_key="ddw_output_dir",
            glob_key="ddw_output_glob",
            default_glob="*_refined.mrc",
        )

    vol = load_volume_array_from_path(chosen)
    rec_sig = numpy_volume_to_signal2d(vol, title="DeepDeWedge reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "deepdewedge")
    rec_sig.metadata.set_item("et_dflow.ddw_output", str(chosen))
    rec_sig.metadata.set_item("et_dflow.ddw_mw_angle", mw_angle)
    if val_loss is not None:
        rec_sig.metadata.set_item("et_dflow.ddw_val_loss", float(val_loss))

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="deepdewedge",
        start_time=start_time,
        extra_metadata={
            "ddw_config": str(yaml_path),
            "ddw_output": str(chosen),
            "ddw_mw_angle": mw_angle,
            "ddw_checkpoint": str(ckpt),
            "ddw_val_loss": val_loss,
            "ddw_subtomo_size": subtomo_size,
            "ddw_num_epochs": num_epochs,
        },
    )
