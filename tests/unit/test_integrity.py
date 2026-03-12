"""
Unit tests for data integrity checking.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.infrastructure.utils.integrity import DataIntegrityChecker
from pathlib import Path
import tempfile


class TestDataIntegrityChecker:
    """Test DataIntegrityChecker."""
    
    def test_checker_creation(self):
        """Test checker can be created."""
        checker = DataIntegrityChecker()
        assert checker.algorithm == "md5"
    
    def test_calculate_checksum_array(self):
        """Test checksum calculation for numpy array."""
        checker = DataIntegrityChecker()
        data = np.random.rand(10, 10)
        
        checksum = checker.calculate_checksum(data)
        assert isinstance(checksum, str)
        assert len(checksum) > 0
    
    def test_verify_checksum(self):
        """Test checksum verification."""
        checker = DataIntegrityChecker()
        data = np.random.rand(10, 10)
        
        checksum = checker.calculate_checksum(data)
        assert checker.verify_checksum(data, checksum) is True
        assert checker.verify_checksum(data, "invalid") is False
    
    def test_add_checksum_to_metadata(self, sample_tilt_series):
        """Test adding checksum to metadata."""
        checker = DataIntegrityChecker()
        signal = checker.add_checksum_to_metadata(sample_tilt_series)
        
        assert signal.metadata.get_item("checksum") is not None
        assert signal.metadata.get_item("checksum_algorithm") == "md5"


