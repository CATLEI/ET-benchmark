"""
dflow OP for comparison and report generation.

Aggregates evaluation results from multiple algorithms and generates comparison report.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List
from dflow.python import OP, OPIO, Parameter, Artifact
import json
from pathlib import Path


class ComparisonOP(OP):
    """
    dflow OP for comparing multiple algorithm results.
    
    Aggregates evaluation results and generates comparison report.
    """
    
    def __init__(self):
        """Initialize comparison OP."""
        pass
    
    @classmethod
    def get_input_sign(cls):
        """Get input signature."""
        return OPIO({
            "metrics_files": Artifact(List[str]),
            "algorithm_names": Parameter(List[str]),
        })
    
    @classmethod
    def get_output_sign(cls):
        """Get output signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "comparison_report": Artifact(str),  # HTML report
            "comparison_json": Artifact(str),  # JSON summary
            "visualizations": Artifact(str),  # Visualization files
        })
    
    @OP.exec_sign_check
    def execute(self, op_in: OPIO) -> OPIO:
        """
        Execute comparison and report generation.
        
        Args:
            op_in: Input OPIO
        
        Returns:
            Output OPIO with comparison report
        """
        metrics_files = op_in["metrics_files"]
        algorithm_names = op_in["algorithm_names"]
        output_path = Path("/tmp/comparison")
        
        # Load all evaluation results from JSON files
        all_results = {}
        for eval_file, alg_name in zip(metrics_files, algorithm_names):
            try:
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                    all_results[alg_name] = eval_data.get("metrics", {})
            except Exception as e:
                print(f"Warning: Failed to load evaluation for {alg_name}: {e}")
                all_results[alg_name] = {}
        
        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate visualizations
        html_report_path = output_path / "comparison_report.html"
        try:
            from et_dflow.infrastructure.visualization.evaluation_visualizer import EvaluationVisualizer
            
            visualizer = EvaluationVisualizer(str(output_path))
            
            # Prepare data for visualization
            viz_data = {alg_name: {"metrics": metrics} 
                       for alg_name, metrics in all_results.items()}
            
            # Create visualizations
            bar_chart = visualizer.visualize_metrics(viz_data, "metrics_comparison")
            radar_chart = visualizer.visualize_metrics_radar(viz_data, "metrics_radar")
            html_report = visualizer.create_summary_report(viz_data, "comparison_report")
            
            visualization_files = []
            if bar_chart:
                visualization_files.append(bar_chart)
            if radar_chart:
                visualization_files.append(radar_chart)
            if html_report:
                html_report_path = Path(html_report)
                visualization_files.append(str(html_report_path))
        except Exception as e:
            print(f"Warning: Visualization generation failed: {e}")
            visualization_files = []
            html_report_path.write_text(
                (
                    "<html><body><h1>Comparison Report</h1>"
                    "<p>Visualization generation failed. JSON summary is available.</p>"
                    f"<pre>{json.dumps(all_results, indent=2)}</pre>"
                    "</body></html>"
                ),
                encoding="utf-8",
            )
        
        # Create JSON summary
        summary = {
            "algorithms": algorithm_names,
            "metrics": all_results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        summary_json = output_path / "comparison_summary.json"
        with open(summary_json, 'w') as f:
            json.dump(summary, f, indent=2)
        
        # visualizations: path to output dir (Artifact expects str, not list)
        viz_path = str(output_path) if visualization_files else str(summary_json)
        
        return OPIO({
            "comparison_report": str(html_report_path),
            "comparison_json": str(summary_json),
            "visualizations": viz_path,
        })

