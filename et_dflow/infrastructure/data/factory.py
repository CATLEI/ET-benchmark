"""
Data loader factory implementation.

Implements factory pattern for creating appropriate data loaders
based on file format.
"""

from pathlib import Path
from typing import Dict, Type
from et_dflow.core.interfaces import IDataLoader
from et_dflow.core.exceptions import DataError


class DataLoaderFactory:
    """
    Factory for creating data loaders.
    
    Automatically detects file format and creates appropriate loader.
    Implements factory pattern for loose coupling.
    
    Example:
        factory = DataLoaderFactory()
        loader = factory.create_loader("data.mrc")
        signal = loader.load("data.mrc")
    """
    
    def __init__(self):
        """Initialize data loader factory."""
        self._loaders: Dict[str, Type[IDataLoader]] = {}
        self._register_default_loaders()
    
    def _register_default_loaders(self):
        """Register default loaders."""
        from et_dflow.infrastructure.data.loaders.hyperspy_loader import HyperspyLoader
        from et_dflow.infrastructure.data.loaders.mrc_loader import MRCLoader
        from et_dflow.infrastructure.data.loaders.tiff_loader import TIFFLoader
        from et_dflow.infrastructure.data.loaders.hdf5_loader import HDF5Loader
        
        self.register_loader("hspy", HyperspyLoader)
        self.register_loader("mrc", MRCLoader)
        self.register_loader("rec", MRCLoader)  # MRC variant
        self.register_loader("tiff", TIFFLoader)
        self.register_loader("tif", TIFFLoader)
        self.register_loader("hdf5", HDF5Loader)
        self.register_loader("h5", HDF5Loader)
    
    def register_loader(self, format_type: str, loader_class: Type[IDataLoader]):
        """
        Register a data loader for a specific format.
        
        Args:
            format_type: File format identifier (e.g., 'mrc', 'tiff', 'hspy')
            loader_class: Loader class implementing IDataLoader
        """
        self._loaders[format_type.lower()] = loader_class
    
    def create_loader(self, file_path: str) -> IDataLoader:
        """
        Create appropriate data loader for file.
        
        Args:
            file_path: Path to data file
        
        Returns:
            Data loader instance
        
        Raises:
            DataError: If format is not supported
        
        Example:
            loader = factory.create_loader("data.mrc")
        """
        format_type = self._detect_format(file_path)
        
        loader_class = self._loaders.get(format_type)
        if not loader_class:
            raise DataError(
                f"Unsupported file format: {format_type}",
                details={"file": file_path, "format": format_type}
            )
        
        return loader_class()
    
    @staticmethod
    def _detect_format(file_path: str) -> str:
        """
        Detect file format from extension.
        
        Args:
            file_path: Path to file
        
        Returns:
            Format identifier (e.g., 'mrc', 'tiff', 'hspy')
        """
        ext = Path(file_path).suffix.lower().lstrip(".")
        
        # Format mapping
        format_map = {
            "hspy": "hspy",
            "mrc": "mrc",
            "rec": "mrc",  # MRC variant
            "tif": "tiff",
            "tiff": "tiff",
            "h5": "hdf5",
            "hdf5": "hdf5",
            "dm3": "dm3",
            "dm4": "dm4",
        }
        
        return format_map.get(ext, ext)


# Global factory instance
_factory: DataLoaderFactory = None


def get_data_loader_factory() -> DataLoaderFactory:
    """
    Get global data loader factory.
    
    Returns:
        Global DataLoaderFactory instance
    """
    global _factory
    if _factory is None:
        _factory = DataLoaderFactory()
    return _factory

