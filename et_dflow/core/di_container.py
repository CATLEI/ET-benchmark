"""
Dependency injection container for ET-dflow Benchmark Framework.

Provides service registration and resolution with support for
singleton and transient lifetimes.
"""

from typing import Dict, Any, Type, TypeVar, Optional, Callable
from et_dflow.core.exceptions import ServiceNotFoundError

T = TypeVar('T')


class DIContainer:
    """
    Dependency injection container.
    
    Manages service registration and resolution with support for
    singleton and transient lifetimes.
    
    Example:
        container = DIContainer()
        container.register(IDataLoader, HyperspyLoader, singleton=True)
        loader = container.get(IDataLoader)
    """
    
    def __init__(self):
        """Initialize dependency injection container."""
        self._services: Dict[Type, Any] = {}
        self._singletons: Dict[Type, Any] = {}
        self._factories: Dict[Type, Callable] = {}
    
    def register(
        self,
        interface: Type[T],
        implementation: Any,
        singleton: bool = False,
        factory: Optional[Callable[[], T]] = None
    ):
        """
        Register service implementation.
        
        Args:
            interface: Interface type (e.g., IDataLoader)
            implementation: Implementation class or instance
            singleton: Whether to create singleton instance
            factory: Factory function for creating instances
        
        Example:
            # Register as singleton
            container.register(IDataLoader, HyperspyLoader, singleton=True)
            
            # Register with factory
            container.register(IDataLoader, factory=lambda: HyperspyLoader())
        """
        if factory:
            self._factories[interface] = factory
            if singleton:
                # Create singleton immediately
                self._singletons[interface] = factory()
        elif singleton:
            self._singletons[interface] = implementation
        else:
            self._services[interface] = implementation
    
    def get(self, interface: Type[T]) -> T:
        """
        Get service instance.
        
        Args:
            interface: Interface type
        
        Returns:
            Service instance
        
        Raises:
            ServiceNotFoundError: If service is not registered
        
        Example:
            loader = container.get(IDataLoader)
        """
        # Check singletons first
        if interface in self._singletons:
            impl = self._singletons[interface]
            # If it's a class, instantiate it
            if isinstance(impl, type):
                self._singletons[interface] = impl()
            return self._singletons[interface]
        
        # Check factories
        if interface in self._factories:
            factory = self._factories[interface]
            return factory()
        
        # Check transient services
        if interface in self._services:
            impl = self._services[interface]
            # If it's a class, instantiate it
            if isinstance(impl, type):
                return impl()
            return impl
        
        raise ServiceNotFoundError(f"Service {interface.__name__} not registered")
    
    def register_instance(self, interface: Type[T], instance: T):
        """
        Register an existing instance as singleton.
        
        Args:
            interface: Interface type
            instance: Instance to register
        """
        self._singletons[interface] = instance
    
    def is_registered(self, interface: Type) -> bool:
        """
        Check if service is registered.
        
        Args:
            interface: Interface type
        
        Returns:
            True if registered, False otherwise
        """
        return (
            interface in self._services or
            interface in self._singletons or
            interface in self._factories
        )
    
    def clear(self):
        """Clear all registered services."""
        self._services.clear()
        self._singletons.clear()
        self._factories.clear()


# Global container instance
_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """
    Get global dependency injection container.
    
    Returns:
        Global DIContainer instance
    """
    global _container
    if _container is None:
        _container = DIContainer()
    return _container


def set_container(container: DIContainer):
    """
    Set global dependency injection container.
    
    Args:
        container: DIContainer instance to use as global container
    """
    global _container
    _container = container

