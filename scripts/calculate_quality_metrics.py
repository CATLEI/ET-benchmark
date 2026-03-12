#!/usr/bin/env python3
"""
Quality Metrics Calculation Script
Automatically calculates quality metrics for a dataset, replacing manual complexity assessment.
"""

import argparse
import yaml
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import hyperspy.api as hs
    HAS_HYPERSPY = True
except ImportError:
    HAS_HYPERSPY = False
    print("Warning: hyperspy not available, some metrics cannot be calculated")


def calculate_snr(tilt_series_path: Path) -> float:
    """Calculate Signal-to-Noise Ratio from tilt series."""
    if not HAS_HYPERSPY:
        return 0.0
    
    try:
        signal = hs.load(str(tilt_series_path))
        data = signal.data
        
        # Simple SNR calculation: mean / std
        mean_signal = np.mean(data)
        std_noise = np.std(data)
        
        if std_noise > 0:
            snr = mean_signal / std_noise
        else:
            snr = 0.0
        
        return float(snr)
    except Exception as e:
        print(f"Warning: Could not calculate SNR: {e}")
        return 0.0


def calculate_missing_wedge(tilt_angles_path: Optional[Path], tilt_range: Optional[list]) -> float:
    """Calculate missing wedge angle from tilt angles or tilt_range."""
    if tilt_range:
        # Calculate from tilt_range
        min_angle, max_angle = tilt_range
        missing_wedge = 180 - (max_angle - min_angle)
        return float(missing_wedge)
    elif tilt_angles_path and tilt_angles_path.exists():
        # Calculate from tilt_angles file
        try:
            angles = np.loadtxt(str(tilt_angles_path))
            if angles.ndim == 0:
                angles = [angles]
            min_angle = float(np.min(angles))
            max_angle = float(np.max(angles))
            missing_wedge = 180 - (max_angle - min_angle)
            return float(missing_wedge)
        except Exception as e:
            print(f"Warning: Could not calculate missing wedge from angles: {e}")
            return 0.0
    else:
        return 0.0


def calculate_data_completeness(tilt_angles_path: Optional[Path], tilt_range: Optional[list], tilt_step: Optional[float]) -> float:
    """Calculate data completeness (0-1) based on tilt series coverage."""
    if tilt_range and tilt_step:
        min_angle, max_angle = tilt_range
        expected_angles = (max_angle - min_angle) / tilt_step + 1
        # Assume full coverage if we have tilt_range and tilt_step
        return 1.0
    elif tilt_angles_path and tilt_angles_path.exists():
        try:
            angles = np.loadtxt(str(tilt_angles_path))
            if angles.ndim == 0:
                angles = [angles]
            num_angles = len(angles)
            # Assume ideal coverage is 180 degrees with 1 degree steps
            ideal_angles = 180
            completeness = min(1.0, num_angles / ideal_angles)
            return float(completeness)
        except Exception as e:
            print(f"Warning: Could not calculate completeness: {e}")
            return 0.0
    else:
        return 0.0


def estimate_resolution(tilt_series_path: Optional[Path]) -> float:
    """Estimate resolution from tilt series (simplified)."""
    # This is a placeholder - actual resolution estimation requires more complex analysis
    return 2.5  # Default estimate in nm


def calculate_contrast(tilt_series_path: Path) -> float:
    """Calculate image contrast (0-1)."""
    if not HAS_HYPERSPY:
        return 0.0
    
    try:
        signal = hs.load(str(tilt_series_path))
        data = signal.data
        
        # Simple contrast calculation: (max - min) / (max + min)
        data_min = np.min(data)
        data_max = np.max(data)
        
        if (data_max + data_min) > 0:
            contrast = (data_max - data_min) / (data_max + data_min)
        else:
            contrast = 0.0
        
        return float(contrast)
    except Exception as e:
        print(f"Warning: Could not calculate contrast: {e}")
        return 0.0


