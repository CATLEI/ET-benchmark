"""
Unit tests for missing wedge simulators.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.infrastructure.data.simulators import MissingWedgeSimulator
from et_dflow.infrastructure.data.fourier_operator import FourierSpaceOperator


class TestMissingWedgeSimulator:
    """Test MissingWedgeSimulator."""
    
    def test_simulator_creation(self):
        """Test simulator can be created."""
        simulator = MissingWedgeSimulator()
        assert simulator is not None
    
    def test_simulate_missing_wedge(self, sample_tilt_series):
        """Test missing wedge simulation."""
        simulator = MissingWedgeSimulator()
        
        result = simulator.simulate(
            sample_tilt_series,
            tilt_range=(-70, 70)
        )
        
        assert result is not None
        assert hasattr(result, "metadata")
        assert "missing_wedge" in result.metadata
    
    def test_asymmetric_missing_wedge(self, sample_tilt_series):
        """Test asymmetric missing wedge simulation."""
        simulator = MissingWedgeSimulator()
        
        result = simulator.simulate(
            sample_tilt_series,
            tilt_range=(-60, 80),  # Asymmetric range
            asymmetric=True
        )
        
        assert result is not None
        assert result.metadata.get_item("missing_wedge.asymmetric") is True
    
    def test_thickness_limitation(self, sample_tilt_series):
        """Test sample thickness limitation."""
        simulator = MissingWedgeSimulator()
        
        result = simulator.simulate(
            sample_tilt_series,
            tilt_range=(-70, 70),
            sample_thickness=50.0,  # 50 nm
            thickness_limit_angle=60.0  # degrees
        )
        
        assert result is not None
        assert result.metadata.get_item("missing_wedge.sample_thickness") == 50.0


class TestFourierSpaceOperator:
    """Test FourierSpaceOperator."""
    
    def test_operator_creation(self):
        """Test operator can be created."""
        operator = FourierSpaceOperator()
        assert operator is not None
    
    def test_fourier_transform(self, sample_ground_truth):
        """Test Fourier transform."""
        operator = FourierSpaceOperator()
        
        fourier_data = operator.to_fourier_space(sample_ground_truth)
        assert fourier_data is not None
        assert fourier_data.shape == sample_ground_truth.data.shape
    
    def test_inverse_fourier_transform(self, sample_ground_truth):
        """Test inverse Fourier transform."""
        operator = FourierSpaceOperator()
        
        fourier_data = operator.to_fourier_space(sample_ground_truth)
        real_data = operator.to_real_space(fourier_data)
        
        assert real_data is not None
        assert real_data.data.shape == sample_ground_truth.data.shape

