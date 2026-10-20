"""
WUCon (WUCON) bridge: stage tilt series, patch upstream src, run recon chunks.

Official WUCON (Van Veen et al.) expects ``{dataset}_prj.mrc`` + ``tilt_angles.tlt``
and hard-coded paths in ``constants.py``. This module:

1. Writes ``etbench`` data under a work directory
2. Copies WUCON ``src`` and patches ``constants.py`` / ``parser.py``
3. Runs ``recon_chunk.py`` (mid, then optional full y-sweep) with ``check=True``
4. Assembles ``mrc/out.mrc`` via upstream ``CryoLoad`` (not official RECON_SUBSET,
   which skips the MRC write)

Optional CLI-only mode: ``wucon_pipeline: false`` + ``wucon_argv``.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Tuple, Union

import numpy as np

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    extract_tilt_angles_degrees,
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.volume_io import (
    load_volume_array_from_path,
    resolve_cli_output_volume,
)

DATASET_NAME = "etbench"
_REQUIRED_SRC_FILES = ("recon_chunk.py", "constants.py", "parser.py", "dataset.py")


def resolve_wucon_src_dir(config: Dict[str, Any]) -> Path:
    """Resolve upstream WUCON ``src`` directory."""
    candidates: List[Path] = []
    if config.get("wucon_src_dir"):
        candidates.append(Path(str(config["wucon_src_dir"])).expanduser())
    env_src = os.environ.get("WUCON_SRC")
    if env_src:
        candidates.append(Path(env_src).expanduser())
    candidates.append(Path("/opt/wucon/src"))

    for cand in candidates:
        if cand.is_dir() and all((cand / name).is_file() for name in _REQUIRED_SRC_FILES):
            return cand.resolve()
    tried = ", ".join(str(c) for c in candidates)
    raise FileNotFoundError(
        "WUCON src not found (need recon_chunk.py etc.). Tried: %s. "
        "Set parameters.wucon_src_dir or env WUCON_SRC." % tried
    )


def ensure_even_height(stack: np.ndarray) -> np.ndarray:
    """Crop last row if height (axis 1) is odd so WUCON batch_size=2 divides it."""
    arr = np.asarray(stack, dtype=np.float32)
    if arr.ndim != 3:
        raise ValueError("tilt series must be (n_tilts, H, W), got %s" % (arr.shape,))
    n, h, w = arr.shape
    if h < 2:
        raise ValueError("tilt series height H=%s too small for WUCON chunks" % h)
    if h % 2 == 1:
        print("WUCON_RUN step=crop-odd-height %s -> %s" % (h, h - 1), flush=True)
        arr = arr[:, : h - 1, :]
    return arr


def write_mrc(path: Path, array: np.ndarray) -> None:
    import mrcfile

    path.parent.mkdir(parents=True, exist_ok=True)
    with mrcfile.new(str(path), overwrite=True) as mrc:
        mrc.set_data(np.ascontiguousarray(array, dtype=np.float32))


def write_tlt(path: Path, angles_deg: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ang in np.asarray(angles_deg, dtype=np.float64).reshape(-1):
            fh.write("%s\n" % float(ang))


def stage_wucon_inputs(
    tilt_series: Any,
    config: Dict[str, Any],
    work_root: Path,
) -> Dict[str, Any]:
    """
    Write ``data/etbench/etbench_prj.mrc`` and ``tilt_angles.tlt``.

    Returns meta including shapes after even-H crop and paths.
    """
    stack = ensure_even_height(np.asarray(tilt_series.data, dtype=np.float32))
    angles = extract_tilt_angles_degrees(tilt_series, config)
    if angles.size != stack.shape[0]:
        # Re-derive linspace if crop changed n_tilts (should not); else truncate/pad.
        if angles.size > stack.shape[0]:
            angles = angles[: stack.shape[0]]
        else:
            raise ValueError(
                "tilt angle count %s != n_tilts %s" % (angles.size, stack.shape[0])
            )

    n_tilts, height, width = stack.shape
    # After official load_prj_file rot90(k=-1): shape (n, W, H)
    prj_size_load = (width, height)
    img_size_load = (width, height, width)

    data_dir = work_root / "data" / DATASET_NAME
    data_dir.mkdir(parents=True, exist_ok=True)
    prj_path = data_dir / ("%s_prj.mrc" % DATASET_NAME)
    tlt_path = data_dir / "tilt_angles.tlt"
    write_mrc(prj_path, stack)
    write_tlt(tlt_path, angles)

    return {
        "n_tilts": n_tilts,
        "height": height,
        "width": width,
        "prj_size_load": prj_size_load,
        "img_size_load": img_size_load,
        "prj_path": prj_path,
        "tlt_path": tlt_path,
        "data_dir": data_dir,
        "angles": angles,
    }


def _render_constants_py(
    *,
    dir_project: Path,
    dir_data: Path,
    img_size_load: Tuple[int, int, int],
    prj_size_load: Tuple[int, int],
    n_tilts: int,
    n_epochs_mid: int,
    n_epochs_all: int,
    case_id: int,
) -> str:
    return textwrap.dedent(
        """\
        import os

        USER = 'etbench'
        DIR_PROJECT = {dir_project!r}
        DIR_DATA = {dir_data!r}
        assert os.path.exists(DIR_PROJECT) and os.path.exists(DIR_DATA)

        MODEL = 'mlp'
        N_FEATURES = 256
        N_LAYERS = 4
        N_INP = 3
        N_OUT = 1

        N_EPOCHS_MID = {n_epochs_mid}
        N_EPOCHS_ALL = {n_epochs_all}

        LOSS_FN = 'l1'
        GPU = 0
        SEED = 0

        USE_LR_SCHEDULER = True
        USE_HALF_PRECISION = True
        USE_BATCHES = True
        EPOCHS_TIL_CKPT = 200
        EPOCHS_TIL_SUMMARY = 100

        N_SLICES_PER_NET = 2
        BATCH_SIZE = 2

        CONFIGS_DATA_TYPE = {{
            'sim': {{
                'lr': 1e-3,
                'lam_tv': 0,
                'n_sparse_prj': 61,
                'fn_tlt': 'tilt_angles.tlt',
            }},
            'acq': {{
                'lr': 1e-3,
                'lam_tv': 1.,
                'fn_tgt': '',
            }},
        }}

        FN_METRICS = 'metrics.json'
        FN_OUT = 'out_val.pt'

        DATASETS = ['etbench']
        DATASETS_SIM = []
        DATASETS_ACQ = ['etbench']

        CONFIGS_DATASET = {{
            'etbench': {{
                'img_size_load': {img_size_load!r},
                'prj_size_load': {prj_size_load!r},
                'fn_prj': 'etbench_prj.mrc',
                'fn_tgt': '',
                'n_sparse_prj': {n_tilts},
                'fn_tlt': 'tilt_angles.tlt',
            }},
        }}

        cases = {{
            0: {{}},
            99: {{}},
            {case_id}: {{}},
        }}
        """
    ).format(
        dir_project=str(dir_project),
        dir_data=str(dir_data),
        n_epochs_mid=int(n_epochs_mid),
        n_epochs_all=int(n_epochs_all),
        img_size_load=tuple(int(x) for x in img_size_load),
        prj_size_load=tuple(int(x) for x in prj_size_load),
        n_tilts=int(n_tilts),
        case_id=int(case_id),
    )


def patch_parser_choices(parser_text: str) -> str:
    """Allow ``etbench`` in argparse dataset choices."""
    patched, n = re.subn(
        r"choices\s*=\s*\[[^\]]*\]",
        "choices=['sph', 'geo', 'p2s', 'etbench']",
        parser_text,
        count=1,
    )
    if n == 0:
        raise RuntimeError("Could not patch dataset choices in parser.py")
    return patched


def prepare_wucon_src_copy(
    src_dir: Path,
    work_root: Path,
    *,
    staged: Dict[str, Any],
    n_epochs_mid: int,
    n_epochs_all: int,
    case_id: int,
) -> Path:
    """Copy upstream src into work_root and apply constants/parser patches."""
    dest = work_root / "wucon_src"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src_dir, dest)

    dir_project = work_root
    dir_data = work_root / "data"
    dir_project.mkdir(parents=True, exist_ok=True)
    dir_data.mkdir(parents=True, exist_ok=True)

    constants_text = _render_constants_py(
        dir_project=dir_project,
        dir_data=dir_data,
        img_size_load=staged["img_size_load"],
        prj_size_load=staged["prj_size_load"],
        n_tilts=staged["n_tilts"],
        n_epochs_mid=n_epochs_mid,
        n_epochs_all=n_epochs_all,
        case_id=case_id,
    )
    (dest / "constants.py").write_text(constants_text, encoding="utf-8")

    parser_path = dest / "parser.py"
    parser_path.write_text(
        patch_parser_choices(parser_path.read_text(encoding="utf-8")),
        encoding="utf-8",
    )
    return dest


def _run_checked(
    cmd: List[str],
    *,
    cwd: Path,
    env: Dict[str, str],
    step: str,
) -> None:
    print("WUCON_RUN step=%s cmd=%s" % (step, " ".join(cmd)), flush=True)
    subprocess.run(cmd, cwd=str(cwd), env=env, check=True)


def _chunk_cmd(
    *,
    python: str,
    case_id: int,
    dataset: str,
    expmt_type: str,
    gpu: int,
    idx_y: Optional[int] = None,
    path_init_model: Optional[str] = None,
) -> List[str]:
    cmd = [
        python,
        "recon_chunk.py",
        "--dataset",
        dataset,
        "--case_id",
        str(case_id),
        "--expmt_type",
        expmt_type,
        "--gpu",
        str(gpu),
    ]
    if idx_y is not None:
        cmd.extend(["--idx_y", str(idx_y)])
    if path_init_model is not None:
        cmd.extend(["--path_init_model", path_init_model])
    return cmd


def _dir_out(work_root: Path, case_id: int) -> Path:
    return work_root / "out" / DATASET_NAME / ("c%d" % case_id)


def run_wucon_full_chunks(
    *,
    src_copy: Path,
    work_root: Path,
    case_id: int,
    height: int,
    env: Dict[str, str],
    python: str,
    gpu_id: int,
) -> None:
    """Official-style adj + up/down sweep after mid chunk (subprocess, check=True)."""
    sy_mid = height // 2
    sy_end = int(2 * sy_mid)
    dir_out = _dir_out(work_root, case_id)
    gpu_u = gpu_id
    gpu_d = gpu_id

    # Adjacent downward chunk initialized from mid
    path_init = dir_out / ("sy%s" % str(sy_mid).zfill(4)) / "checkpoints" / "model_final.pth"
    _run_checked(
        _chunk_cmd(
            python=python,
            case_id=case_id,
            dataset=DATASET_NAME,
            expmt_type="all",
            gpu=gpu_d,
            idx_y=sy_mid - 2,
            path_init_model=str(path_init),
        ),
        cwd=src_copy,
        env=env,
        step="chunk-adj",
    )
    mid_dir = dir_out / ("sy%s" % str(sy_mid).zfill(4))
    no_init = dir_out / ("sy%s_no-init" % str(sy_mid).zfill(4))
    if mid_dir.is_dir():
        if no_init.exists():
            shutil.rmtree(no_init)
        mid_dir.rename(no_init)

    for idx_y in range(sy_mid, sy_end + 2, 2):
        sy_init = idx_y - 2
        init = dir_out / ("sy%s" % str(sy_init).zfill(4)) / "checkpoints" / "model_final.pth"
        _run_checked(
            _chunk_cmd(
                python=python,
                case_id=case_id,
                dataset=DATASET_NAME,
                expmt_type="all",
                gpu=gpu_u,
                idx_y=idx_y,
                path_init_model=str(init),
            ),
            cwd=src_copy,
            env=env,
            step="chunk-up-%s" % idx_y,
        )

    for idx_y in range(sy_mid - 4, -2, -2):
        if idx_y < 0:
            break
        sy_init = idx_y + 2
        init = dir_out / ("sy%s" % str(sy_init).zfill(4)) / "checkpoints" / "model_final.pth"
        _run_checked(
            _chunk_cmd(
                python=python,
                case_id=case_id,
                dataset=DATASET_NAME,
                expmt_type="all",
                gpu=gpu_d,
                idx_y=idx_y,
                path_init_model=str(init),
            ),
            cwd=src_copy,
            env=env,
            step="chunk-down-%s" % idx_y,
        )


def assemble_wucon_mrc(
    *,
    src_copy: Path,
    case_id: int,
    env: Dict[str, str],
    python: str,
) -> Path:
    """Run upstream CryoLoad assemble (same idea as wrap_save_to_mrc)."""
    script = textwrap.dedent(
        """\
        import argparse
        import os
        import shutil
        from parser import set_args
        from dataset import CryoLoad

        args = argparse.Namespace()
        args.dataset = %r
        args.case_id = %d
        args.bypass_tb = False
        args = set_args(args, purpose='load')
        CryoLoad(args)
        dir_indiv = os.path.join(args.dir_out, 'indiv_chunks')
        os.makedirs(dir_indiv, exist_ok=True)
        for name in os.listdir(args.dir_out):
            if name.startswith('sy'):
                src = os.path.join(args.dir_out, name)
                dst = os.path.join(dir_indiv, name)
                if os.path.isdir(src):
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.move(src, dst)
        print(os.path.join(args.dir_out, 'mrc', 'out.mrc'))
        """
        % (DATASET_NAME, int(case_id))
    )
    print("WUCON_RUN step=assemble", flush=True)
    proc = subprocess.run(
        [python, "-c", script],
        cwd=str(src_copy),
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    if proc.stdout:
        print(proc.stdout, flush=True)
    if proc.stderr:
        print(proc.stderr, file=sys.stderr, flush=True)
    # Last non-empty stdout line should be the mrc path
    lines = [ln.strip() for ln in (proc.stdout or "").splitlines() if ln.strip()]
    if not lines:
        raise RuntimeError("assemble produced no stdout path for out.mrc")
    out_mrc = Path(lines[-1])
    if not out_mrc.is_file():
        raise FileNotFoundError("Expected WUCON MRC at %s" % out_mrc)
    return out_mrc


def run_wucon_cli(
    tilt_series: Any,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """Legacy single-argv path when ``wucon_pipeline`` is false."""
    del tilt_series

    argv = config.get("wucon_argv")
    if not argv:
        raise ValueError(
            "native WUCon CLI mode requires parameters.wucon_argv "
            "(list of CLI strings), or leave wucon_pipeline true for automation."
        )
    if isinstance(argv, str):
        raise TypeError("wucon_argv must be a list of strings, not a single string")
    cmd: List[str] = [str(x) for x in argv]

    cwd: Optional[Union[str, Path]] = config.get("wucon_cwd")
    if cwd is not None:
        cwd = str(Path(cwd).expanduser())

    extra_env = config.get("wucon_env") or {}
    if not isinstance(extra_env, MutableMapping):
        raise TypeError("wucon_env must be a dict")
    env = {**os.environ, **{str(k): str(v) for k, v in extra_env.items()}}

    subprocess.run(cmd, cwd=cwd, env=env, check=True)

    out_path = resolve_cli_output_volume(
        config,
        path_key="wucon_output_volume_path",
        dir_key="wucon_output_dir",
        glob_key="wucon_output_glob",
        default_glob="*.mrc",
    )
    vol = load_volume_array_from_path(out_path)
    rec_sig = numpy_volume_to_signal2d(vol, title="WUCon output")
    rec_sig.metadata.set_item("et_dflow.native_solver", "wucon")

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="wucon",
        start_time=start_time,
        extra_metadata={"wucon_output": str(out_path)},
    )


def run_wucon_reconstruction(
    tilt_series: Any,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """
    Full automated WUCON pipeline inside the container / local GPU env.

    Set ``wucon_pipeline: false`` with ``wucon_argv`` for legacy CLI mode.
    """
    if config.get("wucon_pipeline", True) is False:
        return run_wucon_cli(tilt_series, config, start_time=start_time)

    src_dir = resolve_wucon_src_dir(config)
    case_id = int(config.get("wucon_case_id") or 90)
    n_epochs_mid = int(config.get("wucon_n_epochs_mid") or 50)
    n_epochs_all = int(config.get("wucon_n_epochs_all") or 20)
    recon_subset = bool(config.get("wucon_recon_subset", True))
    gpu_id = int(config.get("wucon_gpu_id") or 0)
    python = str(config.get("wucon_python") or sys.executable)

    work_root = Path(config.get("wucon_work_dir") or tempfile.mkdtemp(prefix="et_wucon_"))
    work_root.mkdir(parents=True, exist_ok=True)
    print(
        "WUCON_RUN step=init work=%s src=%s subset=%s case_id=%s"
        % (work_root, src_dir, recon_subset, case_id),
        flush=True,
    )

    staged = stage_wucon_inputs(tilt_series, config, work_root)
    src_copy = prepare_wucon_src_copy(
        src_dir,
        work_root,
        staged=staged,
        n_epochs_mid=n_epochs_mid,
        n_epochs_all=n_epochs_all,
        case_id=case_id,
    )

    env = {**os.environ, **(config.get("wucon_env") or {})}
    env["PYTHONPATH"] = str(src_copy) + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )

    # GPU hard requirement (official recon_volume also requires CUDA).
    try:
        import torch

        if torch.cuda.device_count() < 1:
            raise RuntimeError("WUCON requires at least one CUDA GPU")
    except ImportError as exc:
        raise RuntimeError("WUCON requires PyTorch with CUDA") from exc

    _run_checked(
        _chunk_cmd(
            python=python,
            case_id=case_id,
            dataset=DATASET_NAME,
            expmt_type="mid",
            gpu=gpu_id,
        ),
        cwd=src_copy,
        env=env,
        step="chunk-mid",
    )

    if not recon_subset:
        run_wucon_full_chunks(
            src_copy=src_copy,
            work_root=work_root,
            case_id=case_id,
            height=int(staged["height"]),
            env=env,
            python=python,
            gpu_id=gpu_id,
        )

    if config.get("wucon_output_volume_path") or config.get("wucon_output_dir"):
        chosen = resolve_cli_output_volume(
            config,
            path_key="wucon_output_volume_path",
            dir_key="wucon_output_dir",
            glob_key="wucon_output_glob",
            default_glob="*.mrc",
        )
    else:
        chosen = assemble_wucon_mrc(
            src_copy=src_copy,
            case_id=case_id,
            env=env,
            python=python,
        )

    vol = load_volume_array_from_path(chosen)
    rec_sig = numpy_volume_to_signal2d(vol, title="WUCon reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "wucon")
    rec_sig.metadata.set_item("et_dflow.wucon_output", str(chosen))
    rec_sig.metadata.set_item("et_dflow.wucon_recon_subset", recon_subset)

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="wucon",
        start_time=start_time,
        extra_metadata={
            "wucon_output": str(chosen),
            "wucon_work_dir": str(work_root),
            "wucon_case_id": case_id,
            "wucon_recon_subset": recon_subset,
            "wucon_n_epochs_mid": n_epochs_mid,
            "wucon_n_epochs_all": n_epochs_all,
            "wucon_img_size_load": staged["img_size_load"],
            "wucon_prj_size_load": staged["prj_size_load"],
        },
    )
