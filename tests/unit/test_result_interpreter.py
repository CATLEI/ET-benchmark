"""
Unit tests for result interpreter.
"""

import pytest
from et_dflow.application.result_interpreter import ResultInterpreter, PaperWriter
from et_dflow.core.models import EvaluationResult, AlgorithmResult
from datetime import datetime


class TestResultInterpreter:
    """Test ResultInterpreter."""
    
    def test_interpreter_creation(self):
        """Test interpreter can be created."""
        interpreter = ResultInterpreter()
        assert interpreter is not None
    
    def test_interpret_results(self):
        """Test result interpretation."""
        interpreter = ResultInterpreter()
        
        # Create mock evaluation result
        import numpy as np
        import hyperspy.api as hs
        
        recon1 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        recon2 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        
        alg_result1 = AlgorithmResult(
            algorithm_name="wbp",
            reconstruction=recon1,
            execution_time=1.5,
            memory_usage=1024 * 1024,
            reconstruction_id="test1",
            timestamp=datetime.now(),
            parameters_used={"filter": "ramp"},
            output_path="./output/wbp.hspy",
            metrics={"psnr": 28.5, "ssim": 0.85},
        )
        
        alg_result2 = AlgorithmResult(
            algorithm_name="sirt",
            reconstruction=recon2,
            execution_time=2.0,
            memory_usage=2048 * 1024,
            reconstruction_id="test2",
            timestamp=datetime.now(),
            parameters_used={"iterations": 30},
            output_path="./output/sirt.hspy",
            metrics={"psnr": 32.0, "ssim": 0.92},
        )
        
        eval_result = EvaluationResult(
            evaluation_id="eval1",
            dataset_id="dataset1",
            algorithm_results=[alg_result1, alg_result2],
            timestamp=datetime.now(),
            metrics={"psnr": 30.0, "ssim": 0.88},
            algorithm_name="wbp",
        )
        
        interpretation = interpreter.interpret(eval_result)
        
        assert "overall_quality" in interpretation
        assert "algorithm_rankings" in interpretation
        assert "recommendations" in interpretation
        assert "metric_explanations" in interpretation
    
    def test_assess_quality(self):
        """Test quality assessment."""
        interpreter = ResultInterpreter()
        
        # Test excellent quality
        import numpy as np
        import hyperspy.api as hs
        
        recon = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        alg_result = AlgorithmResult(
            algorithm_name="test",
            reconstruction=recon,
            execution_time=1.0,
            memory_usage=1024,
        )
        
        result = EvaluationResult(
            evaluation_id="test",
            dataset_id="test",
            algorithm_results=[alg_result],
            timestamp=datetime.now(),
            metrics={"psnr": 35.0, "ssim": 0.95},
            algorithm_name="test",
        )
        quality = interpreter._assess_overall_quality(result)
        assert quality in ["excellent", "good", "fair", "poor"]
    
    def test_rank_algorithms(self):
        """Test algorithm ranking."""
        interpreter = ResultInterpreter()
        
        import numpy as np
        import hyperspy.api as hs
        
        recon1 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        recon2 = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        
        alg_result1 = AlgorithmResult(
            algorithm_name="wbp",
            reconstruction=recon1,
            execution_time=1.0,
            memory_usage=1024,
            reconstruction_id="test1",
            timestamp=datetime.now(),
            parameters_used={},
            output_path="./output/wbp.hspy",
            metrics={"psnr": 25.0, "ssim": 0.8},
        )
        
        alg_result2 = AlgorithmResult(
            algorithm_name="sirt",
            reconstruction=recon2,
            execution_time=1.0,
            memory_usage=1024,
            reconstruction_id="test2",
            timestamp=datetime.now(),
            parameters_used={},
            output_path="./output/sirt.hspy",
            metrics={"psnr": 30.0, "ssim": 0.9},
        )
        
        result = EvaluationResult(
            evaluation_id="test",
            dataset_id="test",
            algorithm_results=[alg_result1, alg_result2],
            timestamp=datetime.now(),
            metrics={},
            algorithm_name="test",
        )
        
        rankings = interpreter._rank_algorithms(result)
        assert len(rankings) == 2
        # SIRT should rank higher (better metrics)
        assert rankings[0]["algorithm"] == "sirt"


class TestPaperWriter:
    """Test PaperWriter."""
    
    def test_writer_creation(self):
        """Test writer can be created."""
        writer = PaperWriter()
        assert writer is not None
    
    def test_generate_methods_section(self):
        """Test methods section generation."""
        writer = PaperWriter()
        
        import numpy as np
        import hyperspy.api as hs
        
        recon = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        alg_result = AlgorithmResult(
            algorithm_name="wbp",
            reconstruction=recon,
            execution_time=1.0,
            memory_usage=1024,
            reconstruction_id="test1",
            timestamp=datetime.now(),
            parameters_used={"filter": "ramp"},
            output_path="./output/wbp.hspy",
        )
        
        result = EvaluationResult(
            evaluation_id="test",
            dataset_id="test",
            algorithm_results=[alg_result],
            timestamp=datetime.now(),
            metrics={},
            algorithm_name="wbp",
        )
        
        methods_text = writer.generate_methods_section(result)
        assert "Methods" in methods_text
        assert "wbp" in methods_text
    
    def test_generate_results_section(self):
        """Test results section generation."""
        writer = PaperWriter()
        
        import numpy as np
        import hyperspy.api as hs
        
        recon = hs.signals.Signal1D(np.random.rand(10, 10, 10))
        alg_result = AlgorithmResult(
            algorithm_name="test",
            reconstruction=recon,
            execution_time=1.0,
            memory_usage=1024,
        )
        
        result = EvaluationResult(
            evaluation_id="test",
            dataset_id="test",
            algorithm_results=[alg_result],
            timestamp=datetime.now(),
            metrics={"psnr": 30.0, "ssim": 0.9},
            algorithm_name="test",
        )
        
        results_text = writer.generate_results_section(result)
        assert "Results" in results_text
        assert "psnr" in results_text

