#!/usr/bin/env python
"""
TIGRE adapter: optional GPU parallel-beam reconstruction (pytigre).

- ``use_native: true`` (default): run TIGRE FDK / OS-SART / SIRT when ``import tigre`` works.
- ``use_native: false``: WBP/SIRT stand-in via ``placeholder_backend``.
"""

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
    parser = argparse.ArgumentParser(description="TIGRE adapter (ET-dflow)")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        tilt_series = load_tilt_series_hspy(args.input)
        use_native = config.get("use_native", True)

        if use_native and _HAS_TIGRE:
            try:
                from et_dflow.infrastructure.algorithms.native_tigre import (
                    run_tigre_reconstruction,
                )

                t0 = time.time()
                result = run_tigre_reconstruction(
                    tilt_series, config, start_time=t0
                )
                print("TIGRE native reconstruction completed.")
            except Exception as exc:
                print(
                    f"WARNING: TIGRE native run failed ({exc}); falling back to "
                    "placeholder.",
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="TIGRE",
                    reason=f"native error: {exc}",
                )
        else:
            reason = (
                "tigre package missing in image"
                if not _HAS_TIGRE
                else "use_native is false"
            )
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="TIGRE",
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
