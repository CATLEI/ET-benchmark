"""
Unit tests for visualization.
"""

import pytest
import numpy as np
from et_dflow.infrastructure.visualization.scientific_plotter import ScientificPlotter


class TestScientificPlotter:
    """Test ScientificPlotter."""
    
    def test_plotter_creation(self):
        """Test plotter can be created."""
        plotter = ScientificPlotter()
        assert plotter is not None
    
    def test_plot_fsc_curve(self):
        """Test FSC curve plotting."""
        plotter = ScientificPlotter()
        
        spatial_freqs = np.linspace(0.1, 0.7, 50)
        fsc_values = np.exp(-spatial_freqs * 2)  # Decaying FSC
        
        fig = plotter.plot_fsc_curve(
            spatial_freqs,
            fsc_values,
            threshold=0.143
        )
        
        assert fig is not None
    
    def test_plot_3d_fourier_space(self):
        """Test 3D Fourier space plotting."""
        plotter = ScientificPlotter()
        
        # Create test Fourier data
        fourier_data = np.random.rand(32, 32, 32) + 1j * np.random.rand(32, 32, 32)
        fourier_data = np.abs(fourier_data)
        
        fig = plotter.plot_3d_fourier_space(fourier_data)
        
        assert fig is not None
    
    def test_plot_3d_isosurface(self):
        """Test 3D isosurface plotting."""
        plotter = ScientificPlotter()
        
        # Create test volume
        volume = np.random.rand(32, 32, 32)
        
        fig = plotter.plot_3d_isosurface(volume, isovalue=0.5)
        
        assert fig is not None
    
    def test_plot_comparison(self):
        """Test comparison plotting."""
        plotter = ScientificPlotter()
        
        data_dict = {
            "Algorithm 1": np.random.rand(32, 32, 32),
            "Algorithm 2": np.random.rand(32, 32, 32),
        }
        
        fig = plotter.plot_comparison(data_dict)
        
        assert fig is not None

