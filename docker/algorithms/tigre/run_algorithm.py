#!/usr/bin/env python
"""
Adapter script for TIGRE algorithm.
Converts standard ET-dflow interface to TIGRE-specific interface.

This script serves as an adapter template for external Docker images.
It demonstrates how to bridge the standard ET-dflow interface with
algorithm-specific APIs.

Usage:
    python run_algorithm.py --input <input.hspy> --output <output.hspy> --config <json>
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import hyperspy.api as hs
except ImportError:
    print("ERROR: Hyperspy not available", file=sys.stderr)
    sys.exit(1)

# Try to import TIGRE
try:
    import tigre
    HAS_TIGRE_MODULE = True
except ImportError:
    HAS_TIGRE_MODULE = False
    print("WARNING: TIGRE module not available", file=sys.stderr)
    print("  This adapter requires the tigre Python package", file=sys.stderr)


def main():
    """Main entry point for TIGRE algorithm execution."""
    parser = argparse.ArgumentParser(
        description="TIGRE Algorithm Execution (ET-dflow Adapter)"
    )
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to input tilt series file (.hspy format)"
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output reconstruction file (.hspy format)"
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
        
        # Ensure we have a Signal2D (tilt series)
        if not isinstance(tilt_series, hs.signals.Signal2D):
            print(f"ERROR: Expected Signal2D (tilt series), got {type(tilt_series)}", file=sys.stderr)
            sys.exit(1)
        
        # Extract algorithm parameters from config
        iterations = config.get("iterations", 30)
        
        print(f"Running TIGRE reconstruction...")
        print(f"  Iterations: {iterations}")
        
        # TODO: Implement actual TIGRE reconstruction
        # This is a placeholder - actual implementation depends on TIGRE API
        # Example structure:
        #   import tigre
        #   # Setup geometry
        #   geo = tigre.geometry(...)
        #   # Run reconstruction
        #   reconstruction_data = tigre.algorithm_name(projections, geo, iterations)
        
        # For now, create a placeholder reconstruction
        print("WARNING: Using placeholder reconstruction. Implement actual TIGRE API call.")
        
        # Get tilt series data
        tilt_data = tilt_series.data  # Shape: (n_tilts, height, width)
        n_tilts, height, width = tilt_data.shape
        
        # Placeholder: simple back-projection (replace with TIGRE)
        import numpy as np
        depth = height  # Assume cubic volume
        reconstruction_data = tilt_data.mean(axis=0)  # Simple average (NOT real TIGRE)
        reconstruction_data = reconstruction_data[np.newaxis, :, :].repeat(depth, axis=0)
        
        # Create reconstruction signal
        reconstruction = hs.signals.Signal1D(reconstruction_data)
        reconstruction.metadata.set_item("algorithm", "TIGRE")
        reconstruction.metadata.set_item("iterations", iterations)
        
        # Copy relevant metadata from input
        if hasattr(tilt_series.metadata, "pixel_size"):
            reconstruction.metadata.set_item("pixel_size", tilt_series.metadata.pixel_size)
        
        # Save reconstruction
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Saving reconstruction to: {output_path}")
        reconstruction.save(str(output_path))
        
        print("TIGRE reconstruction completed successfully!")
        print(f"  Output shape: {reconstruction.data.shape}")
        
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
    import numpy as np  # Import here to avoid issues if not available
    sys.exit(main())

