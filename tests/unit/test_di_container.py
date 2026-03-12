"""
Unit tests for dependency injection container.
"""

import pytest
from et_dflow.core.di_container import DIContainer, get_container, set_container


class TestDIContainer:
    """Test DIContainer."""
    
    def test_container_creation(self):
        """Test container can be created."""
        container = DIContainer()
        assert container is not None
    
    def test_register_service(self):
        """Test service registration."""
        container = DIContainer()
        
        class TestService:
            pass
        
        container.register(TestService, TestService)
        assert container.is_registered(TestService)
    
    def test_get_service(self):
        """Test getting service."""
        container = DIContainer()
        
        class TestService:
            def __init__(self):
                self.value = "test"
        
        container.register(TestService, TestService)
        service = container.get(TestService)
        
        assert isinstance(service, TestService)
        assert service.value == "test"
    
    def test_singleton_service(self):
        """Test singleton service."""
        container = DIContainer()
        
        class TestService:
            pass
        
        container.register(TestService, TestService, singleton=True)
        service1 = container.get(TestService)
        service2 = container.get(TestService)
        
        assert service1 is service2
    
    def test_service_not_found(self):
        """Test error when service not found."""
        container = DIContainer()
        
        class TestService:
            pass
        
        with pytest.raises(Exception):  # ServiceNotFoundError
            container.get(TestService)


class TestGlobalContainer:
    """Test global container functions."""
    
    def test_get_container(self):
        """Test getting global container."""
        container = get_container()
        assert container is not None
        assert isinstance(container, DIContainer)
    
    def test_set_container(self):
        """Test setting global container."""
        new_container = DIContainer()
        set_container(new_container)
        
        container = get_container()
        assert container is new_container

