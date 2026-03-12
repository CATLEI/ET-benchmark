"""
Algorithm performance analyzer.

Analyzes algorithm performance and provides insights.
"""

from typing import Dict, Any, List, Optional
from et_dflow.core.models import EvaluationResult, AlgorithmResult


class AlgorithmPerformanceAnalyzer:
    """
    Analyzes algorithm performance.
    
    Provides:
    - Strengths and weaknesses analysis
    - Use case recommendations
    - Performance predictions
    """
    
    def __init__(self):
        """Initialize performance analyzer."""
        pass
    
    def analyze(
        self,
        evaluation_results: List[EvaluationResult]
    ) -> Dict[str, Any]:
        """
        Analyze algorithm performance.
        
        Args:
            evaluation_results: List of evaluation results
        
        Returns:
            Analysis results
        """
        analysis = {
            "strengths_weaknesses": self._analyze_strengths_weaknesses(evaluation_results),
            "use_case_recommendations": self._recommend_use_cases(evaluation_results),
            "performance_predictions": self._predict_performance(evaluation_results),
        }
        
        return analysis
    
    def _analyze_strengths_weaknesses(
        self,
        results: List[EvaluationResult]
    ) -> Dict[str, Dict[str, List[str]]]:
        """Analyze strengths and weaknesses."""
        strengths_weaknesses = {}
        
        for result in results:
            alg_name = result.algorithm_name
            strengths = []
            weaknesses = []
            
            if result.metrics:
                psnr = result.metrics.get("psnr", 0)
                ssim = result.metrics.get("ssim", 0)
                
                if psnr > 30:
                    strengths.append("High PSNR (good reconstruction quality)")
                elif psnr < 20:
                    weaknesses.append("Low PSNR (poor reconstruction quality)")
                
                if ssim > 0.9:
                    strengths.append("High SSIM (good structural similarity)")
                elif ssim < 0.7:
                    weaknesses.append("Low SSIM (poor structural similarity)")
            
            strengths_weaknesses[alg_name] = {
                "strengths": strengths,
                "weaknesses": weaknesses,
            }
        
        return strengths_weaknesses
    
    def _recommend_use_cases(
        self,
        results: List[EvaluationResult]
    ) -> Dict[str, List[str]]:
        """Recommend use cases for each algorithm."""
        recommendations = {}
        
        for result in results:
            alg_name = result.algorithm_name
            use_cases = []
            
            if result.metrics:
                psnr = result.metrics.get("psnr", 0)
                ssim = result.metrics.get("ssim", 0)
                
                if psnr > 30 and ssim > 0.9:
                    use_cases.append("High-quality reconstruction tasks")
                    use_cases.append("Publication-quality results")
                
                if psnr > 25:
                    use_cases.append("General reconstruction tasks")
            
            recommendations[alg_name] = use_cases
        
        return recommendations
    
    def _predict_performance(
        self,
        results: List[EvaluationResult]
    ) -> Dict[str, Dict[str, float]]:
        """Predict performance for different scenarios."""
        predictions = {}
        
        for result in results:
            alg_name = result.algorithm_name
            
            # Simplified prediction model
            # In full implementation, would use machine learning model
            
            if result.metrics:
                base_psnr = result.metrics.get("psnr", 25.0)
                
                predictions[alg_name] = {
                    "high_quality_data": base_psnr * 1.1,
                    "medium_quality_data": base_psnr,
                    "low_quality_data": base_psnr * 0.9,
                }
        
        return predictions

