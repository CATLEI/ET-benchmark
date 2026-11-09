"""
Evaluation result visualization.

Generates publication-quality visualizations for evaluation results.
"""

import html as html_lib
import json
import numpy as np
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional, List, Sequence
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

try:
    import seaborn as sns
except ImportError:  # pragma: no cover - optional for HTML-only report paths
    sns = None

# Set style for publication-quality plots
try:
    plt.style.use('seaborn-v0_8-paper')
except OSError:
    plt.style.use('default')
if sns is not None:
    sns.set_palette("colorblind")


# Metric taxonomy for comparison reports. Unknown keys fall into "Other".
METRIC_GROUPS: List[Dict[str, Any]] = [
    {
        "id": "fidelity",
        "title": "Intensity fidelity",
        "description": "Voxel-wise agreement with ground truth after GT-frame alignment.",
        "metrics": ["psnr", "ssim", "mse", "r2"],
    },
    {
        "id": "resolution",
        "title": "Resolution and geometry",
        "description": "Fourier resolution, edge sharpness, and missing-wedge elongation.",
        "metrics": ["fsc_resolution_px", "edge_rise_px", "elongation"],
    },
    {
        "id": "morphology",
        "title": "Solid–void morphology",
        "description": "Binary solid overlap and surface distance after GT mid-range threshold.",
        "metrics": ["dice", "hausdorff95_px", "porosity_abs_error"],
    },
    {
        "id": "porous",
        "title": "Porous nanomaterials",
        "description": "Pore-size distribution, specific surface area, and connectivity.",
        "metrics": [
            "psd_wasserstein_px",
            "ssa_rel_error",
            "void_cc_fraction_abs_error",
            "percolation_mismatch",
        ],
    },
]

# Direction used to pick the best value in each column.
# "higher" | "lower" | "closer_to_one"
METRIC_BEST_DIRECTION: Dict[str, str] = {
    "psnr": "higher",
    "ssim": "higher",
    "r2": "higher",
    "dice": "higher",
    "mse": "lower",
    "fsc_resolution_px": "lower",
    "edge_rise_px": "lower",
    "hausdorff95_px": "lower",
    "porosity_abs_error": "lower",
    "psd_wasserstein_px": "lower",
    "ssa_rel_error": "lower",
    "void_cc_fraction_abs_error": "lower",
    "percolation_mismatch": "lower",
    "elongation": "closer_to_one",
}

METRIC_DISPLAY_NAMES: Dict[str, str] = {
    "psnr": "PSNR (dB)",
    "ssim": "SSIM",
    "mse": "MSE",
    "r2": "R²",
    "fsc_resolution_px": "FSC res. (px)",
    "edge_rise_px": "Edge rise (px)",
    "elongation": "Elongation",
    "dice": "Dice",
    "hausdorff95_px": "Hausdorff95 (px)",
    "porosity_abs_error": "Porosity |Δ|",
    "psd_wasserstein_px": "PSD W1 (px)",
    "ssa_rel_error": "SSA rel. err.",
    "void_cc_fraction_abs_error": "Void CC |Δ|",
    "percolation_mismatch": "Percolation mismatch",
}

# Ordered (key, label) pairs shown in the report sample header.
SAMPLE_INFO_FIELDS: List[tuple] = [
    ("dataset_key", "Dataset"),
    ("dataset_name", "Dataset name"),
    ("variant", "Variant"),
    ("track", "Track"),
    ("tilt_range", "Tilt range"),
    ("missing_wedge_angle", "Missing wedge (°)"),
    ("gt_shape", "GT shape"),
    ("source_root", "Source root"),
    ("algorithms", "Algorithms"),
    ("generated_at", "Generated at"),
]


