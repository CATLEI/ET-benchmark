#!/usr/bin/env python
"""
ASTRA Toolbox adapter: native parallel3d SIRT/CGLS when ``astra`` is available.

``use_native: false`` forces WBP/SIRT stand-in (``placeholder_backend``).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import astra  # noqa: F401

    _HAS_ASTRA = True
except ImportError:
    _HAS_ASTRA = False

from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)
from et_dflow.infrastructure.algorithms.placeholder_runner import (
    run_placeholder_reconstruction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="ASTRA adapter (ET-dflow)")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        tilt_series = load_tilt_series_hspy(args.input)
        use_native = config.get("use_native", True)

        if use_native and _HAS_ASTRA:
            try:
                from et_dflow.infrastructure.algorithms.native_astra import (
                    run_astra_parallel3d,
                )

                t0 = time.time()
                result = run_astra_parallel3d(
                    tilt_series, config, start_time=t0
                )
                print("ASTRA native reconstruction completed.")
            except Exception as exc:
                print(
                    "WARNING: ASTRA native run failed (%s); using placeholder."
                    % (exc,),
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="ASTRA",
                    reason="native error: %s" % (exc,),
                )
        else:
            reason = (
                "astra Python package missing in image"
                if not _HAS_ASTRA
                else "use_native is false"
            )
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="ASTRA",
                reason=reason,
            )

        save_algorithm_result(result, args.output)
        print_run_summary(result)
        return 0
    except json.JSONDecodeError as e:
        print("ERROR: Invalid JSON configuration: %s" % (e,), file=sys.stderr)
        return 1
    except Exception as e:
        print("ERROR: Algorithm execution failed: %s" % (e,), file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
