"""
Scientific plotting utilities.

Provides publication-quality plotting with colorblind-friendly palettes.
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
from typing import Dict, Any, Optional, Tuple, List
from pathlib import Path


class ScientificPlotter:
    """
    Scientific plotter with publication-quality defaults.
    
    Features:
    - Colorblind-friendly palettes
    - Proper font sizes and styles
    - High-resolution output
    - Consistent styling
    """
    
    # Colorblind-friendly color palettes
    COLORBLIND_PALETTE = {
        "blue": "#0072B2",
        "orange": "#E69F00",
        "green": "#009E73",
        "red": "#D55E00",
        "purple": "#CC79A7",
        "yellow": "#F0E442",
        "cyan": "#56B4E9",
        "pink": "#E69F00",
    }
    
    def __init__(self, style: str = "seaborn-v0_8-whitegrid"):
        """
        Initialize scientific plotter.
        
        Args:
            style: Matplotlib style name
        """
        plt.style.use(style)
        self.style = style
    
    def plot_fsc_curve(
        self,
        spatial_frequencies: np.ndarray,
        fsc_values: np.ndarray,
        threshold: float = 0.143,
        output_path: Optional[str] = None,
        **kwargs
    ) -> plt.Figure:
        """
        Plot FSC curve.
        
        Args:
            spatial_frequencies: Spatial frequencies (1/nm)
            fsc_values: FSC values
            threshold: FSC threshold line
            output_path: Path to save figure
            **kwargs: Additional plot arguments
        
        Returns:
            Matplotlib figure
        """
        fig, ax = plt.subplots(figsize=(8, 6))
        
        # Plot FSC curve
        ax.plot(
            spatial_frequencies,
            fsc_values,
            color=self.COLORBLIND_PALETTE["blue"],
            linewidth=2,
            label="FSC"
        )
        
        # Plot threshold line
        ax.axhline(
            y=threshold,
            color=self.COLORBLIND_PALETTE["red"],
            linestyle="--",
            linewidth=2,
            label=f"Threshold ({threshold})"
        )
        
        # Formatting
        ax.set_xlabel("Spatial Frequency (1/nm)", fontsize=12)
        ax.set_ylabel("FSC", fontsize=12)
        ax.set_title("Fourier Shell Correlation", fontsize=14, fontweight="bold")
        ax.legend(fontsize=10)
        ax.grid(True, alpha=0.3)
        
        plt.tight_layout()
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches="tight")
        
        return fig
    
    def plot_3d_fourier_space(
        self,
        fourier_data: np.ndarray,
        missing_wedge_mask: Optional[np.ndarray] = None,
        output_path: Optional[str] = None,
        **kwargs
    ) -> plt.Figure:
        """
        Plot 3D Fourier space visualization.
        
        Args:
            fourier_data: 3D Fourier space data
            missing_wedge_mask: Missing wedge mask (optional)
            output_path: Path to save figure
            **kwargs: Additional plot arguments
        
        Returns:
            Matplotlib figure
        """
        # Use 3D projection
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Create coordinate arrays
        shape = fourier_data.shape
        coords = np.meshgrid(
            *[np.arange(s) - s // 2 for s in shape],
            indexing='ij'
        )
        
        # Sample points for visualization (reduce for performance)
        step = max(1, min(shape) // 20)
        x = coords[0][::step, ::step, ::step].flatten()
        y = coords[1][::step, ::step, ::step].flatten()
        z = coords[2][::step, ::step, ::step].flatten()
        values = np.abs(fourier_data[::step, ::step, ::step]).flatten()
        
        # Plot scatter
        scatter = ax.scatter(
            x, y, z,
            c=values,
            cmap='viridis',
            alpha=0.6,
            s=10
        )
        
        # Formatting
        ax.set_xlabel("kx", fontsize=12)
        ax.set_ylabel("ky", fontsize=12)
        ax.set_zlabel("kz", fontsize=12)
        ax.set_title("3D Fourier Space", fontsize=14, fontweight="bold")
        
        plt.colorbar(scatter, ax=ax, label="Magnitude")
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches="tight")
        
        return fig
    
    def plot_3d_isosurface(
        self,
        volume: np.ndarray,
        isovalue: Optional[float] = None,
        output_path: Optional[str] = None,
        **kwargs
    ) -> plt.Figure:
        """
        Plot 3D isosurface visualization.
        
        Args:
            volume: 3D volume data
            isovalue: Isosurface value (auto if None)
            output_path: Path to save figure
            **kwargs: Additional plot arguments
        
        Returns:
            Matplotlib figure
        """
        from mpl_toolkits.mplot3d import Axes3D
        
        fig = plt.figure(figsize=(10, 8))
        ax = fig.add_subplot(111, projection='3d')
        
        # Calculate isovalue if not provided
        if isovalue is None:
            isovalue = np.percentile(volume, 75)
        
        # Sample volume for visualization
        step = max(1, min(volume.shape) // 30)
        sampled = volume[::step, ::step, ::step]
        
        # Create isosurface (simplified - would use proper marching cubes)
        # For now, plot threshold points
        coords = np.where(sampled >= isovalue)
        
        if len(coords[0]) > 0:
            ax.scatter(
                coords[0] * step,
                coords[1] * step,
                coords[2] * step,
                c=sampled[coords],
                cmap='viridis',
                alpha=0.6,
                s=5
            )
        
        # Formatting
        ax.set_xlabel("X", fontsize=12)
        ax.set_ylabel("Y", fontsize=12)
        ax.set_zlabel("Z", fontsize=12)
        ax.set_title(f"3D Isosurface (value={isovalue:.2f})", fontsize=14, fontweight="bold")
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches="tight")
        
        return fig
    
    def plot_comparison(
        self,
        data_dict: Dict[str, np.ndarray],
        output_path: Optional[str] = None,
        **kwargs
    ) -> plt.Figure:
        """
        Plot comparison of multiple datasets.
        
        Args:
            data_dict: Dictionary mapping labels to data arrays
            output_path: Path to save figure
            **kwargs: Additional plot arguments
        
        Returns:
            Matplotlib figure
        """
        n_plots = len(data_dict)
        fig, axes = plt.subplots(1, n_plots, figsize=(5 * n_plots, 5))
        
        if n_plots == 1:
            axes = [axes]
        
        colors = list(self.COLORBLIND_PALETTE.values())
        
        for idx, (label, data) in enumerate(data_dict.items()):
            ax = axes[idx]
            
            # Plot 2D slice (middle slice)
            if len(data.shape) == 3:
                slice_idx = data.shape[0] // 2
                im = ax.imshow(data[slice_idx], cmap='viridis')
            else:
                im = ax.imshow(data, cmap='viridis')
            
            ax.set_title(label, fontsize=12, fontweight="bold")
            ax.axis('off')
            plt.colorbar(im, ax=ax)
        
        plt.tight_layout()
        
        if output_path:
            fig.savefig(output_path, dpi=300, bbox_inches="tight")
        
        return fig

