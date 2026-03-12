"""
Core interfaces for ET-dflow Benchmark Framework.

All interfaces follow the Interface Segregation Principle and are designed
to be minimal and focused.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, TYPE_CHECKING

if TYPE_CHECKING:
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D  # Type hint only
else:
    # Runtime import
    import hyperspy.api as hs
    Signal = hs.signals.Signal2D  # Use Signal2D as base type


class IDataLoader(ABC):
    """
    Data loader interface.
    
    All data loaders must implement this interface to ensure
    consistent data loading behavior across different formats.
    """
    
    @abstractmethod
    def load(self, path: str) -> Signal:
        """
        Load data from file path.
        
        Args:
            path: Path to data file
        
        Returns:
            Hyperspy Signal object
        
        Raises:
            DataError: If file cannot be loaded
        """
        pass
    
    @abstractmethod
    def validate(self, path: str) -> bool:
        """
        Validate if file can be loaded by this loader.
        
        Args:
            path: Path to data file
        
        Returns:
            True if file can be loaded, False otherwise
        """
        pass


class IAlgorithm(ABC):
    """
    Algorithm interface.
    
    All reconstruction algorithms must implement this interface
    to ensure consistent execution and resource management.
    """
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Algorithm name.
        
        Returns:
            Algorithm name (e.g., 'wbp', 'sirt', 'genfire')
        """
        pass
    
    @abstractmethod
    def run(
        self,
        data: Signal,
        config: Optional[Dict[str, Any]] = None
    ) -> 'AlgorithmResult':
        """
        Run algorithm on input data.
        
        Args:
            data: Input tilt series as hyperspy Signal
            config: Algorithm-specific configuration parameters
        
        Returns:
            AlgorithmResult containing reconstruction and metadata
        
        Raises:
            AlgorithmError: If algorithm execution fails
        """
        pass
    
    @abstractmethod
    def validate_input(self, data: Signal) -> bool:
        """
        Validate input data before execution.
        
        Args:
            data: Input data to validate
        
        Returns:
            True if input is valid, False otherwise
        
        Raises:
            ValueError: If input validation fails with detailed error message
        """
        pass
    
    @abstractmethod
    def get_requirements(self) -> Dict[str, Any]:
        """
        Get resource requirements for this algorithm.
        
        Returns:
            Dictionary with resource requirements:
            - 'cpu': Number of CPU cores (int)
            - 'memory': Memory requirement (str, e.g., '4Gi')
            - 'gpu': Whether GPU is required (bool)
            - 'gpu_memory': GPU memory requirement if GPU needed (str)
        """
        pass


class IEvaluator(ABC):
    """
    Evaluator interface.
    
    All evaluation metrics must implement this interface
    to ensure consistent evaluation behavior.
    """
    
    @abstractmethod
    def evaluate(
        self,
        result: 'AlgorithmResult',
        ground_truth: Optional[Signal] = None
    ) -> 'EvaluationResult':
        """
        Evaluate algorithm result.
        
        Args:
            result: Algorithm result to evaluate
            ground_truth: Ground truth data (optional, for supervised metrics)
        
        Returns:
            EvaluationResult containing metrics and metadata
        
        Raises:
            EvaluationError: If evaluation fails
        """
        pass


class IPreprocessor(ABC):
    """
    Data preprocessor interface.
    
    All data preprocessors must implement this interface
    to ensure consistent preprocessing behavior.
    """
    
    @abstractmethod
    def preprocess(
        self,
        data: Signal,
        steps: Optional[List[str]] = None
    ) -> Signal:
        """
        Apply preprocessing steps to data.
        
        Args:
            data: Input tilt series
            steps: List of preprocessing steps to apply.
                  If None, apply all default steps.
                  Available steps: 'alignment', 'normalization',
                  'bad_pixels', 'drift'
        
        Returns:
            Preprocessed tilt series
        
        Raises:
            DataError: If preprocessing fails
        """
        pass


class ISimulator(ABC):
    """
    Data simulator interface.
    
    For simulating missing wedge, noise, and other data modifications.
    """
    
    @abstractmethod
    def simulate(
        self,
        data: Signal,
        **kwargs
    ) -> Signal:
        """
        Simulate data modification.
        
        Args:
            data: Input data
            **kwargs: Simulation-specific parameters
        
        Returns:
            Simulated/modified data
        """
        pass