def update_metadata_with_metrics(dataset_path: Path, metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Update metadata with calculated quality metrics."""
    # Get paths
    raw_dir = dataset_path / "raw"
    tilt_series_path = None
    for ext in ['.hspy', '.mrc', '.tiff', '.tif', '.h5']:
        candidate = raw_dir / f"tilt_series{ext}"
        if candidate.exists():
            tilt_series_path = candidate
            break
    
    tilt_angles_path = raw_dir / "tilt_angles.txt"
    if not tilt_angles_path.exists():
        tilt_angles_path = None
    
    # Get experimental parameters
    exp_params = metadata.get('experimental_parameters', {})
    tilt_range = exp_params.get('tilt_range')
    tilt_step = exp_params.get('tilt_step')
    
    # Calculate metrics
    print("Calculating quality metrics...")
    
    snr = 0.0
    contrast = 0.0
    if tilt_series_path:
        snr = calculate_snr(tilt_series_path)
        contrast = calculate_contrast(tilt_series_path)
        print(f"  SNR: {snr:.2f}")
        print(f"  Contrast: {contrast:.2f}")
    
    missing_wedge = calculate_missing_wedge(tilt_angles_path, tilt_range)
    print(f"  Missing wedge angle: {missing_wedge:.1f} degrees")
    
    data_completeness = calculate_data_completeness(tilt_angles_path, tilt_range, tilt_step)
    print(f"  Data completeness: {data_completeness:.2f}")
    
    resolution = estimate_resolution(tilt_series_path)
    print(f"  Estimated resolution: {resolution:.2f} nm")
    
    # Update metadata
    if 'quality_metrics' not in metadata:
        metadata['quality_metrics'] = {}
    
    metadata['quality_metrics'].update({
        'snr': snr,
        'contrast': contrast,
        'missing_wedge_angle': missing_wedge,
        'data_completeness': data_completeness,
        'resolution_estimate': resolution
    })
    
    # Calculate algorithm challenges (auto-calculated from quality metrics)
    if 'algorithm_challenges' not in metadata:
        metadata['algorithm_challenges'] = {}
    
    # Missing wedge severity
    if missing_wedge < 60:
        wedge_severity = "low"
    elif missing_wedge < 120:
        wedge_severity = "medium"
    else:
        wedge_severity = "high"
    
    # Noise level
    if snr < 10:
        noise_level = "high"
    elif snr < 20:
        noise_level = "medium"
    else:
        noise_level = "low"
    
    # Structural complexity (based on sample type)
    sample_type = metadata.get('sample', {}).get('type', 'unknown')
    if sample_type in ['nanoparticle', 'sphere']:
        structural_complexity = "low"
    elif sample_type in ['interface', 'defect']:
        structural_complexity = "high"
    else:
        structural_complexity = "medium"
    
    metadata['algorithm_challenges'] = {
        'missing_wedge_severity': wedge_severity,
        'noise_level': noise_level,
        'structural_complexity': structural_complexity
    }
    
    return metadata


def main():
    parser = argparse.ArgumentParser(description="Calculate quality metrics for a dataset")
    parser.add_argument("dataset_path", type=Path, help="Path to dataset directory")
    parser.add_argument("--update", action="store_true", help="Update metadata.yaml with calculated metrics")
    
    args = parser.parse_args()
    
    dataset_path = Path(args.dataset_path).resolve()
    if not dataset_path.exists():
        print(f"Error: Dataset path does not exist: {dataset_path}")
        return 1
    
    metadata_path = dataset_path / "metadata.yaml"
    if not metadata_path.exists():
        print(f"Error: metadata.yaml not found at {metadata_path}")
        return 1
    
    # Load metadata
    with open(metadata_path, 'r') as f:
        metadata = yaml.safe_load(f)
    
    # Calculate and update metrics
    metadata = update_metadata_with_metrics(dataset_path, metadata)
    
    # Update metadata.yaml if requested
    if args.update:
        with open(metadata_path, 'w') as f:
            yaml.dump(metadata, f, default_flow_style=False, sort_keys=False)
        print(f"\n✓ Updated {metadata_path}")
    else:
        print("\n✓ Metrics calculated (use --update to save to metadata.yaml)")
    
    return 0


if __name__ == "__main__":
    exit(main())

