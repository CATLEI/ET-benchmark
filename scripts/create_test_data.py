#!/usr/bin/env python3
"""
Create test data for benchmark testing.

Generates a simple synthetic ET dataset for testing purposes.
"""

import numpy as np
import warnings
from pathlib import Path
import sys

# Suppress Hyperspy warnings about Numba (harmless)
warnings.filterwarnings('ignore', category=UserWarning, module='hyperspy')

import hyperspy.api as hs

def create_test_dataset(output_dir: str = "./data/test_dataset", size: tuple = (64, 64, 64)):
    """
    Create a simple synthetic test dataset.
    
    Args:
        output_dir: Output directory for test data
        size: Size of the 3D volume (x, y, z)
    """
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    print(f"Creating test dataset in {output_path}...")
    
    # Create a simple 3D volume with a sphere
    x, y, z = np.ogrid[:size[0], :size[1], :size[2]]
    center = (size[0]//2, size[1]//2, size[2]//2)
    radius = min(size) // 4
    
    # Create sphere
    mask = (x - center[0])**2 + (y - center[1])**2 + (z - center[2])**2 < radius**2
    
    # Create volume with some noise
    volume = np.zeros(size, dtype=np.float32)
    volume[mask] = 1.0
    volume += np.random.normal(0, 0.1, size).astype(np.float32)
    volume = np.clip(volume, 0, 1)
    
    # Create tilt series (simplified - just use the volume as is)
    # In real ET, this would be projections at different angles
    tilt_angles = np.linspace(-60, 60, 31)  # 31 projections from -60 to +60 degrees
    
    # Create a simple tilt series (for testing, we'll just save the volume)
    # In a real implementation, you would project the volume at each angle
    print(f"  Volume shape: {volume.shape}")
    print(f"  Tilt angles: {len(tilt_angles)} projections")
    
    # Save as Hyperspy signal
    signal = hs.signals.Signal1D(volume)
    signal.metadata.set_item("General.title", "Test ET Dataset")
    signal.metadata.set_item("Signal.quantity", "Intensity")
    signal.axes_manager[0].name = "X"
    signal.axes_manager[1].name = "Y"
    signal.axes_manager[2].name = "Z"
    
    # Save
    output_file = output_path / "test_data.hspy"
    signal.save(str(output_file))
    print(f"[OK] Test data saved to: {output_file}")
    
    # Also save as numpy array for compatibility
    np.save(output_path / "test_data.npy", volume)
    print(f"[OK] Numpy array saved to: {output_path / 'test_data.npy'}")
    
    print(f"\nTest dataset created successfully!")
    print(f"  Location: {output_path}")
    print(f"  Format: Hyperspy (.hspy)")
    print(f"  Size: {size}")
    
    return str(output_file)

if __name__ == "__main__":
    import argparse
    
    # Fix encoding for Windows
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    
    parser = argparse.ArgumentParser(description="Create test data for ET-dflow benchmark")
    parser.add_argument(
        "--output-dir",
        default="./data/test_dataset",
        help="Output directory for test data"
    )
    parser.add_argument(
        "--size",
        type=int,
        nargs=3,
        default=[64, 64, 64],
        help="Size of the 3D volume (x y z)"
    )
    
    args = parser.parse_args()
    
    try:
        output_file = create_test_dataset(
            output_dir=args.output_dir,
            size=tuple(args.size)
        )
        print(f"\n[SUCCESS] You can now use this data:")
        print(f"  et-dflow quick-start {output_file} --algorithm wbp")
        sys.exit(0)
    except Exception as e:
        print(f"[ERROR] Error creating test data: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

