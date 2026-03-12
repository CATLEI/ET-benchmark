"""
Unit tests for resilience mechanisms.
"""

import pytest
import time
from et_dflow.core.resilience import CircuitBreaker, ResilientExecutor, CircuitState
from et_dflow.core.exceptions import CircuitBreakerOpenError


class TestCircuitBreaker:
    """Test CircuitBreaker."""
    
    def test_circuit_breaker_creation(self):
        """Test circuit breaker can be created."""
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_success(self):
        """Test successful execution keeps circuit closed."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def success_func():
            return "success"
        
        result = cb.call(success_func)
        assert result == "success"
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0
    
    def test_circuit_breaker_failure(self):
        """Test failures increment counter."""
        cb = CircuitBreaker(failure_threshold=3)
        
        def fail_func():
            raise ValueError("test error")
        
        with pytest.raises(ValueError):
            cb.call(fail_func)
        
        assert cb.failure_count == 1
        assert cb.state == CircuitState.CLOSED
    
    def test_circuit_breaker_opens(self):
        """Test circuit opens after threshold failures."""
        cb = CircuitBreaker(failure_threshold=2)
        
        def fail_func():
            raise ValueError("test error")
        
        # Fail twice
        for _ in range(2):
            with pytest.raises(ValueError):
                cb.call(fail_func)
        
        # Circuit should be open
        assert cb.state == CircuitState.OPEN
        
        # Next call should raise CircuitBreakerOpenError
        with pytest.raises(CircuitBreakerOpenError):
            cb.call(fail_func)


class TestResilientExecutor:
    """Test ResilientExecutor."""
    
    def test_executor_creation(self):
        """Test executor can be created."""
        executor = ResilientExecutor()
        assert executor.max_retries == 3
    
    def test_executor_success(self):
        """Test successful execution without retries."""
        executor = ResilientExecutor(max_retries=3)
        
        def success_func():
            return "success"
        
        result = executor.execute(success_func)
        assert result == "success"
    
    def test_executor_retry(self):
        """Test retry on failure."""
        executor = ResilientExecutor(max_retries=2, initial_delay=0.1)
        
        call_count = [0]
        
        def fail_then_succeed():
            call_count[0] += 1
            if call_count[0] < 2:
                raise ValueError("retry")
            return "success"
        
        result = executor.execute(fail_then_succeed)
        assert result == "success"
        assert call_count[0] == 2
    
    def test_executor_max_retries(self):
        """Test executor gives up after max retries."""
        executor = ResilientExecutor(max_retries=2, initial_delay=0.1)
        
        def always_fail():
            raise ValueError("always fails")
        
        with pytest.raises(ValueError):
            executor.execute(always_fail)


