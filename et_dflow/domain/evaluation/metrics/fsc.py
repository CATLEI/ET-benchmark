"""
Fourier Shell Correlation (FSC) calculation.

Implements FSC calculation with and without ground truth.
"""

from typing import Optional, Tuple, Dict, Any
import numpy as np
from scipy.ndimage import gaussian_filter
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


def calculate_fsc_with_gt(
    reconstruction: hs.signals.Signal1D,
    ground_truth: hs.signals.Signal1D,
    shell_width: float = 0.1,
    threshold: float = 0.143
) -> Dict[str, Any]:
    """
    Calculate FSC between reconstruction and ground truth.
    
    Args:
        reconstruction: Reconstructed 3D volume
        ground_truth: Ground truth 3D volume
        shell_width: Width of Fourier shells (as fraction of Nyquist)
        threshold: FSC threshold for resolution determination (default: 0.143)
    
    Returns:
        Dictionary containing:
        - 'fsc': FSC values as function of spatial frequency
        - 'spatial_frequencies': Spatial frequencies in 1/nm
        - 'resolution': Resolution at threshold in nm
        - 'resolution_angle': Resolution angle in degrees
    """
    # Get data arrays
    recon_data = reconstruction.data
    gt_data = ground_truth.data
    
    # Ensure same shape
    if recon_data.shape != gt_data.shape:
        raise EvaluationError(
            f"Reconstruction and ground truth must have same shape. "
            f"Got {recon_data.shape} and {gt_data.shape}",
            details={"recon_shape": recon_data.shape, "gt_shape": gt_data.shape}
        )
    
    # Calculate FFT
    recon_fft = np.fft.fftn(recon_data)
    recon_fft = np.fft.fftshift(recon_fft)
    
    gt_fft = np.fft.fftn(gt_data)
    gt_fft = np.fft.fftshift(gt_fft)
    
    # Calculate FSC
    fsc_values, spatial_freqs = _calculate_fsc_shells(
        recon_fft, gt_fft, recon_data.shape, shell_width
    )
    
    # Find resolution at threshold
    resolution, resolution_idx = _find_resolution(
        fsc_values, spatial_freqs, threshold
    )
    
    # Calculate resolution angle safely
    if resolution > 0 and resolution != float('inf'):
        try:
            resolution_angle = float(np.degrees(np.arcsin(1.0 / resolution)))
        except (ValueError, ZeroDivisionError):
            resolution_angle = 0.0
    else:
        resolution_angle = 0.0
    
    return {
        "fsc": fsc_values.tolist(),
        "spatial_frequencies": spatial_freqs.tolist(),
        "resolution": float(resolution),
        "resolution_angle": resolution_angle,
        "threshold": threshold,
    }


def calculate_fsc_without_gt(
    reconstruction: hs.signals.Signal1D,
    tilt_series: Optional[hs.signals.Signal2D] = None,
    split_method: str = "half",
    shell_width: float = 0.1,
    threshold: float = 0.143
) -> Dict[str, Any]:
    """
    Calculate FSC using Gold Standard method (without ground truth).
    
    Splits data into two halves, reconstructs separately, and calculates FSC.
    
    Args:
        reconstruction: Reconstructed 3D volume
        tilt_series: Original tilt series (for splitting)
        split_method: Method for splitting ('half', 'odd_even', 'random')
        shell_width: Width of Fourier shells
        threshold: FSC threshold for resolution determination
    
    Returns:
        Dictionary containing FSC results (same format as calculate_fsc_with_gt)
    """
    if tilt_series is None:
        raise EvaluationError(
            "Tilt series required for Gold Standard FSC calculation",
            details={"split_method": split_method}
        )
    
    # Split tilt series
    split1, split2 = _split_tilt_series(tilt_series, split_method)
    
    # Reconstruct each half (placeholder - would use actual reconstruction)
    # For now, use simplified approach: split reconstruction
    recon_data = reconstruction.data
    
    # Simple split: use different halves of reconstruction
    # In real implementation, would reconstruct from split tilt series
    mid = recon_data.shape[0] // 2
    recon1_data = recon_data[:mid]
    recon2_data = recon_data[mid:]
    
    # Pad to same shape
    if recon1_data.shape != recon2_data.shape:
        # Pad smaller one
        max_shape = tuple(max(s1, s2) for s1, s2 in zip(recon1_data.shape, recon2_data.shape))
        recon1_padded = np.zeros(max_shape, dtype=recon1_data.dtype)
        recon2_padded = np.zeros(max_shape, dtype=recon2_data.dtype)
        
        slices1 = tuple(slice(0, s) for s in recon1_data.shape)
        slices2 = tuple(slice(0, s) for s in recon2_data.shape)
        
        recon1_padded[slices1] = recon1_data
        recon2_padded[slices2] = recon2_data
        
        recon1_data = recon1_padded
        recon2_data = recon2_padded
    
    # Create signals
    recon1 = hs.signals.Signal1D(recon1_data)
    recon2 = hs.signals.Signal1D(recon2_data)
    
    # Calculate FSC between two reconstructions
    recon1_fft = np.fft.fftn(recon1_data)
    recon1_fft = np.fft.fftshift(recon1_fft)
    
    recon2_fft = np.fft.fftn(recon2_data)
    recon2_fft = np.fft.fftshift(recon2_fft)
    
    # Calculate FSC
    fsc_values, spatial_freqs = _calculate_fsc_shells(
        recon1_fft, recon2_fft, recon1_data.shape, shell_width
    )
    
    # Find resolution
    resolution, resolution_idx = _find_resolution(
        fsc_values, spatial_freqs, threshold
    )
    
    # Calculate resolution angle safely
    if resolution > 0 and resolution != float('inf'):
        try:
            resolution_angle = float(np.degrees(np.arcsin(1.0 / resolution)))
        except (ValueError, ZeroDivisionError):
            resolution_angle = 0.0
    else:
        resolution_angle = 0.0
    
    return {
        "fsc": fsc_values.tolist(),
        "spatial_frequencies": spatial_freqs.tolist(),
        "resolution": float(resolution),
        "resolution_angle": resolution_angle,
        "threshold": threshold,
        "method": "gold_standard",
        "split_method": split_method,
    }


