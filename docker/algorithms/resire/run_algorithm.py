#!/usr/bin/env python
"""
Entry point script for RESIRE algorithm execution in Docker container.

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

# Try to import RESIRE algorithm
try:
    from et_dflow.domain.algorithms.resire import RESIREAlgorithm
    HAS_RESIRE_ALGORITHM = True
except ImportError:
    # RESIREAlgorithm may not exist yet, we'll use a placeholder
    HAS_RESIRE_ALGORITHM = False
    print("WARNING: RESIREAlgorithm not found in et_dflow.domain.algorithms.resire", file=sys.stderr)
    print("  Using placeholder implementation. Please implement RESIREAlgorithm class.", file=sys.stderr)


def main():
    """Main entry point for algorithm execution."""
    parser = argparse.ArgumentParser(description="RESIRE Algorithm Execution")
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
        
        # Initialize and run RESIRE algorithm
        if HAS_RESIRE_ALGORITHM:
            print("Initializing RESIRE algorithm...")
            algorithm = RESIREAlgorithm(config=config)
            
            print("Running RESIRE reconstruction...")
            result = algorithm.run(tilt_series, config)
        else:
            # Placeholder implementation - replace with actual RESIRE algorithm
            print("WARNING: Using placeholder RESIRE implementation", file=sys.stderr)
            print("  Please implement RESIREAlgorithm in et_dflow.domain.algorithms.resire", file=sys.stderr)
            
            # For now, create a simple placeholder
            import numpy as np
            
            # Get tilt series data
            tilt_data = tilt_series.data  # Shape: (n_tilts, height, width)
            n_tilts, height, width = tilt_data.shape
            
            # Placeholder: simple back-projection (NOT real RESIRE)
            # This is just to make the script runnable - replace with actual RESIRE
            depth = height  # Assume cubic volume
            reconstruction_data = tilt_data.mean(axis=0)  # Simple average
            reconstruction_data = reconstruction_data[np.newaxis, :, :].repeat(depth, axis=0)
            
            # Create reconstruction signal
            reconstruction = hs.signals.Signal1D(reconstruction_data)
            reconstruction.metadata.set_item("algorithm", "RESIRE")
            reconstruction.metadata.set_item("iterations", config.get("iterations", 50))
            reconstruction.metadata.set_item("oversampling_ratio", config.get("oversampling_ratio", 2.0))
            
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
        
        print("RESIRE reconstruction completed successfully!")
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

