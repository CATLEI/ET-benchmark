"""
Unit tests for comparison report generator.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.infrastructure.visualization.comparison_report import ComparisonReportGenerator
from et_dflow.core.models import EvaluationResult, AlgorithmResult
from datetime import datetime


class TestComparisonReportGenerator:
    """Test ComparisonReportGenerator."""
    
    def test_generator_creation(self):
        """Test generator can be created."""
        generator = ComparisonReportGenerator()
        assert generator is not None
    
    def test_generate_report(self, tmp_path):
        """Test report generation."""
        generator = ComparisonReportGenerator()
        
        # Create mock results
        recon1 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        recon2 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        
        alg_result1 = AlgorithmResult(
            algorithm_name="wbp",
            reconstruction=recon1,
            execution_time=1.0,
            memory_usage=1024,
        )
        
        alg_result2 = AlgorithmResult(
            algorithm_name="sirt",
            reconstruction=recon2,
            execution_time=2.0,
            memory_usage=2048,
        )
        
        eval_result1 = EvaluationResult(
            evaluation_id="eval1",
            dataset_id="dataset1",
            algorithm_results=[alg_result1],
            timestamp=datetime.now(),
            metrics={"psnr": 28.0, "ssim": 0.85},
            algorithm_name="wbp",
        )
        
        eval_result2 = EvaluationResult(
            evaluation_id="eval2",
            dataset_id="dataset1",
            algorithm_results=[alg_result2],
            timestamp=datetime.now(),
            metrics={"psnr": 32.0, "ssim": 0.92},
            algorithm_name="sirt",
        )
        
        output_path = tmp_path / "report.html"
        report_path = generator.generate_report(
            [eval_result1, eval_result2],
            output_path=str(output_path)
        )
        
        assert Path(report_path).exists()
        assert output_path.exists()

