"""
Exception classes for ET-dflow Benchmark Framework.

All exceptions inherit from ETDflowError base class to allow
for unified error handling.
"""


class ETDflowError(Exception):
    """
    Base exception for all ET-dflow errors.
    
    All custom exceptions should inherit from this class.
    """
    
    def __init__(self, message: str, details: dict = None):
        """
        Initialize exception.
        
        Args:
            message: Error message
            details: Additional error details
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DataError(ETDflowError):
    """
    Data-related errors.
    
    Raised when data loading, validation, or processing fails.
    """
    pass


class AlgorithmError(ETDflowError):
    """
    Algorithm execution errors.
    
    Raised when algorithm execution fails or produces invalid results.
    """
    pass


class EvaluationError(ETDflowError):
    """
    Evaluation errors.
    
    Raised when evaluation metric calculation fails.
    """
    pass


class ConfigurationError(ETDflowError):
    """
    Configuration errors.
    
    Raised when configuration is invalid or missing required fields.
    """
    pass


class WorkflowError(ETDflowError):
    """
    Workflow execution errors.
    
    Raised when workflow execution fails.
    """
    pass


class ServiceNotFoundError(ETDflowError):
    """
    Service not found in dependency injection container.
    
    Raised when requested service is not registered.
    """
    pass


class CircuitBreakerOpenError(ETDflowError):
    """
    Circuit breaker is open.
    
    Raised when circuit breaker prevents execution due to
    too many failures.
    """
    pass


class SecretNotFoundError(ETDflowError):
    """
    Secret not found.
    
    Raised when required secret cannot be found in environment
    or secret manager.
    """
    pass


class PluginError(ETDflowError):
    """
    Plugin-related errors.
    
    Raised when plugin loading, validation, or execution fails.
    """
    pass

