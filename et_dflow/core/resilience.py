"""
Resilience and fault tolerance mechanisms.

Implements retry logic, circuit breaker pattern, and resilient execution.
"""

import time
from typing import Callable, Any, Optional, Dict
from enum import Enum
from et_dflow.core.exceptions import CircuitBreakerOpenError


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    Prevents cascading failures by stopping requests to failing services.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: float = 60.0,
        expected_exception: type = Exception
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Time in seconds before attempting recovery
            expected_exception: Exception type that triggers failures
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.expected_exception = expected_exception
        
        self.failure_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.timeout:
                # Try to recover
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. "
                    f"Will retry after {self.timeout} seconds",
                    details={
                        "state": self.state.value,
                        "failure_count": self.failure_count,
                    }
                )
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        """Handle successful execution."""
        self.failure_count = 0
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        """Handle failed execution."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN


class ResilientExecutor:
    """
    Executor with retry logic and exponential backoff.
    
    Implements retry mechanism with exponential backoff strategy.
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0
    ):
        """
        Initialize resilient executor.
        
        Args:
            max_retries: Maximum number of retry attempts
            initial_delay: Initial delay in seconds
            max_delay: Maximum delay in seconds
            exponential_base: Base for exponential backoff
        """
        self.max_retries = max_retries
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
    
    def execute(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with retry logic.
        
        Args:
            func: Function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            Exception: Last exception if all retries fail
        """
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < self.max_retries:
                    # Calculate delay with exponential backoff
                    delay = min(
                        self.initial_delay * (self.exponential_base ** attempt),
                        self.max_delay
                    )
                    time.sleep(delay)
                else:
                    # All retries exhausted
                    raise last_exception
        
        # Should not reach here
        raise last_exception


