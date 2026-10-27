"""
IsoNet bridge: full-tilt WBP, then ``isonet.py`` prepare_star / extract / refine / predict.

Official IsoNet (Liu et al.) expects an existing tomogram (WBP or SIRT), not a raw
tilt series. This module builds that volume in-process with
:class:`~et_dflow.domain.algorithms.wbp.WBPAlgorithm`, then runs:

1. ``isonet.py prepare_star``
2. ``isonet.py extract`` (no CTF deconv)
3. ``isonet.py refine``
4. ``isonet.py predict``

Optional CLI-only mode: set ``isonet_pipeline: false`` and ``isonet_argv`` to skip
automation and run a single user-supplied command (legacy adapter behavior).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Tuple, Union

import hyperspy.api as hs
import numpy as np

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.volume_io import (
    load_volume_array_from_path,
    resolve_cli_output_volume,
)


def _require_isonet_bin() -> str:
    isonet_bin = shutil.which("isonet.py")
    if not isonet_bin:
        raise RuntimeError("Executable 'isonet.py' not found on PATH")
    return isonet_bin


def _write_mrc(path: Path, volume: np.ndarray) -> None:
    import mrcfile

    path.parent.mkdir(parents=True, exist_ok=True)
    arr = np.ascontiguousarray(volume, dtype=np.float32)
    with mrcfile.new(str(path), overwrite=True) as mrc:
        mrc.set_data(arr)


def _cube_size_for_volume(shape: Tuple[int, ...], config: Dict[str, Any]) -> int:
    """Pick cube_size divisible by 8; crop_size = cube_size + 16 must fit volume."""
    if config.get("isonet_cube_size") is not None:
        size = int(config["isonet_cube_size"])
    else:
        size = 64
    vmin = int(min(shape))
    max_cube = ((vmin - 16) // 8) * 8
    if max_cube < 32:
        raise ValueError(
            "Tomogram min dim %s too small for IsoNet extract "
            "(need crop_size=cube+16 >= 48)" % vmin
        )
    size = min(size, max_cube)
    size = (size // 8) * 8
    if size < 32:
        raise ValueError(
            "Aligned isonet_cube_size %s < 32 for volume shape %s" % (size, shape)
        )
    return size


def _run_isonet(
    isonet_bin: str,
    args: List[str],
    *,
    cwd: Path,
    env: Dict[str, str],
) -> None:
    cmd = [isonet_bin, *args]
    print("ISONET_RUN step=%s cmd=%s" % (args[0], " ".join(cmd)), flush=True)
    # Stream output (refine can be long). IsoNet may still exit 0 after internal
    # failures; callers must validate expected artifacts after each step.
    proc = subprocess.run(cmd, cwd=str(cwd), env=env, check=False)
    if proc.returncode != 0:
        raise RuntimeError(
            "IsoNet step %r failed with exit %s" % (args[0], proc.returncode)
        )


def _count_star_data_rows(star_path: Path) -> int:
    """Count non-header data rows in a Relion-style star (rough but enough)."""
    if not star_path.is_file():
        return 0
    count = 0
    in_data = False
    for line in star_path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("data_"):
            in_data = True
            continue
        if not in_data:
            continue
        if s.startswith("loop_") or s.startswith("_") or s.startswith("#"):
            continue
        count += 1
    return count


def _brief_dir_listing(path: Path, *, limit: int = 40) -> str:
    if not path.exists():
        return "%s (missing)" % path
    if not path.is_dir():
        return "%s (not a directory)" % path
    entries = sorted(path.iterdir(), key=lambda p: p.name)
    if not entries:
        return "%s (empty)" % path
    lines = []
    for p in entries[:limit]:
        kind = "dir" if p.is_dir() else "file"
        lines.append("  %s %s" % (kind, p.name))
    if len(entries) > limit:
        lines.append("  ... (%d more)" % (len(entries) - limit))
    return "%s:\n%s" % (path, "\n".join(lines))


def _find_model_checkpoint(result_dir: Path, iterations: int) -> Path:
    # IsoNet saves zero-padded names: model_iter05.h5 for iterations=5.
    preferred = result_dir / ("model_iter%02d.h5" % iterations)
    if preferred.is_file():
        return preferred
    # Also accept unpadded legacy names.
    alt = result_dir / ("model_iter%d.h5" % iterations)
    if alt.is_file():
        return alt
    candidates = sorted(result_dir.glob("model_iter*.h5"))
    if not candidates:
        candidates = sorted(result_dir.glob("*.h5"))
    if not candidates:
        log_txt = result_dir.parent / "log.txt"
        log_hint = ""
        if log_txt.is_file():
            tail = log_txt.read_text(encoding="utf-8", errors="replace")[-2000:]
            log_hint = "\nIsoNet log.txt tail:\n%s" % tail
        raise FileNotFoundError(
            "No IsoNet model .h5 under %s after refine. "
            "IsoNet often exits 0 even when refine fails (empty subtomos, "
            "GPU/TF error swallowed in refine.py). Expected %s.\n%s%s"
            % (
                result_dir,
                preferred.name,
                _brief_dir_listing(result_dir),
                log_hint,
            )
        )
    chosen = max(candidates, key=lambda p: p.stat().st_mtime)
    print(
        "ISONET_RUN step=pick-model preferred_missing=%s using=%s"
        % (preferred, chosen),
        flush=True,
    )
    return chosen


def run_isonet_cli(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """Legacy single-argv path when ``isonet_pipeline`` is false."""
    del tilt_series

    argv = config.get("isonet_argv")
    if not argv:
        raise ValueError(
            "native IsoNet CLI mode requires parameters.isonet_argv "
            "(list of CLI strings), or leave isonet_pipeline true for automation."
        )
    if isinstance(argv, str):
        raise TypeError("isonet_argv must be a list of strings, not a single string")
    cmd: List[str] = [str(x) for x in argv]

    cwd: Optional[Union[str, Path]] = config.get("isonet_cwd")
    if cwd is not None:
        cwd = str(Path(cwd).expanduser())

    extra_env = config.get("isonet_env") or {}
    if not isinstance(extra_env, MutableMapping):
        raise TypeError("isonet_env must be a dict")
    env = {**os.environ, **{str(k): str(v) for k, v in extra_env.items()}}

    subprocess.run(cmd, cwd=cwd, env=env, check=True)

    out_path = resolve_cli_output_volume(
        config,
        path_key="isonet_output_volume_path",
        dir_key="isonet_output_dir",
        glob_key="isonet_output_glob",
        default_glob="*.mrc",
    )
    vol = load_volume_array_from_path(out_path)
    rec_sig = numpy_volume_to_signal2d(vol, title="IsoNet output")
    rec_sig.metadata.set_item("et_dflow.native_solver", "isonet")
    rec_sig.metadata.set_item("et_dflow.isonet_cli", " ".join(cmd))

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="isonet",
        start_time=start_time,
        extra_metadata={"isonet_output": str(out_path)},
    )


def run_isonet_reconstruction(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """
    Full IsoNet pipeline inside the IsoNet container.

    Set ``isonet_pipeline: false`` with ``isonet_argv`` to only run a custom CLI.
    """
    if config.get("isonet_pipeline", True) is False:
        return run_isonet_cli(tilt_series, config, start_time=start_time)

    if config.get("isonet_pixel_size") is None:
        raise ValueError(
            "native IsoNet pipeline requires parameters.isonet_pixel_size (Å/pixel)"
        )
    pixel_size = float(config["isonet_pixel_size"])
    if pixel_size <= 0:
        raise ValueError("isonet_pixel_size must be > 0, got %s" % pixel_size)

    iterations = int(config.get("isonet_iterations") or 5)
    if iterations < 1:
        raise ValueError("isonet_iterations must be >= 1")
    number_subtomos = int(config.get("isonet_number_subtomos") or 100)
    gpu_id = str(config.get("isonet_gpu_id") or "0")
    preprocessing_ncpus = int(config.get("isonet_preprocessing_ncpus") or 8)

    isonet_bin = _require_isonet_bin()

    print("ISONET_RUN step=wbp", flush=True)
    from et_dflow.domain.algorithms.wbp import WBPAlgorithm

    wbp = WBPAlgorithm(config=config)
    wbp_result = wbp.run(tilt_series, config)
    vol = np.asarray(wbp_result.reconstruction.data, dtype=np.float32)
    if vol.ndim != 3:
        raise ValueError("WBP volume must be 3D, got shape %s" % (vol.shape,))
    cube_size = _cube_size_for_volume(vol.shape, config)
    crop_size = cube_size + 16

    work_root = Path(config.get("isonet_work_dir") or tempfile.mkdtemp(prefix="et_isonet_"))
    work_root.mkdir(parents=True, exist_ok=True)
    tomo_dir = work_root / "tomograms"
    tomo_dir.mkdir(parents=True, exist_ok=True)
    tomo_path = tomo_dir / "tomo.mrc"
    _write_mrc(tomo_path, vol)

    star_path = work_root / "tomograms.star"
    subtomo_star = work_root / "subtomo.star"
    result_dir = work_root / "results"
    corrected_dir = work_root / "corrected_tomos"

    env = {**os.environ, **(config.get("isonet_env") or {})}
    # Do NOT pass ``--use_deconv_tomo=False``: Fire in some IsoNet images treats
    # that token as unrecognized and extract never writes subtomo.star. Default
    # True is safe when prepare_star did not run deconv (falls back to raw tomo).
    old_cwd = os.getcwd()
    try:
        os.chdir(str(work_root))
        _run_isonet(
            isonet_bin,
            [
                "prepare_star",
                str(tomo_dir),
                "--output_star",
                str(star_path),
                "--pixel_size",
                str(pixel_size),
                "--number_subtomos",
                str(number_subtomos),
            ],
            cwd=work_root,
            env=env,
        )
        _run_isonet(
            isonet_bin,
            [
                "extract",
                str(star_path),
                "--subtomo_folder",
                str(work_root / "subtomo"),
                "--subtomo_star",
                str(subtomo_star),
                "--cube_size",
                str(cube_size),
            ],
            cwd=work_root,
            env=env,
        )
        if not subtomo_star.is_file():
            raise RuntimeError(
                "IsoNet extract did not create %s. "
                "Refine will swallow FileNotFoundError and exit 0 with no .h5. "
                "Volume shape=%s cube_size=%s.\n%s\n%s"
                % (
                    subtomo_star,
                    vol.shape,
                    cube_size,
                    _brief_dir_listing(work_root / "subtomo"),
                    _brief_dir_listing(work_root),
                )
            )
        n_subtomo = _count_star_data_rows(subtomo_star)
        print(
            "ISONET_RUN step=extract-check subtomo_star=%s n_rows=%d cube_size=%d"
            % (subtomo_star, n_subtomo, cube_size),
            flush=True,
        )
        if n_subtomo < 1:
            raise RuntimeError(
                "IsoNet extract produced an empty subtomo list (%s). "
                "Refine will exit 0 without writing any model. "
                "Try a larger tomogram, smaller isonet_cube_size, or fewer "
                "isonet_number_subtomos. Volume shape=%s cube_size=%s.\n%s\n%s"
                % (
                    subtomo_star,
                    vol.shape,
                    cube_size,
                    _brief_dir_listing(work_root / "subtomo"),
                    _brief_dir_listing(work_root),
                )
            )
        _run_isonet(
            isonet_bin,
            [
                "refine",
                str(subtomo_star),
                "--gpuID",
                gpu_id,
                "--iterations",
                str(iterations),
                "--result_dir",
                str(result_dir),
                "--preprocessing_ncpus",
                str(preprocessing_ncpus),
            ],
            cwd=work_root,
            env=env,
        )
        model = _find_model_checkpoint(result_dir, iterations)
        print("ISONET_RUN step=pick-model ckpt=%s" % model, flush=True)
        _run_isonet(
            isonet_bin,
            [
                "predict",
                str(star_path),
                str(model),
                "--gpuID",
                gpu_id,
                "--output_dir",
                str(corrected_dir),
                "--cube_size",
                str(cube_size),
                "--crop_size",
                str(crop_size),
            ],
            cwd=work_root,
            env=env,
        )
    finally:
        os.chdir(old_cwd)

    if config.get("isonet_output_volume_path") or config.get("isonet_output_dir"):
        chosen = resolve_cli_output_volume(
            config,
            path_key="isonet_output_volume_path",
            dir_key="isonet_output_dir",
            glob_key="isonet_output_glob",
            default_glob="*.mrc",
        )
    else:
        chosen = resolve_cli_output_volume(
            {
                "isonet_output_dir": str(corrected_dir),
                "isonet_output_glob": "*.mrc",
            },
            path_key="isonet_output_volume_path",
            dir_key="isonet_output_dir",
            glob_key="isonet_output_glob",
            default_glob="*.mrc",
        )

    out_vol = load_volume_array_from_path(chosen)
    rec_sig = numpy_volume_to_signal2d(out_vol, title="IsoNet reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "isonet")
    rec_sig.metadata.set_item("et_dflow.isonet_output", str(chosen))
    rec_sig.metadata.set_item("et_dflow.isonet_pixel_size", pixel_size)
    rec_sig.metadata.set_item("et_dflow.isonet_iterations", iterations)

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="isonet",
        start_time=start_time,
        extra_metadata={
            "isonet_output": str(chosen),
            "isonet_pixel_size": pixel_size,
            "isonet_iterations": iterations,
            "isonet_cube_size": cube_size,
            "isonet_model": str(model),
            "isonet_work_dir": str(work_root),
        },
    )
