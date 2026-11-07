"""TIGRE ASD-POCS (constrained total-variation) for a parallel-beam tilt series.

The call is ``algs.asd_pocs(proj, geo, angles, niter, tviter=...)``.
``tvlambda`` belongs to ``ossart_tv`` and is never forwarded.
"""

from __future__ import annotations

from typing import Any, Dict, Tuple

import hyperspy.api as hs

from et_dflow.core.models import AlgorithmResult
from et_dflow.infrastructure.algorithms.adapter_common import (
    make_adapter_algorithm_result,
    numpy_volume_to_signal2d,
)
from et_dflow.infrastructure.algorithms.native_tigre import prepare_tigre_parallel


def asd_pocs_call_args(config: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    """Positional iteration count and keyword arguments for ``asd_pocs``.

    ``tvm_alpha`` and ``tvm_maxl2err`` are omitted unless the config sets them,
    so TIGRE keeps its own defaults (TV step 0.002, epsilon = 20% of the FDK
    residual).
    """
    niter = int(config.get("tvm_niter", 50))
    kwargs: Dict[str, Any] = {"tviter": int(config.get("tvm_tviter", 20))}
    if config.get("tvm_alpha") is not None:
        kwargs["alpha"] = float(config["tvm_alpha"])
    if config.get("tvm_maxl2err") is not None:
        kwargs["maxl2err"] = float(config["tvm_maxl2err"])
    if "tvlambda" in kwargs:
        raise RuntimeError("ASD-POCS arguments must not include tvlambda")
    return niter, kwargs


def run_tvm(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    start_time: float,
) -> AlgorithmResult:
    import tigre.algorithms as algs

    asd_pocs = getattr(algs, "asd_pocs", None)
    if asd_pocs is None:
        names = sorted(
            name
            for name in dir(algs)
            if callable(getattr(algs, name, None)) and not name.startswith("_")
        )
        raise RuntimeError(
            "TIGRE build has no asd_pocs. Callable algorithms: %s" % (", ".join(names),)
        )

    proj, geo, angles, gpuids, n_voxel = prepare_tigre_parallel(tilt_series, config)
    niter, kwargs = asd_pocs_call_args(config)
    vol = asd_pocs(proj, geo, angles, niter, gpuids=gpuids, **kwargs)

    rec_sig = numpy_volume_to_signal2d(vol, title="TVM ASD-POCS reconstruction")
    rec_sig.metadata.set_item("et_dflow.native_solver", "tvm")
    rec_sig.metadata.set_item("et_dflow.tvm_niter", niter)
    for key, value in kwargs.items():
        rec_sig.metadata.set_item("et_dflow.tvm_%s" % key, value)

    return make_adapter_algorithm_result(
        rec_sig,
        algorithm_name="tvm",
        start_time=start_time,
        extra_metadata={
            "tvm_niter": niter,
            "tvm_kwargs": dict(kwargs),
            "nVoxel": n_voxel.tolist(),
        },
    )
