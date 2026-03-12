"""
Data quality validation implementation.

Provides comprehensive data quality checking before processing.
"""

from typing import Dict, Any, List, TYPE_CHECKING
import numpy as np

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.exceptions import DataError


class DataQualityChecker:
    """
    Check data quality before processing.
    
    Checks:
    - Tilt angle coverage
    - Image quality (SNR, contrast)
    - Drift detection
    - Bad pixel detection
    - Contrast variation
    """
    
    def check_quality(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Comprehensive data quality check.
        
        Args:
            tilt_series: Tilt series to check
        
        Returns:
            Dictionary with quality metrics and warnings
        """
        checks = {
            "tilt_angle_coverage": self._check_tilt_coverage(tilt_series),
            "image_quality": self._check_image_quality(tilt_series),
            "drift_detection": self._detect_drift(tilt_series),
            "bad_pixels": self._detect_bad_pixels(tilt_series),
            "contrast_variation": self._check_contrast_variation(tilt_series),
            "overall_quality": "good",  # or 'fair', 'poor'
        }
        
        # Generate warnings
        warnings = self._generate_warnings(checks)
        checks["warnings"] = warnings
        
        # Determine overall quality
        checks["overall_quality"] = self._determine_overall_quality(checks)
        
        return checks
    
    def _check_tilt_coverage(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Check tilt angle coverage.
        
        Args:
            tilt_series: Tilt series
        
        Returns:
            Dictionary with tilt coverage metrics
        """
        tilt_angles = tilt_series.metadata.get_item("tilt_angles", [])
        
        if len(tilt_angles) == 0:
            # Try to infer from signal dimensions
            if tilt_series.data.ndim >= 2:
                n_tilts = tilt_series.data.shape[0]
                # Assume symmetric range if not specified
                tilt_angles = np.linspace(-70, 70, n_tilts).tolist()
        
        if len(tilt_angles) == 0:
            return {
                "tilt_range": None,
                "tilt_step": None,
                "coverage_score": 0.0,
                "missing_wedge_angle": 90.0,
                "status": "error",
            }
        
        tilt_angles = np.array(tilt_angles)
        tilt_range = (float(tilt_angles.min()), float(tilt_angles.max()))
        
        # Calculate tilt step
        sorted_angles = np.sort(tilt_angles)
        tilt_step = float(np.mean(np.diff(sorted_angles)))
        
        # Calculate coverage score (0-1)
        # Ideal: ±90° coverage = 1.0
        coverage_angle = tilt_range[1] - tilt_range[0]
        coverage_score = coverage_angle / 180.0
        
        # Calculate missing wedge angle
        max_abs_angle = max(abs(tilt_range[0]), abs(tilt_range[1]))
        missing_wedge_angle = 90.0 - max_abs_angle
        
        return {
            "tilt_range": tilt_range,
            "tilt_step": tilt_step,
            "coverage_score": float(coverage_score),
            "missing_wedge_angle": float(missing_wedge_angle),
            "n_tilts": len(tilt_angles),
            "status": "good" if coverage_score > 0.7 else "fair" if coverage_score > 0.5 else "poor",
        }
    
    def _check_image_quality(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Check image quality (SNR, contrast).
        
        Args:
            tilt_series: Tilt series
        
        Returns:
            Dictionary with image quality metrics
        """
        data = tilt_series.data
        
        # Calculate SNR for each image
        snrs = []
        contrasts = []
        
        for i in range(data.shape[0]):
            image = data[i]
            
            # Simple SNR estimation: mean / std
            mean_val = np.mean(image)
            std_val = np.std(image)
            snr = mean_val / std_val if std_val > 0 else 0
            snrs.append(float(snr))
            
            # Contrast: (max - min) / (max + min)
            img_min = image.min()
            img_max = image.max()
            contrast = (img_max - img_min) / (img_max + img_min) if (img_max + img_min) > 0 else 0
            contrasts.append(float(contrast))
        
        avg_snr = float(np.mean(snrs))
        avg_contrast = float(np.mean(contrasts))
        
        # Determine quality
        if avg_snr > 10 and avg_contrast > 0.3:
            quality = "good"
        elif avg_snr > 5 and avg_contrast > 0.2:
            quality = "fair"
        else:
            quality = "poor"
        
        return {
            "average_snr": avg_snr,
            "average_contrast": avg_contrast,
            "snr_range": (float(np.min(snrs)), float(np.max(snrs))),
            "contrast_range": (float(np.min(contrasts)), float(np.max(contrasts))),
            "quality": quality,
        }
    
    def _detect_drift(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Detect sample drift between images.
        
        Args:
            tilt_series: Tilt series
        
        Returns:
            Dictionary with drift detection results
        """
        data = tilt_series.data
        
        # Simple drift detection using cross-correlation
        reference = data[0]
        drifts = []
        
        for i in range(1, min(10, data.shape[0])):  # Check first 10 images
            from scipy.signal import correlate2d
            correlation = correlate2d(
                reference, data[i], mode="full"
            )
            peak = np.unravel_index(
                np.argmax(correlation), correlation.shape
            )
            shift = (
                peak[0] - reference.shape[0] + 1,
                peak[1] - reference.shape[1] + 1
            )
            drift_magnitude = np.sqrt(shift[0]**2 + shift[1]**2)
            drifts.append(float(drift_magnitude))
        
        max_drift = float(np.max(drifts)) if drifts else 0.0
        avg_drift = float(np.mean(drifts)) if drifts else 0.0
        
        # Determine if drift is significant (> 2 pixels)
        has_drift = max_drift > 2.0
        
        return {
            "max_drift": max_drift,
            "average_drift": avg_drift,
            "has_drift": has_drift,
            "status": "warning" if has_drift else "ok",
        }
    
    def _detect_bad_pixels(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Detect bad pixels (dead pixels, hot pixels).
        
        Args:
            tilt_series: Tilt series
        
        Returns:
            Dictionary with bad pixel detection results
        """
        data = tilt_series.data
        
        # Simple bad pixel detection: pixels with extreme values
        # that are consistent across images
        n_bad_pixels = 0
        
        # Check for consistently zero pixels (dead pixels)
        zero_mask = np.all(data == 0, axis=0)
        n_dead_pixels = int(np.sum(zero_mask))
        
        # Check for consistently high pixels (hot pixels)
        # Use 99th percentile as threshold
        threshold = np.percentile(data, 99)
        hot_mask = np.all(data > threshold, axis=0)
        n_hot_pixels = int(np.sum(hot_mask))
        
        n_bad_pixels = n_dead_pixels + n_hot_pixels
        total_pixels = data.shape[1] * data.shape[2]
        bad_pixel_ratio = n_bad_pixels / total_pixels if total_pixels > 0 else 0.0
        
        return {
            "n_bad_pixels": n_bad_pixels,
            "n_dead_pixels": n_dead_pixels,
            "n_hot_pixels": n_hot_pixels,
            "bad_pixel_ratio": float(bad_pixel_ratio),
            "status": "warning" if bad_pixel_ratio > 0.01 else "ok",
        }
    
    def _check_contrast_variation(self, tilt_series: Signal) -> Dict[str, Any]:
        """
        Check contrast variation across tilt series.
        
        Args:
            tilt_series: Tilt series
        
        Returns:
            Dictionary with contrast variation metrics
        """
        data = tilt_series.data
        
        contrasts = []
        for i in range(data.shape[0]):
            image = data[i]
            img_min = image.min()
            img_max = image.max()
            contrast = (img_max - img_min) / (img_max + img_min) if (img_max + img_min) > 0 else 0
            contrasts.append(float(contrast))
        
        contrasts = np.array(contrasts)
        contrast_std = float(np.std(contrasts))
        contrast_cv = contrast_std / np.mean(contrasts) if np.mean(contrasts) > 0 else 0.0
        
        # Variation > 10% is significant
        has_variation = contrast_cv > 0.1
        
        return {
            "contrast_mean": float(np.mean(contrasts)),
            "contrast_std": contrast_std,
            "contrast_cv": float(contrast_cv),
            "has_variation": has_variation,
            "status": "warning" if has_variation else "ok",
        }
    
    def _generate_warnings(self, checks: Dict[str, Any]) -> List[str]:
        """
        Generate warnings based on quality checks.
        
        Args:
            checks: Quality check results
        
        Returns:
            List of warning messages
        """
        warnings = []
        
        # Tilt coverage warnings
        tilt_coverage = checks.get("tilt_angle_coverage", {})
        if tilt_coverage.get("coverage_score", 0) < 0.5:
            warnings.append(
                f"Low tilt coverage: {tilt_coverage.get('coverage_score', 0):.2f}. "
                f"Missing wedge angle: {tilt_coverage.get('missing_wedge_angle', 0):.1f}°"
            )
        
        # Image quality warnings
        image_quality = checks.get("image_quality", {})
        if image_quality.get("quality") == "poor":
            warnings.append(
                f"Poor image quality: SNR={image_quality.get('average_snr', 0):.2f}, "
                f"Contrast={image_quality.get('average_contrast', 0):.2f}"
            )
        
        # Drift warnings
        drift = checks.get("drift_detection", {})
        if drift.get("has_drift", False):
            warnings.append(
                f"Drift detected: max drift = {drift.get('max_drift', 0):.2f} pixels"
            )
        
        # Bad pixel warnings
        bad_pixels = checks.get("bad_pixels", {})
        if bad_pixels.get("bad_pixel_ratio", 0) > 0.01:
            warnings.append(
                f"High bad pixel ratio: {bad_pixels.get('bad_pixel_ratio', 0):.2%}"
            )
        
        # Contrast variation warnings
        contrast_var = checks.get("contrast_variation", {})
        if contrast_var.get("has_variation", False):
            warnings.append(
                f"Significant contrast variation: CV = {contrast_var.get('contrast_cv', 0):.2%}"
            )
        
        return warnings
    
    def _determine_overall_quality(self, checks: Dict[str, Any]) -> str:
        """
        Determine overall data quality.
        
        Args:
            checks: Quality check results
        
        Returns:
            Overall quality: 'good', 'fair', or 'poor'
        """
        # Count issues
        issues = 0
        
        tilt_coverage = checks.get("tilt_angle_coverage", {})
        if tilt_coverage.get("coverage_score", 0) < 0.5:
            issues += 1
        
        image_quality = checks.get("image_quality", {})
        if image_quality.get("quality") == "poor":
            issues += 1
        
        drift = checks.get("drift_detection", {})
        if drift.get("has_drift", False):
            issues += 1
        
        bad_pixels = checks.get("bad_pixels", {})
        if bad_pixels.get("bad_pixel_ratio", 0) > 0.01:
            issues += 1
        
        # Determine quality
        if issues == 0:
            return "good"
        elif issues <= 2:
            return "fair"
        else:
            return "poor"

