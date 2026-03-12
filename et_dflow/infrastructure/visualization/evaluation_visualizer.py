"""
Evaluation result visualization.

Generates publication-quality visualizations for evaluation results.
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, Any, Optional, List
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import seaborn as sns

# Set style for publication-quality plots
plt.style.use('seaborn-v0_8-paper')
sns.set_palette("colorblind")


class EvaluationVisualizer:
    """
    Visualize evaluation results.
    
    Generates publication-quality plots for evaluation metrics.
    """
    
    def __init__(self, output_dir: str):
        """
        Initialize visualizer.
        
        Args:
            output_dir: Output directory for visualization files
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
    
    def visualize_metrics(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        output_name: str = "metrics_comparison"
    ) -> str:
        """
        Visualize evaluation metrics comparison.
        
        Args:
            evaluation_results: Dictionary mapping algorithm names to their metrics
                Example: {
                    "wbp": {"psnr": 28.5, "ssim": 0.85, "mse": 0.001},
                    "sirt": {"psnr": 30.2, "ssim": 0.88, "mse": 0.0008}
                }
            output_name: Base name for output file
        
        Returns:
            Path to saved visualization file
        """
        if not evaluation_results:
            return None
        
        # Extract metrics
        algorithms = list(evaluation_results.keys())
        metrics = set()
        for alg_metrics in evaluation_results.values():
            if isinstance(alg_metrics, dict) and "metrics" in alg_metrics:
                metrics.update(alg_metrics["metrics"].keys())
            elif isinstance(alg_metrics, dict):
                metrics.update(alg_metrics.keys())
        
        metrics = sorted(list(metrics))
        
        if not metrics:
            return None
        
        # Create figure with subplots
        n_metrics = len(metrics)
        n_cols = min(3, n_metrics)
        n_rows = (n_metrics + n_cols - 1) // n_cols
        
        fig, axes = plt.subplots(n_rows, n_cols, figsize=(5 * n_cols, 4 * n_rows))
        if n_metrics == 1:
            axes = [axes]
        else:
            axes = axes.flatten() if n_rows > 1 else axes
        
        # Plot each metric
        for idx, metric in enumerate(metrics):
            ax = axes[idx]
            
            # Extract values for this metric
            values = []
            labels = []
            for alg_name in algorithms:
                alg_data = evaluation_results[alg_name]
                if isinstance(alg_data, dict) and "metrics" in alg_data:
                    metric_value = alg_data["metrics"].get(metric)
                elif isinstance(alg_data, dict):
                    metric_value = alg_data.get(metric)
                else:
                    continue
                
                if metric_value is not None:
                    values.append(metric_value)
                    labels.append(alg_name)
            
            if not values:
                ax.text(0.5, 0.5, f"No data for {metric}", 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title(metric.upper(), fontsize=12, fontweight='bold')
                continue
            
            # Create bar plot
            bars = ax.bar(labels, values, alpha=0.7, edgecolor='black', linewidth=1.5)
            
            # Color bars based on metric type
            if metric in ['psnr', 'ssim']:
                # Higher is better - use green gradient
                colors = plt.cm.Greens(np.linspace(0.4, 0.8, len(bars)))
            elif metric in ['mse']:
                # Lower is better - use red gradient (inverted)
                colors = plt.cm.Reds(np.linspace(0.8, 0.4, len(bars)))
            else:
                colors = plt.cm.Blues(np.linspace(0.4, 0.8, len(bars)))
            
            for bar, color in zip(bars, colors):
                bar.set_facecolor(color)
            
            # Add value labels on bars
            for bar in bars:
                height = bar.get_height()
                ax.text(bar.get_x() + bar.get_width()/2., height,
                       f'{height:.3f}',
                       ha='center', va='bottom', fontsize=9)
            
            ax.set_title(metric.upper(), fontsize=12, fontweight='bold')
            ax.set_ylabel('Value', fontsize=10)
            ax.set_xlabel('Algorithm', fontsize=10)
            ax.grid(True, alpha=0.3, linestyle='--')
            ax.tick_params(axis='x', rotation=45)
        
        # Hide unused subplots
        for idx in range(n_metrics, len(axes)):
            axes[idx].axis('off')
        
        plt.tight_layout()
        
        # Save figure
        output_path = self.output_dir / f"{output_name}.png"
        fig.savefig(output_path, dpi=300, bbox_inches='tight')
        plt.close(fig)
        
        return str(output_path)
    
    def visualize_metrics_radar(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        output_name: str = "metrics_radar"
    ) -> str:
        """
        Create radar chart for metrics comparison.
        
        Args:
            evaluation_results: Dictionary mapping algorithm names to their metrics
            output_name: Base name for output file
        
        Returns:
            Path to saved visualization file
        """
        try:
            from math import pi
            
            if not evaluation_results:
                return None
            
            # Extract metrics
            algorithms = list(evaluation_results.keys())
            metrics = set()
            for alg_metrics in evaluation_results.values():
                if isinstance(alg_metrics, dict) and "metrics" in alg_metrics:
                    metrics.update(alg_metrics["metrics"].keys())
                elif isinstance(alg_metrics, dict):
                    metrics.update(alg_metrics.keys())
            
            metrics = sorted(list(metrics))
            
            if not metrics:
                return None
            
            # Normalize metrics (0-1 scale)
            # For metrics where higher is better (psnr, ssim), normalize directly
            # For metrics where lower is better (mse), invert normalization
            normalized_data = {}
            raw_data = {}
            
            for alg_name in algorithms:
                alg_data = evaluation_results[alg_name]
                if isinstance(alg_data, dict) and "metrics" in alg_data:
                    raw_data[alg_name] = alg_data["metrics"]
                elif isinstance(alg_data, dict):
                    raw_data[alg_name] = alg_data
                else:
                    continue
            
            # Normalize each metric
            for metric in metrics:
                values = [raw_data[alg].get(metric) for alg in algorithms 
                         if raw_data[alg].get(metric) is not None]
                if not values:
                    continue
                
                min_val = min(values)
                max_val = max(values)
                range_val = max_val - min_val
                
                if range_val == 0:
                    # All values are the same
                    for alg_name in algorithms:
                        if alg_name not in normalized_data:
                            normalized_data[alg_name] = {}
                        normalized_data[alg_name][metric] = 0.5
                else:
                    for alg_name in algorithms:
                        if alg_name not in normalized_data:
                            normalized_data[alg_name] = {}
                        val = raw_data[alg_name].get(metric)
                        if val is not None:
                            if metric in ['mse']:
                                # Lower is better - invert
                                normalized_data[alg_name][metric] = 1 - (val - min_val) / range_val
                            else:
                                # Higher is better
                                normalized_data[alg_name][metric] = (val - min_val) / range_val
            
            # Create radar chart
            angles = [n / float(len(metrics)) * 2 * pi for n in range(len(metrics))]
            angles += angles[:1]  # Complete the circle
            
            fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(projection='polar'))
            
            # Plot each algorithm
            colors = plt.cm.Set2(np.linspace(0, 1, len(algorithms)))
            for idx, alg_name in enumerate(algorithms):
                if alg_name not in normalized_data:
                    continue
                
                values = [normalized_data[alg_name].get(metric, 0) for metric in metrics]
                values += values[:1]  # Complete the circle
                
                ax.plot(angles, values, 'o-', linewidth=2, label=alg_name, color=colors[idx])
                ax.fill(angles, values, alpha=0.25, color=colors[idx])
            
            # Set labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels([m.upper() for m in metrics], fontsize=10)
            ax.set_ylim(0, 1)
            ax.set_yticks([0.2, 0.4, 0.6, 0.8, 1.0])
            ax.set_yticklabels(['0.2', '0.4', '0.6', '0.8', '1.0'], fontsize=8)
            ax.grid(True, alpha=0.3)
            
            plt.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=10)
            plt.title('Algorithm Performance Comparison', fontsize=14, fontweight='bold', pad=20)
            
            # Save figure
            output_path = self.output_dir / f"{output_name}.png"
            fig.savefig(output_path, dpi=300, bbox_inches='tight')
            plt.close(fig)
            
            return str(output_path)
            
        except Exception as e:
            # If radar chart fails, fall back to bar chart
            print(f"Radar chart creation failed: {e}, using bar chart instead")
            return self.visualize_metrics(evaluation_results, output_name)
    
    def create_summary_report(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        output_name: str = "evaluation_report"
    ) -> str:
        """
        Create comprehensive evaluation report with visualizations.
        
        Args:
            evaluation_results: Dictionary mapping algorithm names to their metrics
            output_name: Base name for output file
        
        Returns:
            Path to saved report file
        """
        # Create visualizations
        bar_chart_path = self.visualize_metrics(evaluation_results, f"{output_name}_bar")
        radar_chart_path = self.visualize_metrics_radar(evaluation_results, f"{output_name}_radar")
        
        # Create HTML report
        html_content = self._generate_html_report(
            evaluation_results,
            bar_chart_path,
            radar_chart_path
        )
        
        report_path = self.output_dir / f"{output_name}.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(report_path)
    
    def _generate_html_report(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        bar_chart_path: Optional[str],
        radar_chart_path: Optional[str]
    ) -> str:
        """Generate HTML report content."""
        html = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Evaluation Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background-color: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 3px solid #4CAF50; padding-bottom: 10px; }
        h2 { color: #555; margin-top: 30px; }
        table { width: 100%; border-collapse: collapse; margin: 20px 0; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #4CAF50; color: white; }
        tr:hover { background-color: #f5f5f5; }
        .metric-good { color: #4CAF50; font-weight: bold; }
        .metric-bad { color: #f44336; font-weight: bold; }
        img { max-width: 100%; height: auto; margin: 20px 0; border: 1px solid #ddd; border-radius: 4px; }
        .section { margin: 30px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Evaluation Report</h1>
"""
        
        # Add metrics table
        html += "<div class='section'><h2>Metrics Summary</h2><table>"
        
        # Get all metrics
        all_metrics = set()
        for alg_data in evaluation_results.values():
            if isinstance(alg_data, dict) and "metrics" in alg_data:
                all_metrics.update(alg_data["metrics"].keys())
            elif isinstance(alg_data, dict):
                all_metrics.update(alg_data.keys())
        
        all_metrics = sorted(list(all_metrics))
        
        # Table header
        html += "<tr><th>Algorithm</th>"
        for metric in all_metrics:
            html += f"<th>{metric.upper()}</th>"
        html += "</tr>"
        
        # Table rows
        for alg_name, alg_data in evaluation_results.items():
            html += f"<tr><td><strong>{alg_name}</strong></td>"
            
            if isinstance(alg_data, dict) and "metrics" in alg_data:
                metrics = alg_data["metrics"]
            elif isinstance(alg_data, dict):
                metrics = alg_data
            else:
                metrics = {}
            
            for metric in all_metrics:
                value = metrics.get(metric)
                if value is not None:
                    if metric in ['psnr', 'ssim']:
                        css_class = 'metric-good' if value > (30 if metric == 'psnr' else 0.8) else 'metric-bad'
                    elif metric == 'mse':
                        css_class = 'metric-good' if value < 0.01 else 'metric-bad'
                    else:
                        css_class = ''
                    
                    html += f"<td class='{css_class}'>{value:.4f}</td>"
                else:
                    html += "<td>-</td>"
            html += "</tr>"
        
        html += "</table></div>"
        
        # Add visualizations
        if bar_chart_path:
            html += f"<div class='section'><h2>Metrics Comparison (Bar Chart)</h2>"
            html += f"<img src='{Path(bar_chart_path).name}' alt='Bar Chart'></div>"
        
        if radar_chart_path:
            html += f"<div class='section'><h2>Metrics Comparison (Radar Chart)</h2>"
            html += f"<img src='{Path(radar_chart_path).name}' alt='Radar Chart'></div>"
        
        html += """
    </div>
</body>
</html>
"""
        return html

