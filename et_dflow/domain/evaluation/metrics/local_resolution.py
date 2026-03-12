"""
Local resolution calculation.

Calculates resolution map showing resolution variation across the volume.
"""

from typing import Dict, Any, Tuple
import numpy as np
from scipy.ndimage import gaussian_filter
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_local_resolution(
    reconstruction: hs.signals.Signal1D,
    window_size: int = 10,
    method: str = "fsc"
) -> Dict[str, Any]:
    """
    Calculate local resolution map.
    
    Args:
        reconstruction: Reconstructed volume
        window_size: Size of local window for resolution calculation
        method: Calculation method ('fsc', 'fourier_ring_correlation')
    
    Returns:
        Dictionary with local resolution map and statistics
    """
    data = reconstruction.data
    
    if method == "fsc":
        return _calculate_local_resolution_fsc(data, window_size)
    else:
        raise EvaluationError(
            f"Unknown method: {method}",
            details={"method": method}
        )


def _calculate_local_resolution_fsc(
    data: np.ndarray,
    window_size: int
) -> Dict[str, Any]:
    """
    Calculate local resolution using FSC-like method.
    
    Args:
        data: Volume data
        window_size: Window size
    
    Returns:
        Local resolution map
    """
    # Simplified implementation
    # Full implementation would calculate FSC in local windows
    
    # Create resolution map
    resolution_map = np.zeros_like(data, dtype=np.float32)
    
    # Calculate resolution for each local window
    # This is a placeholder - full implementation would:
    # 1. Extract local windows
    # 2. Calculate FSC or similar metric
    # 3. Determine resolution threshold
    
    # For now, use intensity-based approximation
    # Higher intensity regions typically have better resolution
    smoothed = gaussian_filter(data, sigma=window_size / 3)
    normalized = (smoothed - smoothed.min()) / (smoothed.max() - smoothed.min() + 1e-10)
    
    # Convert to resolution (inverse relationship)
    # Higher normalized intensity -> better resolution (lower value)
    resolution_map = 1.0 / (normalized + 0.1)  # Placeholder
    
    return {
        "resolution_map": resolution_map.tolist(),
        "mean_resolution": float(np.mean(resolution_map)),
        "min_resolution": float(np.min(resolution_map)),
        "max_resolution": float(np.max(resolution_map)),
        "std_resolution": float(np.std(resolution_map)),
        "method": "fsc",
        "window_size": window_size,
    }


