"""
Algorithm registry implementation.

Provides algorithm discovery and registration mechanism.
"""

from typing import Dict, Type, List, Optional
from et_dflow.domain.algorithms.base import Algorithm
from et_dflow.core.exceptions import AlgorithmError


class AlgorithmRegistry:
    """
    Registry for managing algorithm instances.
    
    Provides algorithm discovery, registration, and retrieval.
    
    Example:
        registry = AlgorithmRegistry()
        registry.register("wbp", WBPAlgorithm)
        algorithm = registry.get("wbp")
    """
    
    def __init__(self):
        """Initialize algorithm registry."""
        self._algorithms: Dict[str, Type[Algorithm]] = {}
        self._instances: Dict[str, Algorithm] = {}
    
    def register(
        self,
        name: str,
        algorithm_class: Type[Algorithm],
        singleton: bool = False
    ):
        """
        Register an algorithm.
        
        Args:
            name: Algorithm name
            algorithm_class: Algorithm class
            singleton: Whether to create singleton instance
        """
        self._algorithms[name] = algorithm_class
        
        if singleton:
            self._instances[name] = algorithm_class()
    
    def get(self, name: str) -> Algorithm:
        """
        Get algorithm instance.
        
        Args:
            name: Algorithm name
        
        Returns:
            Algorithm instance
        
        Raises:
            AlgorithmError: If algorithm not found
        """
        # Check singleton instances first
        if name in self._instances:
            return self._instances[name]
        
        # Create new instance
        if name in self._algorithms:
            algorithm_class = self._algorithms[name]
            # Pass algorithm name to constructor
            return algorithm_class(name=name)
        
        raise AlgorithmError(
            f"Algorithm not found: {name}",
            details={"algorithm": name, "available": list(self._algorithms.keys())}
        )
    
    def list_algorithms(self) -> List[str]:
        """
        List all registered algorithm names.
        
        Returns:
            List of algorithm names
        """
        return list(self._algorithms.keys())
    
    def is_registered(self, name: str) -> bool:
        """
        Check if algorithm is registered.
        
        Args:
            name: Algorithm name
        
        Returns:
            True if registered, False otherwise
        """
        return name in self._algorithms or name in self._instances


# Global registry instance
_registry: Optional[AlgorithmRegistry] = None


def get_algorithm_registry() -> AlgorithmRegistry:
    """
    Get global algorithm registry.
    
    Returns:
        Global AlgorithmRegistry instance
    """
    global _registry
    if _registry is None:
        _registry = AlgorithmRegistry()
    return _registry


def set_algorithm_registry(registry: AlgorithmRegistry):
    """
    Set global algorithm registry.
    
    Args:
        registry: AlgorithmRegistry instance to use as global registry
    """
    global _registry
    _registry = registry

