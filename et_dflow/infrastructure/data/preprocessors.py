"""
Data preprocessing implementation.

Provides comprehensive data preprocessing for ET tilt series.
"""

from typing import List, Optional, TYPE_CHECKING
import numpy as np
from scipy import ndimage
from scipy.ndimage import gaussian_filter

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IPreprocessor
from et_dflow.core.exceptions import DataError


class DataPreprocessor(IPreprocessor):
    """
    Comprehensive data preprocessing for ET data.
    
    Handles:
    - Alignment
    - Contrast normalization
    - Bad pixel removal
    - Drift correction
    """
    
    def preprocess(
        self,
        tilt_series: Signal,
        steps: Optional[List[str]] = None
    ) -> Signal:
        """
        Apply preprocessing steps.
        
        Args:
            tilt_series: Input tilt series
            steps: List of preprocessing steps to apply.
                  If None, apply all default steps.
                  Available steps: 'alignment', 'normalization',
                  'bad_pixels', 'drift'
        
        Returns:
            Preprocessed tilt series
        
        Raises:
            DataError: If preprocessing fails
        """
        if steps is None:
            steps = ["alignment", "normalization", "bad_pixels", "drift"]
        
        processed = tilt_series.deepcopy()
        
        try:
            for step in steps:
                if step == "alignment":
                    processed = self._align_tilt_series(processed)
                elif step == "normalization":
                    processed = self._normalize_contrast(processed)
                elif step == "bad_pixels":
                    processed = self._remove_bad_pixels(processed)
                elif step == "drift":
                    processed = self._correct_drift(processed)
                else:
                    raise DataError(
                        f"Unknown preprocessing step: {step}",
                        details={"step": step, "available_steps": [
                            "alignment", "normalization", "bad_pixels", "drift"
                        ]}
                    )
            
            # Update metadata
            processed.metadata.set_item("preprocessing_steps", steps)
            
            return processed
        except Exception as e:
            raise DataError(
                f"Error during preprocessing: {e}",
                details={"error": str(e), "steps": steps}
            ) from e
    
    def _align_tilt_series(
        self,
        tilt_series: Signal,
        method: str = "cross_correlation"
    ) -> Signal:
        """
        Align tilt series images.
        
        Methods:
        - 'cross_correlation': Cross-correlation based alignment
        - 'feature_matching': Feature-based alignment
        - 'fiducial_markers': Fiducial marker-based alignment
        
        Args:
            tilt_series: Input tilt series
            method: Alignment method
        
        Returns:
            Aligned tilt series
        """
        if method == "cross_correlation":
            return self._align_cross_correlation(tilt_series)
        elif method == "feature_matching":
            return self._align_feature_matching(tilt_series)
        else:
            # Default to cross-correlation
            return self._align_cross_correlation(tilt_series)
    
    def _align_cross_correlation(self, tilt_series: Signal) -> Signal:
        """
        Align using cross-correlation.
        
        Args:
            tilt_series: Input tilt series
        
        Returns:
            Aligned tilt series
        """
        data = tilt_series.data.copy()
        n_images = data.shape[0]
        
        # Use first image as reference
        reference = data[0]
        
        aligned_data = np.zeros_like(data)
        aligned_data[0] = reference
        
        for i in range(1, n_images):
            # Calculate cross-correlation
            from scipy.signal import correlate2d
            correlation = correlate2d(
                reference, data[i], mode="full"
            )
            
            # Find peak (shift)
            peak = np.unravel_index(
                np.argmax(correlation), correlation.shape
            )
            
            # Calculate shift
            shift = (
                peak[0] - reference.shape[0] + 1,
                peak[1] - reference.shape[1] + 1
            )
            
            # Apply shift
            aligned_data[i] = ndimage.shift(data[i], shift, mode="constant")
        
        # Create aligned signal
        aligned = tilt_series.deepcopy()
        aligned.data = aligned_data
        
        return aligned
    
    def _align_feature_matching(self, tilt_series: Signal) -> Signal:
        """
        Align using feature matching (placeholder for future implementation).
        
        Args:
            tilt_series: Input tilt series
        
        Returns:
            Aligned tilt series (currently returns original)
        """
        # TODO: Implement feature-based alignment
        # For now, return original
        return tilt_series
    
    def _normalize_contrast(
        self,
        tilt_series: Signal,
        method: str = "histogram_equalization"
    ) -> Signal:
        """
        Normalize contrast across tilt series.
        
        Args:
            tilt_series: Input tilt series
            method: Normalization method
        
        Returns:
            Contrast-normalized tilt series
        """
        data = tilt_series.data.copy()
        
        if method == "histogram_equalization":
            # Simple histogram equalization
            normalized_data = np.zeros_like(data)
            
            for i in range(data.shape[0]):
                image = data[i]
                # Normalize to [0, 1]
                image_min = image.min()
                image_max = image.max()
                if image_max > image_min:
                    normalized = (image - image_min) / (image_max - image_min)
                else:
                    normalized = image
                normalized_data[i] = normalized
            
            normalized = tilt_series.deepcopy()
            normalized.data = normalized_data
            return normalized
        else:
            return tilt_series
    
    def _remove_bad_pixels(
        self,
        tilt_series: Signal,
        method: str = "median_filter"
    ) -> Signal:
        """
        Remove bad pixels (dead pixels, hot pixels, etc.).
        
        Args:
            tilt_series: Input tilt series
            method: Bad pixel removal method
        
        Returns:
            Tilt series with bad pixels removed
        """
        data = tilt_series.data.copy()
        
        if method == "median_filter":
            # Apply median filter to remove outliers
            cleaned_data = np.zeros_like(data)
            
            for i in range(data.shape[0]):
                cleaned_data[i] = ndimage.median_filter(data[i], size=3)
            
            cleaned = tilt_series.deepcopy()
            cleaned.data = cleaned_data
            return cleaned
        else:
            return tilt_series
    
    def _correct_drift(
        self,
        tilt_series: Signal,
        method: str = "cross_correlation"
    ) -> Signal:
        """
        Correct sample drift between images.
        
        Args:
            tilt_series: Input tilt series
            method: Drift correction method
        
        Returns:
            Drift-corrected tilt series
        """
        # Similar to alignment, but track cumulative drift
        # For now, use alignment method
        return self._align_tilt_series(tilt_series, method=method)

