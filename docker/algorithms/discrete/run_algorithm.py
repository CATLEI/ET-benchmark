#!/usr/bin/env python
"""DART and TVR-DART. ``discrete_method`` selects which solver runs."""

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

_METHODS = {
    "dart": "et_dflow.infrastructure.algorithms.native_dart",
    "tvr_dart": "et_dflow.infrastructure.algorithms.native_tvr_dart",
}


def main() -> int:
    parser = argparse.ArgumentParser(description="DART / TVR-DART adapter (ET-dflow)")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        tilt_series = load_tilt_series_hspy(args.input)
        use_native = config.get("use_native", True)
        allow_placeholder = bool(config.get("allow_placeholder", False))
        method = str(config.get("discrete_method") or "").strip()
        print(
            "DISCRETE_RUN start method=%s use_native=%s has_astra=%s "
            "allow_placeholder=%s"
            % (method, use_native, _HAS_ASTRA, allow_placeholder)
        )
        if method not in _METHODS:
            raise ValueError(
                "discrete_method must be dart or tvr_dart, got %r" % (method,)
            )

        if use_native and _HAS_ASTRA:
            try:
                import importlib

                module = importlib.import_module(_METHODS[method])
                runner = getattr(module, "run_%s" % method)
                t0 = time.time()
                result = runner(tilt_series, config, start_time=t0)
                print("DISCRETE_RUN result=native method=%s" % method)
            except Exception as exc:
                if not allow_placeholder:
                    print(
                        "ERROR: %s native run failed (%s); placeholder is disabled."
                        % (method, exc),
                        file=sys.stderr,
                    )
                    raise
                print(
                    "WARNING: %s native run failed (%s); using placeholder."
                    % (method, exc),
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm=method,
                    reason="native error: %s" % (exc,),
                )
                print("DISCRETE_RUN result=placeholder reason=%s" % (exc,))
        else:
            reason = (
                "astra package missing in image"
                if not _HAS_ASTRA
                else "use_native is false"
            )
            if not allow_placeholder:
                raise RuntimeError(reason)
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm=method,
                reason=reason,
            )
            print("DISCRETE_RUN result=placeholder reason=%s" % (reason,))

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