def collect_sample_info(
    evaluation_payloads: Sequence[Dict[str, Any]],
    algorithm_names: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """
    Build sample/header metadata from evaluation JSON payloads.

    Prefers the first payload that carries non-empty ``metadata``.
    """
    info: Dict[str, Any] = {}
    for payload in evaluation_payloads:
        if not isinstance(payload, dict):
            continue
        meta = payload.get("metadata") or {}
        if not isinstance(meta, dict):
            meta = {}
        if not info and (meta or payload.get("dataset_name") or payload.get("dataset_key")):
            for key in (
                "dataset_key",
                "variant",
                "track",
                "tilt_range",
                "missing_wedge_angle",
                "gt_shape",
                "source_root",
            ):
                if meta.get(key) is not None and key not in info:
                    info[key] = meta[key]
            dataset_name = payload.get("dataset_name") or meta.get("dataset_name")
            if dataset_name and "dataset_name" not in info:
                info["dataset_name"] = dataset_name
            if not info.get("dataset_key"):
                info["dataset_key"] = (
                    meta.get("dataset_key")
                    or payload.get("dataset_name")
                    or payload.get("dataset_key")
                )
    if algorithm_names:
        info["algorithms"] = ", ".join(str(a) for a in algorithm_names)
    info.setdefault(
        "generated_at",
        datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
    )
    return {k: v for k, v in info.items() if v is not None and v != ""}


def _format_sample_value(key: str, value: Any) -> str:
    if value is None:
        return "-"
    if key == "tilt_range" and isinstance(value, (list, tuple)) and len(value) >= 2:
        return f"[{value[0]}°, {value[1]}°]"
    if key == "gt_shape" and isinstance(value, (list, tuple)):
        return " × ".join(str(int(x)) for x in value)
    if isinstance(value, (list, tuple, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _render_sample_info_section(sample_info: Optional[Dict[str, Any]]) -> str:
    if not sample_info:
        return ""
    display = dict(sample_info)
    # Avoid duplicating the same dataset id under two labels.
    if (
        display.get("dataset_key") is not None
        and display.get("dataset_name") is not None
        and str(display["dataset_key"]) == str(display["dataset_name"])
    ):
        display.pop("dataset_name", None)
    rows = []
    seen = set()
    for key, label in SAMPLE_INFO_FIELDS:
        if key not in display:
            continue
        seen.add(key)
        rows.append(
            "<tr><th>"
            + html_lib.escape(label)
            + "</th><td>"
            + html_lib.escape(_format_sample_value(key, display[key]))
            + "</td></tr>"
        )
    for key, value in display.items():
        if key in seen:
            continue
        rows.append(
            "<tr><th>"
            + html_lib.escape(str(key))
            + "</th><td>"
            + html_lib.escape(_format_sample_value(key, value))
            + "</td></tr>"
        )
    if not rows:
        return ""
    return (
        "<div class='section sample-info'><h2>Sample</h2>"
        "<table class='kv'>"
        + "".join(rows)
        + "</table></div>"
    )


def _extract_metrics(alg_data: Any) -> Dict[str, Any]:
    if isinstance(alg_data, dict) and "metrics" in alg_data:
        return dict(alg_data["metrics"] or {})
    if isinstance(alg_data, dict):
        return dict(alg_data)
    return {}


def _metric_sort_key(metric: str, value: float) -> float:
    direction = METRIC_BEST_DIRECTION.get(metric, "higher")
    if direction == "lower":
        return float(value)
    if direction == "closer_to_one":
        return abs(float(value) - 1.0)
    return -float(value)


def _best_algorithms_for_metric(
    evaluation_results: Dict[str, Dict[str, Any]],
    metric: str,
) -> set:
    scored = []
    for alg_name, alg_data in evaluation_results.items():
        value = _extract_metrics(alg_data).get(metric)
        if value is None:
            continue
        try:
            number = float(value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(number):
            continue
        scored.append((alg_name, number))
    if not scored:
        return set()
    best_key = min(_metric_sort_key(metric, number) for _, number in scored)
    winners = {
        name
        for name, number in scored
        if abs(_metric_sort_key(metric, number) - best_key) <= 1e-12
    }
    return winners


def _grouped_metric_keys(all_metrics: List[str]) -> List[Dict[str, Any]]:
    remaining = set(all_metrics)
    groups: List[Dict[str, Any]] = []
    for group in METRIC_GROUPS:
        present = [m for m in group["metrics"] if m in remaining]
        if not present:
            continue
        groups.append({**group, "metrics": present})
        remaining.difference_update(present)
    if remaining:
        groups.append(
            {
                "id": "other",
                "title": "Other",
                "description": "Metrics not assigned to a standard category.",
                "metrics": sorted(remaining),
            }
        )
    return groups


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
        output_name: str = "evaluation_report",
        sample_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Create comprehensive evaluation report with visualizations.
        
        Args:
            evaluation_results: Dictionary mapping algorithm names to their metrics
            output_name: Base name for output file
            sample_info: Optional sample / dataset header fields
        
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
            radar_chart_path,
            sample_info=sample_info,
        )
        
        report_path = self.output_dir / f"{output_name}.html"
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return str(report_path)
    
    def _generate_html_report(
        self,
        evaluation_results: Dict[str, Dict[str, Any]],
        bar_chart_path: Optional[str],
        radar_chart_path: Optional[str],
        sample_info: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Generate HTML report with metrics grouped by evaluation category."""
        all_metrics: List[str] = []
        seen = set()
        for alg_data in evaluation_results.values():
            for key in _extract_metrics(alg_data):
                if key not in seen:
                    seen.add(key)
                    all_metrics.append(key)

        groups = _grouped_metric_keys(all_metrics)
        winners = {
            metric: _best_algorithms_for_metric(evaluation_results, metric)
            for metric in all_metrics
        }
        header_info = dict(sample_info or {})
        if "algorithms" not in header_info and evaluation_results:
            header_info["algorithms"] = ", ".join(evaluation_results.keys())
        if "generated_at" not in header_info:
            header_info["generated_at"] = datetime.now(timezone.utc).strftime(
                "%Y-%m-%d %H:%M:%S UTC"
            )

        title = "Evaluation Report"
        dataset_label = (
            header_info.get("dataset_key")
            or header_info.get("dataset_name")
            or header_info.get("variant")
        )
        if dataset_label:
            title = f"Evaluation Report — {dataset_label}"

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{html_lib.escape(title)}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }}
        .container {{ max-width: 1100px; margin: 0 auto; background-color: white; padding: 24px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        h1 {{ color: #222; border-bottom: 3px solid #2f6f4e; padding-bottom: 10px; }}
        h2 {{ color: #333; margin-top: 28px; margin-bottom: 6px; }}
        h3 {{ color: #555; margin: 0 0 8px 0; font-size: 1.05rem; }}
        .group-desc {{ color: #666; font-size: 0.92rem; margin: 0 0 10px 0; }}
        table {{ width: 100%; border-collapse: collapse; margin: 8px 0 18px 0; font-size: 0.95rem; }}
        th, td {{ padding: 10px 12px; text-align: right; border-bottom: 1px solid #e5e5e5; }}
        th:first-child, td:first-child {{ text-align: left; }}
        th {{ background-color: #2f6f4e; color: white; font-weight: 600; }}
        tr:hover {{ background-color: #f7faf8; }}
        table.kv th {{ width: 220px; background-color: #eef3f0; color: #333; text-align: left; font-weight: 600; }}
        table.kv td {{ text-align: left; }}
        .sample-info table.kv {{ margin-top: 4px; }}
        .metric-best {{ color: #1b7a3d; font-weight: 700; background-color: #e8f6ee; }}
        .best-tag {{ display: inline-block; margin-left: 6px; padding: 1px 6px; border-radius: 999px; background: #1b7a3d; color: white; font-size: 0.72rem; font-weight: 600; vertical-align: middle; }}
        .legend {{ color: #555; font-size: 0.9rem; margin: 8px 0 18px 0; padding: 10px 12px; background: #f3f7f4; border-radius: 6px; }}
        .winners {{ margin: 12px 0 8px 0; }}
        .winners table th {{ background-color: #3d5a80; }}
        img {{ max-width: 100%; height: auto; margin: 12px 0; border: 1px solid #ddd; border-radius: 4px; }}
        .section {{ margin: 24px 0; }}
        .dir-note {{ color: #888; font-size: 0.78rem; font-weight: normal; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>{html_lib.escape(title)}</h1>
{_render_sample_info_section(header_info)}
        <div class="legend">
            Metrics are grouped by evaluation content. In each column the best
            value is highlighted in green and tagged <span class="best-tag">best</span>.
            Higher is better for PSNR / SSIM / R² / Dice; lower is better for error,
            distance, and mismatch metrics; Elongation is best when closest to 1.
        </div>
"""

        # Compact winners board: one best algorithm per metric.
        html += "<div class='section winners'><h2>Best algorithm per metric</h2><table>"
        html += "<tr><th>Category</th><th>Metric</th><th>Best algorithm(s)</th><th>Value</th></tr>"
        for group in groups:
            for metric in group["metrics"]:
                best_names = sorted(winners.get(metric, set()))
                if not best_names:
                    continue
                sample_metrics = _extract_metrics(evaluation_results[best_names[0]])
                value = sample_metrics.get(metric)
                label = METRIC_DISPLAY_NAMES.get(metric, metric)
                alg_label = ", ".join(best_names)
                value_label = f"{float(value):.4f}" if value is not None else "-"
                html += (
                    f"<tr><td>{group['title']}</td><td>{label}</td>"
                    f"<td>{alg_label}</td><td>{value_label}</td></tr>"
                )
        html += "</table></div>"

        for group in groups:
            html += "<div class='section'>"
            html += f"<h2>{group['title']}</h2>"
            html += f"<p class='group-desc'>{group['description']}</p>"
            html += "<table><tr><th>Algorithm</th>"
            for metric in group["metrics"]:
                label = METRIC_DISPLAY_NAMES.get(metric, metric)
                direction = METRIC_BEST_DIRECTION.get(metric, "higher")
                if direction == "higher":
                    tip = "↑ better"
                elif direction == "lower":
                    tip = "↓ better"
                else:
                    tip = "→ 1 better"
                html += f"<th>{label}<br><span class='dir-note'>{tip}</span></th>"
            html += "</tr>"

            for alg_name, alg_data in evaluation_results.items():
                metrics = _extract_metrics(alg_data)
                html += f"<tr><td><strong>{alg_name}</strong></td>"
                for metric in group["metrics"]:
                    value = metrics.get(metric)
                    if value is None:
                        html += "<td>-</td>"
                        continue
                    try:
                        number = float(value)
                    except (TypeError, ValueError):
                        html += f"<td>{value}</td>"
                        continue
                    is_best = alg_name in winners.get(metric, set())
                    css = "metric-best" if is_best else ""
                    tag = " <span class='best-tag'>best</span>" if is_best else ""
                    html += f"<td class='{css}'>{number:.4f}{tag}</td>"
                html += "</tr>"
            html += "</table></div>"

        if bar_chart_path:
            html += (
                "<div class='section'><h2>Metrics Comparison (Bar Chart)</h2>"
                f"<img src='{Path(bar_chart_path).name}' alt='Bar Chart'></div>"
            )
        if radar_chart_path:
            html += (
                "<div class='section'><h2>Metrics Comparison (Radar Chart)</h2>"
                f"<img src='{Path(radar_chart_path).name}' alt='Radar Chart'></div>"
            )

        html += """
    </div>
</body>
</html>
"""
        return html

