#!/usr/bin/env python
"""
ASTRA Toolbox adapter.

Default reconstruction is parallel3d FBP on CUDA: Ram-Lak filter, then
``BP3D_CUDA``. ``allow_placeholder: true`` is required before a failure is
replaced by the WBP/SIRT stand-in.
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
        allow_placeholder = bool(config.get("allow_placeholder", False))
        print(
            "ASTRA_RUN start use_native=%s has_astra=%s allow_placeholder=%s "
            "astra_algorithm=%s filter_type=%s"
            % (
                use_native,
                _HAS_ASTRA,
                allow_placeholder,
                config.get("astra_algorithm"),
                config.get("filter_type"),
            )
        )

        if use_native and _HAS_ASTRA:
            try:
                from et_dflow.infrastructure.algorithms.native_astra import (
                    run_astra_parallel3d,
                )

                t0 = time.time()
                result = run_astra_parallel3d(
                    tilt_series, config, start_time=t0
                )
                print("ASTRA_RUN result=native")
                print("ASTRA native reconstruction completed.")
            except Exception as exc:
                if not allow_placeholder:
                    print(
                        "ERROR: ASTRA native run failed (%s); placeholder is disabled."
                        % (exc,),
                        file=sys.stderr,
                    )
                    raise
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
                print("ASTRA_RUN result=placeholder reason=%s" % (exc,))
        else:
            reason = (
                "astra Python package missing in image"
                if not _HAS_ASTRA
                else "use_native is false"
            )
            if not allow_placeholder:
                raise RuntimeError(reason)
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="ASTRA",
                reason=reason,
            )
            print("ASTRA_RUN result=placeholder reason=%s" % (reason,))

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
