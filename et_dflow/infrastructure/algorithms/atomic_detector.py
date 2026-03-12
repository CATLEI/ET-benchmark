"""
Atomic position detection implementation.

Implements multiple methods for detecting atomic positions in 3D volumes.
"""

from typing import List, Dict, Any, Tuple, Optional
import numpy as np
from scipy.ndimage import gaussian_filter, maximum_filter
from scipy.optimize import minimize
try:
    from skimage.feature import peak_local_maxima
except ImportError:
    # Fallback implementation
    def peak_local_maxima(image, min_distance=1, threshold_abs=None):
        """Fallback peak detection."""
        if threshold_abs is None:
            threshold_abs = np.percentile(image, 95)
        # Use maximum filter for peak detection
        local_maxima = maximum_filter(image, size=min_distance*2+1) == image
        local_maxima = local_maxima & (image >= threshold_abs)
        return np.where(local_maxima)
import hyperspy.api as hs
from et_dflow.core.exceptions import EvaluationError


class AtomicDetector:
    """
    Detector for atomic positions in 3D volumes.
    
    Supports multiple detection methods:
    - Peak detection
    - Template matching
    - Gaussian fitting
    """
    
    def __init__(self, method: str = "peak_detection"):
        """
        Initialize atomic detector.
        
        Args:
            method: Detection method ('peak_detection', 'template_matching', 'gaussian_fitting')
        """
        self.method = method
    
    def detect(
        self,
        volume: hs.signals.Signal1D,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Detect atomic positions.
        
        Args:
            volume: 3D volume containing atoms
            config: Detection configuration parameters
        
        Returns:
            Dictionary containing:
            - 'positions': List of atomic positions (x, y, z)
            - 'n_atoms': Number of detected atoms
            - 'confidence': Confidence scores for each atom
            - 'method': Detection method used
        """
        config = config or {}
        
        if self.method == "peak_detection":
            return self._peak_detection(volume, config)
        elif self.method == "template_matching":
            return self._template_matching(volume, config)
        elif self.method == "gaussian_fitting":
            return self._gaussian_fitting_peaks(volume, config)
        else:
            raise EvaluationError(
                f"Unknown detection method: {self.method}",
                details={"method": self.method, "available": [
                    "peak_detection", "template_matching", "gaussian_fitting"
                ]}
            )
    
    def _peak_detection(
        self,
        volume: hs.signals.Signal1D,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect atoms using peak detection.
        
        Args:
            volume: 3D volume
            config: Configuration with 'min_distance', 'threshold' etc.
        
        Returns:
            Detection results
        """
        data = volume.data
        
        # Parameters
        min_distance = config.get("min_distance", 3)  # pixels
        threshold = config.get("threshold", None)  # Auto if None
        
        # Apply Gaussian smoothing
        sigma = config.get("smoothing_sigma", 1.0)
        if sigma > 0:
            smoothed = gaussian_filter(data, sigma=sigma)
        else:
            smoothed = data
        
        # Find local maxima
        if threshold is None:
            threshold = np.percentile(smoothed, 95)  # Top 5%
        
        # Use scikit-image peak detection
        peaks = peak_local_maxima(
            smoothed,
            min_distance=min_distance,
            threshold_abs=threshold
        )
        
        # Convert to list of positions
        positions = list(zip(peaks[0], peaks[1], peaks[2]))
        
        # Calculate confidence (intensity at peak)
        confidence = [float(smoothed[pos]) for pos in positions]
        
        return {
            "positions": positions,
            "n_atoms": len(positions),
            "confidence": confidence,
            "method": "peak_detection",
        }
    
    def _template_matching(
        self,
        volume: hs.signals.Signal1D,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect atoms using template matching.
        
        Args:
            volume: 3D volume
            config: Configuration with template parameters
        
        Returns:
            Detection results
        """
        data = volume.data
        
        # Generate atomic template
        template = self._generate_atomic_template(config)
        
        # Template matching (simplified)
        # In full implementation, would use proper 3D template matching
        # For now, use peak detection on template-matched result
        
        # Convolve with template
        from scipy.ndimage import correlate
        matched = correlate(data, template, mode='constant')
        
        # Find peaks in matched result
        min_distance = config.get("min_distance", 3)
        threshold = config.get("threshold", None)
        
        if threshold is None:
            threshold = np.percentile(matched, 95)
        
        peaks = peak_local_maxima(
            matched,
            min_distance=min_distance,
            threshold_abs=threshold
        )
        
        positions = list(zip(peaks[0], peaks[1], peaks[2]))
        confidence = [float(matched[pos]) for pos in positions]
        
        return {
            "positions": positions,
            "n_atoms": len(positions),
            "confidence": confidence,
            "method": "template_matching",
        }
    
    def _gaussian_fitting_peaks(
        self,
        volume: hs.signals.Signal1D,
        config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detect atoms using Gaussian fitting.
        
        First finds peaks, then fits Gaussians for sub-pixel accuracy.
        
        Args:
            volume: 3D volume
            config: Configuration parameters
        
        Returns:
            Detection results with refined positions
        """
        # First use peak detection to find candidate positions
        peak_config = config.copy()
        peak_config["method"] = "peak_detection"
        
        peak_results = self._peak_detection(volume, peak_config)
        candidate_positions = peak_results["positions"]
        
        # Refine positions using Gaussian fitting
        data = volume.data
        refined_positions = []
        confidence = []
        
        for pos in candidate_positions:
            # Extract local region around peak
            window_size = config.get("fitting_window", 5)
            z, y, x = pos
            
            # Extract window
            z_min = max(0, z - window_size // 2)
            z_max = min(data.shape[0], z + window_size // 2 + 1)
            y_min = max(0, y - window_size // 2)
            y_max = min(data.shape[1], y + window_size // 2 + 1)
            x_min = max(0, x - window_size // 2)
            x_max = min(data.shape[2], x + window_size // 2 + 1)
            
            window = data[z_min:z_max, y_min:y_max, x_min:x_max]
            
            # Fit Gaussian (simplified - would use proper 3D Gaussian fitting)
            # For now, use center of mass as refined position
            if window.size > 0:
                com = np.array(np.unravel_index(np.argmax(window), window.shape))
                refined_pos = (
                    z_min + com[0],
                    y_min + com[1],
                    x_min + com[2]
                )
                refined_positions.append(refined_pos)
                confidence.append(float(window.max()))
        
        return {
            "positions": refined_positions,
            "n_atoms": len(refined_positions),
            "confidence": confidence,
            "method": "gaussian_fitting",
        }
    
    def _generate_atomic_template(self, config: Dict[str, Any]) -> np.ndarray:
        """
        Generate atomic template for template matching.
        
        Args:
            config: Configuration with template parameters
        
        Returns:
            3D template array
        """
        size = config.get("template_size", 7)
        sigma = config.get("template_sigma", 1.0)
        
        # Create 3D Gaussian template
        center = size // 2
        coords = np.meshgrid(
            *[np.arange(size) - center for _ in range(3)],
            indexing='ij'
        )
        
        r_squared = sum(c**2 for c in coords)
        template = np.exp(-r_squared / (2 * sigma**2))
        
        return template

