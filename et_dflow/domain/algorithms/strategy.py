"""
Algorithm strategy pattern implementation.

Provides strategy pattern for algorithm execution and selection.
"""

from typing import Optional, Dict, Any, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D
else:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D

from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.models import AlgorithmResult


class AlgorithmStrategy:
    """
    Strategy pattern for algorithm execution.
    
    Allows runtime selection of algorithm implementation.
    
    Example:
        strategy = AlgorithmStrategy(WBPAlgorithm())
        result = strategy.execute(data, config)
    """
    
    def __init__(self, algorithm: Algorithm):
        """
        Initialize algorithm strategy.
        
        Args:
            algorithm: Algorithm instance
        """
        self.algorithm = algorithm
    
    def execute(
        self,
        data: Signal,
        config: Optional[Dict[str, Any]] = None
    ) -> AlgorithmResult:
        """
        Execute algorithm strategy.
        
        Args:
            data: Input data
            config: Algorithm configuration
        
        Returns:
            Algorithm result
        """
        return self.algorithm.run(data, config)


class AlgorithmContext:
    """
    Context for algorithm execution.
    
    Uses strategy pattern to execute different algorithms.
    
    Example:
        context = AlgorithmContext()
        context.set_strategy(AlgorithmStrategy(WBPAlgorithm()))
        result = context.run(data)
    """
    
    def __init__(self, strategy: Optional[AlgorithmStrategy] = None):
        """
        Initialize algorithm context.
        
        Args:
            strategy: Initial algorithm strategy
        """
        self.strategy = strategy
    
    def set_strategy(self, strategy: AlgorithmStrategy):
        """
        Set algorithm strategy.
        
        Args:
            strategy: Algorithm strategy to use
        """
        self.strategy = strategy
    
    def run(
        self,
        data: Signal,
        config: Optional[Dict[str, Any]] = None
    ) -> AlgorithmResult:
        """
        Run algorithm using current strategy.
        
        Args:
            data: Input data
            config: Algorithm configuration
        
        Returns:
            Algorithm result
        
        Raises:
            ValueError: If no strategy is set
        """
        if not self.strategy:
            raise ValueError("No algorithm strategy set")
        
        return self.strategy.execute(data, config)

