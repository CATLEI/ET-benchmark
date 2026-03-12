"""
Interactive result viewer using Plotly Dash.

Provides interactive 3D visualization and result exploration.
"""

import json
from typing import Dict, Any, List, Optional
from pathlib import Path
import numpy as np
try:
    import plotly.graph_objects as go
    import plotly.express as px
    from dash import Dash, html, dcc, Input, Output
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False


class InteractiveResultViewer:
    """
    Interactive result viewer.
    
    Creates interactive HTML visualizations using Plotly Dash.
    """
    
    def __init__(self):
        """Initialize interactive viewer."""
        if not PLOTLY_AVAILABLE:
            raise ImportError(
                "Plotly and Dash are required for interactive viewer. "
                "Install with: pip install plotly dash"
            )
    
    def create_viewer(
        self,
        results: Dict[str, Any],
        output_path: str = "interactive_viewer.html"
    ) -> str:
        """
        Create interactive HTML viewer.
        
        Args:
            results: Dictionary containing evaluation results
            output_path: Path to save HTML file
        
        Returns:
            Path to generated HTML file
        """
        # Create Dash app
        app = Dash(__name__)
        
        # Create layout
        app.layout = self._create_layout(results)
        
        # Register callbacks
        self._register_callbacks(app, results)
        
        # Generate HTML
        app.run_server(debug=False, port=8050)
        
        # For static HTML export, use plotly
        fig = self._create_3d_plot(results)
        fig.write_html(output_path)
        
        return output_path
    
    def _create_layout(self, results: Dict[str, Any]) -> html.Div:
        """Create Dash layout."""
        return html.Div([
            html.H1("ET-dflow Benchmark Results", style={'textAlign': 'center'}),
            html.Div(id='3d-viewer'),
            html.Div(id='metrics-display'),
        ])
    
    def _register_callbacks(self, app: Dash, results: Dict[str, Any]):
        """Register Dash callbacks."""
        @app.callback(
            Output('3d-viewer', 'children'),
            Input('3d-viewer', 'id')
        )
        def update_viewer(_):
            fig = self._create_3d_plot(results)
            return dcc.Graph(figure=fig)
    
    def _create_3d_plot(self, results: Dict[str, Any]) -> go.Figure:
        """Create 3D plotly figure."""
        fig = go.Figure()
        
        # Add 3D scatter plot (placeholder)
        # In full implementation, would plot actual reconstruction data
        
        x = np.random.rand(100)
        y = np.random.rand(100)
        z = np.random.rand(100)
        
        fig.add_trace(go.Scatter3d(
            x=x,
            y=y,
            z=z,
            mode='markers',
            marker=dict(
                size=5,
                color=z,
                colorscale='Viridis',
            )
        ))
        
        fig.update_layout(
            title="3D Reconstruction Viewer",
            scene=dict(
                xaxis_title="X",
                yaxis_title="Y",
                zaxis_title="Z",
            )
        )
        
        return fig
    
    def generate_html(
        self,
        results: Dict[str, Any],
        output_path: str = "results_viewer.html"
    ) -> str:
        """
        Generate static HTML viewer.
        
        Args:
            results: Evaluation results
            output_path: Output HTML file path
        
        Returns:
            Path to HTML file
        """
        if not PLOTLY_AVAILABLE:
            # Fallback: create simple HTML
            html_content = self._create_simple_html(results)
            with open(output_path, 'w') as f:
                f.write(html_content)
            return output_path
        
        # Create interactive plotly figure
        fig = self._create_3d_plot(results)
        fig.write_html(output_path)
        
        return output_path
    
    def _create_simple_html(self, results: Dict[str, Any]) -> str:
        """Create simple HTML without Plotly."""
        html_content = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>ET-dflow Benchmark Results</title>
        </head>
        <body>
            <h1>ET-dflow Benchmark Results</h1>
            <div id="results">
                <h2>Results Summary</h2>
                <pre>{}</pre>
            </div>
        </body>
        </html>
        """.format(json.dumps(results, indent=2))
        
        return html_content

