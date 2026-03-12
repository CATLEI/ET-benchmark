"""
Unit tests for data loaders.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from pathlib import Path
import tempfile
import shutil
from et_dflow.infrastructure.data.factory import DataLoaderFactory
from et_dflow.infrastructure.data.loaders.hyperspy_loader import HyperspyLoader
from et_dflow.infrastructure.data.loaders.mrc_loader import MRCLoader
from et_dflow.core.exceptions import DataError


class TestDataLoaderFactory:
    """Test DataLoaderFactory."""
    
    def test_factory_creation(self):
        """Test factory can be created."""
        factory = DataLoaderFactory()
        assert factory is not None
    
    def test_register_loader(self):
        """Test loader registration."""
        factory = DataLoaderFactory()
        factory.register_loader("test_format", HyperspyLoader)
        assert factory._loaders["test_format"] == HyperspyLoader
    
    def test_detect_format(self):
        """Test format detection."""
        factory = DataLoaderFactory()
        
        assert factory._detect_format("test.hspy") == "hspy"
        assert factory._detect_format("test.mrc") == "mrc"
        assert factory._detect_format("test.tiff") == "tiff"
        assert factory._detect_format("test.h5") == "hdf5"
    
    def test_create_loader(self):
        """Test loader creation."""
        factory = DataLoaderFactory()
        loader = factory.create_loader("test.hspy")
        assert isinstance(loader, HyperspyLoader)


class TestHyperspyLoader:
    """Test HyperspyLoader."""
    
    def test_validate_hyperspy_file(self, temp_dir):
        """Test validation of hyperspy file."""
        loader = HyperspyLoader()
        
        # Create a test hyperspy file
        signal = hs.signals.Signal2D(np.random.rand(10, 10))
        test_file = temp_dir / "test.hspy"
        signal.save(str(test_file))
        
        assert loader.validate(str(test_file)) is True
        assert loader.validate("nonexistent.hspy") is False
        assert loader.validate("test.txt") is False
    
    def test_load_hyperspy_file(self, temp_dir):
        """Test loading hyperspy file."""
        loader = HyperspyLoader()
        
        # Create a test hyperspy file
        original_data = np.random.rand(10, 10)
        signal = hs.signals.Signal2D(original_data)
        test_file = temp_dir / "test.hspy"
        signal.save(str(test_file))
        
        # Load it
        loaded_signal = loader.load(str(test_file))
        assert loaded_signal is not None
        np.testing.assert_array_almost_equal(
            loaded_signal.data, original_data
        )
    
    def test_load_nonexistent_file(self):
        """Test loading nonexistent file raises error."""
        loader = HyperspyLoader()
        
        with pytest.raises(DataError):
            loader.load("nonexistent.hspy")

