"""
Unit tests for directional resolution calculation.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.domain.evaluation.metrics.directional_resolution import (
    calculate_directional_resolution,
    _calculate_full_directional_resolution,
    _calculate_sampled_directional_resolution,
    _calculate_approximate_directional_resolution
)
from et_dflow.core.exceptions import EvaluationError


class TestDirectionalResolution:
    """Test directional resolution calculation."""
    
    def test_calculate_directional_resolution_sampled(self, sample_ground_truth):
        """Test sampled directional resolution calculation."""
        tilt_angles = np.linspace(-70, 70, 21)
        
        result = calculate_directional_resolution(
            sample_ground_truth,
            tilt_angles,
            method="sampled",
            n_directions=50
        )
        
        assert "directional_resolution" in result
        assert "directions" in result
        assert "average_resolution" in result
        assert "min_resolution" in result
        assert "max_resolution" in result
        assert result["method"] == "sampled"
        assert result["n_directions"] == 50
    
    def test_calculate_directional_resolution_approximate(self, sample_ground_truth):
        """Test approximate directional resolution calculation."""
        tilt_angles = np.linspace(-70, 70, 21)
        
        result = calculate_directional_resolution(
            sample_ground_truth,
            tilt_angles,
            method="approximate"
        )
        
        assert "directional_resolution" in result
        assert "directions" in result
        assert "average_resolution" in result
        assert result["method"] == "approximate"
        assert "missing_wedge_angle" in result
    
    def test_calculate_directional_resolution_invalid_method(self, sample_ground_truth):
        """Test invalid method raises error."""
        tilt_angles = np.linspace(-70, 70, 21)
        
        with pytest.raises(EvaluationError):
            calculate_directional_resolution(
                sample_ground_truth,
                tilt_angles,
                method="invalid"
            )
    
    def test_sampled_directional_resolution(self, sample_ground_truth):
        """Test sampled method directly."""
        tilt_angles = np.linspace(-70, 70, 21)
        
        result = _calculate_sampled_directional_resolution(
            sample_ground_truth,
            tilt_angles,
            n_directions=20,
            shell_width=0.1
        )
        
        assert len(result["directions"]) == 20
        assert len(result["directional_resolution"]) == 20
    
    def test_approximate_directional_resolution(self, sample_ground_truth):
        """Test approximate method directly."""
        tilt_angles = np.linspace(-60, 60, 21)
        
        result = _calculate_approximate_directional_resolution(
            sample_ground_truth,
            tilt_angles,
            shell_width=0.1
        )
        
        assert len(result["directions"]) == 6  # Key directions
        assert result["missing_wedge_angle"] > 0


