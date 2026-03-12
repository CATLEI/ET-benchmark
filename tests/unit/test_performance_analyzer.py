"""
Unit tests for performance analyzer.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.application.performance_analyzer import AlgorithmPerformanceAnalyzer
from et_dflow.core.models import EvaluationResult, AlgorithmResult
from datetime import datetime


class TestAlgorithmPerformanceAnalyzer:
    """Test AlgorithmPerformanceAnalyzer."""
    
    def test_analyzer_creation(self):
        """Test analyzer can be created."""
        analyzer = AlgorithmPerformanceAnalyzer()
        assert analyzer is not None
    
    def test_analyze_performance(self):
        """Test performance analysis."""
        analyzer = AlgorithmPerformanceAnalyzer()
        
        recon = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        alg_result = AlgorithmResult(
            algorithm_name="wbp",
            reconstruction=recon,
            execution_time=1.0,
            memory_usage=1024,
        )
        
        eval_result = EvaluationResult(
            evaluation_id="test",
            dataset_id="test",
            algorithm_results=[alg_result],
            timestamp=datetime.now(),
            metrics={"psnr": 28.0, "ssim": 0.85},
            algorithm_name="wbp",
        )
        
        analysis = analyzer.analyze([eval_result])
        
        assert "strengths_weaknesses" in analysis
        assert "use_case_recommendations" in analysis
        assert "performance_predictions" in analysis