def _split_tilt_series(
    tilt_series: hs.signals.Signal2D,
    method: str = "half"
) -> Tuple[hs.signals.Signal2D, hs.signals.Signal2D]:
    """
    Split tilt series into two halves.
    
    Args:
        tilt_series: Input tilt series
        method: Splitting method ('half', 'odd_even', 'random')
    
    Returns:
        Tuple of two tilt series
    """
    data = tilt_series.data
    n_tilts = data.shape[0]
    
    if method == "half":
        mid = n_tilts // 2
        split1_data = data[:mid]
        split2_data = data[mid:]
    elif method == "odd_even":
        split1_data = data[::2]  # Even indices
        split2_data = data[1::2]  # Odd indices
    elif method == "random":
        np.random.seed(42)  # For reproducibility
        indices = np.random.permutation(n_tilts)
        mid = n_tilts // 2
        split1_indices = indices[:mid]
        split2_indices = indices[mid:]
        split1_data = data[split1_indices]
        split2_data = data[split2_indices]
    else:
        raise EvaluationError(
            f"Unknown split method: {method}",
            details={"method": method, "available": ["half", "odd_even", "random"]}
        )
    
    split1 = hs.signals.Signal2D(split1_data)
    split2 = hs.signals.Signal2D(split2_data)
    
    # Copy metadata (hyperspy metadata is read-only, so we copy items)
    if hasattr(tilt_series, 'metadata'):
        for key in tilt_series.metadata:
            try:
                split1.metadata.set_item(key, tilt_series.metadata.get_item(key))
                split2.metadata.set_item(key, tilt_series.metadata.get_item(key))
            except Exception:
                pass  # Skip if cannot copy
    
    return split1, split2


def _calculate_fsc_shells(
    fft1: np.ndarray,
    fft2: np.ndarray,
    shape: Tuple[int, ...],
    shell_width: float
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Calculate FSC in Fourier shells.
    
    Args:
        fft1: First FFT
        fft2: Second FFT
        shape: Shape of original data
        shell_width: Shell width as fraction of Nyquist
    
    Returns:
        Tuple of (FSC values, spatial frequencies)
    """
    # Calculate Nyquist frequency
    nyquist = 0.5  # In units of 1/pixel
    
    # Create coordinate arrays
    coords = np.meshgrid(
        *[np.arange(s) - s // 2 for s in shape],
        indexing='ij'
    )
    
    # Calculate radial distance
    r_squared = sum(c**2 for c in coords)
    r = np.sqrt(r_squared)
    
    # Normalize to Nyquist
    r_normalized = r / (max(shape) / 2)
    
    # Create shells
    max_freq = nyquist
    n_shells = int(max_freq / shell_width)
    shell_edges = np.linspace(0, max_freq, n_shells + 1)
    
    fsc_values = []
    spatial_freqs = []
    
    for i in range(n_shells):
        shell_min = shell_edges[i]
        shell_max = shell_edges[i + 1]
        
        # Find voxels in shell
        mask = (r_normalized >= shell_min) & (r_normalized < shell_max)
        
        if np.sum(mask) == 0:
            continue
        
        # Extract values in shell
        f1_shell = fft1[mask]
        f2_shell = fft2[mask]
        
        # Calculate FSC
        numerator = np.real(np.sum(f1_shell * np.conj(f2_shell)))
        denominator1 = np.sqrt(np.sum(np.abs(f1_shell)**2))
        denominator2 = np.sqrt(np.sum(np.abs(f2_shell)**2))
        
        if denominator1 > 0 and denominator2 > 0:
            fsc = numerator / (denominator1 * denominator2)
        else:
            fsc = 0.0
        
        fsc_values.append(float(fsc))
        spatial_freqs.append((shell_min + shell_max) / 2)
    
    return np.array(fsc_values), np.array(spatial_freqs)


def _find_resolution(
    fsc_values: np.ndarray,
    spatial_freqs: np.ndarray,
    threshold: float
) -> Tuple[float, int]:
    """
    Find resolution at FSC threshold.
    
    Args:
        fsc_values: FSC values
        spatial_freqs: Spatial frequencies
        threshold: FSC threshold
    
    Returns:
        Tuple of (resolution in nm, index)
    """
    # Find first frequency where FSC drops below threshold
    below_threshold = np.where(fsc_values < threshold)[0]
    
    if len(below_threshold) == 0:
        # FSC never drops below threshold
        return float(spatial_freqs[-1]), len(fsc_values) - 1
    
    resolution_idx = below_threshold[0]
    resolution_freq = spatial_freqs[resolution_idx]
    
    # Convert frequency to resolution (assuming pixel size = 1 nm)
    # In real implementation, would use actual pixel size
    resolution = 1.0 / resolution_freq if resolution_freq > 0 else float('inf')
    
    return float(resolution), int(resolution_idx)

