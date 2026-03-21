#!/usr/bin/env python
"""
RESIRE adapter for ET-dflow Docker images.

``RESIREAlgorithm`` in ``et_dflow.domain.algorithms.resire`` is optional.
If missing, uses WBP/SIRT stand-in (``placeholder_backend``).
"""

from __future__ import annotations

import argparse
import json
import sys

from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)
from et_dflow.infrastructure.algorithms.placeholder_runner import (
    run_placeholder_reconstruction,
)

try:
    from et_dflow.domain.algorithms.resire import RESIREAlgorithm

    _HAS_RESIRE = True
except ImportError:
    _HAS_RESIRE = False


def main() -> int:
    parser = argparse.ArgumentParser(description="RESIRE adapter (ET-dflow)")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        tilt_series = load_tilt_series_hspy(args.input)

        use_native = config.get("use_native", True) and _HAS_RESIRE
        if use_native:
            print("Running native RESIREAlgorithm...")
            algorithm = RESIREAlgorithm(config=config)
            result = algorithm.run(tilt_series, config)
        else:
            reason = (
                "RESIREAlgorithm not found in et_dflow"
                if not _HAS_RESIRE
                else "use_native is false in config"
            )
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="RESIRE",
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
