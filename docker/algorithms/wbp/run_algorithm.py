#!/usr/bin/env python
"""
Entry point script for WBP algorithm execution in Docker container.

This script is called by dflow AlgorithmExecutionOP with:
  --input, --output, --config (JSON string)
"""

from __future__ import annotations

import argparse
import json
import sys

from et_dflow.domain.algorithms.wbp import WBPAlgorithm
from et_dflow.infrastructure.algorithms.docker_entrypoint_io import (
    load_tilt_series_hspy,
    print_run_summary,
    save_algorithm_result,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="WBP Algorithm Execution")
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--config", type=str, required=True)
    args = parser.parse_args()

    try:
        config = json.loads(args.config)
        print(f"Loading input data from: {args.input}")
        tilt_series = load_tilt_series_hspy(args.input)

        print("Initializing WBP algorithm...")
        algorithm = WBPAlgorithm(config=config)
        print("Running WBP reconstruction...")
        result = algorithm.run(tilt_series, config)

        save_algorithm_result(result, args.output)
        print("WBP reconstruction completed successfully!")
        print_run_summary(result)

    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Algorithm execution failed: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
