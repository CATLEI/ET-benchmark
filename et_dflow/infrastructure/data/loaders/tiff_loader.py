"""
TIFF data loader implementation.

Loads TIFF format files and converts to hyperspy.
"""

from pathlib import Path
import numpy as np
import tifffile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IDataLoader
from et_dflow.core.exceptions import DataError


class TIFFLoader(IDataLoader):
    """
    Loader for TIFF format files.
    
    Supports both single TIFF files and TIFF stacks.
    Converts to hyperspy Signal format.
    """
    
    def load(self, path: str) -> Signal:
        """
        Load TIFF file and convert to hyperspy Signal.
        
        Args:
            path: Path to .tif or .tiff file
        
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
                f"Invalid TIFF file: {path}",
                details={"file": path}
            )
        
        try:
            # Load TIFF file
            data = tifffile.imread(str(file_path))
            
            # Determine signal type based on dimensions
            if data.ndim == 2:
                signal = hs.signals.Signal2D(data)
            elif data.ndim == 3:
                # Assume tilt series: (n_tilts, height, width)
                signal = hs.signals.Signal2D(data)
            else:
                raise DataError(
                    f"Unsupported TIFF data dimensions: {data.ndim}",
                    details={"file": path, "dimensions": data.ndim}
                )
            
            # Add metadata
            signal.metadata.set_item("original_format", "tiff")
            signal.metadata.set_item("original_file", str(file_path))
            
            return signal
        except Exception as e:
            raise DataError(
                f"Error loading TIFF file {path}: {e}",
                details={"file": path, "error": str(e)}
            ) from e
    
    def validate(self, path: str) -> bool:
        """
        Validate if file is a valid TIFF file.
        
        Args:
            path: Path to file
        
        Returns:
            True if file is valid TIFF format
        """
        file_path = Path(path)
        
        # Check extension
        if file_path.suffix.lower() not in [".tif", ".tiff"]:
            return False
        
        # Check if file exists
        if not file_path.exists():
            return False
        
        # Try to read and validate
        try:
            tifffile.imread(str(file_path))
            return True
        except Exception:
            return False

