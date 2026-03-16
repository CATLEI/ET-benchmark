#!/usr/bin/env python
"""
Entry point script for SIRT algorithm execution in Docker container.

This script is called by dflow AlgorithmExecutionOP with the following arguments:
  --input: Path to input data file (.hspy format)
  --output: Path to output reconstruction file (.hspy format)
  --config: JSON string containing algorithm configuration
"""

import argparse
import json
import sys
from pathlib import Path

import hyperspy.api as hs

from et_dflow.domain.algorithms.sirt import SIRTAlgorithm


def main():
    """Main entry point for algorithm execution."""
    parser = argparse.ArgumentParser(description="SIRT Algorithm Execution")
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input tilt series file (.hspy)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output reconstruction file (.hspy)"
    )
    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="JSON string containing algorithm configuration"
    )

    args = parser.parse_args()

    try:
        config = json.loads(args.config)

        input_path = Path(args.input)
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)

        print(f"Loading input data from: {input_path}")
        loaded = hs.load(str(input_path))
        if isinstance(loaded, list):
            if not loaded:
                print("ERROR: No signal in file", file=sys.stderr)
                sys.exit(1)
            tilt_series = loaded[0]
        else:
            tilt_series = loaded

        if not isinstance(tilt_series, hs.signals.Signal2D):
            if hasattr(tilt_series, "data") and tilt_series.data.ndim >= 2:
                tilt_series = hs.signals.Signal2D(tilt_series.data.copy())
            else:
                print(
                    f"ERROR: Expected Signal2D or 2D/3D data, got {type(tilt_series)}",
                    file=sys.stderr,
                )
                sys.exit(1)

        print("Initializing SIRT algorithm...")
        algorithm = SIRTAlgorithm(config=config)

        print("Running SIRT reconstruction...")
        result = algorithm.run(tilt_series, config)

        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        print(f"Saving reconstruction to: {output_path}")
        result.reconstruction.save(str(output_path))

        print("SIRT reconstruction completed successfully!")
        print(f"Execution time: {result.execution_time:.2f} seconds")
        print(f"Memory usage: {result.memory_usage:.2f} MB")

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
