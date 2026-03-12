"""
Unit tests for evaluation metrics.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.domain.evaluation.chain import (
    MetricHandler,
    PSNRMetricHandler,
    SSIMMetricHandler,
    MSEMetricHandler,
    build_evaluation_chain
)
from et_dflow.core.models import AlgorithmResult


class TestMetricHandlers:
    """Test metric handlers."""
    
    def test_psnr_handler(self, sample_ground_truth):
        """Test PSNR metric handler."""
        # Create reconstruction (slightly different from GT)
        reconstruction = sample_ground_truth.deepcopy()
        reconstruction.data = sample_ground_truth.data + np.random.randn(*sample_ground_truth.data.shape) * 0.1
        
        result = AlgorithmResult(
            reconstruction=reconstruction,
            execution_time=1.0,
            memory_usage=1024,
            metadata={},
            algorithm_name="test"
        )
        
        handler = PSNRMetricHandler()
        metrics = handler.handle(result, sample_ground_truth)
        
        assert "psnr" in metrics
        assert isinstance(metrics["psnr"], float)
        assert metrics["psnr"] > 0
    
    def test_ssim_handler(self, sample_ground_truth):
        """Test SSIM metric handler."""
        reconstruction = sample_ground_truth.deepcopy()
        reconstruction.data = sample_ground_truth.data + np.random.randn(*sample_ground_truth.data.shape) * 0.1
        
        result = AlgorithmResult(
            reconstruction=reconstruction,
            execution_time=1.0,
            memory_usage=1024,
            metadata={},
            algorithm_name="test"
        )
        
        handler = SSIMMetricHandler()
        metrics = handler.handle(result, sample_ground_truth)
        
        assert "ssim" in metrics
        assert isinstance(metrics["ssim"], float)
        assert 0 <= metrics["ssim"] <= 1
    
    def test_mse_handler(self, sample_ground_truth):
        """Test MSE metric handler."""
        reconstruction = sample_ground_truth.deepcopy()
        reconstruction.data = sample_ground_truth.data + np.random.randn(*sample_ground_truth.data.shape) * 0.1
        
        result = AlgorithmResult(
            reconstruction=reconstruction,
            execution_time=1.0,
            memory_usage=1024,
            metadata={},
            algorithm_name="test"
        )
        
        handler = MSEMetricHandler()
        metrics = handler.handle(result, sample_ground_truth)
        
        assert "mse" in metrics
        assert isinstance(metrics["mse"], float)
        assert metrics["mse"] >= 0


class TestEvaluationChain:
    """Test evaluation chain."""
    
    def test_build_chain(self):
        """Test building evaluation chain."""
        chain = build_evaluation_chain(["psnr", "ssim", "mse"])
        assert chain is not None
        assert isinstance(chain, MetricHandler)
    
    def test_chain_execution(self, sample_ground_truth):
        """Test chain execution."""
        reconstruction = sample_ground_truth.deepcopy()
        reconstruction.data = sample_ground_truth.data + np.random.randn(*sample_ground_truth.data.shape) * 0.1
        
        result = AlgorithmResult(
            reconstruction=reconstruction,
            execution_time=1.0,
            memory_usage=1024,
            metadata={},
            algorithm_name="test"
        )
        
        chain = build_evaluation_chain(["psnr", "ssim", "mse"])
        metrics = chain.process(result, sample_ground_truth)
        
        assert "psnr" in metrics
        assert "ssim" in metrics
        assert "mse" in metrics

