"""
WBP (Weighted Back-Projection) algorithm implementation.

This module provides the WBP reconstruction algorithm for electron tomography.
"""

import numpy as np
import hyperspy.api as hs
from typing import Dict, Any
from scipy.interpolate import interp1d
from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.exceptions import AlgorithmError


class WBPAlgorithm(Algorithm):
    """
    Weighted Back-Projection (WBP) algorithm for ET reconstruction.
    
    WBP is a classic reconstruction method that back-projects filtered
    projections to reconstruct the 3D volume.
    """
    
    def __init__(self, name: str = "wbp", config: Dict[str, Any] = None):
        """
        Initialize WBP algorithm.
        
        Args:
            name: Algorithm name (default: "wbp")
            config: Default configuration parameters
        """
        default_config = {
            "filter_type": "ramp",  # Options: "ramp", "shepp-logan", "cosine", "hamming", "hann", "none"
            "filter_cutoff": 1.0,   # Filter cutoff frequency (0.0 to 1.0) - not used in current implementation
            "interpolation": "linear",  # Options: "linear", "nearest", "spline", "cubic"
            "Nrecon": None,  # Reconstruction size (None = auto)
        }
        
        if config:
            default_config.update(config)
        
        super().__init__(name, default_config)
    
    def _execute(
        self,
        data: hs.signals.Signal2D,
        config: Dict[str, Any]
    ) -> hs.signals.Signal1D:
        """
        Execute WBP reconstruction.
        
        Args:
            data: Input tilt series as Hyperspy Signal2D
                Expected shape: (n_tilts, height, width)
            config: Algorithm configuration
        
        Returns:
            Reconstructed 3D volume as Hyperspy Signal1D
                Shape: (depth, height, width)
        
        Raises:
            AlgorithmError: If reconstruction fails
        """
        try:
            # Get tilt series data
            tilt_series = data.data
            
            # Get tilt angles from metadata
            tilt_angles = self._get_tilt_angles(data, config)
            
            # Get configuration parameters
            filter_type = config.get("filter_type", "ramp")
            interpolation = config.get("interpolation", "linear")
            Nrecon = config.get("Nrecon", None)
            
            # Convert data format for wbp_reconstruct
            # Input: tilt_series shape (n_tilts, height, width)
            # wbp_reconstruct expects (Nslice, Nray, Nproj)
            # where Nslice=height (slices), Nray=width (rays), Nproj=n_tilts (projections)
            n_tilts, height, width = tilt_series.shape
            
            # Reshape: (n_tilts, height, width) -> (height, width, n_tilts)
            # This matches: (Nslice, Nray, Nproj) where:
            #   - Nslice = height (each slice is a row in the tilt series)
            #   - Nray = width (number of rays/detector pixels)
            #   - Nproj = n_tilts (number of projections/angles)
            data_reshaped = np.transpose(tilt_series, (1, 2, 0))  # (height, width, n_tilts)
            
            # Perform WBP reconstruction
            reconstruction = self._wbp_reconstruct(
                data=data_reshaped,
                angles=tilt_angles,
                Nrecon=Nrecon,
                filter=filter_type,
                interp=interpolation,
            )
            
            # Create output signal
            # For 3D volume data (depth, height, width), use Signal2D
            # where navigation dimension = depth (Z), signal dimensions = (height, width) (Y, X)
            result_signal = hs.signals.Signal2D(reconstruction)
            result_signal.metadata.set_item("General.title", "WBP Reconstruction")
            result_signal.metadata.set_item("Signal.quantity", "Intensity")
            
            # Set axis names
            # For 3D volume: navigation axis = Z, signal axes = Y, X
            try:
                if result_signal.axes_manager:
                    # Set navigation axis (Z dimension)
                    if result_signal.axes_manager.navigation_dimension > 0:
                        nav_axis = result_signal.axes_manager.navigation_axes[0]
                        nav_axis.name = "Z"
                        nav_axis.units = "px"
                    
                    # Set signal axes (Y, X dimensions)
                    if result_signal.axes_manager.signal_dimension >= 2:
                        sig_axes = result_signal.axes_manager.signal_axes
                        sig_axes[0].name = "Y"
                        sig_axes[0].units = "px"
                        sig_axes[1].name = "X"
                        sig_axes[1].units = "px"
            except (AttributeError, IndexError, TypeError):
                pass
            
            return result_signal
            
        except Exception as e:
            raise AlgorithmError(
                f"WBP reconstruction failed: {e}",
                details={"algorithm": "wbp", "error": str(e)}
            ) from e
    
    def _get_tilt_angles(self, data: hs.signals.Signal2D, config: Dict[str, Any]) -> np.ndarray:
        """
        Get tilt angles from data metadata or config.
        
        Args:
            data: Input data signal
            config: Configuration dictionary
        
        Returns:
            Array of tilt angles in degrees
        """
        # Try to get from config first (highest priority)
        if "tilt_angles" in config:
            angles = config["tilt_angles"]
            if isinstance(angles, (list, np.ndarray)):
                return np.array(angles)
        
        # Try to get from metadata
        try:
            if hasattr(data.metadata, "Acquisition_instrument"):
                tem = getattr(data.metadata.Acquisition_instrument, "TEM", None)
                if tem and hasattr(tem, "tilt_series"):
                    tilt_angles = tem.tilt_series
                    if tilt_angles is not None:
                        return np.array(tilt_angles)
        except (AttributeError, TypeError):
            pass
        
        # Default: generate evenly spaced angles based on data shape
        n_tilts = data.data.shape[0]
        tilt_range = config.get("tilt_range", [-60, 60])
        return np.linspace(tilt_range[0], tilt_range[1], n_tilts)
    
    def _wbp_reconstruct(
        self,
        data: np.ndarray,
        angles: np.ndarray,
        Nrecon: int = None,
        filter: str = 'ramp',
        interp: str = 'linear'
    ) -> np.ndarray:
        """
        Perform WBP reconstruction on 3D data (multiple sinograms).
        
        This is your actual WBP implementation.
        
        Args:
            data: 3D projection data, shape (Nslice, Nray, Nproj)
                where Nslice=height, Nray=width, Nproj=n_tilts
            angles: Tilt angles in degrees, shape (Nproj,)
            Nrecon: Reconstruction output size (None = auto)
            filter: Filter type ('ramp', 'shepp-logan', 'cosine', 'hamming', 'hann', 'none')
            interp: Interpolation method ('linear', 'nearest', 'spline', 'cubic')
        
        Returns:
            Reconstructed 3D volume, shape (Nslice, Nrecon, Nrecon)
        """
        Nslice, Nray, Nproj = data.shape
        
        if Nproj != angles.size:
            raise ValueError(f'Data shape {data.shape} does not match angles size {angles.size}! '
                           f'Expected Nproj={Nproj} to match angles.size={angles.size}')
        
        if Nrecon is None:
            Nrecon = Nray
        
        recon = np.empty([Nslice, Nrecon, Nrecon], dtype=np.float32, order='F')
        for i in range(Nslice):
            # data[i, :, :] is shape (Nray, Nproj) which is the sinogram for slice i
            recon[i, :, :] = self._wbp2(data[i, :, :], angles, Nrecon, filter, interp)
        
        return recon
    
    def _wbp2(
        self,
        sinogram: np.ndarray,
        angles: np.ndarray,
        N: int = None,
        filter: str = "ramp",
        interp: str = "linear"
    ) -> np.ndarray:
        """
        Perform 2D WBP reconstruction on a single sinogram.
        
        This is your actual WBP implementation.
        
        Args:
            sinogram: 2D sinogram data, shape (Nray, Nproj)
            angles: Tilt angles in degrees, shape (Nproj,)
            N: Reconstruction output size (None = auto)
            filter: Filter type
            interp: Interpolation method
        
        Returns:
            Reconstructed 2D slice, shape (N, N)
        """
        if sinogram.ndim != 2:
            raise ValueError('Sinogram must be 2D')
        
        (Nray, Nproj) = sinogram.shape
        if Nproj != angles.size:
            raise ValueError('Sinogram does not match angles!')
        
        interpolation_methods = ('linear', 'nearest', 'spline', 'cubic')
        if interp not in interpolation_methods:
            raise ValueError("Unknown interpolation: %s" % interp)
        
        if not N:
            N = int(np.floor(np.sqrt(Nray**2 / 2.0)))
        
        # Convert angles to radians
        ang = np.double(angles) * np.pi / 180.0
        
        # Generate filter
        F = self._make_filter(Nray, filter)
        
        # Pad sinogram to filter size
        s = np.pad(sinogram, ((0, F.size - Nray), (0, 0)), 'constant', constant_values=(0, 0))
        
        # Apply FFT and filter
        s = np.fft.fft(s, axis=0) * F
        
        # Inverse FFT
        s = np.real(np.fft.ifft(s, axis=0))
        
        # Extract valid region
        s = s[:Nray, :]
        
        # Initialize reconstruction
        recon = np.zeros((N, N), np.float32)
        center_proj = Nray // 2
        
        # Generate reconstruction grid
        [X, Y] = np.mgrid[0:N, 0:N]
        xpr = X - int(N) // 2
        ypr = Y - int(N) // 2
        
        # Back-project for each angle
        for j in range(Nproj):
            t = ypr * np.cos(ang[j]) - xpr * np.sin(ang[j])
            x = np.arange(Nray) - center_proj
            
            # Interpolate
            if interp == 'linear':
                bp = np.interp(t, x, s[:, j], left=0, right=0)
            elif interp == 'spline':
                interpolant = interp1d(x, s[:, j], kind='slinear', bounds_error=False, fill_value=0)
                bp = interpolant(t)
            else:
                interpolant = interp1d(x, s[:, j], kind=interp, bounds_error=False, fill_value=0)
                bp = interpolant(t)
            
            recon = recon + bp
        
        # Normalize
        recon = recon * np.pi / 2 / Nproj
        
        return recon
    
    def _make_filter(self, Nray: int, filter_method: str = "ramp") -> np.ndarray:
        """
        Generate filter for filtered back-projection.
        
        Args:
            Nray: Number of rays (projection data rows)
            filter_method: Filter type ('ramp', 'shepp-logan', 'cosine', 'hamming', 'hann', 'none')
        
        Returns:
            Filter array
        """
        N2 = 2**np.ceil(np.log2(Nray))
        freq = np.fft.fftfreq(int(N2)).reshape(-1, 1)
        omega = 2 * np.pi * freq
        filter_array = 2 * np.abs(freq)
        
        if filter_method == "ramp":
            pass
        elif filter_method == "shepp-logan":
            filter_array[1:] = filter_array[1:] * np.sin(omega[1:]) / omega[1:]
        elif filter_method == "cosine":
            filter_array[1:] = filter_array[1:] * np.cos(filter_array[1:])
        elif filter_method == "hamming":
            filter_array[1:] = filter_array[1:] * (0.54 + 0.46 * np.cos(omega[1:] / 2))
        elif filter_method == "hann":
            filter_array[1:] = filter_array[1:] * (1 + np.cos(omega[1:] / 2)) / 2
        elif filter_method == "none":
            filter_array[:] = 1
        else:
            raise ValueError("Unknown filter: %s" % filter_method)
        
        return filter_array
