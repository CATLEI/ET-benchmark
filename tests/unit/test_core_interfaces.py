"""
Unit tests for core interfaces.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.core.interfaces import IDataLoader, IAlgorithm, IEvaluator, IPreprocessor
from et_dflow.core.models import AlgorithmResult, EvaluationResult
from et_dflow.core.exceptions import DataError, AlgorithmError


class TestIDataLoader:
    """Test IDataLoader interface."""
    
    def test_load_interface(self):
        """Test that loaders implement load method."""
        from et_dflow.infrastructure.data.loaders.hyperspy_loader import HyperspyLoader
        
        loader = HyperspyLoader()
        assert hasattr(loader, 'load')
        assert hasattr(loader, 'validate')
        assert callable(loader.load)
        assert callable(loader.validate)


class TestIAlgorithm:
    """Test IAlgorithm interface."""
    
    def test_algorithm_interface(self):
        """Test that algorithms implement required methods."""
        from et_dflow.domain.algorithms.base import Algorithm
        
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        assert alg.name == "test"
        assert hasattr(alg, 'run')
        assert hasattr(alg, 'validate_input')
        assert hasattr(alg, 'get_requirements')


class TestModels:
    """Test data models."""
    
    def test_algorithm_result(self, sample_ground_truth):
        """Test AlgorithmResult model."""
        result = AlgorithmResult(
            reconstruction=sample_ground_truth,
            execution_time=1.5,
            memory_usage=1024 * 1024,
            metadata={"test": "value"},
            algorithm_name="test_algorithm"
        )
        
        assert result.algorithm_name == "test_algorithm"
        assert result.execution_time == 1.5
        assert result.memory_usage > 0
        assert "test" in result.metadata
    
    def test_evaluation_result(self):
        """Test EvaluationResult model."""
        result = EvaluationResult(
            metrics={"psnr": 30.5, "ssim": 0.95},
            algorithm_name="test_algorithm"
        )
        
        assert result.algorithm_name == "test_algorithm"
        assert result.metrics["psnr"] == 30.5
        assert result.metrics["ssim"] == 0.95

