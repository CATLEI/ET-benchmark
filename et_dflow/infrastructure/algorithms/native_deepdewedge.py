"""
DeepDeWedge bridge via the ``ddw`` CLI (``refine-tomogram``).

DeepDeWedge is **not** a single-step tilt-series → volume method in production:
you normally run ``prepare-data`` → ``fit-model`` → ``refine-tomogram``. For
ET-dflow we only automate the last step when you already have a YAML config
inside the container that points to your tomogram(s) and checkpoint(s).

Required in ``parameters`` when ``use_native: true``:

- ``ddw_refine_config_yaml``: absolute path to a DeepDeWedge YAML config for
  ``ddw refine-tomogram``.

Optional:

- ``ddw_output_volume_path``: path to the primary output volume (``.mrc`` or
  ``.npy``) written by refine. If omitted, we try ``ddw_output_glob`` under
  ``ddw_output_dir``.
- ``ddw_output_dir`` + ``ddw_output_glob``: e.g. directory ``/out`` and glob
  ``"*.mrc"``; the newest matching file is loaded.

If none of the above resolve to a file, :class:`FileNotFoundError` is raised.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List

import hyperspy.api as hs

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.volume_io import (
    load_volume_array_from_path,
    resolve_cli_output_volume,
)


def run_deepdewedge_refine(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    """
    Run ``ddw refine-tomogram``; load result volume from explicit path or glob.

    ``tilt_series`` is accepted for CLI compatibility but is **not** passed to
    ``ddw`` unless your YAML reads paths you prepared separately.
    """
    del tilt_series  # workflow contract only; refine is driven by YAML

    yaml_path = config.get("ddw_refine_config_yaml")
    if not yaml_path:
        raise ValueError(
            "native DeepDeWedge requires parameters.ddw_refine_config_yaml "
            "(path to refine YAML inside the container)."
        )
    yaml_path = str(Path(yaml_path).expanduser())
    if not os.path.isfile(yaml_path):
        raise FileNotFoundError(f"ddw_refine_config_yaml not found: {yaml_path}")

    ddw_bin = shutil.which("ddw")
    if not ddw_bin:
        raise RuntimeError("Executable 'ddw' not found on PATH")

    extra_args: List[str] = config.get("ddw_refine_extra_args") or []
    if not isinstance(extra_args, list):
        raise TypeError("ddw_refine_extra_args must be a list of CLI strings")

    cmd: List[str] = [ddw_bin, "refine-tomogram", "--config", yaml_path, *extra_args]
    env = {**os.environ, **(config.get("ddw_env") or {})}
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
