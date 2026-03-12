"""
Hyperspy data loader implementation.

Loads data in hyperspy format (.hspy files).
"""

from pathlib import Path
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IDataLoader
from et_dflow.core.exceptions import DataError


class HyperspyLoader(IDataLoader):
    """
    Loader for hyperspy format (.hspy files).
    
    Hyperspy is the internal unified format for ET-dflow.
    """
    
    def load(self, path: str) -> Signal:
        """
        Load hyperspy signal from file.
        
        Args:
            path: Path to .hspy file
        
        Returns:
            Hyperspy Signal object
        
        Raises:
            DataError: If file cannot be loaded
        """
        file_path = Path(path)
        
        if not file_path.exists():
            raise DataError(
                f"File not found: {path}",
                details={"file": path}
            )
        
        if not self.validate(path):
            raise DataError(
                f"Invalid hyperspy file: {path}",
                details={"file": path}
            )
        
        try:
            signal = hs.load(str(file_path))
            
            # Handle list of signals (take first)
            if isinstance(signal, list):
                if len(signal) == 0:
                    raise DataError(
                        f"Empty hyperspy file: {path}",
                        details={"file": path}
                    )
                signal = signal[0]
            
            return signal
        except Exception as e:
            raise DataError(
                f"Error loading hyperspy file {path}: {e}",
                details={"file": path, "error": str(e)}
            ) from e
    
    def validate(self, path: str) -> bool:
        """
        Validate if file is a valid hyperspy file.
        
        Args:
            path: Path to file
        
        Returns:
            True if file is valid hyperspy format
        """
        file_path = Path(path)
        
        # Check extension
        if file_path.suffix.lower() != ".hspy":
            return False
        
        # Check if file exists
        if not file_path.exists():
            return False
        
        # Try to load and validate
        try:
            signal = hs.load(str(file_path))
            return signal is not None
        except Exception:
            return False

