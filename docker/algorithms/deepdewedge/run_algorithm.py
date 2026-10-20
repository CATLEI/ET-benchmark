#!/usr/bin/env python
"""
DeepDeWedge adapter.

Default native path (``use_native: true``): even/odd ramp FBP inside the
container, then ``ddw prepare-data`` → ``fit-model`` → pick best val checkpoint
→ ``refine-tomogram``. Set ``ddw_pipeline: false`` and
``ddw_refine_config_yaml`` for refine-only.

``allow_placeholder: false`` (default): missing package or any native error
exits 1 (no WBP stand-in).
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import ddw  # noqa: F401

    _HAS_DDW = True
except ImportError:
    _HAS_DDW = False

from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)
from et_dflow.infrastructure.algorithms.placeholder_runner import (
    run_placeholder_reconstruction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepDeWedge adapter (ET-dflow)")
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
            "DDW_RUN start use_native=%s has_ddw=%s allow_placeholder=%s "
            "ddw_pipeline=%s"
            % (
                use_native,
                _HAS_DDW,
                allow_placeholder,
                config.get("ddw_pipeline", True),
            ),
            flush=True,
        )

        if use_native and _HAS_DDW:
            try:
                from et_dflow.infrastructure.algorithms.native_deepdewedge import (
                    run_deepdewedge_reconstruction,
                )

                t0 = time.time()
                result = run_deepdewedge_reconstruction(
                    tilt_series, config, start_time=t0
                )
                print("DDW_RUN result=native")
                print("DeepDeWedge native reconstruction completed.")
            except Exception as exc:
                if not allow_placeholder:
                    print(
                        "ERROR: DeepDeWedge native run failed (%s); "
                        "placeholder is disabled."
                        % (exc,),
                        file=sys.stderr,
                    )
                    raise
                print(
                    "WARNING: DeepDeWedge native run failed (%s); using placeholder."
                    % (exc,),
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="DeepDeWedge",
                    reason="native error: %s" % (exc,),
                )
                print("DDW_RUN result=placeholder reason=%s" % (exc,))
        else:
            reason = (
                "ddw package missing in image"
                if not _HAS_DDW
                else "use_native is false"
            )
            if not allow_placeholder:
                raise RuntimeError(reason)
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="DeepDeWedge",
                reason=reason,
            )
            print("DDW_RUN result=placeholder reason=%s" % (reason,))

        save_algorithm_result(result, args.output)
        print_run_summary(result)
        return 0
    except json.JSONDecodeError as e:
        print("ERROR: Invalid JSON configuration: %s" % e, file=sys.stderr)
        return 1
    except Exception as e:
        print("ERROR: Algorithm execution failed: %s" % e, file=sys.stderr)
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
