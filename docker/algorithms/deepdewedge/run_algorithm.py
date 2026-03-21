#!/usr/bin/env python
"""
DeepDeWedge adapter.

Native path runs ``ddw refine-tomogram`` using a YAML path you provide in config
(``ddw_refine_config_yaml``); it does **not** feed the HyperSpy tilt series into
``ddw`` automatically. For tilt-series-only benchmarks, leave ``use_native`` false
or omit ``ddw_refine_config_yaml`` to use the WBP/SIRT stand-in.
"""

from __future__ import annotations

import argparse
import json
import sys

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
        has_yaml = bool(config.get("ddw_refine_config_yaml"))

        if use_native and _HAS_DDW and has_yaml:
            try:
                from et_dflow.infrastructure.algorithms.native_deepdewedge import (
                    run_deepdewedge_refine,
                )

                import time as _time

                t0 = _time.time()
                result = run_deepdewedge_refine(
                    tilt_series, config, start_time=t0
                )
                print("DeepDeWedge refine-tomogram completed.")
            except Exception as exc:
                print(
                    f"WARNING: DeepDeWedge native run failed ({exc}); "
                    "falling back to placeholder.",
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="DeepDeWedge",
                    reason=f"native error: {exc}",
                )
        else:
            if not _HAS_DDW:
                reason = "ddw package missing in image"
            elif not use_native:
                reason = "use_native is false"
            elif not has_yaml:
                reason = (
                    "ddw_refine_config_yaml not set (native refine needs YAML path)"
                )
            else:
                reason = "unknown"
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="DeepDeWedge",
                reason=reason,
            )

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
