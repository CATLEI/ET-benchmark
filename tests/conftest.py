"""
pytest configuration and fixtures.

Provides common fixtures for testing.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def sample_tilt_series():
    """
    Create a sample tilt series for testing.
    
    Returns:
        Hyperspy Signal with sample tilt series data
    """
    # Create synthetic tilt series
    n_tilts = 21
    height, width = 64, 64
    
    # Generate synthetic data
    data = np.random.rand(n_tilts, height, width).astype(np.float32)
    
    # Create signal
    signal = hs.signals.Signal2D(data)
    
    # Add metadata
    tilt_angles = np.linspace(-70, 70, n_tilts)
    signal.metadata.set_item("tilt_angles", tilt_angles.tolist())
    signal.metadata.set_item("pixel_size", 0.5)
    
    return signal


@pytest.fixture
def sample_ground_truth():
    """
    Create sample ground truth volume.
    
    Returns:
        Hyperspy Signal with ground truth 3D volume
    """
    # Create synthetic 3D volume
    depth, height, width = 64, 64, 64
    
    # Generate synthetic data
    data = np.random.rand(depth, height, width).astype(np.float32)
    
    # Create signal
    signal = hs.signals.Signal1D(data)
    
    # Add metadata
    signal.metadata.set_item("pixel_size", 0.5)
    
    return signal


@pytest.fixture
def temp_dir():
    """
    Create temporary directory for testing.
    
    Yields:
        Path to temporary directory
    """
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


@pytest.fixture
def mock_algorithm():
    """
    Create mock algorithm for testing.
    
    Returns:
        Mock algorithm instance
    """
    from unittest.mock import Mock
    from et_dflow.domain.algorithms.base import Algorithm
    
    class MockAlgorithm(Algorithm):
        def _execute(self, data, config):
            # Return mock reconstruction
            return data.deepcopy()
    
    return MockAlgorithm("mock_algorithm")


@pytest.fixture
def config_manager():
    """
    Create configuration manager for testing.
    
    Returns:
        ConfigManager instance
    """
    from et_dflow.core.config import ConfigManager
    return ConfigManager(env="test")


@pytest.fixture
def di_container():
    """
    Create dependency injection container for testing.
    
    Returns:
        DIContainer instance
    """
    from et_dflow.core.di_container import DIContainer
    return DIContainer()

