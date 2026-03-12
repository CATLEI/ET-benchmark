"""
HDF5 data loader implementation.

Loads HDF5 format files and converts to hyperspy.
"""

from pathlib import Path
import h5py
import numpy as np
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IDataLoader
from et_dflow.core.exceptions import DataError


class HDF5Loader(IDataLoader):
    """
    Loader for HDF5 format files.
    
    Converts HDF5 data to hyperspy Signal format.
    Supports various HDF5 structures.
    """
    
    def load(self, path: str, dataset_path: str = "/data") -> Signal:
        """
        Load HDF5 file and convert to hyperspy Signal.
        
        Args:
            path: Path to .h5 or .hdf5 file
            dataset_path: Path to dataset within HDF5 file (default: '/data')
        
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
                f"Invalid HDF5 file: {path}",
                details={"file": path}
            )
        
        try:
            # Load HDF5 file
            with h5py.File(str(file_path), "r") as f:
                # Try to find dataset
                if dataset_path in f:
                    data = f[dataset_path][:]
                else:
                    # Try common dataset names
                    common_paths = ["/data", "/dataset", "/image", "/volume"]
                    data = None
                    for common_path in common_paths:
                        if common_path in f:
                            data = f[common_path][:]
                            break
                    
                    if data is None:
                        # Use first dataset
                        keys = list(f.keys())
                        if len(keys) == 0:
                            raise DataError(
                                f"No datasets found in HDF5 file: {path}",
                                details={"file": path}
                            )
                        data = f[keys[0]][:]
            
            # Determine signal type based on dimensions
            if data.ndim == 2:
                signal = hs.signals.Signal2D(data)
            elif data.ndim == 3:
                signal = hs.signals.Signal2D(data)  # Tilt series
            else:
                raise DataError(
                    f"Unsupported HDF5 data dimensions: {data.ndim}",
                    details={"file": path, "dimensions": data.ndim}
                )
            
            # Add metadata
            signal.metadata.set_item("original_format", "hdf5")
            signal.metadata.set_item("original_file", str(file_path))
            signal.metadata.set_item("hdf5_dataset_path", dataset_path)
            
            return signal
        except Exception as e:
            raise DataError(
                f"Error loading HDF5 file {path}: {e}",
                details={"file": path, "error": str(e)}
            ) from e
    
    def validate(self, path: str) -> bool:
        """
        Validate if file is a valid HDF5 file.
        
        Args:
            path: Path to file
        
        Returns:
            True if file is valid HDF5 format
        """
        file_path = Path(path)
        
        # Check extension
        if file_path.suffix.lower() not in [".h5", ".hdf5"]:
            return False
        
        # Check if file exists
        if not file_path.exists():
            return False
        
        # Try to open and validate
        try:
            with h5py.File(str(file_path), "r") as f:
                return len(f.keys()) > 0
        except Exception:
            return False

