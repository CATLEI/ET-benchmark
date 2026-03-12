"""
Data integrity checking.

Implements checksum calculation and verification for data integrity.
"""

import hashlib
from typing import Dict, Any, Optional
from pathlib import Path
import hyperspy.api as hs
from et_dflow.core.exceptions import DataError


class DataIntegrityChecker:
    """
    Check data integrity using checksums.
    
    Calculates and verifies checksums for data files and metadata.
    """
    
    def __init__(self, algorithm: str = "md5"):
        """
        Initialize integrity checker.
        
        Args:
            algorithm: Checksum algorithm ('md5', 'sha256')
        """
        self.algorithm = algorithm
        self.hash_func = getattr(hashlib, algorithm)
    
    def calculate_checksum(self, data: Any) -> str:
        """
        Calculate checksum for data.
        
        Args:
            data: Data to checksum (file path, numpy array, or bytes)
        
        Returns:
            Hexadecimal checksum string
        """
        if isinstance(data, (str, Path)):
            # File path
            return self._calculate_file_checksum(data)
        elif hasattr(data, '__array__'):
            # NumPy array or similar
            import numpy as np
            return self._calculate_array_checksum(np.asarray(data))
        else:
            # Bytes or other
            return self._calculate_bytes_checksum(data)
    
    def _calculate_file_checksum(self, file_path: str) -> str:
        """Calculate checksum for file."""
        hash_obj = self.hash_func()
        
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_obj.update(chunk)
        
        return hash_obj.hexdigest()
    
    def _calculate_array_checksum(self, array) -> str:
        """Calculate checksum for numpy array."""
        import numpy as np
        # Convert to bytes
        array_bytes = array.tobytes()
        return self._calculate_bytes_checksum(array_bytes)
    
    def _calculate_bytes_checksum(self, data: bytes) -> str:
        """Calculate checksum for bytes."""
        hash_obj = self.hash_func()
        hash_obj.update(data)
        return hash_obj.hexdigest()
    
    def verify_checksum(
        self,
        data: Any,
        expected_checksum: str
    ) -> bool:
        """
        Verify data checksum.
        
        Args:
            data: Data to verify
            expected_checksum: Expected checksum value
        
        Returns:
            True if checksum matches, False otherwise
        """
        calculated = self.calculate_checksum(data)
        return calculated.lower() == expected_checksum.lower()
    
    def add_checksum_to_metadata(
        self,
        signal: hs.signals.Signal2D,
        checksum: Optional[str] = None
    ) -> hs.signals.Signal2D:
        """
        Add checksum to signal metadata.
        
        Args:
            signal: Hyperspy signal
            checksum: Checksum value (calculated if None)
        
        Returns:
            Signal with checksum in metadata
        """
        if checksum is None:
            checksum = self.calculate_checksum(signal.data)
        
        signal.metadata.set_item("checksum", checksum)
        signal.metadata.set_item("checksum_algorithm", self.algorithm)
        
        return signal


