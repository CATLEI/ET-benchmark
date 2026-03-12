"""
Format converter for converting between different data formats.

All converters convert to hyperspy format, which is the internal
unified format for ET-dflow.
"""

from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IDataLoader
from et_dflow.infrastructure.data.factory import get_data_loader_factory
from et_dflow.core.exceptions import DataError


class FormatConverter:
    """
    Converter for transforming data between different formats.
    
    All conversions target hyperspy format as the internal standard.
    """
    
    def __init__(self):
        """Initialize format converter."""
        self.factory = get_data_loader_factory()
    
    def convert_to_hyperspy(
        self,
        input_path: str,
        output_path: Optional[str] = None
    ) -> Signal:
        """
        Convert any supported format to hyperspy.
        
        Args:
            input_path: Path to input file
            output_path: Optional path to save converted file
        
        Returns:
            Hyperspy Signal object
        
        Raises:
            DataError: If conversion fails
        """
        # Load using appropriate loader
        loader = self.factory.create_loader(input_path)
        signal = loader.load(input_path)
        
        # Save if output path provided
        if output_path:
            signal.save(output_path)
        
        return signal
    
    def auto_load(self, file_path: str) -> Signal:
        """
        Automatically detect format and load as hyperspy.
        
        Args:
            file_path: Path to data file
        
        Returns:
            Hyperspy Signal object
        
        Raises:
            DataError: If file cannot be loaded
        """
        loader = self.factory.create_loader(file_path)
        return loader.load(file_path)


# Convenience functions for common conversions
def mrc_to_hyperspy(mrc_file: str, output_path: Optional[str] = None) -> Signal:
    """
    Convert MRC file to hyperspy format.
    
    Args:
        mrc_file: Path to MRC file
        output_path: Optional path to save hyperspy file
    
    Returns:
        Hyperspy Signal object
    """
    converter = FormatConverter()
    return converter.convert_to_hyperspy(mrc_file, output_path)


def tiff_to_hyperspy(tiff_file: str, output_path: Optional[str] = None) -> Signal:
    """
    Convert TIFF file to hyperspy format.
    
    Args:
        tiff_file: Path to TIFF file
        output_path: Optional path to save hyperspy file
    
    Returns:
        Hyperspy Signal object
    """
    converter = FormatConverter()
    return converter.convert_to_hyperspy(tiff_file, output_path)


def hdf5_to_hyperspy(hdf5_file: str, output_path: Optional[str] = None) -> Signal:
    """
    Convert HDF5 file to hyperspy format.
    
    Args:
        hdf5_file: Path to HDF5 file
        output_path: Optional path to save hyperspy file
    
    Returns:
        Hyperspy Signal object
    """
    converter = FormatConverter()
    return converter.convert_to_hyperspy(hdf5_file, output_path)

