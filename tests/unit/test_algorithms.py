"""
Unit tests for algorithms.
"""

import pytest
import numpy as np
import hyperspy.api as hs
from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.domain.algorithms.strategy import AlgorithmStrategy, AlgorithmContext
from et_dflow.domain.algorithms.registry import AlgorithmRegistry
from et_dflow.core.exceptions import AlgorithmError


class TestAlgorithm:
    """Test Algorithm base class."""
    
    def test_algorithm_creation(self):
        """Test algorithm can be created."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        assert alg.name == "test"
        assert alg.config == {}
    
    def test_algorithm_with_config(self):
        """Test algorithm with configuration."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        config = {"param1": "value1"}
        alg = TestAlgorithm("test", config)
        assert alg.config == config
    
    def test_validate_input(self, sample_tilt_series):
        """Test input validation."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        assert alg.validate_input(sample_tilt_series) is True
        
        with pytest.raises(ValueError):
            alg.validate_input(None)
    
    def test_get_requirements(self):
        """Test resource requirements."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test", {"cpu": 4, "memory": "8Gi"})
        requirements = alg.get_requirements()
        
        assert requirements["cpu"] == 4
        assert requirements["memory"] == "8Gi"
    
    def test_run_algorithm(self, sample_tilt_series):
        """Test algorithm execution."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        result = alg.run(sample_tilt_series)
        
        assert result is not None
        assert result.algorithm_name == "test"
        assert result.execution_time >= 0
        assert result.reconstruction is not None


class TestAlgorithmStrategy:
    """Test AlgorithmStrategy."""
    
    def test_strategy_creation(self):
        """Test strategy can be created."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        strategy = AlgorithmStrategy(alg)
        assert strategy.algorithm == alg
    
    def test_strategy_execute(self, sample_tilt_series):
        """Test strategy execution."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        alg = TestAlgorithm("test")
        strategy = AlgorithmStrategy(alg)
        result = strategy.execute(sample_tilt_series)
        
        assert result is not None
        assert result.algorithm_name == "test"


class TestAlgorithmRegistry:
    """Test AlgorithmRegistry."""
    
    def test_registry_creation(self):
        """Test registry can be created."""
        registry = AlgorithmRegistry()
        assert registry is not None
    
    def test_register_algorithm(self):
        """Test algorithm registration."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        registry = AlgorithmRegistry()
        registry.register("test", TestAlgorithm)
        assert registry.is_registered("test")
    
    def test_get_algorithm(self):
        """Test getting algorithm from registry."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        registry = AlgorithmRegistry()
        registry.register("test", TestAlgorithm)
        
        alg = registry.get("test")
        assert isinstance(alg, TestAlgorithm)
        assert alg.name == "test"
    
    def test_list_algorithms(self):
        """Test listing registered algorithms."""
        class TestAlgorithm(Algorithm):
            def _execute(self, data, config):
                return data.deepcopy()
        
        registry = AlgorithmRegistry()
        registry.register("test1", TestAlgorithm)
        registry.register("test2", TestAlgorithm)
        
        algorithms = registry.list_algorithms()
        assert "test1" in algorithms
        assert "test2" in algorithms

