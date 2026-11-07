#!/usr/bin/env python
"""TVM adapter: TIGRE ASD-POCS on the same parallel geometry as TIGRE SIRT."""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import tigre  # noqa: F401

    _HAS_TIGRE = True
except ImportError:
    _HAS_TIGRE = False

from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)
from et_dflow.infrastructure.algorithms.placeholder_runner import (
    run_placeholder_reconstruction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="TVM ASD-POCS adapter (ET-dflow)")
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
            "TVM_RUN start use_native=%s has_tigre=%s allow_placeholder=%s"
            % (use_native, _HAS_TIGRE, allow_placeholder)
        )

        if use_native and _HAS_TIGRE:
            try:
                from et_dflow.infrastructure.algorithms.native_tvm import run_tvm

                t0 = time.time()
                result = run_tvm(tilt_series, config, start_time=t0)
                print("TVM_RUN result=native")
                print("TVM ASD-POCS reconstruction completed.")
            except Exception as exc:
                if not allow_placeholder:
                    print(
                        "ERROR: TVM native run failed (%s); placeholder is disabled."
                        % (exc,),
                        file=sys.stderr,
                    )
                    raise
                print(
                    "WARNING: TVM native run failed (%s); using placeholder."
                    % (exc,),
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="TVM",
                    reason="native error: %s" % (exc,),
                )
                print("TVM_RUN result=placeholder reason=%s" % (exc,))
        else:
            reason = (
                "tigre package missing in image"
                if not _HAS_TIGRE
                else "use_native is false"
            )
            if not allow_placeholder:
                raise RuntimeError(reason)
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="TVM",
                reason=reason,
            )
            print("TVM_RUN result=placeholder reason=%s" % (reason,))

        save_algorithm_result(result, args.output)
        print_run_summary(result)
        return 0
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON configuration: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"ERROR: Algorithm execution failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
