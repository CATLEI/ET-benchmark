"""
Comparison report generator.

Generates comprehensive comparison reports for algorithm evaluation.
"""

from typing import Dict, Any, List, Optional
from pathlib import Path
import json
from datetime import datetime
from et_dflow.core.models import EvaluationResult, AlgorithmResult
from et_dflow.application.result_interpreter import ResultInterpreter


class ComparisonReportGenerator:
    """
    Generates comparison reports for algorithm evaluation.
    
    Creates comprehensive reports with:
    - Performance comparison tables
    - Visual comparisons
    - Algorithm recommendations
    """
    
    def __init__(self):
        """Initialize report generator."""
        self.interpreter = ResultInterpreter()
    
    def generate_report(
        self,
        evaluation_results: List[EvaluationResult],
        output_path: str = "comparison_report.html"
    ) -> str:
        """
        Generate comparison report.
        
        Args:
            evaluation_results: List of evaluation results
            output_path: Path to save report
        
        Returns:
            Path to generated report
        """
        # Generate report content
        report_content = self._generate_report_content(evaluation_results)
        
        # Save as HTML
        html_content = self._create_html_report(report_content)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        return output_path
    
    def _generate_report_content(
        self,
        evaluation_results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """Generate report content."""
        content = {
            "title": "Algorithm Comparison Report",
            "timestamp": datetime.now().isoformat(),
            "summary": self._generate_summary(evaluation_results),
            "algorithm_comparison": self._compare_algorithms(evaluation_results),
            "recommendations": self._generate_recommendations(evaluation_results),
        }
        
        return content
    
    def _generate_summary(
        self,
        evaluation_results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """Generate summary statistics."""
        if not evaluation_results:
            return {}
        
        # Aggregate metrics
        all_metrics = {}
        for result in evaluation_results:
            if result.metrics:
                for metric_name, metric_value in result.metrics.items():
                    if metric_name not in all_metrics:
                        all_metrics[metric_name] = []
                    all_metrics[metric_name].append(metric_value)
        
        summary = {}
        for metric_name, values in all_metrics.items():
            summary[metric_name] = {
                "mean": float(np.mean(values)),
                "std": float(np.std(values)),
                "min": float(np.min(values)),
                "max": float(np.max(values)),
            }
        
        return summary
    
    def _compare_algorithms(
        self,
        evaluation_results: List[EvaluationResult]
    ) -> List[Dict[str, Any]]:
        """Compare algorithms."""
        comparisons = []
        
        for result in evaluation_results:
            comparison = {
                "algorithm": result.algorithm_name,
                "metrics": result.metrics or {},
                "timestamp": result.timestamp.isoformat(),
            }
            comparisons.append(comparison)
        
        return comparisons
    
    def _generate_recommendations(
        self,
        evaluation_results: List[EvaluationResult]
    ) -> List[str]:
        """Generate recommendations."""
        recommendations = []
        
        # Interpret each result
        for result in evaluation_results:
            interpretation = self.interpreter.interpret(result)
            recommendations.extend(interpretation.get("recommendations", []))
        
        return list(set(recommendations))  # Remove duplicates
    
    def _create_html_report(self, content: Dict[str, Any]) -> str:
        """Create HTML report."""
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>{content['title']}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            <h1>{content['title']}</h1>
            <p>Generated: {content['timestamp']}</p>
            
            <h2>Summary</h2>
            <pre>{json.dumps(content['summary'], indent=2)}</pre>
            
            <h2>Algorithm Comparison</h2>
            <table>
                <tr>
                    <th>Algorithm</th>
                    <th>Metrics</th>
                </tr>
        """
        
        for comparison in content['algorithm_comparison']:
            html += f"""
                <tr>
                    <td>{comparison['algorithm']}</td>
                    <td><pre>{json.dumps(comparison['metrics'], indent=2)}</pre></td>
                </tr>
            """
        
        html += """
            </table>
            
            <h2>Recommendations</h2>
            <ul>
        """
        
        for rec in content['recommendations']:
            html += f"<li>{rec}</li>"
        
        html += """
            </ul>
        </body>
        </html>
        """
        
        return html

