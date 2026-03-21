"""
WUCon bridge: run a user-defined command (e.g. Python entrypoint under
``/opt/wucon/src``), then load ``.mrc`` / ``.npy`` output into HyperSpy.

Required for native mode:

- ``wucon_argv``: list of CLI strings, e.g.
  ``["python", "/opt/wucon/scripts/run.py", "--config", "/data/config.yaml"]``

Optional:

- ``wucon_cwd``, ``wucon_env``
- ``wucon_output_volume_path`` or ``wucon_output_dir`` + ``wucon_output_glob``
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


def run_wucon_cli(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    del tilt_series

    argv = config.get("wucon_argv")
    if not argv:
        raise ValueError(
            "native WUCon requires parameters.wucon_argv (list of CLI strings)."
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
