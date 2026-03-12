"""
Directional resolution calculation.

Implements directional resolution calculation with different sampling strategies.
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np
from scipy.spatial.distance import cdist
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_directional_resolution(
    reconstruction: hs.signals.Signal1D,
    tilt_angles: np.ndarray,
    method: str = "sampled",
    n_directions: int = 100,
    shell_width: float = 0.1
) -> Dict[str, Any]:
    """
    Calculate directional resolution.
    
    Args:
        reconstruction: Reconstructed 3D volume
        tilt_angles: Array of tilt angles used in reconstruction
        method: Calculation method ('full', 'sampled', 'approximate')
        n_directions: Number of directions to sample (for sampled method)
        shell_width: Width of Fourier shells
    
    Returns:
        Dictionary containing:
        - 'directional_resolution': Resolution map as function of direction
        - 'directions': Unit vectors representing directions
        - 'average_resolution': Average resolution across all directions
        - 'min_resolution': Minimum resolution (best direction)
        - 'max_resolution': Maximum resolution (worst direction)
    """
    if method == "full":
        return _calculate_full_directional_resolution(
            reconstruction, tilt_angles, shell_width
        )
    elif method == "sampled":
        return _calculate_sampled_directional_resolution(
            reconstruction, tilt_angles, n_directions, shell_width
        )
    elif method == "approximate":
        return _calculate_approximate_directional_resolution(
            reconstruction, tilt_angles, shell_width
        )
    else:
        raise EvaluationError(
            f"Unknown method: {method}",
            details={"method": method, "available": ["full", "sampled", "approximate"]}
        )


def _calculate_full_directional_resolution(
    reconstruction: hs.signals.Signal1D,
    tilt_angles: np.ndarray,
    shell_width: float
) -> Dict[str, Any]:
    """
    Calculate full directional resolution (all directions).
    
    This is computationally expensive but most accurate.
    
    Args:
        reconstruction: Reconstructed volume
        tilt_angles: Tilt angles
        shell_width: Shell width
    
    Returns:
        Directional resolution dictionary
    """
    # Get FFT
    data = reconstruction.data
    fft = np.fft.fftn(data)
    fft = np.fft.fftshift(fft)
    
    shape = data.shape
    center = tuple(s // 2 for s in shape)
    
    # Create coordinate arrays
    coords = np.meshgrid(
        *[np.arange(s) - center[i] for i, s in enumerate(shape)],
        indexing='ij'
    )
    
    # Calculate all directions (unit vectors)
    # This is simplified - full implementation would properly sample sphere
    directions = []
    resolutions = []
    
    # Sample directions on sphere (simplified)
    # In full implementation, would use proper spherical sampling
    n_samples = 1000  # Large number for "full" calculation
    
    for i in range(n_samples):
        # Generate random direction on unit sphere
        direction = np.random.randn(3)
        direction = direction / np.linalg.norm(direction)
        
        # Calculate resolution in this direction
        resolution = _calculate_resolution_in_direction(
            fft, shape, direction, shell_width
        )
        
        directions.append(direction.tolist())
        resolutions.append(resolution)
    
    resolutions = np.array(resolutions)
    
    return {
        "directional_resolution": resolutions.tolist(),
        "directions": directions,
        "average_resolution": float(np.mean(resolutions)),
        "min_resolution": float(np.min(resolutions)),
        "max_resolution": float(np.max(resolutions)),
        "method": "full",
    }


def _calculate_sampled_directional_resolution(
    reconstruction: hs.signals.Signal1D,
    tilt_angles: np.ndarray,
    n_directions: int,
    shell_width: float
) -> Dict[str, Any]:
    """
    Calculate directional resolution using sampling strategy.
    
    Samples a subset of directions for efficiency.
    
    Args:
        reconstruction: Reconstructed volume
        tilt_angles: Tilt angles
        n_directions: Number of directions to sample
        shell_width: Shell width
    
    Returns:
        Directional resolution dictionary
    """
    # Get FFT
    data = reconstruction.data
    fft = np.fft.fftn(data)
    fft = np.fft.fftshift(fft)
    
    shape = data.shape
    
    # Sample directions on sphere
    directions = []
    resolutions = []
    
    np.random.seed(42)  # For reproducibility
    
    for i in range(n_directions):
        # Generate random direction on unit sphere
        direction = np.random.randn(3)
        direction = direction / np.linalg.norm(direction)
        
        # Calculate resolution in this direction
        resolution = _calculate_resolution_in_direction(
            fft, shape, direction, shell_width
        )
        
        directions.append(direction.tolist())
        resolutions.append(resolution)
    
    resolutions = np.array(resolutions)
    
    return {
        "directional_resolution": resolutions.tolist(),
        "directions": directions,
        "average_resolution": float(np.mean(resolutions)),
        "min_resolution": float(np.min(resolutions)),
        "max_resolution": float(np.max(resolutions)),
        "method": "sampled",
        "n_directions": n_directions,
    }


def _calculate_approximate_directional_resolution(
    reconstruction: hs.signals.Signal1D,
    tilt_angles: np.ndarray,
    shell_width: float
) -> Dict[str, Any]:
    """
    Calculate approximate directional resolution.
    
    Uses analytical approximation based on tilt angle coverage.
    
    Args:
        reconstruction: Reconstructed volume
        tilt_angles: Tilt angles
        shell_width: Shell width
    
    Returns:
        Directional resolution dictionary
    """
    # Calculate missing wedge angle
    max_abs_angle = np.max(np.abs(tilt_angles))
    missing_wedge_angle = 90.0 - max_abs_angle
    
    # Approximate resolution based on missing wedge
    # Resolution is worst in direction perpendicular to tilt axis
    # Best in direction parallel to tilt axis
    
    # Simplified approximation
    # In full implementation, would calculate proper directional resolution
    
    # Sample key directions
    key_directions = [
        [1, 0, 0],  # X direction
        [0, 1, 0],  # Y direction
        [0, 0, 1],  # Z direction (tilt axis)
        [1, 1, 0] / np.sqrt(2),  # XY plane
        [1, 0, 1] / np.sqrt(2),  # XZ plane
        [0, 1, 1] / np.sqrt(2),  # YZ plane
    ]
    
    # Approximate resolutions based on missing wedge
    # Resolution is better parallel to tilt axis, worse perpendicular
    base_resolution = 1.0  # Placeholder
    resolutions = []
    
    for direction in key_directions:
        # Calculate angle with tilt axis (Z-axis)
        angle_with_tilt = np.arccos(np.abs(direction[2]))
        
        # Resolution degrades with angle from tilt axis
        resolution = base_resolution / (1.0 + missing_wedge_angle / 90.0 * np.sin(angle_with_tilt))
        resolutions.append(resolution)
    
    resolutions = np.array(resolutions)
    
    # Convert directions to lists
    directions_list = []
    for d in key_directions:
        if isinstance(d, np.ndarray):
            directions_list.append(d.tolist())
        else:
            directions_list.append(list(d))
    
    return {
        "directional_resolution": resolutions.tolist(),
        "directions": directions_list,
        "average_resolution": float(np.mean(resolutions)),
        "min_resolution": float(np.min(resolutions)),
        "max_resolution": float(np.max(resolutions)),
        "method": "approximate",
        "missing_wedge_angle": float(missing_wedge_angle),
    }


def _calculate_resolution_in_direction(
    fft: np.ndarray,
    shape: Tuple[int, ...],
    direction: np.ndarray,
    shell_width: float
) -> float:
    """
    Calculate resolution in a specific direction.
    
    Args:
        fft: Fourier transform of volume
        shape: Shape of volume
        direction: Unit vector representing direction
        shell_width: Shell width
    
    Returns:
        Resolution in nm (approximate)
    """
    # This is a simplified implementation
    # Full implementation would properly calculate resolution
    # based on Fourier space coverage in the given direction
    
    # For now, return a placeholder value
    # In real implementation, would:
    # 1. Extract Fourier space values along direction
    # 2. Calculate FSC or similar metric
    # 3. Determine resolution threshold
    
    return 1.0  # Placeholder

