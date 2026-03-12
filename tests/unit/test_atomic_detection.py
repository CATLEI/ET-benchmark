"""
Unit tests for atomic detection.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.infrastructure.algorithms.atomic_detector import AtomicDetector
from et_dflow.core.exceptions import EvaluationError


class TestAtomicDetector:
    """Test AtomicDetector."""
    
    def test_detector_creation(self):
        """Test detector can be created."""
        detector = AtomicDetector(method="peak_detection")
        assert detector.method == "peak_detection"
    
    def test_peak_detection(self, sample_ground_truth):
        """Test peak detection method."""
        detector = AtomicDetector(method="peak_detection")
        
        result = detector.detect(
            sample_ground_truth,
            config={"min_distance": 3, "threshold": None}
        )
        
        assert "positions" in result
        assert "n_atoms" in result
        assert "confidence" in result
        assert result["method"] == "peak_detection"
        assert len(result["positions"]) == result["n_atoms"]
    
    def test_template_matching(self, sample_ground_truth):
        """Test template matching method."""
        detector = AtomicDetector(method="template_matching")
        
        result = detector.detect(
            sample_ground_truth,
            config={"min_distance": 3, "template_size": 7}
        )
        
        assert "positions" in result
        assert result["method"] == "template_matching"
    
    def test_gaussian_fitting(self, sample_ground_truth):
        """Test Gaussian fitting method."""
        detector = AtomicDetector(method="gaussian_fitting")
        
        result = detector.detect(
            sample_ground_truth,
            config={"min_distance": 3, "fitting_window": 5}
        )
        
        assert "positions" in result
        assert result["method"] == "gaussian_fitting"
    
    def test_invalid_method(self, sample_ground_truth):
        """Test invalid method raises error."""
        detector = AtomicDetector(method="invalid")
        
        with pytest.raises(EvaluationError):
            detector.detect(sample_ground_truth)
    
    def test_generate_template(self):
        """Test template generation."""
        detector = AtomicDetector()
        template = detector._generate_atomic_template({"template_size": 5, "template_sigma": 1.0})
        
        assert template.shape == (5, 5, 5)
        assert template.max() > 0


