"""
Algorithm base class implementation.

Provides base class for all reconstruction algorithms with
strategy pattern support.
"""

from abc import abstractmethod
from typing import Dict, Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.core.interfaces import IAlgorithm
from et_dflow.core.models import AlgorithmResult
from et_dflow.core.exceptions import AlgorithmError


class Algorithm(IAlgorithm):
    """
    Base class for all reconstruction algorithms.
    
    Implements Strategy pattern for algorithm selection.
    All algorithms must inherit from this class.
    
    Example:
        class WBPAlgorithm(Algorithm):
            def __init__(self):
                super().__init__("wbp")
            
            def _execute(self, data, config):
                # Implementation
                pass
    """
    
    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        """
        Initialize algorithm.
        
        Args:
            name: Algorithm name
            config: Default configuration parameters
        """
        self._name = name
        self.config = config or {}
    
    @property
    def name(self) -> str:
        """Get algorithm name."""
        return self._name
    
    def run(
        self,
        data: Signal,
        config: Optional[Dict[str, Any]] = None
    ) -> AlgorithmResult:
        """
        Run algorithm on data.
        
        This method handles common logic (validation, timing, etc.)
        and delegates actual execution to _execute method.
        
        Args:
            data: Input tilt series as hyperspy Signal
            config: Algorithm-specific configuration parameters
        
        Returns:
            AlgorithmResult containing reconstruction and metadata
        
        Raises:
            AlgorithmError: If algorithm execution fails
        """
        import time
        
        # Validate input
        if not self.validate_input(data):
            raise AlgorithmError(
                f"Invalid input for algorithm {self.name}",
                details={"algorithm": self.name}
            )
        
        # Merge configs (user config overrides default)
        merged_config = {**self.config, **(config or {})}
        
        # Execute algorithm with timing
        start_time = time.time()
        try:
            result = self._execute(data, merged_config)
            execution_time = time.time() - start_time
            
            # Create AlgorithmResult
            algorithm_result = AlgorithmResult(
                reconstruction=result,
                execution_time=execution_time,
                memory_usage=self._get_memory_usage(),
                metadata={
                    "algorithm": self.name,
                    "config": merged_config,
                },
                algorithm_name=self.name,
            )
            
            return algorithm_result
        except Exception as e:
            raise AlgorithmError(
                f"Algorithm {self.name} execution failed: {e}",
                details={"algorithm": self.name, "error": str(e)}
            ) from e
    
    @abstractmethod
    def _execute(
        self,
        data: Signal,
        config: Dict[str, Any]
    ) -> Signal:
        """
        Execute algorithm (to be implemented by subclass).
        
        Args:
            data: Input tilt series
            config: Algorithm configuration
        
        Returns:
            Reconstructed 3D volume as hyperspy Signal
        """
        pass
    
    def validate_input(self, data: Signal) -> bool:
        """
        Validate input data.
        
        Args:
            data: Input data to validate
        
        Returns:
            True if input is valid
        
        Raises:
            ValueError: If input validation fails
        """
        if data is None:
            raise ValueError("Input data cannot be None")
        
        if not hasattr(data, "data"):
            raise ValueError("Input data must have 'data' attribute")
        
        if not hasattr(data, "metadata"):
            raise ValueError("Input data must have 'metadata' attribute")
        
        # Check data dimensions
        if data.data.ndim < 2:
            raise ValueError(f"Input data must be at least 2D, got {data.data.ndim}D")
        
        return True
    
    def get_requirements(self) -> Dict[str, Any]:
        """
        Get resource requirements.
        
        Returns:
            Dictionary with resource requirements
        """
        return {
            "cpu": self.config.get("cpu", 2),
            "memory": self.config.get("memory", "4Gi"),
            "gpu": self.config.get("gpu", False),
            "gpu_memory": self.config.get("gpu_memory", None),
        }
    
    def _get_memory_usage(self) -> float:
        """
        Get current memory usage.
        
        Returns:
            Memory usage in bytes
        """
        import psutil
        import os
        process = psutil.Process(os.getpid())
        return float(process.memory_info().rss)

