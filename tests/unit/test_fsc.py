"""
Unit tests for FSC calculation.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.domain.evaluation.metrics.fsc import (
    calculate_fsc_with_gt,
    calculate_fsc_without_gt,
    _split_tilt_series,
    _calculate_fsc_shells,
    _find_resolution
)
from et_dflow.core.exceptions import EvaluationError


class TestFSCWithGT:
    """Test FSC calculation with ground truth."""
    
    def test_fsc_with_gt_basic(self, sample_ground_truth):
        """Test basic FSC calculation with GT."""
        # Create reconstruction (slightly different from GT)
        reconstruction = sample_ground_truth.deepcopy()
        reconstruction.data = sample_ground_truth.data + np.random.randn(*sample_ground_truth.data.shape) * 0.1
        
        result = calculate_fsc_with_gt(reconstruction, sample_ground_truth)
        
        assert "fsc" in result
        assert "spatial_frequencies" in result
        assert "resolution" in result
        assert len(result["fsc"]) > 0
        assert len(result["spatial_frequencies"]) > 0
    
    def test_fsc_with_gt_shape_mismatch(self, sample_ground_truth):
        """Test FSC with shape mismatch raises error."""
        reconstruction = sample_ground_truth.deepcopy()
        # Change shape
        reconstruction.data = reconstruction.data[:32, :32, :32]
        
        with pytest.raises(EvaluationError):
            calculate_fsc_with_gt(reconstruction, sample_ground_truth)
    
    def test_fsc_resolution(self, sample_ground_truth):
        """Test resolution calculation."""
        reconstruction = sample_ground_truth.deepcopy()
        result = calculate_fsc_with_gt(reconstruction, sample_ground_truth, threshold=0.5)
        
        assert result["resolution"] > 0
        assert result["threshold"] == 0.5


class TestFSCWithoutGT:
    """Test FSC calculation without ground truth (Gold Standard)."""
    
    def test_fsc_without_gt(self, sample_tilt_series, sample_ground_truth):
        """Test Gold Standard FSC calculation."""
        result = calculate_fsc_without_gt(
            sample_ground_truth,
            tilt_series=sample_tilt_series,
            split_method="half"
        )
        
        assert "fsc" in result
        assert "spatial_frequencies" in result
        assert "resolution" in result
        assert result["method"] == "gold_standard"
        assert result["split_method"] == "half"
    
    def test_fsc_without_gt_no_tilt_series(self, sample_ground_truth):
        """Test FSC without GT raises error if no tilt series."""
        with pytest.raises(EvaluationError):
            calculate_fsc_without_gt(sample_ground_truth, tilt_series=None)
    
    def test_split_tilt_series_half(self, sample_tilt_series):
        """Test splitting tilt series by half."""
        split1, split2 = _split_tilt_series(sample_tilt_series, method="half")
        
        assert split1.data.shape[0] + split2.data.shape[0] == sample_tilt_series.data.shape[0]
    
    def test_split_tilt_series_odd_even(self, sample_tilt_series):
        """Test splitting tilt series by odd/even."""
        split1, split2 = _split_tilt_series(sample_tilt_series, method="odd_even")
        
        total = split1.data.shape[0] + split2.data.shape[0]
        assert total == sample_tilt_series.data.shape[0]
    
    def test_split_tilt_series_invalid_method(self, sample_tilt_series):
        """Test invalid split method raises error."""
        with pytest.raises(EvaluationError):
            _split_tilt_series(sample_tilt_series, method="invalid")


class TestFSCHelpers:
    """Test FSC helper functions."""
    
    def test_calculate_fsc_shells(self):
        """Test FSC shell calculation."""
        shape = (32, 32, 32)
        fft1 = np.random.randn(*shape) + 1j * np.random.randn(*shape)
        fft2 = np.random.randn(*shape) + 1j * np.random.randn(*shape)
        
        fsc_values, spatial_freqs = _calculate_fsc_shells(fft1, fft2, shape, shell_width=0.1)
        
        assert len(fsc_values) > 0
        assert len(spatial_freqs) > 0
        assert len(fsc_values) == len(spatial_freqs)
        assert all(-1 <= fsc <= 1 for fsc in fsc_values)
    
    def test_find_resolution(self):
        """Test resolution finding."""
        # Create FSC curve that drops below threshold
        fsc_values = np.array([1.0, 0.9, 0.7, 0.5, 0.3, 0.1, 0.05])
        spatial_freqs = np.linspace(0.1, 0.7, len(fsc_values))
        
        resolution, idx = _find_resolution(fsc_values, spatial_freqs, threshold=0.143)
        
        assert resolution > 0
        assert 0 <= idx < len(fsc_values)


