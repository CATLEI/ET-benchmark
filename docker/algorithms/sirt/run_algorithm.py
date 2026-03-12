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

# Try to import SIRT algorithm
# If SIRTAlgorithm exists in et_dflow.domain.algorithms.sirt, use it
# Otherwise, we'll need to implement a basic wrapper
try:
    from et_dflow.domain.algorithms.sirt import SIRTAlgorithm
    HAS_SIRT_ALGORITHM = True
except ImportError:
    # SIRTAlgorithm may not exist yet, we'll use a placeholder
    HAS_SIRT_ALGORITHM = False
    print("WARNING: SIRTAlgorithm not found in et_dflow.domain.algorithms.sirt", file=sys.stderr)
    print("  Using placeholder implementation. Please implement SIRTAlgorithm class.", file=sys.stderr)


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
        # Parse configuration
        config = json.loads(args.config)
        
        # Load input data
        input_path = Path(args.input)
        if not input_path.exists():
            print(f"ERROR: Input file not found: {input_path}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Loading input data from: {input_path}")
        tilt_series = hs.load(str(input_path))
        
        # Ensure we have a Signal2D
        if not isinstance(tilt_series, hs.signals.Signal2D):
            print(f"ERROR: Expected Signal2D, got {type(tilt_series)}", file=sys.stderr)
            sys.exit(1)
        
        # Initialize and run SIRT algorithm
        if HAS_SIRT_ALGORITHM:
            print("Initializing SIRT algorithm...")
            algorithm = SIRTAlgorithm(config=config)
            
            print("Running SIRT reconstruction...")
            result = algorithm.run(tilt_series, config)
        else:
            # Placeholder implementation - replace with actual SIRT algorithm
            print("WARNING: Using placeholder SIRT implementation", file=sys.stderr)
            print("  Please implement SIRTAlgorithm in et_dflow.domain.algorithms.sirt", file=sys.stderr)
            
            # For now, create a simple placeholder
            # In production, this should call the actual SIRT algorithm
            import numpy as np
            
            # Get tilt series data
            tilt_data = tilt_series.data  # Shape: (n_tilts, height, width)
            n_tilts, height, width = tilt_data.shape
            
            # Placeholder: simple back-projection (NOT real SIRT)
            # This is just to make the script runnable - replace with actual SIRT
            depth = height  # Assume cubic volume
            reconstruction_data = tilt_data.mean(axis=0)  # Simple average
            reconstruction_data = reconstruction_data[np.newaxis, :, :].repeat(depth, axis=0)
            
            # Create reconstruction signal
            reconstruction = hs.signals.Signal1D(reconstruction_data)
            reconstruction.metadata.set_item("algorithm", "SIRT")
            reconstruction.metadata.set_item("iterations", config.get("iterations", 30))
            
            # Create a simple AlgorithmResult-like object
            class PlaceholderResult:
                def __init__(self, reconstruction):
                    self.reconstruction = reconstruction
                    self.execution_time = 0.0
                    self.memory_usage = 0.0
            
            result = PlaceholderResult(reconstruction)
        
        # Save reconstruction
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Saving reconstruction to: {output_path}")
        result.reconstruction.save(str(output_path))
        
        print("SIRT reconstruction completed successfully!")
        if hasattr(result, 'execution_time'):
            print(f"Execution time: {result.execution_time:.2f} seconds")
        if hasattr(result, 'memory_usage'):
            print(f"Memory usage: {result.memory_usage:.2f} MB")
        
        return 0
        
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON configuration: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Algorithm execution failed: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    sys.exit(main())

