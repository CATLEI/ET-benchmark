"""
When a third-party solver (ASTRA, TIGRE, …) is not wired in the Docker adapter yet,
run a **real** et_dflow reconstruction (WBP or SIRT) as a numerical stand-in.

This replaces the old "mean along tilts" placeholder, which is not a valid ET
reconstruction and breaks evaluation pipelines.

YAML / JSON config:
    ``placeholder_backend``: ``"wbp"`` (default) or ``"sirt"``
"""

from __future__ import annotations

import sys
from typing import Any, Dict, Optional

import hyperspy.api as hs

from et_dflow.core.models import AlgorithmResult


def run_placeholder_reconstruction(
    tilt_series: hs.signals.Signal2D,
    config: Dict[str, Any],
    *,
    target_algorithm: str,
    reason: Optional[str] = None,
) -> AlgorithmResult:
    """
    Run WBP or SIRT from et_dflow, tag metadata so outputs are traceable.

    Args:
        tilt_series: Input tilt series.
        config: Algorithm parameters (passed through to WBP/SIRT).
        target_algorithm: Logical name (e.g. ``"ASTRA"``, ``"GENFIRE"``).
        reason: Short message logged to stderr and stored in metadata.
    """
    backend = (config.get("placeholder_backend") or "wbp").lower()
    if backend not in ("wbp", "sirt"):
        raise ValueError(
            f"placeholder_backend must be 'wbp' or 'sirt', got {backend!r}"
        )

    msg = (
        f"{target_algorithm}: native solver not integrated in this image. "
        f"Using et_dflow '{backend}' as stand-in reconstruction."
    )
    if reason:
        msg = f"{target_algorithm}: {reason} {msg}"
    print(f"WARNING: {msg}", file=sys.stderr)

    if backend == "sirt":
        from et_dflow.domain.algorithms.sirt import SIRTAlgorithm

        algorithm = SIRTAlgorithm(config=config)
    else:
        from et_dflow.domain.algorithms.wbp import WBPAlgorithm

        algorithm = WBPAlgorithm(config=config)

    result = algorithm.run(tilt_series, config)
    rec = result.reconstruction
    rec.metadata.set_item("et_dflow.target_algorithm", target_algorithm)
    rec.metadata.set_item("et_dflow.placeholder_backend", backend)
    if reason:
        rec.metadata.set_item("et_dflow.placeholder_reason", reason[:500])
    return result
