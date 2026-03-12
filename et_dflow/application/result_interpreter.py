"""
Result interpreter for evaluation results.

Provides interpretation and recommendations based on evaluation metrics.
"""

from typing import Dict, Any, List, Optional
from et_dflow.core.models import EvaluationResult, AlgorithmResult


class ResultInterpreter:
    """
    Interprets evaluation results and provides recommendations.
    
    Analyzes metrics and provides:
    - Quality ratings
    - Algorithm recommendations
    - Metric explanations
    """
    
    def __init__(self):
        """Initialize result interpreter."""
        pass
    
    def interpret(self, evaluation_result: EvaluationResult) -> Dict[str, Any]:
        """
        Interpret evaluation results.
        
        Args:
            evaluation_result: Evaluation result to interpret
        
        Returns:
            Dictionary with interpretation and recommendations
        """
        interpretation = {
            "overall_quality": self._assess_overall_quality(evaluation_result),
            "algorithm_rankings": self._rank_algorithms(evaluation_result),
            "recommendations": self._generate_recommendations(evaluation_result),
            "metric_explanations": self._explain_metrics(evaluation_result),
        }
        
        return interpretation
    
    def _assess_overall_quality(self, result: EvaluationResult) -> str:
        """
        Assess overall reconstruction quality.
        
        Args:
            result: Evaluation result
        
        Returns:
            Quality rating: 'excellent', 'good', 'fair', 'poor'
        """
        # Simplified quality assessment
        # In full implementation, would analyze all metrics
        
        if not result.metrics:
            return "unknown"
        
        # Check key metrics
        psnr = result.metrics.get("psnr", 0)
        ssim = result.metrics.get("ssim", 0)
        
        if psnr > 30 and ssim > 0.9:
            return "excellent"
        elif psnr > 25 and ssim > 0.8:
            return "good"
        elif psnr > 20 and ssim > 0.7:
            return "fair"
        else:
            return "poor"
    
    def _rank_algorithms(self, result: EvaluationResult) -> List[Dict[str, Any]]:
        """
        Rank algorithms by performance.
        
        Args:
            result: Evaluation result
        
        Returns:
            List of algorithm rankings
        """
        rankings = []
        
        for alg_result in result.algorithm_results:
            score = self._calculate_algorithm_score(alg_result)
            rankings.append({
                "algorithm": alg_result.algorithm_name,
                "score": score,
                "metrics": alg_result.metrics or {},
            })
        
        # Sort by score (descending)
        rankings.sort(key=lambda x: x["score"], reverse=True)
        
        return rankings
    
    def _calculate_algorithm_score(self, alg_result: AlgorithmResult) -> float:
        """
        Calculate overall score for algorithm.
        
        Args:
            alg_result: Algorithm result
        
        Returns:
            Score (0-100)
        """
        if not alg_result.metrics:
            return 0.0
        
        # Weighted combination of metrics
        psnr = alg_result.metrics.get("psnr", 0)
        ssim = alg_result.metrics.get("ssim", 0)
        
        # Normalize and combine
        psnr_score = min(psnr / 40.0 * 50, 50)  # Max 50 points
        ssim_score = ssim * 50  # Max 50 points
        
        return psnr_score + ssim_score
    
    def _generate_recommendations(self, result: EvaluationResult) -> List[str]:
        """
        Generate recommendations based on results.
        
        Args:
            result: Evaluation result
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        # Analyze metrics and generate recommendations
        if result.metrics:
            psnr = result.metrics.get("psnr", 0)
            if psnr < 20:
                recommendations.append(
                    "Low PSNR detected. Consider using iterative algorithms "
                    "or increasing number of iterations."
                )
            
            ssim = result.metrics.get("ssim", 0)
            if ssim < 0.7:
                recommendations.append(
                    "Low SSIM detected. Check data quality and preprocessing steps."
                )
        
        return recommendations
    
    def _explain_metrics(self, result: EvaluationResult) -> Dict[str, str]:
        """
        Explain evaluation metrics.
        
        Args:
            result: Evaluation result
        
        Returns:
            Dictionary mapping metric names to explanations
        """
        explanations = {
            "psnr": (
                "Peak Signal-to-Noise Ratio (PSNR) measures reconstruction quality. "
                "Higher values (typically >25 dB) indicate better quality."
            ),
            "ssim": (
                "Structural Similarity Index (SSIM) measures structural similarity. "
                "Values range from 0 to 1, with 1 indicating perfect similarity."
            ),
            "mse": (
                "Mean Squared Error (MSE) measures average squared difference. "
                "Lower values indicate better reconstruction."
            ),
            "fsc": (
                "Fourier Shell Correlation (FSC) measures resolution. "
                "FSC > 0.143 indicates reliable resolution."
            ),
        }
        
        return explanations


class PaperWriter:
    """
    Paper writing support tool.
    
    Generates text and figures for scientific papers.
    """
    
    def __init__(self):
        """Initialize paper writer."""
        pass
    
    def generate_methods_section(
        self,
        evaluation_result: EvaluationResult
    ) -> str:
        """
        Generate methods section text.
        
        Args:
            evaluation_result: Evaluation result
        
        Returns:
            Methods section text
        """
        text = "## Methods\n\n"
        text += "We evaluated multiple reconstruction algorithms using "
        text += f"{len(evaluation_result.algorithm_results)} different methods.\n\n"
        
        # Add algorithm descriptions
        for alg_result in evaluation_result.algorithm_results:
            text += f"### {alg_result.algorithm_name}\n\n"
            text += f"Parameters: {alg_result.parameters_used}\n\n"
        
        return text
    
    def generate_results_section(
        self,
        evaluation_result: EvaluationResult
    ) -> str:
        """
        Generate results section text.
        
        Args:
            evaluation_result: Evaluation result
        
        Returns:
            Results section text
        """
        text = "## Results\n\n"
        
        if evaluation_result.metrics:
            text += "### Quantitative Metrics\n\n"
            for metric_name, metric_value in evaluation_result.metrics.items():
                text += f"- {metric_name}: {metric_value:.3f}\n"
            text += "\n"
        
        return text

