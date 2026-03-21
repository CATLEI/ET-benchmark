"""
IsoNet bridge: run a user-supplied command (typically ``isonet.py`` + subcommand),
then load the output volume and wrap as HyperSpy for unified ``.hspy`` export.

IsoNet workflows normally use star files and multiple steps; this adapter only
orchestrates **one** subprocess you define, then picks up the result volume.

Required when using native mode:

- ``isonet_argv``: executable + args, e.g. ``["isonet.py", "refine", "job.star"]``
  or ``["python", "/path/to/isonet.py", "check"]`` (use whatever your image provides).

Optional:

- ``isonet_cwd``: working directory for the subprocess
- ``isonet_env``: extra environment variables (merged into ``os.environ``)
- ``isonet_output_volume_path`` or ``isonet_output_dir`` + ``isonet_output_glob``
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any, Dict, List, MutableMapping, Optional, Union

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


def run_isonet_cli(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    del tilt_series

    argv = config.get("isonet_argv")
    if not argv:
        raise ValueError(
            "native IsoNet requires parameters.isonet_argv (list of CLI strings)."
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
