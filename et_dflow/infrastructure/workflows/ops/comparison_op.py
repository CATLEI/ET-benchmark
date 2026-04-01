"""
dflow OP for comparison and report generation.

Aggregates evaluation results from multiple algorithms and generates comparison report.
"""

from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List
from dflow.python import OP, OPIO, Parameter, Artifact
import csv
import json
import re
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
            "row_labels": Parameter(List[str], optional=True),
        })
    
    @classmethod
    def get_output_sign(cls):
        """Get output signature (use dflow.python.Artifact with type for OPIO)."""
        return OPIO({
            "comparison_report": Artifact(str),  # HTML report
            "comparison_json": Artifact(str),  # JSON summary
            "visualizations": Artifact(str),  # Visualization files
            "leaderboard_json": Artifact(str),  # suite aggregate (by track)
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
        row_labels: List[str] = op_in.get("row_labels") or list(algorithm_names)
        if len(row_labels) != len(algorithm_names):
            row_labels = [
                row_labels[i] if i < len(row_labels) else algorithm_names[i]
                for i in range(len(algorithm_names))
            ]
        output_path = Path("/tmp/comparison")
        
        def _safe_track_name(track: str) -> str:
            s = re.sub(r"[^a-zA-Z0-9._-]+", "_", track or "unknown").strip("_")
            return s or "unknown"

        # Load all evaluation results from JSON files
        all_results: Dict[str, Dict[str, Any]] = {}
        leaderboard_rows: List[Dict[str, Any]] = []
        by_track: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        for eval_file, alg_name, row_label in zip(metrics_files, algorithm_names, row_labels):
            try:
                with open(eval_file, 'r') as f:
                    eval_data = json.load(f)
                    metrics = eval_data.get("metrics", {})
                    all_results[row_label] = metrics
                    meta = eval_data.get("metadata") or {}
                    track = meta.get("track") or "unknown"
                    row = {
                        "row_label": row_label,
                        "algorithm_name": alg_name,
                        "dataset_key": meta.get("dataset_key"),
                        "track": track,
                        "variant": meta.get("variant"),
                        "metrics": metrics,
                        "load_error": "",
                    }
                    leaderboard_rows.append(row)
                    by_track[track].append(row)
            except Exception as e:
                print(f"Warning: Failed to load evaluation for {row_label}: {e}")
                all_results[row_label] = {}
                err_track = "_failed_load"
                row = {
                    "row_label": row_label,
                    "algorithm_name": alg_name,
                    "dataset_key": None,
                    "track": err_track,
                    "variant": None,
                    "metrics": {},
                    "load_error": str(e),
                }
                leaderboard_rows.append(row)
                by_track[err_track].append(row)
        
        # Ensure output directory exists
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Generate visualizations
        html_report_path = output_path / "comparison_report.html"
        try:
            from et_dflow.infrastructure.visualization.evaluation_visualizer import EvaluationVisualizer
            
            visualizer = EvaluationVisualizer(str(output_path))
            
            # Prepare data for visualization
            viz_data = {label: {"metrics": metrics}
                       for label, metrics in all_results.items()}
            
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
            "row_labels": row_labels,
            "metrics": all_results,
            "leaderboard_by_track": {k: v for k, v in by_track.items()},
            "leaderboard_rows": leaderboard_rows,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        
        summary_json = output_path / "comparison_summary.json"
        with open(summary_json, 'w') as f:
            json.dump(summary, f, indent=2)

        leaderboard_dir = output_path / "leaderboard"
        leaderboard_dir.mkdir(parents=True, exist_ok=True)
        for track, rows in by_track.items():
            tfile = leaderboard_dir / f"{_safe_track_name(track)}.json"
            with open(tfile, "w", encoding="utf-8") as f:
                json.dump({"track": track, "rows": rows}, f, indent=2, default=str)

        leaderboard_table = output_path / "leaderboard.csv"
        metric_keys: List[str] = sorted(
            {k for r in leaderboard_rows for k in (r.get("metrics") or {}).keys()}
        )
        base_fields = ["track", "dataset_key", "variant", "algorithm_name", "row_label", "load_error"]
        with open(leaderboard_table, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=base_fields + metric_keys)
            writer.writeheader()
            for r in leaderboard_rows:
                m = r.get("metrics") or {}
                row_out = {
                    "track": r.get("track"),
                    "dataset_key": r.get("dataset_key"),
                    "variant": r.get("variant"),
                    "algorithm_name": r.get("algorithm_name"),
                    "row_label": r.get("row_label"),
                    "load_error": r.get("load_error", ""),
                }
                for mk in metric_keys:
                    row_out[mk] = m.get(mk)
                writer.writerow(row_out)

        suite_leaderboard_path = output_path / "suite_leaderboard.json"
        with open(suite_leaderboard_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "by_track": {k: v for k, v in by_track.items()},
                    "csv": str(leaderboard_table),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                f,
                indent=2,
                default=str,
            )
        
        # visualizations: path to output dir (Artifact expects str, not list)
        viz_path = str(output_path) if visualization_files else str(summary_json)
        
        return OPIO({
            "comparison_report": str(html_report_path),
            "comparison_json": str(summary_json),
            "visualizations": viz_path,
            "leaderboard_json": str(suite_leaderboard_path),
        })

