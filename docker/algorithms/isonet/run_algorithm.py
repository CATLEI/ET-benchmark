#!/usr/bin/env python
"""
IsoNet adapter.

Default native path (``use_native: true``): full-tilt WBP inside the container,
then ``isonet.py prepare_star`` → ``extract`` → ``refine`` → ``predict``.
Set ``isonet_pipeline: false`` and ``isonet_argv`` for a single custom CLI.

``allow_placeholder: false`` (default): missing package or any native error
exits 1 (no WBP stand-in). Internal WBP for IsoNet input is not a placeholder.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

try:
    import IsoNet  # noqa: F401

    _HAS_ISONET = True
except ImportError:
    _HAS_ISONET = False

from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)
from et_dflow.infrastructure.algorithms.placeholder_runner import (
    run_placeholder_reconstruction,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="IsoNet adapter (ET-dflow)")
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
            "ISONET_RUN start use_native=%s has_isonet=%s allow_placeholder=%s "
            "isonet_pipeline=%s"
            % (
                use_native,
                _HAS_ISONET,
                allow_placeholder,
                config.get("isonet_pipeline", True),
            ),
            flush=True,
        )

        if use_native and _HAS_ISONET:
            try:
                from et_dflow.infrastructure.algorithms.native_isonet import (
                    run_isonet_reconstruction,
                )

                t0 = time.time()
                result = run_isonet_reconstruction(
                    tilt_series, config, start_time=t0
                )
                print("ISONET_RUN result=native")
                print("IsoNet native reconstruction completed.")
            except Exception as exc:
                if not allow_placeholder:
                    print(
                        "ERROR: IsoNet native run failed (%s); "
                        "placeholder is disabled."
                        % (exc,),
                        file=sys.stderr,
                    )
                    raise
                print(
                    "WARNING: IsoNet native run failed (%s); using placeholder."
                    % (exc,),
                    file=sys.stderr,
                )
                result = run_placeholder_reconstruction(
                    tilt_series,
                    config,
                    target_algorithm="IsoNet",
                    reason="native error: %s" % (exc,),
                )
                print("ISONET_RUN result=placeholder reason=%s" % (exc,))
        else:
            reason = (
                "IsoNet package missing in image"
                if not _HAS_ISONET
                else "use_native is false"
            )
            if not allow_placeholder:
                raise RuntimeError(reason)
            result = run_placeholder_reconstruction(
                tilt_series,
                config,
                target_algorithm="IsoNet",
                reason=reason,
            )
            print("ISONET_RUN result=placeholder reason=%s" % (reason,))

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
