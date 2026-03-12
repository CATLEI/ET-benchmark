"""
MRC data loader implementation.

Loads MRC format files and converts to hyperspy.
"""

from pathlib import Path
import numpy as np
try:
    import mrcfile
except ImportError:
    mrcfile = None  # Optional dependency
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IDataLoader
from et_dflow.core.exceptions import DataError


class MRCLoader(IDataLoader):
    """
    Loader for MRC format files.
    
    Converts MRC data to hyperspy Signal format.
    """
    
    def load(self, path: str) -> Signal:
        """
        Load MRC file and convert to hyperspy Signal.
        
        Args:
            path: Path to .mrc file
        
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
                f"Invalid MRC file: {path}",
                details={"file": path}
            )
        
        if mrcfile is None:
            raise DataError(
                "mrcfile package not installed. Install with: pip install mrcfile",
                details={"file": path}
            )
        try:
            # Load MRC file
            with mrcfile.open(str(file_path), mode="r") as mrc:
                data = mrc.data
                pixel_size = mrc.voxel_size.x  # Assume isotropic voxels
            
            # Determine signal type based on dimensions
            if data.ndim == 2:
                signal = hs.signals.Signal2D(data)
            elif data.ndim == 3:
                # Assume 3D volume
                signal = hs.signals.Signal1D(data)
            else:
                raise DataError(
                    f"Unsupported MRC data dimensions: {data.ndim}",
                    details={"file": path, "dimensions": data.ndim}
                )
            
            # Set pixel size in metadata
            if pixel_size:
                signal.axes_manager[0].scale = pixel_size
                signal.axes_manager[0].units = "nm"
                if len(signal.axes_manager) > 1:
                    signal.axes_manager[1].scale = pixel_size
                    signal.axes_manager[1].units = "nm"
                if len(signal.axes_manager) > 2:
                    signal.axes_manager[2].scale = pixel_size
                    signal.axes_manager[2].units = "nm"
            
            # Add metadata
            signal.metadata.set_item("original_format", "mrc")
            signal.metadata.set_item("original_file", str(file_path))
            
            return signal
        except Exception as e:
            raise DataError(
                f"Error loading MRC file {path}: {e}",
                details={"file": path, "error": str(e)}
            ) from e
    
    def validate(self, path: str) -> bool:
        """
        Validate if file is a valid MRC file.
        
        Args:
            path: Path to file
        
        Returns:
            True if file is valid MRC format
        """
        file_path = Path(path)
        
        # Check extension
        if file_path.suffix.lower() not in [".mrc", ".rec"]:
            return False
        
        # Check if file exists
        if not file_path.exists():
            return False
        
        # Try to open and validate
        if mrcfile is None:
            return False
        try:
            with mrcfile.open(str(file_path), mode="r", permissive=True) as mrc:
                return mrc.data is not None
        except Exception:
            return False

